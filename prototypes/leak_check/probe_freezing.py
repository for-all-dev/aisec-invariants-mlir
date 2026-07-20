"""
Constant-folding under Inductor freezing: does the compiler bake a secret-derived
scalar into the generated code?

Structural lowerings (relu/exp/matmul) key codegen on shape/dtype, so the weight is
just runtime data -- nothing for the optimizer to specialize on, and the
"compiler-INTRODUCED leak" quadrant of this corpus has stayed empty. The lever is
CONSTANT-FOLDING. `torch._inductor.config.freezing = True` makes the weight a
compile-time constant, so a secret-derived scalar the forward computes
(quantization scale = w.abs().max()/127, or w.max(), w.sum(), 1/w.norm()) is
computable at compile time and may be FOLDED into a literal in the generated C++.

This is the 2x2 the corpus never had:

                       codegen(class A) vs codegen(class B)
    non-frozen compile : IDENTICAL   -> scalar computed at runtime -> OBLIVIOUS
    frozen     compile : DIFFERS     -> scalar folded to a literal -> LEAK

If the frozen codegen differs by class AND the diff contains the folded scalar,
that is the gun: recover and print the literal, and show it equals the expected
folded statistic (e.g. recovered scale ~= max|w|/127).

Detector = probe_softmax's Check A machinery: dump output_code, normalize with
probe_autotune.normalize (the POST-BUGFIX normalizer -- do not reimplement it),
diff. Controls (PRINCIPLES §5): force_disable_caches + a private cache dir per
compile (in the worker), and a SAME-CLASS control -- an independent draw with the
SAME folded statistic as class A must produce IDENTICAL frozen codegen, or the
detector is broken rather than the compiler.

    python probe_freezing.py            # all surfaces
    python probe_freezing.py quant_scale
"""

import difflib
import getpass
import os
import re
import subprocess
import sys

import numpy as np

import corpus_freezing as CF
from probe_autotune import normalize
from probe_softmax import kernel_body

HERE = os.path.dirname(os.path.abspath(__file__))
SEC = os.path.join(HERE, "secrets", "freeze")
# Repo root, redacted out of recorded evidence: absolute /home paths are PII
# (see leak_check.count-confound.agents.md).
_REPO = os.path.dirname(os.path.dirname(HERE))
_USER = getpass.getuser()
_FLOAT = re.compile(r"[-+]?\d+\.\d+(?:e[-+]?\d+)?")


def redact(text):
    return text.replace(_REPO, "<repo>").replace(f"torchinductor_{_USER}", "torchinductor_<user>")


def run(surface, secret_path, mode):
    env = dict(
        os.environ,
        TORCH_LOGS="output_code",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        PYTHONHASHSEED="0",
    )
    p = subprocess.run(
        [sys.executable, "_freezing_worker.py", surface, secret_path, mode],
        cwd=HERE,
        capture_output=True,
        text=True,
        env=env,
        timeout=1800,
    )
    result = None
    for line in p.stdout.splitlines():
        if line.startswith("RESULT"):
            result = line
    if result is None:
        raise RuntimeError(
            f"{surface}/{mode}/{os.path.basename(secret_path)}: no RESULT\n"
            f"STDERR tail:\n{redact(p.stderr[-2000:])}"
        )
    return result, normalize(p.stderr), p.stderr


def gen(surface):
    os.makedirs(SEC, exist_ok=True)
    (la, a), (lb, b), (lc, c) = CF.secret_classes(surface)
    paths = {}
    for lab, arr in ((la, a), (lb, b), (lc, c)):
        pth = os.path.join(SEC, f"{surface}_{lab}.npy")
        np.save(pth, arr)
        paths[lab] = (pth, arr)
    return (la, lb, lc), paths


def recover_literal(code, expected, tol=1e-3):
    """Return the float literal in the frozen kernel closest to `expected` within a
    relative tolerance (folded value is float32-rounded), else None."""
    body = kernel_body(code)
    best, best_err = None, tol
    for m in _FLOAT.finditer(body):
        val = float(m.group())
        if expected == 0:
            continue
        err = abs(val - expected) / abs(expected)
        if err <= best_err:
            best, best_err = val, err
    return best


def diff_lines(a, b, la, lb):
    return list(
        difflib.unified_diff(
            a.splitlines(), b.splitlines(), fromfile=la, tofile=lb, lineterm="", n=1
        )
    )


