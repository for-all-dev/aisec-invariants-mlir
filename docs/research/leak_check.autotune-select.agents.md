# max-autotune GEMM kernel selection is value-independent (by construction)

Companion to `leak_check.results.siddarth.md`. That file is Siddarth's under the repo's
`*.<yourname>.md` ownership convention; this note records a follow-up that bears on its
"Probe 1 — max-autotune" result rather than editing it. Implied edits are listed at the
end for the author to make or reject.

Code: `leak_check/probe_autotune_select.py`, `leak_check/_autotune_select_worker.py`,
`leak_check/tests/test_autotune_select.py`. Raw evidence:
`leak_check/probe_autotune_select.out`.

## Config point (PRINCIPLES §2)

**torch 2.13.0+cu130 (CUDA wheel, run CPU-only — `torch.cuda.is_available()` is False),
Python 3.14.0, 24-core AMD Ryzen AI 9 HX 370, OMP/MKL pinned to 1 thread**, Inductor
`max_autotune + max_autotune_gemm + freezing`, `force_disable_caches=True`, private
`TORCHINDUCTOR_CACHE_DIR` per compile, GEMM shape `512×512 @ 512×512` fp32. This is not
Siddarth's machine and says nothing about torch 2.12 / 8-core.

## Summary

At this config point, Inductor's max-autotune does not specialize GEMM kernel selection to
the weight values. Across six baits that differ only in a tuner-relevant property of the
weight (dense, subnormal, 90% sparse, tiny-magnitude, large-magnitude, rank-4) the autotune
**decision is identical** — same candidate set, same winner (`cpp_CppMicroGemmFP32Vec` over
`_mkl_linear`) — and the normalized generated code is **byte-identical**. The same-class
control (three independent `dense` draws) is clean, so the identity is a real negative and
not a dead detector.

The result has a **source-level mechanism**, which is what makes it more than "not detected":
Inductor benchmarks autotune candidates on **random synthetic tensors**, never the real
(frozen) weight. So the tuner cannot specialize to values it never observes. This closes the
lead that `results.siddarth.md` calls "the max-autotune false positive from a normalizer bug"
— now with both a fixed detector and a reason.

## 1. The probe engages a real autotune decision (measured)

