r"""Non-interference for one kernel, by self-composition -- steps 1, 2, 4 and 5.

`pdl_ct` and `structural` ask whether a *transformation* preserves whatever leakage a
program already had. That question needs no secret/public labelling, which is what lets
it quantify over all programs. This module asks the other question, the one the plan
starts from: given a labelling, is *this* program constant-time at all?

    forall public p, secrets s, s'.  L(p, s) = L(p, s')

The encoding is the textbook one:

1. **Labels.** Arguments carry `{fcvdct.secret}` (or `{stagingni.protected}`, the
   marking `prototypes/Staging_NI` already uses, so one annotation serves both tools).
2. **Two runs.** The kernel is lowered to SMT twice. Public arguments are *the same SMT
   constant* in both runs and secrets are two independent ones, which states "the runs
   agree on the public part" without needing an assumption. Both runs start from the
   same effect state: same initial memory.
3. **Obligations.** Observations are tagged by which channel they come through, and
   each channel is proved separately, so a verdict names the leak:

   | obligation | observations | the plan's wording |
   |---|---|---|
   | `control`  | branch conditions, trip counts | "conditions and iteration counts are equal" |
   | `address`  | load/store addresses | "computed addresses agree to the bit" |
   | `latency`  | operands of `div`/`rem` | variable-latency instructions |
   | `resource` | allocation sizes, freed pointers | "the sets of allocated and un-freed memory are identical" |

4. **Verdict.** Each obligation is one `check-sat` on `not (traces agree)`: `unsat` =
   proved for this kernel and this leakage model, `sat` = z3 hands back the two secrets
   that separate the traces, anything else = `unknown`, never folded into `secure`.

Control flow (including bounded loops) comes from `predication.flatten`, so an
observation is compared together with the guard it happens under -- and since a guard
is itself built from branch conditions, "the runs took different paths" shows up as a
`control` violation rather than as a spurious value mismatch.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from io import StringIO
from typing import Literal

from xdsl.builder import Builder
from xdsl.context import Context
from xdsl.dialects.builtin import DictionaryAttr, ModuleOp
from xdsl.dialects.func import FuncOp
from xdsl.ir import Operation, SSAValue
from xdsl.rewriter import InsertPoint
from xdsl.transforms.canonicalize import CanonicalizePass
from xdsl.transforms.common_subexpression_elimination import (
    CommonSubexpressionElimination,
)
from xdsl_smt.dialects import smt_dialect as smt
from xdsl_smt.dialects.effects.effect import StateType
from xdsl_smt.passes.dead_code_elimination import DeadCodeElimination
from xdsl_smt.passes.lower_effects_with_memory import LowerEffectsWithMemoryPass
from xdsl_smt.passes.lower_memory_effects import LowerMemoryEffectsPass
from xdsl_smt.passes.lower_memory_to_array import LowerMemoryToArrayPass
from xdsl_smt.passes.lower_pairs import LowerPairs
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer
from xdsl_smt.passes.smt_expand import SMTExpand
from xdsl_smt.traits.smt_printer import print_to_smtlib

from .dialect import ADDRESS, CONTROL, LATENCY, OTHER, RESOURCE, Observation
from .leakage import LeakageRule
from .predication import DEFAULT_MAX_VISITS, UnsupportedTemplate
from .smtutil import instantiate, traces_agree

Verdict = Literal["secure", "insecure", "unknown"]

SECRET_ATTRIBUTES = ("fcvdct.secret", "stagingni.protected")
"""Argument attributes that mark an input as secret. Everything else is public."""

OBLIGATIONS: tuple[str, ...] = (CONTROL, ADDRESS, LATENCY, RESOURCE, OTHER)


class NotLabelled(Exception):
    """The kernel does not say what is secret, so there is no property to prove."""


@dataclass
class ObligationResult:
    kind: str
    verdict: Verdict
    n_observations: int
    counterexample: str = ""
    reason: str = ""


@dataclass
class SelfCompResult:
    verdict: Verdict
    obligations: list[ObligationResult] = field(default_factory=list[ObligationResult])
    bounded: bool = False
    """A loop was cut by the unrolling bound: the verdict covers those iterations only."""
    reason: str = ""
    secrets: tuple[str, ...] = ()
    smtlib: str = ""


def _is_secret(attributes: DictionaryAttr | None) -> bool:
    return attributes is not None and any(name in attributes.data for name in SECRET_ATTRIBUTES)


def secret_arguments(function: FuncOp) -> list[bool]:
    """Which arguments are secret, from the argument attributes."""
    arg_attrs = function.arg_attrs
    if arg_attrs is None:
        return [False] * len(function.function_type.inputs)
    return [_is_secret(attrs) for attrs in arg_attrs]


def find_kernel(module: ModuleOp, name: str | None = None) -> FuncOp:
    """The function to check: the named one, the labelled one, or the only one."""
    functions = [op for op in module.body.ops if isinstance(op, FuncOp)]
    if name is not None:
        for function in functions:
            if function.sym_name.data == name:
                return function
        raise NotLabelled(f"no function @{name} in this module")
    labelled = [function for function in functions if any(secret_arguments(function))]
    if len(labelled) == 1:
        return labelled[0]
    if len(functions) == 1:
        return functions[0]
    raise NotLabelled(
        "which function should be checked? mark one argument secret, or pass --function"
    )


def build_query(
    ctx: Context,
    function: FuncOp,
    kind: str,
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
    max_visits: int = DEFAULT_MAX_VISITS,
) -> tuple[str, dict[str, int], bool]:
    """Build the SMTLib script asserting that `kind` observations *can* differ."""
    secret = secret_arguments(function)
    if not any(secret):
        raise NotLabelled(
            f"@{function.sym_name.data} marks no argument secret "
            f"({' or '.join('{' + a + '}' for a in SECRET_ATTRIBUTES)})"
        )

    module = ModuleOp([])
    builder = Builder(InsertPoint.at_end(module.body.block))

    # Public inputs and the initial memory are shared between the runs; secrets are not.
    # Sharing rather than asserting equality keeps the query smaller and makes the model
    # z3 prints show only the values that actually differ.
    shared: list[SSAValue | None] = []
    for index, input_type in enumerate(function.function_type.inputs):
        if secret[index]:
            shared.append(None)
            continue
        declared = builder.insert(smt.DeclareConstOp(SMTLowerer.lower_type(input_type)))
        declared.res.name_hint = f"public{index}"
        shared.append(declared.res)
    state = builder.insert(smt.DeclareConstOp(StateType())).res
    state.name_hint = "memory_in"

    bounded = False
    traces: list[Sequence[Observation]] = []
    for run in range(2):
        inputs: list[SSAValue] = []
        for index, input_type in enumerate(function.function_type.inputs):
            public = shared[index]
            if public is not None:
                inputs.append(public)
                continue
            declared = builder.insert(smt.DeclareConstOp(SMTLowerer.lower_type(input_type)))
            declared.res.name_hint = f"secret{index}_run{run}"
            inputs.append(declared.res)
        trace, run_bounded, _ = instantiate(function, inputs, builder, model, max_visits, state)
        bounded = bounded or run_bounded
        traces.append(trace.observations)

    counts = {
        obligation: sum(1 for o in traces[0] if o.kind == obligation) for obligation in OBLIGATIONS
    }
    selected = [[o for o in trace if o.kind == kind] for trace in traces]
    agree = traces_agree(builder, selected[0], selected[1])
    builder.insert(smt.AssertOp(builder.insert(smt.NotOp(agree)).result))
    builder.insert(smt.CheckSatOp())

    # The memory pipeline, in upstream's own order (`xdsl_smt/cli/xdsl_tv.py`): effects
    # become a (memory, ub) pair, then memory becomes SMT arrays.
    LowerMemoryEffectsPass().apply(ctx, module)
    LowerEffectsWithMemoryPass().apply(ctx, module)
    if opt:
        LowerPairs().apply(ctx, module)
        CanonicalizePass().apply(ctx, module)
    LowerMemoryToArrayPass().apply(ctx, module)
    SMTExpand().apply(ctx, module)
    if opt:
        LowerPairs().apply(ctx, module)
        CanonicalizePass().apply(ctx, module)
        CommonSubexpressionElimination().apply(ctx, module)
        CanonicalizePass().apply(ctx, module)
        DeadCodeElimination().apply(ctx, module)
    module.verify()

    stream = StringIO()
    print_to_smtlib(module, stream)
    return stream.getvalue(), counts, bounded


_SECRET_IN_MODEL = re.compile(
    r"\(define-fun \$(secret\d+_run\d+)_first \(\)[^)]*\)\s*(#[xb][0-9a-fA-F]+|true|false)"
)


def separating_secrets(model: str) -> list[tuple[str, str]]:
    """The `(name, value)` pairs of the two runs' secrets, pulled out of z3's model.

    The full model also describes the memory arrays, which is rarely what a reader
    wants to see; the values that separate the runs are.
    """
    return [(name, value) for name, value in _SECRET_IN_MODEL.findall(model)]


def _run_z3(script: str, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["z3", "-in", f"-T:{timeout}"],
        capture_output=True,
        input=script,
        text=True,
        check=False,
    )


def check_kernel(
    ctx: Context,
    function: FuncOp,
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
    timeout: int = 60,
    max_visits: int = DEFAULT_MAX_VISITS,
) -> SelfCompResult:
    """Prove, or refute, non-interference of one labelled kernel, obligation by obligation."""
    secret = secret_arguments(function)
    names = tuple(f"arg{index}" for index, is_secret in enumerate(secret) if is_secret)

    obligations: list[ObligationResult] = []
    bounded = False
    first_script = ""
    for kind in OBLIGATIONS:
        try:
            script, counts, kind_bounded = build_query(ctx, function, kind, model, opt, max_visits)
        except (NotLabelled, UnsupportedTemplate) as e:
            return SelfCompResult("unknown", [], reason=f"{type(e).__name__}: {e}", secrets=names)
        except Exception as e:  # an operation without semantics, a type we cannot lower
            return SelfCompResult("unknown", [], reason=f"{type(e).__name__}: {e}", secrets=names)
        bounded = bounded or kind_bounded
        first_script = first_script or script
        if counts[kind] == 0:
            # Nothing of this kind happens in the kernel. Vacuously true, and reported
            # with its count so that "secure" cannot be mistaken for "checked something".
            obligations.append(ObligationResult(kind, "secure", 0))
            continue
        result = _run_z3(script, timeout)
        output = result.stdout.strip()
        if output.startswith("unsat"):
            obligations.append(ObligationResult(kind, "secure", counts[kind]))
        elif output.startswith("sat"):
            with_model = _run_z3(script + "\n(get-model)\n", timeout)
            obligations.append(
                ObligationResult(kind, "insecure", counts[kind], with_model.stdout.strip())
            )
        else:
            obligations.append(
                ObligationResult(
                    kind,
                    "unknown",
                    counts[kind],
                    reason=f"solver said {output or '<nothing>'}; {result.stderr.strip()}",
                )
            )

    verdicts = {obligation.verdict for obligation in obligations}
    verdict: Verdict = (
        "insecure" if "insecure" in verdicts else "unknown" if "unknown" in verdicts else "secure"
    )
    return SelfCompResult(verdict, obligations, bounded, secrets=names, smtlib=first_script)


def check_module(
    ctx: Context,
    module: ModuleOp,
    name: str | None = None,
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
    timeout: int = 60,
    max_visits: int = DEFAULT_MAX_VISITS,
) -> SelfCompResult:
    try:
        function = find_kernel(module, name)
    except NotLabelled as e:
        return SelfCompResult("unknown", [], reason=f"NotLabelled: {e}")
    return check_kernel(ctx, function, model, opt, timeout, max_visits)
