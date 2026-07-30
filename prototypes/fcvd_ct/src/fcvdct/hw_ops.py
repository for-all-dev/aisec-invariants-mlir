"""`hw.constant` -- the one CIRCT operation the arithmetic path cannot do without.

CIRCT's `--map-arith-to-comb` sends every integer `arith.constant` to `hw.constant`
(`lib/Transforms/MapArithToComb.cpp:159`), so a template for that lowering cannot even
be written without it. xdsl-smt declares the `hw` dialect but gives it neither a custom
syntax nor semantics, so both are written here: this is the second translation of our
own, next to `arith` on `index` in `index_ops.py`.

The value semantics are the same as `arith.constant`'s -- a bitvector constant that is
never poison -- and, like every constant, it is invisible to the leakage model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from xdsl.dialects.builtin import IntegerAttr, IntegerType
from xdsl.ir import Attribute, Dialect, SSAValue
from xdsl.irdl import IRDLOperation, irdl_op_definition, prop_def, result_def
from xdsl.parser import Parser
from xdsl.pattern_rewriter import PatternRewriter
from xdsl.printer import Printer
from xdsl_smt.dialects import smt_bitvector_dialect as smt_bv
from xdsl_smt.dialects import smt_dialect as smt
from xdsl_smt.dialects import smt_utils_dialect as smt_utils
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer
from xdsl_smt.semantics.semantics import OperationSemantics


@irdl_op_definition
class HWConstantOp(IRDLOperation):
    """`hw.constant 7 : i32`, with the result type taken from the attribute."""

    name = "hw.constant"

    value = prop_def(IntegerAttr)
    result = result_def(IntegerType)

    def __init__(self, value: IntegerAttr):
        super().__init__(properties={"value": value}, result_types=[value.type])

    @classmethod
    def parse(cls, parser: Parser) -> HWConstantOp:
        value = parser.parse_attribute()
        if not isinstance(value, IntegerAttr):
            parser.raise_error("hw.constant expects an integer attribute")
        return HWConstantOp(value)

    def print(self, printer: Printer) -> None:
        printer.print_string(" ")
        printer.print_attribute(self.value)


HWConstant = Dialect("hw", [HWConstantOp])


class HWConstantSemantics(OperationSemantics):
    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        value = attributes["value"]
        assert isinstance(value, IntegerAttr)
        assert isinstance(value.type, IntegerType)
        constant = smt_bv.ConstantOp(
            value.value.data % (1 << value.type.width.data), value.type.width.data
        )
        poison = smt.ConstantBoolOp(False)
        pair = smt_utils.PairOp(constant.res, poison.result)
        rewriter.insert_op_before_matched_op([constant, poison, pair])
        return (pair.res,), effect_state


def load_hw_semantics() -> None:
    """Register `hw.constant` with the SMT lowerer, next to upstream's own entries."""
    SMTLowerer.op_semantics = {**SMTLowerer.op_semantics, HWConstantOp: HWConstantSemantics()}
