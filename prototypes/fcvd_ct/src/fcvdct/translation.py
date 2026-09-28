"""Which operation occurrences in a corpus actually translate -- not which names are known.

`coverage.semantics_registry` answers "is there a rule for this operation name?". That
is an upper bound and nothing more: several rules are partial and reject whole classes
of occurrences (a dynamic `memref.alloca`, a float `memref.load`), and a name lookup
counts those as covered anyway (issue #63). This module measures the other thing -- it
parses the corpus and runs the real lowering on every occurrence:

- a **non-terminator** is lifted into a probe function of its own: every value it uses
  from outside becomes an argument of the same type, its attributes, properties and
  result types are kept, and the probe goes through the same `flatten` +
  `SMTLowerer` + `finish_module` path the checkers use. Nested regions come along, so a
  region operation (`scf.for`, `func.func`) translates only if everything inside it
  does -- the honest reading, since that is what a check of it would need;
- a **terminator** (`scf.yield`, `func.return`, `cf.br`) has no meaning on its own and is
  judged together with the operation that owns it;
- a **split** (`// -----`) that xdsl cannot parse is not measured at all: its mentions
  are counted as *unparsed*, never as translated.

Occurrences are compared against the corpus's textual mentions (the same count the
name-level report uses), and a name is never credited with more translated occurrences
than it has mentions, so the two numbers share a denominator and the gap between them
is exactly what the name lookup overstated.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from xdsl.builder import Builder
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.dialects.func import FuncOp, ReturnOp
from xdsl.ir import Block, Operation, Region, SSAValue
from xdsl.parser import Parser
from xdsl.rewriter import InsertPoint
from xdsl.traits import IsTerminator
from xdsl_smt.dialects import smt_dialect as smt
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer

from .context import make_context
from .predication import DEFAULT_MAX_VISITS
from .smtutil import finish_module, instantiate

#: `mlir-opt --split-input-file` separator: each part is an independent module.
SPLIT = re.compile(r"^// -----\s*$", re.MULTILINE)


@dataclass
class TranslationMeasure:
    """Per operation name: occurrences that translated, that did not, that went unread."""

    translated: Counter[str] = field(default_factory=Counter[str])
    rejected: Counter[str] = field(default_factory=Counter[str])
    unparsed: Counter[str] = field(default_factory=Counter[str])
    reasons: dict[str, Counter[str]] = field(default_factory=dict[str, Counter[str]])
    """Why occurrences of a name were rejected, first line of the exception."""
    functions: int = 0
    functions_translated: int = 0
    """Corpus functions with a body that translate whole, i.e. could be checked as-is."""
    splits: int = 0
    splits_parsed: int = 0


def _external_values(op: Operation) -> list[SSAValue]:
    """Values `op` (or anything nested in it) uses but does not define."""
    inside: set[SSAValue] = set()
    for nested in op.walk():
        inside.update(nested.results)
        for region in nested.regions:
            for block in region.blocks:
                inside.update(block.args)
    used: list[SSAValue] = []
    seen: set[SSAValue] = set()
    for nested in op.walk():
        for operand in nested.operands:
            if operand not in inside and operand not in seen:
                seen.add(operand)
                used.append(operand)
    return used


def probe_function(op: Operation) -> FuncOp:
    """`op` alone in a function, its outside operands turned into arguments."""
    if isinstance(op, FuncOp):
        return op.clone()
    external = _external_values(op)
    block = Block(arg_types=[value.type for value in external])
    mapping: dict[SSAValue, SSAValue] = dict(zip(external, block.args, strict=True))
    block.add_op(op.clone(value_mapper=mapping))
    block.add_op(ReturnOp())
    return FuncOp.from_region("probe", [value.type for value in external], [], Region(block))


def translate(ctx: Context, function: FuncOp, max_visits: int = DEFAULT_MAX_VISITS) -> str:
    """Lower one function the way the checkers do; "" on success, else the reason."""
    if not function.body.blocks:
        # A declaration has nothing to translate but its signature.
        try:
            for input_type in function.function_type.inputs:
                SMTLowerer.lower_type(input_type)
        except Exception as error:  # noqa: BLE001 -- any refusal is a finding
            return _reason(error)
        return ""
    try:
        module = ModuleOp([])
        builder = Builder(InsertPoint.at_end(module.body.block))
        inputs = [
            builder.insert(smt.DeclareConstOp(SMTLowerer.lower_type(t))).res
            for t in function.function_type.inputs
        ]
        instantiate(function, inputs, builder, None, max_visits)
        finish_module(ctx, module, opt=False)
    except Exception as error:  # noqa: BLE001 -- any refusal is a finding
        return _reason(error)
    return ""


def _reason(error: BaseException) -> str:
    text = str(error).strip().splitlines()
    return f"{type(error).__name__}: {text[-1].strip() if text else ''}"[:120]


def _unit(op: Operation) -> Operation | None:
    """The operation whose translation decides `op`'s: itself, or its owner if it ends a block."""
    if op.has_trait(IsTerminator):
        return op.parent_op()
    return op


def measure_text(
    ctx: Context,
    text: str,
    wanted: set[str],
    mention: re.Pattern[str],
    result: TranslationMeasure,
    max_visits: int = DEFAULT_MAX_VISITS,
) -> None:
    """Measure one file: every split is parsed and every occurrence in it probed."""
    for split in SPLIT.split(text):
        mentions: Counter[str] = Counter()
        for line in split.splitlines():
            for dialect, name in mention.findall(line.split("//")[0]):
                if dialect in wanted:
                    mentions[f"{dialect}.{name}"] += 1
        result.splits += 1
        try:
            module = Parser(ctx, split).parse_module()
        except Exception:  # noqa: BLE001 -- unreadable splits are reported, not probed
            result.unparsed.update(mentions)
            continue
        result.splits_parsed += 1

        verdicts: dict[int, str] = {}
        translated: Counter[str] = Counter()
        rejected: dict[str, list[str]] = {}
        for op in module.walk():
            if op is module or op.name.split(".")[0] not in wanted:
                continue
            unit = _unit(op)
            if unit is None or unit is module:
                rejected.setdefault(op.name, []).append("no enclosing operation to judge it by")
                continue
            if id(unit) not in verdicts:
                verdicts[id(unit)] = translate(ctx, probe_function(unit), max_visits)
                if isinstance(unit, FuncOp) and unit.body.blocks:
                    result.functions += 1
                    result.functions_translated += verdicts[id(unit)] == ""
            if verdicts[id(unit)] == "":
                translated[op.name] += 1
            else:
                rejected.setdefault(op.name, []).append(verdicts[id(unit)])

        for name, count in mentions.items():
            ok = min(translated[name], count)
            result.translated[name] += ok
            if count > ok:
                result.rejected[name] += count - ok
                reasons = result.reasons.setdefault(name, Counter())
                for reason in rejected.get(name, ["mentioned, but not an operation xdsl parsed"])[
                    : count - ok
                ]:
                    reasons[reason] += 1


def measure(
    checkout: Path,
    globs: Sequence[str],
    dialects: Iterable[str],
    mention: re.Pattern[str],
    max_visits: int = DEFAULT_MAX_VISITS,
) -> TranslationMeasure:
    """Measure a whole corpus, file by file, in the order `scan_operations` reads it."""
    ctx = make_context()
    ctx.allow_unregistered = True
    wanted = set(dialects)
    result = TranslationMeasure()
    for glob in globs:
        for path in sorted(checkout.glob(glob)):
            if path.is_file():
                measure_text(
                    ctx, path.read_text(errors="replace"), wanted, mention, result, max_visits
                )
    return result
