"""Missing translations, batch 1: arithmetic on `index`.

FCVD lowers the `index` *type* (a 64-bit bitvector with a poison flag) but not the
arithmetic on it: every `arith` semantics upstream asserts that its result type is an
`IntegerType`, so `arith.addi` on two indices stops the lowering dead. Loop counters
are indices, which is why this is the first thing in the way once loops get unrolled.

Nothing here reimplements upstream's arithmetic. The wrapper tells the existing
semantics that the result is the 64-bit integer the index already lowers to, and hands
the work straight over. `arith.index_cast` has no upstream semantics at all, so it is
written out here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from xdsl.dialects import arith
from xdsl.dialects.builtin import IndexType, IntegerType
from xdsl.ir import Attribute, Operation, SSAValue
from xdsl.pattern_rewriter import PatternRewriter
from xdsl_smt.dialects import smt_bitvector_dialect as smt_bv
from xdsl_smt.dialects import smt_utils_dialect as smt_utils
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer
from xdsl_smt.semantics.semantics import OperationSemantics

INDEX_WIDTH = 64
"""What FCVD lowers `index` to (`IndexTypeSemantics`)."""


@dataclass
class IndexAsInteger(OperationSemantics):
    """Run an `arith` operation's own semantics, with `index` read as `i64`."""

    inner: OperationSemantics

    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        widened = [
            IntegerType(INDEX_WIDTH) if isinstance(result, IndexType) else result
            for result in results
        ]
        return self.inner.get_semantics(operands, widened, attributes, effect_state, rewriter)


class IndexCastSemantics(OperationSemantics):
    """`arith.index_cast`: sign-extend or truncate, keeping the poison flag."""

    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        (operand,) = operands
        (result,) = results
        if isinstance(result, IndexType):
            width = INDEX_WIDTH
        elif isinstance(result, IntegerType):
            width = result.width.data
        else:
            raise ValueError(f"arith.index_cast to {result} is not an integer cast")

        value_op = smt_utils.FirstOp(operand)
        poison_op = smt_utils.SecondOp(operand)
        rewriter.insert_op_before_matched_op([value_op, poison_op])
        value = value_op.res
        assert isinstance(value.type, smt_bv.BitVectorType)
        source_width = value.type.width.data

        if width > source_width:
            # index is a signed quantity in MLIR, so widening sign-extends.
            cast = smt_bv.SignExtendOp(value, smt_bv.BitVectorType(width))
        elif width < source_width:
            cast = smt_bv.ExtractOp(value, width - 1, 0)
        else:
            cast = None

        if cast is not None:
            rewriter.insert_op_before_matched_op([cast])
            value = cast.res

        pair = smt_utils.PairOp(value, poison_op.res)
        rewriter.insert_op_before_matched_op([pair])
        return (pair.res,), effect_state


#: The `arith` operations a loop counter goes through.
_WRAPPED: tuple[type[Operation], ...] = (
    arith.AddiOp,
    arith.SubiOp,
    arith.MuliOp,
    arith.CmpiOp,
    arith.SelectOp,
    arith.ConstantOp,
    arith.MaxSIOp,
    arith.MinSIOp,
    arith.MaxUIOp,
    arith.MinUIOp,
)


def load_index_semantics() -> None:
    """Register the translations above. Call after `load_vanilla_semantics()`."""
    semantics = dict(SMTLowerer.op_semantics)
    for op_type in _WRAPPED:
        if op_type in semantics and not isinstance(semantics[op_type], IndexAsInteger):
            semantics[op_type] = IndexAsInteger(semantics[op_type])
    semantics[arith.IndexCastOp] = IndexCastSemantics()
    SMTLowerer.op_semantics = semantics
