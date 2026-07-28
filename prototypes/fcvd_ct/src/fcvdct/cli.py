"""The two entry points.

`fcvd-ct-pdl` takes PDL rewrites, `fcvd-ct-lowering` takes structural lowering
specifications; both answer the same question -- does this transformation preserve
constant-time for every program it applies to?
"""

from __future__ import annotations

import argparse
import sys

from xdsl.dialects.builtin import ModuleOp
from xdsl.dialects.pdl import PatternOp
from xdsl.parser import Parser

from .context import make_context
from .pdl_ct import CTResult, check_pattern
from .structural import LoweringResult, check_lowering

_VERDICT_LINE = {
    "ct-preserving": "CT-PRESERVING",
    "ct-breaking": "CT-BREAKING",
    "unknown": "UNKNOWN",
}


def _report(name: str, result: CTResult | LoweringResult, show_counterexample: bool) -> None:
    print(
        f"{name}: {_VERDICT_LINE[result.verdict]} "
        f"(observations: source {result.n_source_observations}, "
        f"target {result.n_target_observations})"
    )
    if result.reason:
        print(f"  reason: {result.reason}")
    if result.verdict == "ct-breaking" and show_counterexample and result.counterexample:
        for line in result.counterexample.splitlines():
            print(f"  | {line}")


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


def main_lowering() -> None:
    arg_parser = argparse.ArgumentParser(
        description="Verify that a structural lowering specification (@source and "
        "@target functions over holes) preserves constant-time, for every program it "
        "can be instantiated with."
    )
    arg_parser.add_argument("file", help="MLIR file containing @source and @target")
    arg_parser.add_argument(
        "--counterexample",
        action="store_true",
        help="print the model z3 returns for a CT-breaking lowering",
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

    if args.print_smt:
        from .structural import build_query

        script, _, _ = build_query(ctx, module, opt=not args.no_opt)
        print(script)
        return

    result = check_lowering(ctx, module, opt=not args.no_opt, timeout=args.timeout)
    _report(args.file, result, args.counterexample)
    if result.verdict == "ct-breaking":
        raise SystemExit(1)
    if result.verdict == "unknown":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
