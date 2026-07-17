"""Command-line interface for ctverify.

    ctverify checkct BINARY --cfg a.cfg [--features ct|layerA|<list>] [--json]
    ctverify contract BINARY --cfg b.cfg --elem 4 --count 8 [--line 64] [--json]

``checkct`` runs binsec at the chosen channels (layer A). ``contract`` runs the
memory-access check, then computes the cache-line leakage-contract verdict from
the declared access layout (layer B).
"""

from __future__ import annotations

import argparse
import json
import sys

from .checkct import DEFAULT_CT, LAYER_A, BinsecNotFound, run_checkct
from .contract import AccessLayout, cacheline_verdict

_FEATURE_ALIASES = {"ct": DEFAULT_CT, "default": DEFAULT_CT, "layera": LAYER_A, "a": LAYER_A}


def _resolve_features(spec: str) -> tuple[str, ...]:
    key = spec.lower()
    if key in _FEATURE_ALIASES:
        return _FEATURE_ALIASES[key]
    return tuple(part.strip() for part in spec.split(",") if part.strip())


def _cmd_checkct(args) -> int:
    features = _resolve_features(args.features)
    res = run_checkct(args.binary, args.cfg, features=features, isa=args.isa, timeout=args.timeout)
    if args.json:
        print(json.dumps(res.to_dict(), indent=2))
    else:
        leaks = ", ".join(f"{leak.instruction}:{leak.kind}" for leak in res.leaks) or "-"
        print(f"{res.verdict:<9} features={'+'.join(features)} leaks={leaks}")
    return 1 if res.verdict == "insecure" else 0


def _cmd_contract(args) -> int:
    # The [ct] verdict comes from a byte-granularity memory-access run.
    ct = run_checkct(args.binary, args.cfg, features=DEFAULT_CT, isa=args.isa, timeout=args.timeout)
    layout = AccessLayout(elem_size=args.elem, index_count=args.count, aligned=not args.unaligned)
    res = cacheline_verdict(ct.verdict, layout, line_bytes=args.line)
    if args.json:
        out = res.to_dict()
        out["leaks"] = [leak.instruction for leak in ct.leaks]
        print(json.dumps(out, indent=2))
    else:
        leak = ct.leaks[0].instruction if ct.leaks else "-"
        print(
            f"[ct]={res.ct_verdict:<9} [cache-line]={res.contract_verdict:<9} "
            f"leak@{leak} {res.detail}"
        )
    return 1 if res.contract_verdict == "insecure" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ctverify", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("binary", help="path to the -m32 binary under test")
    common.add_argument("--cfg", required=True, help="binsec SSE script (secret/public globals)")
    common.add_argument("--isa", default="x86-32")
    common.add_argument("--timeout", type=int, default=240)
    common.add_argument("--json", action="store_true", help="emit a JSON verdict")

    p_check = sub.add_parser("checkct", parents=[common], help="constant-time / layer-A check")
    p_check.add_argument(
        "--features", default="layerA", help="ct | layerA | comma-separated binsec features"
    )
    p_check.set_defaults(func=_cmd_checkct)

    p_contract = sub.add_parser(
        "contract", parents=[common], help="cache-line leakage contract (layer B)"
    )
    p_contract.add_argument("--elem", type=int, required=True, help="element/stride size in bytes")
    p_contract.add_argument(
        "--count", type=int, required=True, help="number of secret-selected indices"
    )
    p_contract.add_argument("--line", type=int, default=64, help="cache-line size in bytes")
    p_contract.add_argument("--unaligned", action="store_true", help="base is not line-aligned")
    p_contract.set_defaults(func=_cmd_contract)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BinsecNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