def probe(surface):
    (la, lb, lc), paths = gen(surface)
    pa, arr_a = paths[la]
    pb, arr_b = paths[lb]
    pc, arr_c = paths[lc]
    exp_a = CF.stat(surface, arr_a)
    exp_b = CF.stat(surface, arr_b)

    print("=" * 78)
    print(f"SURFACE: {surface}   classes: {la} vs {lb}  (same-class control: {lc})")
    print(f"  expected folded statistic:  {la}={exp_a:.9g}   {lb}={exp_b:.9g}")
    print("=" * 78)

    # Frozen arm (the leak column) + same-class control.
    res_fa, code_fa, _ = run(surface, pa, "frozen")
    res_fb, code_fb, _ = run(surface, pb, "frozen")
    res_fc, code_fc, _ = run(surface, pc, "frozen")
    # Non-frozen arm (the oblivious column).
    res_na, code_na, _ = run(surface, pa, "nonfrozen")
    res_nb, code_nb, _ = run(surface, pb, "nonfrozen")

    for r in (res_fa, res_fb, res_fc, res_na, res_nb):
        print(f"  {r}")
    print()

    frozen_differs = code_fa != code_fb
    control_ok = code_fa == code_fc
    nonfrozen_same = code_na == code_nb

    print("2x2  (codegen(A) vs codegen(B)):")
    print(f"  non-frozen : {'IDENTICAL -> oblivious' if nonfrozen_same else 'DIFFERS'}")
    print(f"  frozen     : {'DIFFERS -> leak' if frozen_differs else 'IDENTICAL'}")
    print(
        f"  same-class control (frozen {la} vs {lc}): {'IDENTICAL (ok)' if control_ok else 'DIFFERS (DETECTOR BROKEN)'}"
    )
    print()

    rec_a = rec_b = None
    if frozen_differs:
        d = diff_lines(code_fa, code_fb, la, lb)
        print(f"  frozen codegen DIFFERS -- {len(d)} diff lines:")
        for ln in d:
            print("    " + redact(ln))
        rec_a = recover_literal(code_fa, exp_a)
        rec_b = recover_literal(code_fb, exp_b)
        print()
        print("  recovered literal vs expected folded statistic:")
        for lab, rec, exp in ((la, rec_a, exp_a), (lb, rec_b, exp_b)):
            if rec is None:
                print(
                    f"    {lab}: NO literal within tol of {exp:.9g} (folded to a buffer, not inline?)"
                )
            else:
                print(
                    f"    {lab}: recovered={rec:.9g}  expected={exp:.9g}  match={abs(rec - exp) <= 1e-3 * abs(exp)}"
                )
        # persist the frozen dumps as cited evidence
        outp = os.path.join(SEC, "code")
        os.makedirs(outp, exist_ok=True)
        for lab, code in ((la, code_fa), (lb, code_fb)):
            with open(os.path.join(outp, f"{surface}_frozen_{lab}.txt"), "w") as f:
                f.write(redact(code))
    else:
        print("  frozen codegen IDENTICAL across classes: freezing folded nothing")
        print("  inline (or folded to a constant buffer not shown in output_code).")

    gun = (
        frozen_differs and control_ok and nonfrozen_same and rec_a is not None and rec_b is not None
    )
    print()
    verdict = (
        "COMPILER-INTRODUCED LEAK" if gun else ("inconclusive" if frozen_differs else "no fold")
    )
    print(f"  VERDICT[{surface}]: {verdict}")
    print()
    return {
        "surface": surface,
        "frozen_differs": frozen_differs,
        "control_ok": control_ok,
        "nonfrozen_same": nonfrozen_same,
        "recovered": (rec_a, rec_b),
        "expected": (exp_a, exp_b),
        "gun": gun,
    }


def main():
    surfaces = sys.argv[1:] or CF.names()
    print("Freezing constant-fold probe (Inductor) | detector: output_code diff, normalized\n")
    print(f"torch {__import__('torch').__version__}\n")
    rows = [probe(s) for s in surfaces]

    print("=" * 78)
    print("SUMMARY  (non-frozen A=B? / frozen A!=B? / control ok? / literal recovered? -> verdict)")
    print("=" * 78)
    for r in rows:
        rec = r["recovered"]
        recovered = rec[0] is not None and rec[1] is not None
        print(
            f"  {r['surface']:<12} "
            f"oblivious={'Y' if r['nonfrozen_same'] else 'n'}  "
            f"frozen-diff={'Y' if r['frozen_differs'] else 'n'}  "
            f"control={'Y' if r['control_ok'] else 'n'}  "
            f"literal={'Y' if recovered else 'n'}  "
            f"-> {'GUN' if r['gun'] else 'no'}"
        )


if __name__ == "__main__":
    main()
