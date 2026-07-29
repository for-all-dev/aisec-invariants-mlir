"""`tensor.extract` and `tensor.insert` -- the translation HEIR cannot be checked without.

HEIR's constant-time hardening passes are written on tensors: `tensor.extract` at a
secret index is the very thing `--convert-secret-extract-to-static-extract` exists to
remove (`lib/Transforms/ConvertSecretExtractToStaticExtract`). Neither the operations
nor the type have semantics upstream, so both are written here.

The encoding is the obvious one, and the same one the SMT-LIB theory of arrays was made
for: a static one-dimensional `tensor<NxT>` is an array from a 64-bit index to the
lowered element type, carried in the usual (value, poison) pair. Extraction is `select`,
insertion is `store`, and an out-of-bounds index is undefined behaviour, exactly as
`memref.load` treats one.

Leakage: an extraction observes its index, under the same rule as a memory load. That is
a modelling assumption and it is HEIR's own -- the pass would have no purpose if a
secret-indexed extract were free -- but it is worth naming: it holds because these
tensors become memrefs before the backend (`oneShotBufferize` in HEIR's pipeline,
`lib/Pipelines/PipelineRegistration.cpp:47`), and a load from a secret address is what
the address obligation is about. On a ciphertext, where an "extract" is a rotation, the
assumption would be a different one and so would the rule.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from xdsl.dialects import tensor
from xdsl.dialects.builtin import ArrayAttr, TensorType
from xdsl.ir import Attribute, SSAValue
from xdsl.pattern_rewriter import PatternRewriter
from xdsl.utils.hints import isa
from xdsl_smt.dialects import smt_array_dialect as smt_array
from xdsl_smt.dialects import smt_bitvector_dialect as smt_bv
from xdsl_smt.dialects import smt_dialect as smt
from xdsl_smt.dialects import smt_utils_dialect as smt_utils
from xdsl_smt.dialects.effects import ub_effect
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer
from xdsl_smt.semantics.semantics import OperationSemantics, TypeSemantics

INDEX_WIDTH = 64


class UnsupportedTensor(Exception):
    """A tensor shape this encoding does not cover."""


class TensorTypeSemantics(TypeSemantics):
    """`tensor<NxT>` becomes `((Array (_ BitVec 64) T'), Bool)`."""

    def get_semantics(self, type: Attribute) -> Attribute:
        assert isinstance(type, TensorType)
        shape = type.get_shape()
        if len(shape) != 1:
            raise UnsupportedTensor(f"only one-dimensional tensors are modelled, got {type}")
        element = SMTLowerer.lower_type(type.get_element_type())
        return smt_utils.PairType(
            smt_array.ArrayType(smt_bv.BitVectorType(INDEX_WIDTH), element),
            smt.BoolType(),
        )


def _unpack(value: SSAValue, rewriter: PatternRewriter) -> tuple[SSAValue, SSAValue]:
    first = smt_utils.FirstOp(value)
    second = smt_utils.SecondOp(value)
    rewriter.insert_op_before_matched_op([first, second])
    return first.res, second.res


def _in_bounds(index: SSAValue, size: int, rewriter: PatternRewriter) -> SSAValue:
    limit = smt_bv.ConstantOp(size, INDEX_WIDTH)
    below = smt_bv.UltOp(index, limit.res)
    rewriter.insert_op_before_matched_op([limit, below])
    return below.res


def _tensor_size(attributes: Mapping[str, Attribute | SSAValue], position: int) -> int:
    """The static extent of the tensor operand, from the pre-lowering operand types."""
    types = attributes.get("__operand_types")
    if not isa(types, ArrayAttr[Attribute]):
        raise UnsupportedTensor("tensor operand types were not recorded")
    tensor_type = tuple(types)[position]
    if not isinstance(tensor_type, TensorType):
        raise UnsupportedTensor(f"expected a tensor operand, got {tensor_type}")
    shape = tensor_type.get_shape()
    if len(shape) != 1:
        raise UnsupportedTensor(f"only one-dimensional tensors are modelled, got {tensor_type}")
    return shape[0]


class ExtractSemantics(OperationSemantics):
    """`tensor.extract %t[%i]` -- `select`, with out-of-bounds raising UB."""

    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        if len(operands) != 2:
            raise UnsupportedTensor("only one-dimensional extraction is modelled")
        array, tensor_poison = _unpack(operands[0], rewriter)
        index, index_poison = _unpack(operands[1], rewriter)

        select = smt_array.SelectOp(array, index)
        rewriter.insert_op_before_matched_op([select])

        in_bounds = _in_bounds(index, _tensor_size(attributes, 0), rewriter)
        assert effect_state is not None
        state = _trigger_ub_unless(in_bounds, [tensor_poison, index_poison], effect_state, rewriter)
        return (select.res,), state


class InsertSemantics(OperationSemantics):
    """`tensor.insert %v into %t[%i]` -- `store`, with out-of-bounds raising UB."""

    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        if len(operands) != 3:
            raise UnsupportedTensor("only one-dimensional insertion is modelled")
        value = operands[0]
        array, tensor_poison = _unpack(operands[1], rewriter)
        index, index_poison = _unpack(operands[2], rewriter)

        store = smt_array.StoreOp(array, index, value)
        poison = smt.ConstantBoolOp(False)
        pair = smt_utils.PairOp(store.res, poison.result)
        rewriter.insert_op_before_matched_op([store, poison, pair])

        in_bounds = _in_bounds(index, _tensor_size(attributes, 1), rewriter)
        assert effect_state is not None
        state = _trigger_ub_unless(in_bounds, [tensor_poison, index_poison], effect_state, rewriter)
        return (pair.res,), state


def _trigger_ub_unless(
    in_bounds: SSAValue,
    poisons: Sequence[SSAValue],
    effect_state: SSAValue,
    rewriter: PatternRewriter,
) -> SSAValue:
    """UB if the access is out of bounds or any input is poison -- as `memref` does."""
    condition = smt.NotOp(in_bounds)
    rewriter.insert_op_before_matched_op([condition])
    bad: SSAValue = condition.result
    for poison in poisons:
        merged = smt.OrOp(bad, poison)
        rewriter.insert_op_before_matched_op([merged])
        bad = merged.result
    triggered = ub_effect.TriggerOp(effect_state)
    chosen = smt.IteOp(bad, triggered.res, effect_state)
    rewriter.insert_op_before_matched_op([triggered, chosen])
    return chosen.res


def load_tensor_semantics() -> None:
    SMTLowerer.type_lowerers = {
        **SMTLowerer.type_lowerers,
        TensorType: TensorTypeSemantics(),
    }
    SMTLowerer.op_semantics = {
        **SMTLowerer.op_semantics,
        tensor.ExtractOp: ExtractSemantics(),
        tensor.InsertOp: InsertSemantics(),
    }
