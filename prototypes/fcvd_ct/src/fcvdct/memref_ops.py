"""`memref.alloca` syntax, and a guard on the memref shapes upstream's semantics accept.

Two separate gaps, both in upstream's `memref` support, both found by measuring what the
Polygeist corpus actually translates (issue #63) rather than which names are registered:

1. xdsl declares `memref.alloca` without a custom syntax, so any file that writes
   `%m = memref.alloca() : memref<1xi32>` -- which is every Polygeist test that allocates
   -- cannot be read at all. The syntax is attached here.
2. Upstream's `memref.load`/`memref.store` semantics mean to refuse dynamic shapes, but
   the assertion that should do it compares the *index operands* against
   `DYNAMIC_INDEX` instead of the *shape*. A `memref<?xi32>` access is therefore
   "translated" with a bound of -1, which makes every access out of bounds and so
   undefined: the program is lowered, but to something that says nothing, and a
   source that is always UB excuses any target. The wrapper below refuses those shapes
   (and the non-`i8` elements upstream asserts on) with an exception naming why, so a
   program using them is reported as untranslatable rather than vacuously checked.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from xdsl.dialects import memref
from xdsl.dialects.builtin import DYNAMIC_INDEX, ArrayAttr, IndexType, IntegerType, MemRefType
from xdsl.ir import Attribute, SSAValue
from xdsl.parser import Parser
from xdsl.pattern_rewriter import PatternRewriter
from xdsl.printer import Printer
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer
from xdsl_smt.semantics.semantics import OperationSemantics


class UnsupportedMemRef(ValueError):
    """A memref shape or element type upstream's memory model cannot express."""


def memref_limitation(memref_type: Attribute) -> str | None:
    """Why upstream's `memref.load`/`store` cannot translate an access to this type."""
    if not isinstance(memref_type, MemRefType):
        return None
    if any(size == DYNAMIC_INDEX for size in memref_type.get_shape()):
        return f"dynamic shape {memref_type} (upstream's bound check would read it as -1)"
    if memref_type.get_element_type() != IntegerType(8):
        return f"element type of {memref_type} (upstream's memory stores i8 only)"
    return None


class _StaticShapeOnly(OperationSemantics):
    """Upstream's load/store semantics, refusing the shapes it would get wrong."""

    def __init__(self, inner: OperationSemantics, memref_position: int) -> None:
        self.inner = inner
        self.memref_position = memref_position

    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        types = attributes.get("__operand_types")
        if isinstance(types, ArrayAttr) and len(types.data) > self.memref_position:
            reason = memref_limitation(types.data[self.memref_position])
            if reason is not None:
                raise UnsupportedMemRef(f"cannot translate a memref access: {reason}")
        return self.inner.get_semantics(operands, results, attributes, effect_state, rewriter)


def _parse_alloca(cls: type[memref.AllocaOp], parser: Parser) -> memref.AllocaOp:
    dynamic = parser.parse_comma_separated_list(
        Parser.Delimiter.PAREN, parser.parse_unresolved_operand
    )
    symbols = (
        parser.parse_optional_comma_separated_list(
            Parser.Delimiter.SQUARE, parser.parse_unresolved_operand
        )
        or []
    )
    attributes = parser.parse_optional_attr_dict()
    parser.parse_punctuation(":")
    result_type = parser.parse_type()
    index = [parser.resolve_operand(o, IndexType()) for o in dynamic]
    symbol = [parser.resolve_operand(o, IndexType()) for o in symbols]
    op = cls(operands=[index, symbol], result_types=[result_type])
    for name, value in attributes.items():
        if name == "alignment":
            op.properties[name] = value
        else:
            op.attributes[name] = value
    return op


def _print_alloca(self: memref.AllocaOp, printer: Printer) -> None:
    printer.print_string("(")
    printer.print_list(self.dynamic_sizes, printer.print_ssa_value)
    printer.print_string(")")
    if self.symbol_operands:
        printer.print_string("[")
        printer.print_list(self.symbol_operands, printer.print_ssa_value)
        printer.print_string("]")
    extra = dict(self.attributes)
    if self.alignment is not None:
        extra["alignment"] = self.alignment
    printer.print_op_attributes(extra)
    printer.print_string(" : ")
    printer.print_attribute(self.memref.type)


def install_memref_support() -> None:
    """Attach `memref.alloca` syntax and guard upstream's load/store semantics."""
    setattr(memref.AllocaOp, "parse", classmethod(_parse_alloca))  # noqa: B010
    setattr(memref.AllocaOp, "print", _print_alloca)  # noqa: B010
    semantics = SMTLowerer.op_semantics
    for op_type, position in ((memref.LoadOp, 0), (memref.StoreOp, 1)):
        inner = semantics.get(op_type)
        if inner is not None and not isinstance(inner, _StaticShapeOnly):
            semantics[op_type] = _StaticShapeOnly(inner, position)
