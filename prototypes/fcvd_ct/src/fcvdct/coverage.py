"""How much of a given compiler can this method actually verify today?

The plan picks the first compilers to verify by "which ones have the fewest translations
that are not proved". That is a question with a number as an answer, so it should be
computed rather than argued. For a compiler checkout, this module

1. reads the operations that actually occur in the compiler's **own test corpus** --
   usage-weighted, so an operation nobody writes does not count as much as one every
   test uses;
2. classifies each of them into one of the three forms below;
3. prints the counts, and the unproved operations in order of how often they occur.

The forms are the ones the plan names:

- **form 0** -- the operation has SMT semantics, so FCVD can translate it directly and
  a program using it can be checked as it stands. Read from the live registry
  (`SMTLowerer.op_semantics`), never from a hand-written list, so it cannot drift.
- **form 1** -- no semantics, but the operation is covered by a **macro-template**: a
  structural specification proved once by `fcvd-ct-lowering`. Counted only if the proof
  passes *now*, and only if **both** halves of the gate pass: `fcvd-ct-coverage` re-runs
  it (unless `--no-prove`), because a template that has stopped proving covers nothing,
  and one that preserves constant-time while changing what the code computes was never
  a translation of it in the first place.
- **form 2** -- neither. This is the work item, and the number the choice of compiler
  should be based on.

A form-0 count is not a claim that the compiler is verified; it is the size of the
subset a proof can currently talk about.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.parser import Parser
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer

from .context import make_context
from .structural import check_template

COMPILERS = Path(__file__).parent.parent.parent / "compilers"
TEMPLATES = Path(__file__).parent.parent.parent / "templates"

#: An operation mention in MLIR text: `dialect.op`, not preceded by the sigils that
#: introduce a type (`!hw.array`), an attribute alias (`#hw.output_file`), an SSA value
#: or a symbol, and not followed by `<`, which makes it a parametrised attribute
#: (`arith.fastmath<none>`) rather than an operation.
OP_MENTION = re.compile(r"(?<![\w.!#%@])([a-z][a-z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)(?![\w<])")


@dataclass(frozen=True)
class Stage:
    """One lowering step of the compiler's own pipeline, as its source spells it."""

    pass_name: str
    source_dialects: tuple[str, ...]
    target_dialects: tuple[str, ...]
    cited: str
    """`file:line` in the compiler checkout the step was read from."""


@dataclass(frozen=True)
class Template:
    file: str
    covers: tuple[str, ...]
    """Operations this template's proof accounts for."""
    verifies: str = ""
    """The pipeline step this template is a specification of."""
    breaks_ops: tuple[str, ...] = ()
    """Operations this template shows to be dangerous under their real lowering.

    Separate from `covers`, and orthogonal to it: an operation can have SMT semantics
    and still be one whose lowering introduces a leak. `comb.divu` is both.
    """
    expect: str = "ct-preserving"
    """What the template is documented to come back as.

    A template that is *expected* to break constant-time is a finding, not a failure --
    `--convert-comb-to-arith` is one. Either way the checker must agree with the
    documentation, or the descriptor is stale and neither the coverage nor the finding
    can be believed.
    """


@dataclass
class Compiler:
    name: str
    repo: str
    commit: str
    checkout: Path
    dialects: tuple[str, ...]
    test_globs: tuple[str, ...]
    pipeline: tuple[Stage, ...]
    templates: tuple[Template, ...]
    note: str = ""

    @staticmethod
    def load(path: Path, checkout: Path | None = None) -> Compiler:
        raw = json.loads(path.read_text())
        return Compiler(
            name=raw["name"],
            repo=raw["repo"],
            commit=raw["commit"],
            checkout=(checkout or Path(raw["checkout"]).expanduser()),
            dialects=tuple(raw["dialects"]),
            test_globs=tuple(raw["test_globs"]),
            pipeline=tuple(
                Stage(
                    s["pass"],
                    tuple(s["from"]),
                    tuple(s["to"]),
                    s["cited"],
                )
                for s in raw["pipeline"]
            ),
            templates=tuple(
                Template(
                    t["file"],
                    tuple(t.get("covers", ())),
                    t.get("verifies", ""),
                    tuple(t.get("breaks_ops", ())),
                    t.get("expect", "ct-preserving"),
                )
                for t in raw["templates"]
            ),
            note=raw.get("note", ""),
        )


