"""SMT semantics for the LLVM memory operations `--convert-polygeist-to-llvm` emits.

Upstream `xdsl-smt` lowers the integer LLVM ops but none of its memory ops, which is
what left the memref->llvm slice of Polygeist's final lowering unverifiable. This module
supplies the missing three -- `llvm.getelementptr`, `llvm.load`, `llvm.store` -- plus the
lowering of the `!llvm.ptr` type, on the *same* memory model upstream already uses for
`memref`: a value of pointer type is a `Pair(mem_effect.PointerType, Bool)` (the pointer
and its poison bit), memory is the effect state threaded through the program, and a load
is an `mem_effect.ReadOp` at an offset pointer. Because it is the same model, a `memref`
argument and the `!llvm.ptr` it lowers to are the *same* SMT value, so a before/after
template can share one initial memory across the memref side and the llvm side -- which is
the whole point of checking this lowering.

Scope, stated plainly, matching upstream's own memref limits:

- **i8 elements only.** Upstream's memref load/store assert an i8 element type; the
  Polygeist C-style path this specifies is byte-addressed too, so a GEP index is a byte
  offset and no `sizeof(elem)` scaling is needed. A non-i8 access raises rather than
  silently mis-scaling.
- **One index per GEP.** The C-style `getAddress` (ConvertPolygeistToLLVM.cpp:1193)
  emits one `GEPArg` per memref index; a multi-index or all-static GEP is refused.
- Loads and stores trigger UB on a poison pointer, exactly as `memref` does, so a
  program that reaches one is `unknown`, never silently secure.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from xdsl.dialects import llvm
from xdsl.dialects.builtin import DYNAMIC_INDEX, DenseArrayBase, IntegerType
from xdsl.ir import Attribute, SSAValue
from xdsl.pattern_rewriter import PatternRewriter
from xdsl.utils.hints import isa
from xdsl_smt.dialects import smt_bitvector_dialect as smt_bv
from xdsl_smt.dialects import smt_dialect as smt
from xdsl_smt.dialects import smt_utils_dialect as smt_utils
from xdsl_smt.dialects.effects import memory_effect as mem_effect
from xdsl_smt.dialects.effects import ub_effect
from xdsl_smt.dialects.smt_utils_dialect import PairType
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer
from xdsl_smt.semantics.memref_semantics import combine_poison_values, get_value_and_poison
from xdsl_smt.semantics.semantics import OperationSemantics, TypeSemantics

I8 = IntegerType(8)


class PointerTypeSemantics(TypeSemantics):
    """`!llvm.ptr` is a pointer with a poison bit -- the same shape as a memref value."""

    def get_semantics(self, type: Attribute) -> Attribute:
        return smt_utils.PairType(mem_effect.PointerType(), smt.BoolType())


class GEPSemantics(OperationSemantics):
    """`llvm.getelementptr %p[%i]` (one byte index) is `offset_ptr`, poison combined."""

    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        raw = attributes.get("rawConstantIndices")
        one_dynamic = DenseArrayBase.from_list(IntegerType(32), [DYNAMIC_INDEX])
        if raw != one_dynamic:
            raise ValueError("only a single dynamic-index getelementptr is modelled")
        elem = attributes.get("elem_type")
        if elem != I8:
            raise ValueError("only an i8-element getelementptr is modelled")

        (pointer, index), poison = combine_poison_values(operands, rewriter)
        offset = GEPSemantics._as_bv64(index, rewriter)
        offset_op = mem_effect.OffsetPointerOp(pointer, offset)
        result = smt_utils.PairOp(offset_op.res, poison)
        rewriter.insert_op_before_matched_op([offset_op, result])
        return (result.res,), effect_state

    @staticmethod
    def _as_bv64(index: SSAValue, rewriter: PatternRewriter) -> SSAValue:
        assert isa(index.type, smt_bv.BitVectorType)
        width = index.type.width.data
        if width == 64:
            return index
        if width < 64:
            ext = smt_bv.ZeroExtendOp(index, smt_bv.BitVectorType(64))
            rewriter.insert_op_before_matched_op([ext])
            return ext.res
        trunc = smt_bv.ExtractOp(index, 63, 0)
        rewriter.insert_op_before_matched_op([trunc])
        return trunc.res


class LoadSemantics(OperationSemantics):
    """`llvm.load %p` reads at the pointer; a poison pointer triggers UB (as memref)."""

    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        assert effect_state is not None
        element = SMTLowerer.lower_type(results[0])
        if not (
            isa(element, PairType[smt_bv.BitVectorType, smt.BoolType])
            and element.first.width.data == 8
        ):
            raise ValueError("only an i8 llvm.load is modelled")
        pointer, poison = get_value_and_poison(operands[0], rewriter)
        read = mem_effect.ReadOp(effect_state, pointer, element)
        trigger = ub_effect.TriggerOp(effect_state)
        new_state = smt.IteOp(poison, trigger.res, read.new_state)
        rewriter.insert_op_before_matched_op([read, trigger, new_state])
        return (read.res,), new_state.res


class StoreSemantics(OperationSemantics):
    """`llvm.store %v, %p` writes at the pointer; a poison pointer triggers UB."""

    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        assert effect_state is not None
        value = operands[0]
        assert (
            isa(value.type, PairType[smt_bv.BitVectorType, smt.BoolType])
            and value.type.first.width.data == 8
        ), "only an i8 llvm.store is modelled"
        pointer, poison = get_value_and_poison(operands[1], rewriter)
        write = mem_effect.WriteOp(value, effect_state, pointer)
        trigger = ub_effect.TriggerOp(effect_state)
        new_state = smt.IteOp(poison, trigger.res, write.new_state)
        rewriter.insert_op_before_matched_op([write, trigger, new_state])
        return (), new_state.res


def load_llvm_memory_semantics() -> None:
    """Register the `!llvm.ptr` type and the three memory ops. Call after vanilla."""
    SMTLowerer.type_lowerers = {
        **SMTLowerer.type_lowerers,
        llvm.LLVMPointerType: PointerTypeSemantics(),
    }
    SMTLowerer.op_semantics = {
        **SMTLowerer.op_semantics,
        llvm.GEPOp: GEPSemantics(),
        llvm.LoadOp: LoadSemantics(),
        llvm.StoreOp: StoreSemantics(),
    }
