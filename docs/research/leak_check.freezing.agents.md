# Constant-folding under Inductor freezing bakes secret-derived weight
# statistics into the generated code

Companion to `leak_check.results.siddarth.md` and
`leak_check.count-confound.agents.md`. This is the first entry in the
**compiler-INTRODUCED leak** quadrant that this corpus's structural surfaces
(relu/exp/matmul) had left empty.

Code: `prototypes/leak_check/probe_freezing.py`, `corpus_freezing.py`,
`_freezing_worker.py`, `tests/test_freezing.py`.
Raw evidence: `prototypes/leak_check/probe_freezing.out`.

    cd prototypes/leak_check && uv run python probe_freezing.py    # -> probe_freezing.out

## Config point (PRINCIPLES §2)

**torch 2.13.0+cu130, Inductor CPU backend, Python 3.14, x86-64 (AVX-512, 16-wide
`at::vec::Vectorized<float>`), OMP/MKL pinned to 1 thread, `PYTHONHASHSEED=0`.**
`torch._inductor.config.freezing` toggled per compile; `force_disable_caches=True`
and a private `TORCHINDUCTOR_CACHE_DIR` per compile. Nothing here generalizes to
other torch versions, backends, or ISAs. The finding is specifically about the
`freezing` pass; it does not appear without that flag (§2).

## Summary

Structural lowerings key codegen on shape and dtype, so weights are runtime data
and the optimizer has nothing to specialize on. The lever that fills the empty
quadrant is **constant-folding**: `torch._inductor.config.freezing = True` promotes
the weight buffer to a compile-time constant, so any secret-derived scalar the
forward computes from it becomes computable at compile time. Inductor's constant
folding then **evaluates that scalar and emits it as a numeric literal in the
generated C++**. The secret is no longer only a runtime value flowing through a
fixed kernel; a statistic of it is now part of the generated *code*.

The clean 2x2, measured on four folding surfaces (`probe_freezing.out`):

| surface | folded scalar | non-frozen codegen A vs B | frozen codegen A vs B | recovered literal |
|---|---|---|---|---|
| `quant_scale` | `w.abs().max()/127` | identical (oblivious) | **differs** | `0.007874015718698502` vs `0.787401556968689` |
| `wmax` | `w.max()` | identical (oblivious) | **differs** | `3.0` vs `100.0` |
| `wnorm` | `1/w.norm()` | identical (oblivious) | **differs** | `0.5` vs `0.010000000707805157` |
| `wsum` | `w.sum()` | identical (oblivious) | **differs** | `7.000056…` vs `99.99998…` (control not clean, §3) |

For `quant_scale`, `wmax`, and `wnorm` all three guards hold and the recovered
literal equals the expected folded statistic to float32 precision: these are
**compiler-introduced confidentiality findings** at this config point. `wsum` is
reported inconclusive because its same-class control did not hold (§3) — the
control catching a bait defect, which is what it is for.

## 1. The gun: a secret-derived literal in the frozen kernel (measured)

The primary surface is quantization. `scale = w.abs().max() / 127` is the standard
symmetric-quantization scale — a scalar derived entirely from the secret weights.
The bait is the task's: class A weights with `max|w| = 1.0`, class B with
`max|w| = 100.0`, same shape, same dtype, same underlying random field, differing
only in the statistic the compiler folds (`corpus_freezing._draw`). The model is
data-oblivious in eager: `w.abs().max()/127` is the same instruction sequence for
both classes on different values.

Under freezing the two classes generate **different** C++. The only difference is
one line inside the vectorized kernel (`probe_freezing.out`):

```
-                    auto tmp1 = static_cast<float>(0.007874015718698502);
+                    auto tmp1 = static_cast<float>(0.787401556968689);
```

`0.007874015718698502 = 1.0/127` and `0.787401556968689 = 100.0/127` (float32
rounded). The probe recovers each literal from the frozen kernel body and checks it
against `max|w|/127` computed independently in numpy: both match to within
`rel 1e-3`. An attacker who can read the generated object code (or the intermediate
`output_code`) recovers `max|w|` for the compiled class exactly, without running
the kernel or timing anything.

`wmax` (`x * w.max()`) and `wnorm` (`x * (1/w.norm())`) behave identically: the
frozen kernel carries `static_cast<float>(3.0)` vs `100.0`, and `0.5` vs `0.01`,
each matching the expected statistic.

## 2. The 2x2 isolates freezing as the cause (measured)

The oblivious column is a **non-frozen compile of the same source** — the same
Inductor, the same kernel shape, only `freezing` flipped off. There the weight
stays a runtime input, so the scalar is computed by the kernel at run time and the
generated code is byte-identical across the two classes (normalized). Flipping only
the `freezing` flag turns identical codegen into class-dependent codegen. So the
distinguishability is introduced by the freezing pass, not authored in the source
and not a property of Inductor in general:

