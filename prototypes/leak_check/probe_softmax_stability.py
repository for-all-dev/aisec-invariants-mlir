"""
Check B of the softmax lead (see results.siddarth.md, "softmax: an UNVERIFIED lead").

The doc's required check: "re-run the compiled softmax pair to confirm the count
difference is deterministic (callgrind is deterministic, so a stable != 0 is real;
a varying one is a harness artifact)."

This runs that check with an added WITHIN-CLASS control, which is what actually
discriminates the two cases. Repeating only the ACROSS-class diff cannot tell a
real secret-dependent path from harness jitter, because both produce a nonzero
dIr. So measure both:

  within-class spread : run the SAME secret R times. Callgrind is deterministic,
                        so this MUST be 0. If it is not, the harness has a
                        nondeterministic component (allocator, dispatch, GC) and
                        dIr is noise -- the lead dies.
  across-class dIr    : Ir(large) - Ir(small), per repeat.

Verdict:
  within == 0 and dIr stable != 0  -> a real secret-dependent execution path
  within == 0 and dIr == 0         -> oblivious; the original -573 did not reproduce
  within  > 0                      -> harness artifact; dIr is not interpretable

Prediction registered from Check A (probe_softmax.py): the generated softmax kernel
has no secret-dependent branch, and both uniform classes make x-max == 0 exactly, so
identical data flows through exp/divide. Any dIr must therefore be extra-kernel, and
should show up as nonzero WITHIN-class spread.

NOTE (added later): this probe asks whether repeating a run AT ONE PATH is
deterministic, which is what probe_softmax_stability.out records. That is NOT the
question `noninterference.counts` answers -- it deliberately varies the context per
repeat, because a fixed path is bit-identical every time and its spread is 0 by
construction (see leak_check.count-confound.agents.md §2). The two measure different
things, so this keeps its own fixed-path loop rather than reusing NI.counts.

    python probe_softmax_stability.py                # softmax, 3 repeats
    python probe_softmax_stability.py exp 5          # any activation, 5 repeats
"""

import sys

import instruments as I
import run_activations as RA
from run_all import ensure_shim


def counts(act, secret, compile, repeats):
    """`repeats` runs of one secret at ONE fixed path — see the module note."""
    return [I.callgrind_count(act, secret, compile=compile) for _ in range(repeats)]


def report(label, rows):
    ir = [r["Ir"] for r in rows]
    bc = [r["Bc"] for r in rows]
    spread = max(ir) - min(ir)
    print(f"    {label:<7}: Ir={ir}  spread={spread:+,}")
    print(f"    {'':<7}  Bc={bc}")
    return ir, bc, spread


def main():
    act = sys.argv[1] if len(sys.argv) > 1 else "softmax"
    # A spread needs two points; below that, report() would compute max()/min()
    # of an empty list or a one-element one and print a spread of 0 that means
    # "not measured" while looking exactly like "measured, and stable".
    try:
        repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    except ValueError:
        sys.exit(f"repeats must be an integer >= 2, got {sys.argv[2]!r}")
    if repeats < 2:
        sys.exit(f"repeats must be >= 2 to have a spread at all, got {repeats}")

    ensure_shim()
    la, pa, lb, pb = RA.gen(act)

    print(f"Check B — callgrind determinism for `{act}` | repeats={repeats}")
    print(f"classes: {la} vs {lb}\n")

    for build, compile in (("eager", False), ("compiled", True)):
        print(f"  build={build}")
        rows_a = counts(act, pa, compile, repeats)
        rows_b = counts(act, pb, compile, repeats)
        ir_a, bc_a, sp_a = report(la, rows_a)
        ir_b, bc_b, sp_b = report(lb, rows_b)

        d_ir = [b - a for a, b in zip(ir_a, ir_b, strict=True)]
        d_bc = [b - a for a, b in zip(bc_a, bc_b, strict=True)]
        print(f"    dIr({lb}-{la}) per repeat = {d_ir}")
        print(f"    dBc({lb}-{la}) per repeat = {d_bc}")

        within_ok = sp_a == 0 and sp_b == 0
        if not within_ok:
            verdict = (
                "HARNESS ARTIFACT — within-class spread is nonzero, so "
                "callgrind is not deterministic here and dIr is not "
                "interpretable as a secret-dependent path"
            )
        elif all(d == 0 for d in d_ir) and all(d == 0 for d in d_bc):
            verdict = "OBLIVIOUS — identical counts across secrets, every repeat"
        elif len(set(d_ir)) == 1:
            verdict = (
                f"STABLE dIr={d_ir[0]:+,} with zero within-class spread — "
                "a REAL secret-dependent execution path"
            )
        else:
            verdict = (
                f"UNSTABLE dIr (varies {min(d_ir):+,}..{max(d_ir):+,}) despite "
                "zero within-class spread — investigate"
            )
        print(f"    => {verdict}\n")


if __name__ == "__main__":
    main()
