"""The entry points.

`fcvd-ct-pdl` takes PDL rewrites and `fcvd-ct-lowering` takes structural lowering
specifications; both answer the same question -- does this transformation preserve
constant-time for every program it applies to? `fcvd-ct` asks the other one: is *this*
labelled kernel constant-time, obligation by obligation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from xdsl.dialects.builtin import ModuleOp
from xdsl.dialects.pdl import PatternOp
from xdsl.parser import Parser

from .context import make_context
from .coverage import COMPILERS, Compiler, report
from .pdl_ct import CTResult, check_pattern
from .predication import DEFAULT_MAX_VISITS
from .selfcomp import check_module, separating_secrets
from .structural import GateResult, LoweringResult, check_lowering, check_template

_SELFCOMP_LINE = {
    "secure": "SECURE",
    "insecure": "INSECURE",
    "unknown": "UNKNOWN",
}

_VERDICT_LINE = {
    "ct-preserving": "CT-PRESERVING",
    "ct-breaking": "CT-BREAKING",
    "unknown": "UNKNOWN",
}

_GATE_LINE = {
    "verified": "VERIFIED",
    "rejected": "REJECTED",
    "unknown": "UNKNOWN",
}

_EQUIVALENCE_LINE = {
    "equivalent": "EQUIVALENT",
    "not-equivalent": "NOT-EQUIVALENT",
    "unknown": "UNKNOWN",
}

_BOUNDED = "bounded: loops were unrolled, so this covers only the unrolled iterations"


def _report(name: str, result: CTResult | LoweringResult, show_counterexample: bool) -> None:
    print(
        f"{name}: {_VERDICT_LINE[result.verdict]} "
        f"(observations: source {result.n_source_observations}, "
        f"target {result.n_target_observations})"
    )
    if getattr(result, "bounded", False):
        print("  bounded: loops were unrolled, so this covers only the unrolled iterations")
    if result.reason:
        print(f"  reason: {result.reason}")
    if result.verdict == "ct-breaking" and show_counterexample and result.counterexample:
        for line in result.counterexample.splitlines():
            print(f"  | {line}")


def _report_gate(name: str, gate: GateResult, show_counterexample: bool) -> None:
    """Both halves, always both, and which one refused."""
    ct, equivalence = gate.constant_time, gate.equivalence
    print(f"{name}: {_GATE_LINE[gate.verdict]}")
    print(
        f"  constant-time  {_VERDICT_LINE[ct.verdict]:<14} "
        f"(observations: source {ct.n_source_observations}, target {ct.n_target_observations})"
    )
    memory = (
        "the memory left behind"
        if equivalence.memory_compared
        else "memory NOT compared (declared values-only)"
    )
    compared = (
        f"{equivalence.n_compared} returned value(s) + {memory}"
        if equivalence.n_compared
        else f"nothing returned, so {memory} is all that was compared"
    )
    print(f"  equivalence    {_EQUIVALENCE_LINE[equivalence.verdict]:<14} ({compared})")
    if ct.bounded or equivalence.bounded:
        print(f"  {_BOUNDED}")
    for half, result in (("constant-time", ct), ("equivalence", equivalence)):
        if result.reason:
            print(f"  reason ({half}): {result.reason}")
        if show_counterexample and result.counterexample and result.verdict in _REFUTED:
            print(f"  counterexample ({half}):")
            for line in result.counterexample.splitlines():
                print(f"  | {line}")


_REFUTED = ("ct-breaking", "not-equivalent")


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        description="Verify that PDL rewrites preserve constant-time, for every program they match."
    )
    arg_parser.add_argument("file", help="MLIR file containing pdl.pattern operations")
    arg_parser.add_argument(
        "--counterexample",
        action="store_true",
        help="print the model z3 returns for a CT-breaking rewrite",
    )
    arg_parser.add_argument(
        "--print-smt", action="store_true", help="print the SMTLib query and exit"
    )
    arg_parser.add_argument("--timeout", type=int, default=60, help="solver timeout, s")
    arg_parser.add_argument("--no-opt", action="store_true", help="skip SMT-level simplification")
    args = arg_parser.parse_args()

    ctx = make_context()
    with open(args.file) as f:
        module = Parser(ctx, f.read(), args.file).parse_module()

    patterns = [op for op in module.walk() if isinstance(op, PatternOp)]
    if not patterns:
        print(f"{args.file}: no pdl.pattern found", file=sys.stderr)
        raise SystemExit(2)

    broken = 0
    unknown = 0
    for pattern in patterns:
        name = f"pattern @{pattern.sym_name.data}" if pattern.sym_name else "anonymous pattern"
        single = ModuleOp([pattern.clone()])
        if args.print_smt:
            from .pdl_ct import build_query

            script, _, _ = build_query(ctx, single, opt=not args.no_opt)
            print(script)
            continue
        result = check_pattern(ctx, single, opt=not args.no_opt, timeout=args.timeout)
        _report(name, result, args.counterexample)
        broken += result.verdict == "ct-breaking"
        unknown += result.verdict == "unknown"

    if args.print_smt:
        return
    if broken:
        print(f"{broken} rewrite(s) introduce leakage")
        raise SystemExit(1)
    if unknown:
        print(f"{unknown} rewrite(s) could not be decided")
        raise SystemExit(3)
    print("all rewrites preserve constant-time")


def main_selfcomp() -> None:
    arg_parser = argparse.ArgumentParser(
        description="Prove non-interference (constant-time) of one labelled kernel by "
        "self-composition: public inputs equal, secrets free, observations must match."
    )
    arg_parser.add_argument("file", help="MLIR file containing the kernel")
    arg_parser.add_argument("--function", help="which function to check")
    arg_parser.add_argument(
        "--unroll",
        type=int,
        default=DEFAULT_MAX_VISITS,
        help="how many times a block may be re-entered on a path, i.e. the loop bound",
    )
    arg_parser.add_argument(
        "--counterexample",
        action="store_true",
        help="print the two secrets z3 returns for a violated obligation",
    )
    arg_parser.add_argument(
        "--full-model",
        action="store_true",
        help="print z3's whole model, memory arrays included, not just the secrets",
    )
    arg_parser.add_argument("--timeout", type=int, default=60, help="solver timeout, s")
    arg_parser.add_argument("--no-opt", action="store_true", help="skip SMT-level simplification")
    args = arg_parser.parse_args()

    ctx = make_context()
    with open(args.file) as f:
        module = Parser(ctx, f.read(), args.file).parse_module()

    result = check_module(
        ctx,
        module,
        name=args.function,
        opt=not args.no_opt,
        timeout=args.timeout,
        max_visits=args.unroll,
    )
    print(f"{args.file}: {_SELFCOMP_LINE[result.verdict]}")
    if result.bounded:
        print("  bounded: loops were unrolled, so this covers only the unrolled iterations")
    if result.reason:
        print(f"  reason: {result.reason}")
    for obligation in result.obligations:
        line = (
            f"  {obligation.kind:<9} {_SELFCOMP_LINE[obligation.verdict]:<8} "
            f"({obligation.n_observations} observation(s))"
        )
        print(line if obligation.n_observations else f"{line} - nothing of this kind happens")
        if obligation.reason:
            print(f"    reason: {obligation.reason}")
        if obligation.verdict == "insecure" and args.counterexample and obligation.counterexample:
            secrets = separating_secrets(obligation.counterexample)
            if secrets and not args.full_model:
                for name, value in secrets:
                    print(f"    | {name} = {value}")
            else:
                for text in obligation.counterexample.splitlines():
                    print(f"    | {text}")

    if result.verdict == "insecure":
        raise SystemExit(1)
    if result.verdict == "unknown":
        raise SystemExit(3)


def main_lowering() -> None:
    arg_parser = argparse.ArgumentParser(
        description="Verify a structural lowering specification (@source and @target "
        "functions over holes), for every program it can be instantiated with: it must "
        "preserve constant-time AND compute the same thing. Both halves are reported, "
        "and VERIFIED needs both."
    )
    arg_parser.add_argument("file", help="MLIR file containing @source and @target")
    arg_parser.add_argument(
        "--unroll",
        type=int,
        default=DEFAULT_MAX_VISITS,
        help="how many times a block may be re-entered on a path, i.e. the loop bound",
    )
    arg_parser.add_argument(
        "--counterexample",
        action="store_true",
        help="print the model z3 returns for a refuted half",
    )
    arg_parser.add_argument(
        "--ct-only",
        action="store_true",
        help="the leakage half alone, without the equivalence half (a partial answer)",
    )
    arg_parser.add_argument(
        "--print-smt", action="store_true", help="print the SMTLib query and exit"
    )
    arg_parser.add_argument(
        "--print-smt-equivalence",
        action="store_true",
        help="print the SMTLib query of the equivalence half and exit",
    )
    arg_parser.add_argument("--timeout", type=int, default=60, help="solver timeout, s")
    arg_parser.add_argument("--no-opt", action="store_true", help="skip SMT-level simplification")
    args = arg_parser.parse_args()

    ctx = make_context()
    with open(args.file) as f:
        module = Parser(ctx, f.read(), args.file).parse_module()

    if args.print_smt or args.print_smt_equivalence:
        from .structural import build_equivalence_query, build_query

        if args.print_smt_equivalence:
            script, _, _, _ = build_equivalence_query(
                ctx, module, opt=not args.no_opt, max_visits=args.unroll
            )
        else:
            script, _, _, _ = build_query(ctx, module, opt=not args.no_opt, max_visits=args.unroll)
        print(script)
        return

    if args.ct_only:
        result = check_lowering(
            ctx, module, opt=not args.no_opt, timeout=args.timeout, max_visits=args.unroll
        )
        _report(args.file, result, args.counterexample)
        print("  half-checked: --ct-only, so nothing was proved about what it computes")
        if result.verdict == "ct-breaking":
            raise SystemExit(1)
        if result.verdict == "unknown":
            raise SystemExit(3)
        return

    gate = check_template(
        ctx, module, opt=not args.no_opt, timeout=args.timeout, max_visits=args.unroll
    )
    _report_gate(args.file, gate, args.counterexample)
    if gate.verdict == "rejected":
        raise SystemExit(1)
    if gate.verdict == "unknown":
        raise SystemExit(3)


if __name__ == "__main__":
    main()


def main_coverage() -> None:
    arg_parser = argparse.ArgumentParser(
        description="How many of a compiler's operations can be verified today: with "
        "SMT semantics (form 0), by a proved macro-template (form 1), or not at all "
        "(form 2)."
    )
    arg_parser.add_argument(
        "compiler",
        nargs="*",
        help="which descriptors in compilers/ to report on; default is all of them",
    )
    arg_parser.add_argument(
        "--checkout", help="override the compiler checkout the descriptor names"
    )
    arg_parser.add_argument(
        "--no-prove",
        action="store_true",
        help="trust the descriptor's template claims instead of re-proving them",
    )
    arg_parser.add_argument(
        "--top", type=int, default=12, help="how many unproved operations to list"
    )
    arg_parser.add_argument("--timeout", type=int, default=120, help="solver timeout, s")
    args = arg_parser.parse_args()

    paths = sorted(COMPILERS.glob("*.json"))
    if args.compiler:
        wanted = set(args.compiler)
        paths = [p for p in paths if p.stem in wanted or Path(p).name in wanted]
        if not paths:
            print(f"no descriptor matches {args.compiler}", file=sys.stderr)
            raise SystemExit(2)

    for path in paths:
        compiler = Compiler.load(path, Path(args.checkout) if args.checkout else None)
        if not compiler.checkout.exists():
            print(f"{compiler.name}: no checkout at {compiler.checkout}, skipped")
            continue
        result = report(compiler, prove=not args.no_prove, timeout=args.timeout)
        total = sum(op.occurrences for op in result.operations)
        print(
            f"\n{result.compiler} @ {result.commit} "
            f"({result.files_scanned} test files, {len(result.operations)} distinct "
            f"operations, {total} mentions)"
        )
        for form, label in (
            (0, "form 0  SMT semantics    "),
            (1, "form 1  proved template  "),
            (2, "form 2  UNPROVED         "),
        ):
            ops = result.by_form(form)
            mentions = sum(op.occurrences for op in ops)
            share = 100 * mentions / total if total else 0.0
            print(f"  {label} {len(ops):>4} operations  {mentions:>6} mentions  {share:5.1f}%")
        if result.failed_templates:
            for failure in result.failed_templates:
                print(f"  template did not prove, so it covers nothing: {failure}")
        ready = [stage for stage in result.stages if stage.ready]
        print(
            f"  pipeline: {len(ready)}/{len(result.stages)} lowering steps have every "
            f"source operation translatable"
        )
        specified = [s for s in result.stages if s.proved or s.breaks]
        print(
            f"  specification: {len(specified)}/{len(result.stages)} steps have a checked template"
        )
        for stage in result.stages:
            mark = "ok     " if stage.ready else "blocked"
            spec = ""
            if stage.proved:
                spec = f"   proved CT-preserving: {', '.join(stage.proved)}"
            if stage.breaks:
                spec += f"   SHOWN CT-BREAKING: {', '.join(stage.breaks)}"
            print(
                f"    {mark} {stage.stage.pass_name:<44} "
                f"form0 {stage.forms[0]:>3}  form1 {stage.forms[1]:>3}  "
                f"form2 {stage.forms[2]:>3}   [{stage.stage.cited}]{spec}"
            )
        top = result.by_form(2)[: args.top]
        if top:
            print("  most-used unproved operations:")
            for op in top:
                print(f"    {op.occurrences:>6}  {op.name}")