```
                       codegen(class A) vs codegen(class B)
    non-frozen compile : IDENTICAL   -> scalar computed at runtime -> oblivious
    frozen     compile : DIFFERS     -> scalar folded to a literal -> leak
```

This is the shape the corpus has wanted and never had: provably oblivious without
the compiler (eager and non-frozen both run the same instructions for both
classes), yet the compiler manufactures a secret-dependent artifact once it is
allowed to treat the weight as a constant.

## 3. Controls (PRINCIPLES §5)

**Cache disabled per compile.** `force_disable_caches=True` and a private
`TORCHINDUCTOR_CACHE_DIR` per worker (`_freezing_worker.py`). Without this, class B
reuses class A's cached `.so` and every diff is vacuously identical — a
false-negative generator. This is the control the project was burned by twice.

**Same-class control.** For each surface a third, independent draw with the *same*
folded statistic as class A is compiled frozen; its normalized codegen must equal
class A's, or the detector/normalizer is broken rather than the compiler. It holds
for `quant_scale`, `wmax`, `wnorm` — the same detector that reports A≠B reports
A=A′, so the A≠B difference is the folded value and not normalizer noise.

For `wsum` the control **fails**, and correctly: the folded scalar is a global sum,
and two independent draws constructed to the same *target* sum do not fold to the
same float32 literal — floating-point summation over a different random field lands
on `7.000056…` for one draw and `6.99997…` for the other. The statistic is not held
fixed across draws at float precision, so a same-class pair is not identical and the
surface is not a clean gun. The detector is not implicated: it passes the identical
control on the other three surfaces. `wsum` is therefore reported **inconclusive**,
not a finding (`probe_freezing.out`, `VERDICT[wsum]: inconclusive`). The lesson is
the softmax lesson again — the bait must hold the folded statistic fixed to the
precision the compiler folds at, and a global reduction over an independent draw
does not.

**Normalizer.** Reuses `probe_autotune.normalize` (the post-bugfix normalizer that
strips the `TORCH_LOGS` timestamp/PID prefix; the earlier missing strip manufactured
the max-autotune false positive) and `probe_softmax.kernel_body`. Not reimplemented.

## 4. What is folded, and what is not

The folded value here is a **scalar** — one number that Inductor's constant folding
computes and inlines as a `static_cast<float>` literal. This is why the surfaces
that fire all reduce the weight to a scalar the input is then scaled by.

Freezing folding a *tensor*-valued constant (e.g. BatchNorm affine parameters into a
preceding conv weight, or a whole quantized weight matrix) is a different case: the
result is a constant **buffer**, materialized once and referenced by the kernel, not
a sequence of inline literals in `output_code`. That still moves secret-derived data
into the frozen artifact, but the codegen-diff detector as built here keys on inline
literals and would report such a case as "codegen identical" (the buffer contents
live outside the dumped code). The scalar surfaces are the ones where the secret
becomes literally visible in the generated source. Buffer-valued folding is a
**hypothesized** adjacent leak, not measured here.

## 5. Claim labels (PRINCIPLES §1)

- **Measured:** at this config point, freezing folds `w.abs().max()/127`, `w.max()`,
  and `1/w.norm()` into `static_cast<float>` literals in the generated CPU kernel
  that differ by secret class; the recovered literal equals the independently
  computed statistic to float32 precision; the non-frozen compile of the same source
  produces byte-identical (normalized) codegen across classes; the same-class
  control holds for these three surfaces and fails for `wsum`.
- **Measured (negative-ish):** `wsum`'s same-class control fails, so it is
  inconclusive, not a finding — a global-sum bait does not hold the folded statistic
  fixed across independent draws at float32 precision.
- **Hypothesized:** that tensor-valued folding (BatchNorm-into-conv, folded quantized
  weight matrices) moves secret data into a frozen constant *buffer*; this probe's
  inline-literal detector would not see it. Untested here.
- **Not established:** that this reproduces on any other torch version, backend
  (Triton/GPU), or ISA; that eager or non-frozen execution is oblivious in any sense
  beyond "identical generated instructions for these classes" (no taint channel was
  run — codegen-diff is the channel here, and it is enough for the frozen-vs-nonfrozen
  contrast). The eager-obliviousness cross-check via `noninterference.analyze` is left
  as the bonus it was scoped to be.

## 6. One sentence for a security reviewer

With `torch._inductor.config.freezing = True`, Inductor constant-folds any
secret-derived scalar a model computes from its weights (quantization scale,
`w.max()`, `1/w.norm()`) and emits it as a numeric literal in the generated CPU
kernel, so at this config point (torch 2.13.0+cu130) the compiled artifact discloses
that statistic of the weights exactly — a leak that is absent from the identical
source compiled without freezing.
