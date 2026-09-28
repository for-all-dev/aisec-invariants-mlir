r"""Template families: one lowering rule, checked over every instance a sweep declares.

A template is a hand transcription of one rewrite, and a hand transcription picks
concrete sizes, element types, trip counts and strides -- `memref<4xi8>`, a loop
`0 to 3`, a row stride of 3 -- where the pass itself is general over all of them
(issue #63). Holes already quantify over the code *inside* a rewrite; what they cannot
quantify over is the rewrite's own shape parameters, because those have to be concrete
for the program to be written down at all (a semi-affine stride, a dynamic memref
extent, an arbitrary bit width are not expressible to the lowering). A sweep makes
the choice of instance explicit and plural instead of silent and single:

    // fcvdct.sweep W = i8, i16, i32, i64
    // fcvdct.sweep N = 1, 2, 4
    ... memref<${N}xi8> ... arith.addi %a, %b : ${W} ... affine_map<(d0) -> (d0 * ${N - 1})>

Every `${...}` is replaced, in every combination of the declared values (the cartesian
product), by the bound value or by the integer an arithmetic expression over bound
integers evaluates to. The template is then checked once per instance, and it counts
as proved only if **every** instance passes both halves of the gate; the first instance
that refutes a half is named in the result. A template with no `fcvdct.sweep` line is
one instance, as before -- and says so in the report.

This is still sampling, not a proof over all shapes, and the report says how many
instances were checked so that it cannot be read as one. An unsubstituted `${` is not
MLIR, so a placeholder the sweep forgot to bind fails to parse rather than being
checked as something else.
"""

from __future__ import annotations

import ast
import operator
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from xdsl.context import Context
from xdsl.ir import Operation
from xdsl.parser import Parser

from .leakage import LeakageRule
from .predication import DEFAULT_MAX_VISITS
from .structural import EquivalenceResult, GateResult, LoweringResult, check_template

SWEEP = re.compile(r"^//\s*fcvdct\.sweep\s+([A-Za-z_]\w*)\s*=\s*(.+?)\s*$", re.MULTILINE)
PLACEHOLDER = re.compile(r"\$\{([^}]*)\}")

_BINARY: dict[type[ast.operator], Callable[[int, int], int]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}


@dataclass(frozen=True)
class Instance:
    binding: tuple[tuple[str, str], ...]
    text: str

    @property
    def label(self) -> str:
        return ", ".join(f"{name}={value}" for name, value in self.binding) or "single instance"


def _evaluate(expression: str, binding: Mapping[str, str]) -> str:
    """A bound name as written, or integer arithmetic over bound integers."""
    expression = expression.strip()
    if expression in binding:
        return binding[expression]

    def value(node: ast.AST) -> int:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name) and node.id in binding:
            return int(binding[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            return _BINARY[type(node.op)](value(node.left), value(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -value(node.operand)
        raise ValueError(f"unsupported sweep expression: ${{{expression}}}")

    return str(value(ast.parse(expression, mode="eval").body))


def _value(raw: str, binding: Mapping[str, str]) -> str:
    """A sweep value: arithmetic over earlier parameters if it uses any, else literal."""
    try:
        return _evaluate(raw, binding)
    except (ValueError, SyntaxError):
        return raw


def instances(text: str) -> list[Instance]:
    """Every instance a template's `fcvdct.sweep` lines declare, in declaration order.

    A value may be an expression over parameters declared *above* it (`K = 0, N - 1`),
    so an axis can depend on another; combinations that come out identical are checked
    once.
    """
    axes: list[tuple[str, list[str]]] = []
    for name, values in SWEEP.findall(text):
        if any(name == existing for existing, _ in axes):
            raise ValueError(f"sweep parameter {name} is declared twice")
        axes.append((name, [v.strip() for v in values.split(",") if v.strip()]))
    body = SWEEP.sub("", text)

    bindings: list[dict[str, str]] = [{}]
    for name, values in axes:
        extended: list[dict[str, str]] = []
        for binding in bindings:
            seen: set[str] = set()
            for raw in values:
                value = _value(raw, binding)
                if value not in seen:
                    seen.add(value)
                    extended.append({**binding, name: value})
        bindings = extended

    return [
        Instance(
            tuple(binding.items()),
            PLACEHOLDER.sub(lambda m, b=binding: _evaluate(m.group(1), b), body),
        )
        for binding in bindings
    ]


def is_closed(text: str) -> bool:
    """No hole: every instance proves one fixed program pair and nothing around it."""
    return "fcvd.hole" not in SWEEP.sub("", text)


_CT_RANK = {"ct-preserving": 0, "unknown": 1, "ct-breaking": 2}
_EQ_RANK = {"equivalent": 0, "unknown": 1, "not-equivalent": 2}


@dataclass
class SweptGate:
    """The gate over a whole family: each half is the worst any instance returned."""

    gate: GateResult
    instances: int
    closed: bool
    decided_by: dict[str, str] = field(default_factory=dict[str, str])
    """For each half that did not pass, the instance that refuted it."""

    @property
    def verdict(self) -> str:
        return self.gate.verdict


def check_template_text(
    ctx: Context,
    text: str,
    name: str = "<template>",
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
    timeout: int = 60,
    max_visits: int = DEFAULT_MAX_VISITS,
) -> SweptGate:
    """Run the gate on every instance; the family passes a half only if all instances do."""
    family = instances(text)
    worst_ct: tuple[LoweringResult, str] | None = None
    worst_eq: tuple[EquivalenceResult, str] | None = None
    for instance in family:
        module = Parser(ctx, instance.text, name).parse_module()
        gate = check_template(ctx, module, model, opt, timeout, max_visits)
        ct, eq = gate.constant_time, gate.equivalence
        if worst_ct is None or _CT_RANK[ct.verdict] > _CT_RANK[worst_ct[0].verdict]:
            worst_ct = (ct, instance.label)
        if worst_eq is None or _EQ_RANK[eq.verdict] > _EQ_RANK[worst_eq[0].verdict]:
            worst_eq = (eq, instance.label)
        if worst_ct[0].verdict == "ct-breaking" and worst_eq[0].verdict == "not-equivalent":
            break  # both halves refuted: nothing further can change the verdict
    assert worst_ct is not None and worst_eq is not None
    ct, eq = worst_ct[0], worst_eq[0]
    if ct.verdict == "unknown" or eq.verdict == "unknown":
        verdict = "unknown"
    elif ct.verdict == "ct-preserving" and eq.verdict == "equivalent":
        verdict = "verified"
    else:
        verdict = "rejected"
    decided_by: dict[str, str] = {}
    if len(family) > 1:
        if ct.verdict != "ct-preserving":
            decided_by["constant-time"] = worst_ct[1]
        if eq.verdict != "equivalent":
            decided_by["equivalence"] = worst_eq[1]
    return SweptGate(
        GateResult(verdict, ct, eq),  # type: ignore[arg-type]
        len(family),
        is_closed(text),
        decided_by,
    )


def check_template_file(
    ctx: Context,
    path: Path,
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
    timeout: int = 60,
    max_visits: int = DEFAULT_MAX_VISITS,
) -> SweptGate:
    return check_template_text(ctx, path.read_text(), str(path), model, opt, timeout, max_visits)