@dataclass
class OperationCoverage:
    name: str
    occurrences: int
    form: int
    covered_by: str = ""
    broken_by: tuple[str, ...] = ()
    """Templates that show this operation's real lowering to introduce a leak.

    Orthogonal to `form`: knowing how to translate an operation and knowing that its
    lowering is unsafe are different facts, and an operation can carry both.
    """


@dataclass
class StageCoverage:
    """One lowering step of the pipeline, and how much of its input we can translate.

    A step whose source operations are all form 0 or form 1 is one this method can be
    pointed at today; a step with form-2 inputs cannot be checked per-program until
    those operations are given semantics or covered by a template.
    """

    stage: Stage
    forms: tuple[int, int, int]
    """How many distinct source-dialect operations fall in form 0, 1 and 2."""
    proved: tuple[str, ...] = ()
    """Templates that specify this step and came back ct-preserving, as documented."""
    breaks: tuple[str, ...] = ()
    """Templates that specify this step and came back ct-breaking, as documented."""

    @property
    def ready(self) -> bool:
        return self.forms[2] == 0 and (self.forms[0] + self.forms[1]) > 0


@dataclass
class CoverageReport:
    compiler: str
    commit: str
    files_scanned: int
    operations: list[OperationCoverage] = field(default_factory=list[OperationCoverage])
    proved_templates: list[str] = field(default_factory=list[str])
    failed_templates: list[str] = field(default_factory=list[str])

    stages: list[StageCoverage] = field(default_factory=list["StageCoverage"])

    def by_form(self, form: int) -> list[OperationCoverage]:
        return [op for op in self.operations if op.form == form]

    @property
    def unproved(self) -> int:
        """The number the choice of compiler is supposed to be made on."""
        return len(self.by_form(2))


#: Control flow has no SMT semantics anywhere and does not need any: `predication.py`
#: translates it by if-conversion and, for back edges, by bounded unrolling. That is a
#: translation we wrote, so these operations are covered -- with the bound stated.
FLATTENED_OPS = {
    "cf.br": "if-conversion (fcvdct.predication)",
    "cf.cond_br": "if-conversion (fcvdct.predication)",
    "scf.if": "if-conversion (fcvdct.predication)",
    "scf.yield": "if-conversion (fcvdct.predication)",
    "scf.for": "bounded unrolling (fcvdct.predication)",
    "scf.while": "bounded unrolling (fcvdct.predication)",
    "scf.condition": "bounded unrolling (fcvdct.predication)",
    "affine.for": "exact unrolling, constant bounds only (fcvdct.predication)",
    "affine.yield": "exact unrolling, constant bounds only (fcvdct.predication)",
    "affine.load": "map expansion to memref.load, dim/const maps only (fcvdct.predication)",
    "affine.store": "map expansion to memref.store, dim/const maps only (fcvdct.predication)",
}


def semantics_registry() -> dict[str, str]:
    """What FCVD can translate right now, and by which mechanism.

    Three registries feed this, all read live so that the report cannot drift from the
    code: operation semantics, the structural rewrite patterns (`func.func` and
    `func.return` are lowered by those, not by a semantics entry), and our own
    control-flow flattener.
    """
    make_context()  # loads upstream's semantics plus the ones this package adds
    names: dict[str, str] = {}
    for op_type in SMTLowerer.op_semantics:
        name = getattr(op_type, "name", None)
        if isinstance(name, str):
            names[name] = "SMT semantics"
    for op_type in SMTLowerer.rewrite_patterns:
        name = getattr(op_type, "name", None)
        if isinstance(name, str):
            names.setdefault(name, "structural lowering")
    for name, mechanism in FLATTENED_OPS.items():
        names.setdefault(name, mechanism)
    return names


def scan_operations(checkout: Path, globs: Sequence[str], dialects: Iterable[str]) -> Counter[str]:
    """Count operation mentions in a compiler's test corpus, restricted to `dialects`."""
    wanted = set(dialects)
    counts: Counter[str] = Counter()
    files = 0
    for glob in globs:
        for path in sorted(checkout.glob(glob)):
            if not path.is_file():
                continue
            files += 1
            for line in path.read_text(errors="replace").splitlines():
                text = line.split("//")[0]
                for dialect, op in OP_MENTION.findall(text):
                    if dialect in wanted:
                        counts[f"{dialect}.{op}"] += 1
    counts["__files__"] = files
    return counts


@dataclass
class TemplateOutcome:
    template: Template
    verdict: str
    as_documented: bool
    reason: str = ""
    equivalence: str = "equivalent"
    """The other half. A template may only stand in for a translation if it preserves
    constant-time *and* leaves what the program computes alone, so this decides whether
    a ct-preserving template counts towards form 1."""


