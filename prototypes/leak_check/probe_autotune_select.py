"""Probe: is max-autotune's GEMM KERNEL SELECTION value-specialized?

Follow-up to probe_autotune.py, which found no compile-time leak but exercised a
1×512 gemv that autotune resolved to a single foregone choice (no real decision).
Here `freezing=True` bakes the weight in as a prepacked constant, which makes
Inductor register a genuine *multi-choice* CPU GEMM autotune: it BENCHMARKS
candidate kernels (cpp micro-gemm vs the mkl extern kernel) and picks the fastest.

Hypothesis (settled by the probe): if the tuner times candidates on the REAL
secret weight, then a weight whose VALUES change kernel timing (sparsity,
subnormals, magnitude, structure) could flip the winner -> the selected kernel,
and the generated code, would differ by secret class -> a compiler-introduced
channel.

The decisive channel is the autotune DECISION itself: the ordered candidate list
and which kernel won, parsed from the select_algorithm log. Corroborated by the
normalized generated code (reusing probe_autotune.normalize) and by timing.

Controls (this surface already produced one false positive — a normalizer bug):
  * SAME-CLASS control: independent draws (different seed) of the SAME bait must
    yield the SAME decision + codegen. If they differ, the detector is broken
    (tuner jitter / normalizer), not the compiler. Run BEFORE trusting any
    cross-class difference.
  * STABILITY: a cross-class difference counts only if it is stable and the
    same-class control is clean. A winner that flips run-to-run within one class
    is jitter, not secret dependence.
  * Private per-compile TORCHINDUCTOR_CACHE_DIR + force_disable_caches so class B
    never reuses class A's tuned kernel and sibling jobs never collide.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

from probe_autotune import normalize  # reuse the FIXED normalizer; do not reimplement

HERE = os.path.dirname(os.path.abspath(__file__))

# A candidate line in an AUTOTUNE block: "  <name> <t> ms <pct>%". The winner is
# the fastest (100.0%). Kernel names carry a run-local numeric suffix
# (cpp_CppMicroGemmFP32Vec_0); strip it so we compare kernel *families*, which is
# what "which kernel was selected" means. NB the header is followed by
# `strides:`/`dtypes:` lines BEFORE the candidates, so the parser must not treat
# a non-candidate line as the end of the block (that bug read every winner None).
_CAND = re.compile(r"^\s+(\S+)\s+([\d.]+)\s+ms\s+([\d.]+)%")
_BEST = re.compile(r'"best_kernel":\s*"([^"]+)"')
_SUFFIX = re.compile(r"_\d+$")


def parse_decision(stderr: str):
    """Return (winner_family, [(family, pct), ...]) from the AUTOTUNE block, or
    (None, []) if no multi-choice autotune ran. Winner is taken from the
    select_algorithm 'best_kernel' stat when present (authoritative), else the
    fastest candidate line."""
    cands = []
    in_block = False
    for line in stderr.splitlines():
        if line.startswith("AUTOTUNE "):
            in_block = True
            cands = []
            continue
        if in_block:
            if line.startswith("SingleProcess"):
                in_block = False
                continue
            m = _CAND.match(line)
            if m:
                cands.append((_SUFFIX.sub("", m.group(1)), float(m.group(3))))
    if not cands:
        return None, []
    mj = _BEST.search(stderr)
    winner = _SUFFIX.sub("", mj.group(1)) if mj else max(cands, key=lambda c: c[1])[0]
    return winner, cands


# The generated-code channel shares one capture with the decision channel, so the
# select_algorithm log (benchmark timings, precompile durations, object addresses)
# rides along and is pure run-to-run noise. Isolate codegen by keeping only lines
# carrying the [__output_code] artifact tag, then normalize. One residue remains:
# the frozen-param placeholder comments print a bare object id() (12+ hex chars,
# no 0x prefix, so probe_autotune.normalize's 0x-rule misses it) — an address, not
# secret content (frozen weight values are stored out-of-line, never in the C++).
_HEXADDR = re.compile(r"\b[0-9a-f]{12,}\b")


def normalize_codegen(stderr: str) -> str:
    code = [line for line in stderr.splitlines() if "[__output_code]" in line]
    return _HEXADDR.sub("ADDR", normalize("\n".join(code)))


def run(bait, seed):
    """One fresh compile in its own cache dir. Returns dict with the decision,
    normalized codegen, and the compiled-artifact timing median (us)."""
    with tempfile.TemporaryDirectory(prefix="at_sel_") as cache_dir:
        out_npy = os.path.join(cache_dir, "t.npy")
        env = dict(
            os.environ,
            TORCHINDUCTOR_CACHE_DIR=cache_dir,  # private per compile
            TORCH_LOGS="output_code,+torch._inductor.select_algorithm",
            OMP_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
        )
        p = subprocess.run(
            [sys.executable, "_autotune_select_worker.py", bait, str(seed), out_npy],
            cwd=HERE,
            capture_output=True,
            text=True,
            env=env,
            timeout=900,
        )
        median = None
        for line in p.stdout.splitlines():
            if line.startswith("RESULT"):
                median = float(line.split("median_us=")[1])
        if median is None:
            raise RuntimeError(f"{bait}/{seed}: no RESULT\nSTDERR tail:\n{p.stderr[-2000:]}")
        winner, cands = parse_decision(p.stderr)
        return {
            "bait": bait,
            "seed": seed,
            "winner": winner,
            "candidates": cands,
            "code": normalize_codegen(p.stderr),
            "median_us": median,
        }


def fingerprint(r):
    """The DECISION: winner + the set of candidate families. Timings are noisy
    and excluded; the selection is what leaks (or does not)."""
    return (r["winner"], tuple(sorted(f for f, _ in r["candidates"])))


def show(r):
    ranked = "  ".join(f"{f}={p:.1f}%" for f, p in r["candidates"])
    print(
        f"  {r['bait']:8s} seed={r['seed']}  winner={r['winner']}  [{ranked}]  t0={r['median_us']:.0f}us"
    )


def main():
    import torch

    print("Probe — value-specialized max-autotune GEMM kernel selection\n")
    print(f"config point: torch {torch.__version__}, cpu, freezing+max_autotune, DIM=512\n")

    # --- SAME-CLASS control: three independent 'dense' draws. -----------------
    # Must share one decision + codegen. This is the control that catches the old
    # false positive (normalizer / tuner jitter masquerading as a leak).
    print("SAME-CLASS control (independent 'dense' draws, seeds 0/1/2):")
    same = [run("dense", s) for s in (0, 1, 2)]
    for r in same:
        show(r)
    same_fps = {fingerprint(r) for r in same}
    same_code = len({r["code"] for r in same}) == 1
    same_clean = len(same_fps) == 1 and same_code
    print(f"  -> same decision across draws: {len(same_fps) == 1}; same codegen: {same_code}")
    print(f"  -> SAME-CLASS CONTROL {'CLEAN' if same_clean else 'DIRTY (detector broken)'}\n")

    # --- CROSS-CLASS: baits differing in one tuner-relevant property. ---------
    baits = ["dense", "denormal", "sparse", "small", "large", "lowrank"]
    print("CROSS-CLASS baits (same shape+dtype, one property each, seed 0):")
    cross = [same[0]] + [run(b, 0) for b in baits if b != "dense"]
    for r in cross:
        show(r)

    # Engagement guard: a real multi-choice autotune must have run, or "decisions
    # all identical" is vacuously true (all None). Show autotune engaged.
    engaged = all(len(r["candidates"]) >= 2 for r in (*same, *cross))
    n_choices = len(cross[0]["candidates"])
    print(
        f"\n  autotune engaged (>=2 candidates every run): {engaged}  (dense: {n_choices} choices)"
    )

    ref = cross[0]  # dense
    all_same_decision = all(fingerprint(r) == fingerprint(ref) for r in cross)
    all_same_code = all(r["code"] == ref["code"] for r in cross)
    print()
    print(f"  decision identical across all baits: {all_same_decision}")
    print(f"  normalized codegen identical vs dense: {all_same_code}")

    # --- Verdict --------------------------------------------------------------
    print()
    if not engaged:
        print(
            "=> INCONCLUSIVE: multi-choice autotune did not engage; nothing to decide/leak was measured."
        )
        verdict = "inconclusive"
    elif not same_clean:
        print(
            "=> INCONCLUSIVE: same-class control is dirty; any cross-class diff is untrustworthy."
        )
        verdict = "inconclusive"
    elif all_same_decision and all_same_code:
        print(
            "=> NO leak: kernel selection is VALUE-INDEPENDENT. Every bait selects the same\n"
            "   kernel with the same candidate set and byte-identical normalized codegen, and\n"
            "   independent same-class draws are indistinguishable. The old max-autotune\n"
            "   'compiler-introduced leak' does NOT reproduce with the fixed normalizer."
        )
        verdict = "value-independent"
    else:
        print(
            "=> POSSIBLE leak: a bait changed the autotune decision or codegen while the\n"
            "   same-class control stayed clean. Inspect secrets/at_sel_* for the diff."
        )
        verdict = "value-dependent"
        os.makedirs(os.path.join(HERE, "secrets"), exist_ok=True)
        for r in cross:
            with open(os.path.join(HERE, "secrets", f"at_sel_code_{r['bait']}.txt"), "w") as f:
                f.write(r["code"])

    # Machine-readable summary for the note / re-runs.
    print(
        "\nSUMMARY "
        + json.dumps(
            {
                "verdict": verdict,
                "autotune_engaged": engaged,
                "same_class_clean": same_clean,
                "decisions": {
                    r["bait"]: {"winner": r["winner"], "candidates": r["candidates"]} for r in cross
                },
            }
        )
    )


if __name__ == "__main__":
    main()