`probe_autotune.py` (Siddarth's Probe 1) compiled a `1×512 @ 512×512` gemv, which Inductor
resolves to a **single** foregone choice (`extern_kernels.mm`) — "Max autotune selects from
1 choices." There is no decision there to be value-dependent; the probe could only observe
codegen identity, which it correctly did.

To put a real choice in front of the tuner, this probe adds `freezing=True`, which turns the
weight into a prepacked constant. Inductor then registers a genuine **two-candidate** CPU
GEMM autotune and benchmarks them:

    AUTOTUNE packed_linear(512x512, 1459233x1, 512x512)
      cpp_CppMicroGemmFP32Vec_0  1.89 ms  100.0%
      _mkl_linear                2.30 ms   82.3%

The probe asserts engagement (≥2 candidates on every run) before reading any verdict, so an
empty capture cannot pass vacuously — the failure mode of the first draft of this probe (§3).

## 2. The decision does not move with the secret (measured)

    cd prototypes/leak_check && uv run python probe_autotune_select.py   # -> probe_autotune_select.out

Six baits, one weight property each, same shape+dtype, `seed=0`:

| bait | winner | candidate set | codegen vs dense |
|---|---|---|---|
| dense | cpp_CppMicroGemmFP32Vec | {cpp, mkl} | — |
| denormal (~1e-40, subnormal) | cpp_CppMicroGemmFP32Vec | {cpp, mkl} | identical |
| sparse (90% zeros) | cpp_CppMicroGemmFP32Vec | {cpp, mkl} | identical |
| small (~1e-4) | cpp_CppMicroGemmFP32Vec | {cpp, mkl} | identical |
| large (~1e4) | cpp_CppMicroGemmFP32Vec | {cpp, mkl} | identical |
| lowrank (rank 4) | cpp_CppMicroGemmFP32Vec | {cpp, mkl} | identical |

**Same-class control** (three independent `dense` draws, seeds 0/1/2): same winner, same
candidate set, byte-identical normalized codegen. This is the guard that catches a dead or
noisy detector; it is clean, so the cross-class identity is trustworthy.

The winner is the **decision** — which kernel Inductor emits. The benchmark *timings* are
not: the losing `_mkl_linear` reads anywhere from 55% to 92% across runs of the same class,
pure cross-process jitter (cf. the timing-on-w0 AUC in `results.siddarth.md`, "unreliable
channel"). The winner never flips within that jitter — `cpp` wins every one of the nine runs
here — because the margin is comfortable. A verdict built on the jittering percentage would
be noise; a verdict built on the emitted-kernel identity is stable.

## 3. Mechanism: the tuner benchmarks random data, not the weight (measured, source)

`torch/_inductor/select_algorithm.py` at this version:
`AlgorithmSelectorCache.get_inputs` builds benchmark inputs from
`benchmark_example_value` → `generate_example_value`, which calls **`rand_strided(...)`**
under `preserve_rng_state()` — a fresh random tensor of the right shape/stride/dtype. The
only way a real tensor reaches benchmarking is a per-argument `input_gen_fns` override, and
grepping the tree, only `kernel/mm_grouped.py` (offsets) and `kernel/custom_op.py`
(user-supplied) pass one; the plain mm / linear / CPP-GEMM lowerings pass **none**. So the
frozen weight's values are never presented to the tuner. Selection is value-independent *by
construction* — not merely "not detected."

This matches §2's timings directly: the subnormal bait, which would cripple any kernel that
actually multiplied its values (see below), benchmarks at the same ~1.9 ms as dense —
because the benchmark multiplies random normals, not the secret.

## 4. Denormal is a weak bait on this shape (measured — a caveat, not a result)

`probe_fastmath.out` records a 26.9× eager slowdown for subnormal weights, so subnormals
looked like a strong lever on kernel timing. But that measurement is a `1×4096` gemv with
**uniformly** ±denormal weights; the `512×512` GEMM this probe tunes takes a different
kernel path. Measured here (eager, seed 0, 30 reps):

| shape | dense | denormal (~1e-40) | ratio |
|---|---|---|---|
| 512×512 @ 512×512 (this probe) | 2.49 ms | 2.51 ms | **1.0×** |
| 1×4096 @ 4096×4096 (probe_fastmath) | 6.60 ms | 177.3 ms | 26.9× |

On the tuned shape the MKL/oneDNN sgemm path is not subnormal-sensitive on this hardware, so
even if the tuner *did* time the real weight, the denormal bait would not move it. The
argument for value-independence therefore rests on §3 (mechanism) and the sparse / magnitude
/ lowrank baits, not on denormal. Stated so the evidence is not overclaimed.

## 5. Two detector bugs found and fixed (measured — near-misses, PRINCIPLES §1)

The first run of this probe returned INCONCLUSIVE and the controls caught why. Both bugs were
in the *detector*, not the compiler:

1. **Decision parser exited the block early.** The `AUTOTUNE` header is followed by
   `strides:` / `dtypes:` lines *before* the candidate rows; the parser treated the first
   non-candidate line as end-of-block and read every winner as `None`. With all decisions
   `None`, "decisions identical across baits" was vacuously true — exactly the trap the
   engagement guard (§1) now closes. Fixed to scan to the `SingleProcess` terminator and to
   read the winner from the authoritative `best_kernel` stat.

2. **The codegen channel was dirty.** The capture multiplexes `output_code` with the
   `select_algorithm` log, whose benchmark timings, precompile durations, and object
   addresses are run-to-run noise. Isolating the `[__output_code]`-tagged lines removed most
   of it; a residue remained — the frozen-param placeholder comments print a bare `id()`
   pointer (12+ hex chars, no `0x`, which `probe_autotune.normalize`'s `0x`-rule misses).
   Stripped as an address (the frozen weight *values* are stored out-of-line and never
   appear in the C++). After the fix the same-class control is byte-identical (§2).

Both are recorded because, per the count-confound note's pattern, a confident-looking verdict
from a broken detector is the failure this project most needs to avoid. The same-class
control is what made both visible.

## 6. Claim labels (PRINCIPLES §1)

- **Measured:** autotune engages a 2-candidate GEMM decision under `freezing`; the decision
  (winner + candidate set) and normalized codegen are identical across all six baits and
  across three same-class draws; the same-class control is clean; eager 512×512 denormal
  ratio ≈ 1.0×.
- **Measured (source):** the tuner's benchmark inputs come from `rand_strided`, and the
  mm/linear/CPP-GEMM lowerings pass no `input_gen_fns`, so the real weight is never
  benchmarked — value-independence by construction.
- **Not established:** that autotune is value-independent at other config points (a machine
  where `cpp` and `mkl` are within jitter could see the winner flip *within a class* — that
  would be tuner noise, still not a secret-dependent selection, but it would need the
  stability guard to say so); that any Triton/GPU autotune, which benchmarks differently,
  behaves the same; that a shape whose fastest kernel is genuinely value-sensitive and whose
  candidates are timed on real data exists — the mechanism (§3) says it cannot here.

## 7. Open

1. **GPU / Triton autotune** is a separate surface (different benchmarking, different
   candidate pool) and is unmeasured.
2. **A shape where the two candidates are within timing jitter** would exercise the stability
   guard (winner flipping run-to-run within one class). Not found at 512×512 here; the margin
   is wide. If sought, the verdict would still be "no secret-dependent selection" — a flip
   inside a fixed class is noise — but the probe would need repeats to say it, and the note
   would have to lean entirely on §3.
3. **`input_gen_fns` for a custom op** (`kernel/custom_op.py`) *does* forward real data to
   the tuner. A user-registered custom GEMM that opts into value-based benchmarking is the
   one place this mechanism could leak; untested.

## 8. Implied edits to Siddarth's files (not made here)

- `results.siddarth.md` §"Probe 1 — max-autotune": the "NO compile-time leak" verdict holds
  and now has (a) a real multi-choice decision behind it, not only a single foregone
  `extern_kernels.mm`, and (b) a source mechanism (`rand_strided` benchmark inputs). Worth a
  one-line pointer to this note. The "Status of the compiler-introduced quadrant" tally can
  add `packed_linear` selection as a sixth probed config that did not fire.
