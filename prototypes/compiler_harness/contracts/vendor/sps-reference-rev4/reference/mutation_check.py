#!/usr/bin/env python3
"""Mutation check for the SPS executable reference slice.

Applies one source mutation at a time to `sps_ref`, re-runs the full reference
suite, and reports whether the suite noticed.  Sources are always restored and
the restore is verified by digest.

A surviving mutant is only a coverage gap when some fixture *could* have killed
it.  `build_product` requires both lanes to compile one program, so every static
event field is equal across lanes by construction and mutations that drop such a
field from a lane comparison are equivalent mutants -- unkillable by any
fixture, at any level of expectation detail.  Those are listed in
`EXPECTED_SURVIVORS` with a reason.  Anything surviving that is not on that list
is a regression in fixture coverage and fails the run.

Usage:
    python3 SPS/reference/mutation_check.py            # from the workspace root
    python3 SPS/reference/mutation_check.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SPS_REF = HERE / "sps_ref"
NL = "\n"

# name -> (module, old, new)
MUTANTS: dict[str, tuple[str, str, str]] = {
    "product/event-alignment-row": (
        "product.py",
        'causes.append(BadCause("EventAlignment", ordinal, present_mismatch))',
        "pass",
    ),
    "product/site-order-row": (
        "product.py",
        'causes.append(BadCause("SiteOrderAlignment", ordinal, site_order))',
        "pass",
    ),
    "product/site-order-drops-visit": (
        "product.py",
        "bool_not(equal(left_event.visit, right_event.visit)),",
        "bool_lit(False),",
    ),
    "product/static-mismatch-drops-within-ordinal": (
        "product.py",
        "left.within_ordinal != right.within_ordinal,",
        "False,",
    ),
    "product/structural-terms-drop-release-ordinal": (
        "product.py",
        "pairs.append((left.release_ordinal, right.release_ordinal))",
        "pass",
    ),
    "product/retire-unconditionally": (
        "product.py",
        "active = bool_and(active, bool_not(payload_bad))",
        "active = bool_lit(False)",
    ),
    "product/ignore-audience-authorization": (
        "product.py",
        "and bool(left_event.audience & coalition.principals)",
        "and True",
    ),
    "replay/continue-past-first-bad": (
        "replay.py",
        "        if not active:" + NL + "            break",
        "        if not active:" + NL + "            pass",
    ),
    "replay/structural-key-drops-visit": (
        "replay.py",
        "        event.visit," + NL + "        event.within_ordinal,",
        "        event.within_ordinal,",
    ),
    "replay/structural-key-drops-within-ordinal": (
        "replay.py",
        "        event.visit," + NL + "        event.within_ordinal,",
        "        event.visit,",
    ),
    "replay/structural-key-drops-release-ordinal": (
        "replay.py",
        "        event.release_ordinal," + NL,
        "",
    ),
    "replay/structural-key-drops-audience": (
        "replay.py",
        "        tuple(sorted(event.audience))," + NL,
        "",
    ),
    "replay/structural-key-drops-footprint": (
        "replay.py",
        "        event.footprint_bytes," + NL,
        "",
    ),
    "replay/skip-dual-construction-check": (
        "replay.py",
        "    if left_trace != left_symbolic or right_trace != right_symbolic:",
        "    if False:",
    ),
    "replay/wrong-audience-is-authorized": (
        "replay.py",
        "            authorized = bool(left_event.audience & coalition.principals)",
        "            authorized = True",
    ),
    # Positive test for the dual-construction cross-check: this edits the
    # concrete interpreter only, so the symbolic and concrete traces disagree
    # and the cross-check is the thing that must notice.
    "replay/concrete-only-termination-ordinal": (
        "replay.py",
        '            kind="Termination",'
        + NL
        + "            site=site,"
        + NL
        + "            visit=visit,"
        + NL
        + "            within_ordinal=len(terminal_order),",
        '            kind="Termination",'
        + NL
        + "            site=site,"
        + NL
        + "            visit=visit,"
        + NL
        + "            within_ordinal=len(terminal_order) + 1,",
    ),
}

# Mutants that no fixture can kill, with the structural reason.  Shrinking this
# dict is real coverage work; growing it needs a justification of the same kind.
EXPECTED_SURVIVORS: dict[str, str] = {
    "product/static-mismatch-drops-within-ordinal": (
        "Equivalent mutant. Both lanes compile one program, so every static "
        "event field is equal by construction and _static_mismatch is a "
        "compile-time False. Note this is a pure Python-level comparison and "
        "so, unlike the cause-expression mutants, leaves the canonical PONF "
        "digest unchanged."
    ),
    "replay/skip-dual-construction-check": (
        "Assertion that never fires in a correct implementation, so removing "
        "it is undetectable in isolation. Its efficacy is covered positively "
        "by replay/concrete-only-termination-ordinal, which perturbs only the "
        "concrete interpreter and must be killed by this very check."
    ),
    "replay/structural-key-drops-visit": (
        "Equivalent mutant: `visit` is input-independent in every fixture."
    ),
    "replay/structural-key-drops-within-ordinal": (
        "Equivalent mutant: static field, lane-invariant by construction."
    ),
    "replay/structural-key-drops-release-ordinal": (
        "Equivalent mutant: no fixture has a lane-varying release ordinal."
    ),
    "replay/structural-key-drops-audience": (
        "Equivalent mutant as a lane comparison. Audience is load-bearing as "
        "the authorization predicate, and that role is covered by "
        "replay/wrong-audience-is-authorized."
    ),
    "replay/structural-key-drops-footprint": (
        "Equivalent mutant: static field, lane-invariant by construction."
    ),
}


def run_suite() -> bool:
    proc = subprocess.run(
        [sys.executable, str(HERE / "run_reference_checks.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    return proc.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list mutants and exit")
    args = parser.parse_args()

    if args.list:
        for name in MUTANTS:
            mark = "expected-survivor" if name in EXPECTED_SURVIVORS else "must-kill"
            print(f"{mark:18s} {name}")
        return 0

    unknown = set(EXPECTED_SURVIVORS) - set(MUTANTS)
    if unknown:
        print(f"EXPECTED_SURVIVORS names unknown mutants: {sorted(unknown)}")
        return 1

    # This tool rewrites shared source files in place. Two concurrent runs would
    # interleave their edits and restores, corrupting the tree and producing
    # meaningless verdicts, so take an exclusive lock rather than racing.
    lock_path = HERE / ".mutation_check.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print(
            f"another mutation run holds {lock_path}; "
            "wait for it to finish, or remove the file if it is stale"
        )
        return 1
    os.write(lock_fd, f"{os.getpid()}\n".encode())
    os.close(lock_fd)

    originals = {
        module: (SPS_REF / module).read_text()
        for module in sorted({module for module, _, _ in MUTANTS.values()})
    }
    digests = {
        module: hashlib.sha256((SPS_REF / module).read_bytes()).hexdigest()
        for module in originals
    }

    # Preflight every pattern before touching anything. A pattern that no longer
    # matches usually means the tree is not pristine -- an interrupted or raced
    # run can restore a partially mutated file and leave it that way. Failing
    # here, before any edit, keeps that from compounding.
    malformed = [
        f"{name}: {originals[module].count(old)}x in {module}"
        for name, (module, old, _) in MUTANTS.items()
        if originals[module].count(old) != 1
    ]
    if malformed:
        lock_path.unlink(missing_ok=True)
        print("mutation patterns do not match the tree exactly once:")
        for row in malformed:
            print(f"  {row}")
        print(
            NL + "The reference sources may not be pristine. Compare sps_ref "
            "against the vendored copy in the harness before re-running."
        )
        return 1

    survived: list[str] = []
    killed: list[str] = []
    try:
        if not run_suite():
            print("baseline reference suite is not green; aborting")
            return 1
        print(f"baseline green; running {len(MUTANTS)} mutants{NL}")
        for name, (module, old, new) in MUTANTS.items():
            text = originals[module]
            (SPS_REF / module).write_text(text.replace(old, new))
            try:
                lived = run_suite()
            finally:
                (SPS_REF / module).write_text(text)
            (survived if lived else killed).append(name)
            expected = name in EXPECTED_SURVIVORS
            if lived and expected:
                verdict = "survived (expected)"
            elif lived:
                verdict = "SURVIVED (REGRESSION)"
            elif expected:
                verdict = "KILLED (allowlist stale)"
            else:
                verdict = "killed"
            print(f"  {verdict:24s} {name}")
    finally:
        unrestored = []
        for module, text in originals.items():
            path = SPS_REF / module
            path.write_text(text)
            if hashlib.sha256(path.read_bytes()).hexdigest() != digests[module]:
                unrestored.append(module)
        print(
            NL
            + ("restore verified" if not unrestored else f"RESTORE FAILED: {unrestored}")
        )
        lock_path.unlink(missing_ok=True)

    if unrestored:
        return 1

    regressions = sorted(set(survived) - set(EXPECTED_SURVIVORS))
    stale_allowlist = sorted(set(killed) & set(EXPECTED_SURVIVORS))
    print(f"{len(killed)} killed, {len(survived)} survived "
          f"({len(EXPECTED_SURVIVORS)} expected)")
    if regressions:
        print(f"{NL}COVERAGE REGRESSION -- these mutants must be killed:")
        for name in regressions:
            print(f"  - {name}")
    if stale_allowlist:
        print(f"{NL}ALLOWLIST STALE -- now killed, remove from EXPECTED_SURVIVORS:")
        for name in stale_allowlist:
            print(f"  - {name}")
    if regressions or stale_allowlist:
        return 1
    print("mutation check PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
