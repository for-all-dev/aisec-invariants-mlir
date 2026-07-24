"""Command-line interface for infoleak (layers C and D).

    infoleak measure DRIVER KERNEL [--n N --warmup W --seed S --bins B --perms R] [--json]
    infoleak silicon DRIVER KERNEL --contract-verdict secure|insecure
                     [--contract [ct]] [--allowed-bits X] [...] [--json]

``measure`` is layer D: run the kernel on this CPU and estimate the bits its
timing leaks (mutual information + dudect t-test). ``silicon`` is layer C: do the
same measurement, then compare the measured bits to what an A/B contract verdict
allows, flagging a silicon-leaks-beyond-the-model violation.
"""

from __future__ import annotations

import argparse
import json
import sys

from .contract_check import validate_against_silicon
from .estimate import estimate_leak
from .ftz import ObjdumpNotFound, run_ftz
from .measure import DriverNotFound, run_driver


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("driver", help="path to the compiled measurement driver")
    p.add_argument("kernel", help="kernel name in the driver's registry")
    p.add_argument("--n", type=int, default=20000, help="measured samples (default 20000)")
    p.add_argument("--warmup", type=int, default=2000, help="discarded warmup calls")
    p.add_argument("--seed", type=int, default=12345, help="PRNG seed (class sequence)")
    p.add_argument("--bins", type=int, default=None, help="timing histogram bins (default: auto)")
    p.add_argument("--perms", type=int, default=300, help="label permutations for the null")
    p.add_argument("--json", action="store_true", help="emit a JSON verdict")


def _measure_and_estimate(args):
    classes, cycles = run_driver(
        args.driver, args.kernel, n=args.n, warmup=args.warmup, seed=args.seed
    )
    return estimate_leak(
        classes,
        cycles,
        kernel=args.kernel,
        bins=args.bins,
        permutations=args.perms,
        seed=args.seed,
    )


def _cmd_measure(args) -> int:
    est = _measure_and_estimate(args)
    if args.json:
        print(json.dumps(est.to_dict(), indent=2))
    else:
        flag = "LEAK" if est.verdict == "leak" else "no leak"
        print(
            f"{est.kernel:<20} {flag:<8} MI={est.mi_bits:.3f}/{est.max_bits:.2f} bits "
            f"(p={est.mi_p_value:.2g}, dudect t={est.t_stat:.1f}) — {est.detail}"
        )
    return 1 if est.verdict == "leak" else 0


def _cmd_silicon(args) -> int:
    est = _measure_and_estimate(args)
    v = validate_against_silicon(
        est,
        contract=args.contract,
        contract_verdict=args.contract_verdict,
        allowed_bits=args.allowed_bits,
    )
    if args.json:
        out = v.to_dict()
        out["estimate"] = est.to_dict()
        print(json.dumps(out, indent=2))
    else:
        print(
            f"{v.kernel:<20} contract={v.contract}={v.contract_verdict:<8} "
            f"measured={v.measured_bits:.3f} bits  ->  {v.status.upper()}\n"
            f"    {v.detail}"
        )
    # non-zero exit when the silicon refutes a "secure" contract
    return 1 if v.status == "contract-violated" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="infoleak", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_m = sub.add_parser("measure", help="layer D: estimate bits leaked via timing")
    _add_common(p_m)
    p_m.set_defaults(func=_cmd_measure)

    p_s = sub.add_parser("silicon", help="layer C: validate a contract against silicon")
    _add_common(p_s)
    p_s.add_argument("--contract", default="[ct]", help="contract label being validated")
    p_s.add_argument(
        "--contract-verdict",
        required=True,
        choices=["secure", "insecure"],
        help="what A/B concluded for this kernel in the model",
    )
    p_s.add_argument(
        "--allowed-bits",
        type=float,
        default=None,
        help="bits the contract permits (default: 0 if secure, H(S) if insecure)",
    )
    p_s.set_defaults(func=_cmd_silicon)

    p_f = sub.add_parser(
        "ftz", help="static FTZ/DAZ check: is the denormal channel closed by config?"
    )
    p_f.add_argument("binary", help="path to the binary to disassemble")
    p_f.add_argument("--json", action="store_true", help="emit a JSON verdict")
    p_f.set_defaults(func=_cmd_ftz)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (DriverNotFound, ObjdumpNotFound, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _cmd_ftz(args) -> int:
    res = run_ftz(args.binary)
    if args.json:
        print(json.dumps(res.to_dict(), indent=2))
    else:
        print(f"{res.verdict:<8} FTZ={res.ftz} DAZ={res.daz} — {res.detail}")
    # exit 0 when denormals are provably flushed, 1 otherwise (channel may be open)
    return 0 if res.denormals_flushed else 1


if __name__ == "__main__":
    raise SystemExit(main())
