"""Textual syntax for the `affine` loop, restricted to the shape the hardenings emit.

HEIR's data-oblivious passes and onnx-mlir's `--convert-krnl-to-affine` both produce
`affine.for` with *constant* bounds -- which is the point of them: a loop whose trip
count is fixed by the map cannot leak a secret through how many times it runs. xdsl
declares the operation but gives it no custom syntax, so the IR those compilers print
cannot be read in at all. This module attaches the syntax for the constant-bound form
to xdsl's own `affine.for`:

    affine.for %i = 0 to 32 { ... affine.yield }
    affine.for %i = 0 to 32 step 2 iter_args(%acc = %init) -> (i16) { ... }

Data-dependent bounds (`affine.for %i = 0 to %n`) are deliberately *not* parsed. They
are the case the hardening passes exist to eliminate, so a loop that still has one must
fail to be read rather than be checked as though it were static.
"""

from __future__ import annotations

from collections.abc import Sequence

from xdsl.dialects.affine import ForOp, YieldOp
from xdsl.dialects.builtin import IndexType
from xdsl.ir import Attribute, Block, Region
from xdsl.parser import Parser, UnresolvedOperand
from xdsl.printer import Printer


def constant_bound(bound: Attribute) -> int | None:
    """The value of an affine bound map, if it is a single constant expression."""
    affine_map = getattr(bound, "data", None)
    results = getattr(affine_map, "results", ())
    if len(results) != 1:
        return None
    value = getattr(results[0], "value", None)
    return value if isinstance(value, int) else None


def _parse(cls: type[ForOp], parser: Parser) -> ForOp:
    induction = parser.parse_argument(expect_type=False)
    parser.parse_punctuation("=")
    lower = parser.parse_integer()
    parser.parse_keyword("to")
    upper = parser.parse_integer()
    step = parser.parse_integer() if parser.parse_optional_keyword("step") else 1

    arguments: list[Parser.Argument] = []
    inits: list[UnresolvedOperand] = []
    if parser.parse_optional_keyword("iter_args"):
        parser.parse_punctuation("(")
        while True:
            arguments.append(parser.parse_argument(expect_type=False))
            parser.parse_punctuation("=")
            inits.append(parser.parse_unresolved_operand())
            if not parser.parse_optional_punctuation(","):
                break
        parser.parse_punctuation(")")

    result_types: Sequence[Attribute] = ()
    if parser.parse_optional_punctuation("->"):
        result_types = parser.parse_comma_separated_list(parser.Delimiter.PAREN, parser.parse_type)
    resolved = [
        parser.resolve_operand(init, type) for init, type in zip(inits, result_types, strict=True)
    ]

    entry = [
        induction.resolve(IndexType()),
        *(argument.resolve(type) for argument, type in zip(arguments, result_types, strict=True)),
    ]
    body = parser.parse_region(entry)
    if not body.blocks:
        body = Region(Block(arg_types=[IndexType(), *result_types]))
    attributes = parser.parse_optional_attr_dict()

    op = ForOp.from_region((), (), resolved, result_types, lower, upper, body, step)
    op.attributes.update(attributes)
    return op


def _print(self: ForOp, printer: Printer) -> None:
    block = self.body.block
    lower = constant_bound(self.lowerBoundMap)
    upper = constant_bound(self.upperBoundMap)
    printer.print_string(" ")
    printer.print_ssa_value(block.args[0])
    printer.print_string(f" = {lower} to {upper}")
    if self.step.value.data != 1:
        printer.print_string(f" step {self.step.value.data}")
    if self.inits:
        printer.print_string(" iter_args(")
        for position, (argument, init) in enumerate(zip(block.args[1:], self.inits, strict=True)):
            printer.print_string(", " if position else "")
            printer.print_ssa_value(argument)
            printer.print_string(" = ")
            printer.print_ssa_value(init)
        printer.print_string(") -> (")
        for position, result_type in enumerate(self.result_types):
            printer.print_string(", " if position else "")
            printer.print_attribute(result_type)
        printer.print_string(")")
    printer.print_string(" ")
    printer.print_region(self.body, print_entry_block_args=False)


def _parse_yield(cls: type[YieldOp], parser: Parser) -> YieldOp:
    operands = parser.parse_optional_undelimited_comma_separated_list(
        parser.parse_optional_unresolved_operand, parser.parse_unresolved_operand
    )
    if not operands:
        return YieldOp(operands=[[]], result_types=[])
    parser.parse_punctuation(":")
    types = parser.parse_comma_separated_list(parser.Delimiter.NONE, parser.parse_type)
    return YieldOp(
        operands=[
            [
                parser.resolve_operand(operand, type)
                for operand, type in zip(operands, types, strict=True)
            ]
        ],
        result_types=[],
    )


def _print_yield(self: YieldOp, printer: Printer) -> None:
    if not self.operands:
        return
    printer.print_string(" ")
    for position, operand in enumerate(self.operands):
        printer.print_string(", " if position else "")
        printer.print_ssa_value(operand)
    printer.print_string(" : ")
    for position, operand in enumerate(self.operands):
        printer.print_string(", " if position else "")
        printer.print_attribute(operand.type)


def install_affine_syntax() -> None:
    """Attach parsers and printers to xdsl's `affine.for`/`affine.yield`.

    Both ship without one, so IR containing them cannot be read in as it stands.
    """
    ForOp.parse = classmethod(_parse)  # type: ignore[method-assign, assignment]
    ForOp.print = _print  # type: ignore[method-assign, assignment]
    YieldOp.parse = classmethod(_parse_yield)  # type: ignore[method-assign, assignment]
    YieldOp.print = _print_yield  # type: ignore[method-assign, assignment]