def prove_templates(compiler: Compiler, timeout: int = 120) -> list[TemplateOutcome]:
    """Run every template the descriptor claims, and see whether it still behaves so.

    A template only carries weight if the checker agrees with what the descriptor says
    it does: a template that has stopped proving covers nothing, and a template
    documented as ct-breaking has to still break, or the finding it records is stale.

    Both halves of the gate are run. `expect` documents the leakage half, because that
    is what a descriptor is a claim about; the equivalence half is not a matter of
    documentation -- a macro-template that changes the meaning of the code cannot stand
    in for a translation, whatever the descriptor says.
    """
    ctx = make_context()
    outcomes: list[TemplateOutcome] = []
    for template in compiler.templates:
        path = TEMPLATES / template.file
        module = Parser(ctx, path.read_text(), str(path)).parse_module()
        gate = check_template(ctx, module, timeout=timeout)
        outcomes.append(
            TemplateOutcome(
                template,
                gate.constant_time.verdict,
                gate.constant_time.verdict == template.expect,
                gate.reason,
                gate.equivalence.verdict,
            )
        )
    return outcomes


def report(compiler: Compiler, prove: bool = True, timeout: int = 120) -> CoverageReport:
    registry = semantics_registry()
    counts = scan_operations(compiler.checkout, compiler.test_globs, compiler.dialects)
    files = counts.pop("__files__", 0)

    covered: dict[str, str] = {}
    failed: list[str] = []
    proved_steps: dict[str, list[str]] = {}
    breaking_steps: dict[str, list[str]] = {}
    dangerous: dict[str, list[str]] = {}
    if prove:
        for outcome in prove_templates(compiler, timeout):
            template = outcome.template
            if not outcome.as_documented:
                failed.append(
                    f"{template.file}: documented {template.expect}, checker says "
                    f"{outcome.verdict} {outcome.reason}".strip()
                )
                continue
            if outcome.verdict == "ct-preserving":
                if outcome.equivalence != "equivalent":
                    failed.append(
                        f"{template.file}: preserves constant-time but the equivalence half "
                        f"says {outcome.equivalence}, so it specifies nothing and covers nothing"
                    )
                    continue
                for op in template.covers:
                    covered.setdefault(op, template.file)
                if template.verifies:
                    proved_steps.setdefault(template.verifies, []).append(template.file)
            elif outcome.verdict == "ct-breaking":
                for op in template.breaks_ops:
                    dangerous.setdefault(op, []).append(template.file)
                if template.verifies:
                    breaking_steps.setdefault(template.verifies, []).append(template.file)
    else:
        # Claimed, not proved: only honest to report when the caller asked to skip.
        for template in compiler.templates:
            if template.expect != "ct-preserving":
                continue
            for op in template.covers:
                covered.setdefault(op, f"{template.file} (claimed, not re-proved)")
            if template.verifies:
                proved_steps.setdefault(template.verifies, []).append(f"{template.file} (claimed)")

    operations = []
    for name, occurrences in counts.most_common():
        broken = tuple(dangerous.get(name, ()))
        if name in registry:
            operations.append(OperationCoverage(name, occurrences, 0, registry[name], broken))
        elif name in covered:
            operations.append(OperationCoverage(name, occurrences, 1, covered[name], broken))
        else:
            operations.append(OperationCoverage(name, occurrences, 2, "", broken))
    per_dialect: dict[str, list[OperationCoverage]] = {}
    for op in operations:
        per_dialect.setdefault(op.name.split(".")[0], []).append(op)
    stages = []
    for stage in compiler.pipeline:
        forms = [0, 0, 0]
        for dialect in stage.source_dialects:
            for op in per_dialect.get(dialect, []):
                forms[op.form] += 1
        stages.append(
            StageCoverage(
                stage,
                (forms[0], forms[1], forms[2]),
                tuple(proved_steps.get(stage.pass_name, ())),
                tuple(breaking_steps.get(stage.pass_name, ())),
            )
        )

    return CoverageReport(
        compiler.name,
        compiler.commit,
        files,
        operations,
        sorted(set(covered.values())),
        failed,
        stages,
    )


def load_all(checkouts: dict[str, Path] | None = None) -> list[Compiler]:
    checkouts = checkouts or {}
    return [
        Compiler.load(path, checkouts.get(path.stem)) for path in sorted(COMPILERS.glob("*.json"))
    ]


def parse_module(ctx: Context, path: Path) -> ModuleOp:
    return Parser(ctx, path.read_text(), str(path)).parse_module()
