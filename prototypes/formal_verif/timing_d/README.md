# Layer D — the wall-clock net, as an information estimate

Layer D of the timing roadmap in [`../README.md`](../README.md). Layers A/B are
**formal**: a solver (binsec) proves, in a *model* of the machine, that no
secret-dependent branch / address / variable-latency op exists. That model is
blind to microarchitecture — a subnormal-float assist, a data-dependent
prefetch, cache eviction timing. Layer D is the measured safety net for exactly
that gap: run the real binary on the real CPU and ask **how many bits of the
secret the wall-clock time actually leaks.**

"Timing attacks via information estimates" — we quantify the channel with an
**information estimate**, the mutual information `I(secret; timing)` in bits, not
just a yes/no. `0` bits = timing is independent of the secret; `1` bit (for a
2-class test) = the timing fully determines which secret ran. Bits-per-query is
the physically meaningful number, and — because model weights are queried
*unbounded* times (see
[`../../../docs/research/formal_verif.threat-model.agents.md`](../../../docs/research/formal_verif.threat-model.agents.md))
— it is exactly what bounds how fast an attacker recovers the secret.

The estimator and the dudect-style driver live in the reusable
[`../infoleak/`](../infoleak/) package (`infoleak measure`); this directory is a
worked-example corpus (`cases.c`) whose `run.sh` compiles it into the driver and
drives that CLI — the same split as `timing_a/` ↔ `ctverify`.

## How the estimate is computed (and why it is honest)

For every measured call we record the secret class `S ∈ {0,1}` and the cycle
count `T`. Then:

1. **Interleaved measurement.** The driver draws each call's class from a PRNG,
   so thermal/frequency drift is uncorrelated with the label and cannot fake a
   signal (the `leak_check` "measure at matched contexts" lesson).
2. **Plug-in MI** `Î(S;T)` from a quantile-binned histogram of `T`.
3. **Permutation-null debias.** Plug-in MI is biased *upward* on finite samples
   (sparse histogram cells look informative). We shuffle the labels — which
   destroys any real dependence but keeps the sample sizes and the `T`
   distribution — recompute MI, and repeat. **The mean of that null IS the
   bias**; we subtract it. The fraction of shuffles beating the observed MI is a
   distribution-free p-value.
4. **Verdict = effect size AND significance.** We call a leak only when the
   debiased MI clears a floor *and* the permutation p is small — decide on a
   debiased effect, not a raw statistic (`leak_check.lessons.agents.md`).
5. **dudect / TVLA t-test** (Welch t on tail-cropped cycles) is reported
   alongside as an independent corroborating detector — the primitive the
   roadmap names for this layer.

## Run

```sh
bash run.sh            # gcc
N=40000 bash run.sh    # more samples => tighter estimate
```

Needs a C compiler and `uv`. **No binsec, no -m32** — D measures the native
binary on this silicon.

## Result (gcc `-O2 -march=native`, Intel Xeon 8168, N=15000–20000)

| kernel | raw cycles (class0 → class1) | MI (bits) | dudect t | verdict |
|---|---|---|---|---|
| `d_ct_baseline` | 680 → 680 (1.00×) | **0.000** / 1.00 | 0.2 | no leak (control ✓) |
| `d_branch_earlyexit` | 48 → 2194 (45.7×) | **0.998** / 1.00 | −14657 | **LEAK** |
| `d_denormal` | 6026 → 232456 (38.6×) | **0.997** / 1.00 | −3592 | **LEAK** |
| `d_idiv_secret` | 12672 → 12672 (1.00×) | **0.000** / 1.00 | −0.3 | no leak |

- **`d_ct_baseline` (negative control)** does identical integer work either way;
  the debiased MI is `0.000` bits (raw `0.001` − bias `0.001`) — the harness
  does not manufacture a leak. If this ever fires, the estimates are not
  trustworthy; calibrate before reading the rest.
- **`d_branch_earlyexit` (positive control)** is a memcmp-style early exit; time
  scales with the match length. `A`/binsec catch this too (control-flow) — it
  proves the harness detects a *known* leak.
- **`d_denormal` is the point of layer D.** It is a plain FP multiply-accumulate:
  no secret-dependent branch, address, or integer mul/div. binsec does not model
  FP latency — worse, it does **not even decode** SSE/x87 (it cuts the path as
  `uninterpreted` and returns **`unknown`, not `secure`**). So on FP code the
  formal layer is not "clean", it is **silent**. Yet subnormal secret operands
  take a ~39× microcode assist on this CPU, and the timing leaks ~1 bit/query.
  This is the ~25× denormal channel `leak_check` measured (Andrysco et al., IEEE
  S&P 2015), reproduced inside the formal pipeline as the case that **only D
  (and its FTZ static check) covers**.
- **`d_idiv_secret` is the reverse case: formal `secure`, silicon also clean.**
  Integer division by a secret divisor — no branch, no secret address — so
  binsec's *default* CT check decodes it and proves `secure` (and its layer-A
  `divisor` feature flags it `insecure`). But on this Skylake-SP the 32-bit
  `idiv` is constant-latency, so D measures `0.000` bits: the channel layer A
  warns about does **not** actually leak here. A concrete instance of layer A
  being *conservative* — the opposite of the denormal gap.

## Denormal formal fix — the FTZ static check

Because binsec is silent on FP, the formal answer for denormals is not a solver
proof (timing is unprovable) but a **config proof**: build under flush-to-zero
(FTZ) + denormals-are-zero (DAZ) so the FPU turns subnormals into 0 in hardware,
and verify that config **statically** with `infoleak ftz` (it scans the binary
for an `ldmxcsr` that sets the FTZ/DAZ bits). `run.sh` builds the driver twice
and shows the loop closes:

| build | `infoleak ftz` (static) | `d_denormal` measured (D) |
|---|---|---|
| normal (`-fno-fast-math`) | `none` — MXCSR default | **LEAK** ~0.99 bits |
| FTZ (`-DINFOLEAK_FTZ`) | `flushed` — FTZ+DAZ set | **no leak** 0.000 bits |

The static check *predicts* the channel is closed; D *confirms* it. This is the
formal denormal layer that A/B could not provide — it runs right after the binsec
step. Note FTZ changes numerics (small values become 0), so it is a deliberate
build decision, not a free win.

Layer **C** ([`../silicon_c/`](../silicon_c/)) takes these same measurements and
compares them to the A/B contract verdict: `d_denormal` (normal build) is where a
`secure`/`unknown` model meets a leaking chip — quantified in bits.

## Scope limits (honest)

- **Detection, never proof.** A null (`d_ct_baseline`) means "no channel above
  this harness's floor on this CPU at this N", **not** "provably constant-time".
  Only A/B give a proof, and only within their model.
- **Per-CPU, per-config.** The denormal assist magnitude, the cache geometry,
  DOIT/DIT and flush-to-zero (FTZ/DAZ) state are all properties of *this* build
  on *this* silicon. `-ffast-math` sets FTZ and would erase `d_denormal`'s
  channel — which is itself the finding: whether the channel exists is a
  deployment property, exactly layer C's question.
- **The estimate is a lower bound on leakage** at the chosen resolution: a real
  attacker with a better timer / more queries / a cache primitive may extract
  more than the histogram MI at N samples shows.

## References

- Reparaz, Balasch, Verbauwhede, *dudect: Dude, is my code constant time?* (DATE 2017) — the measured timing test.
- Andrysco et al., *On Subnormal Floating Point and Abnormal Timing* (IEEE S&P 2015) — the denormal channel.
- Standaert, *How (not) to Use Welch's T-test in Side-Channel Analysis* — effect size vs. p-value discipline.
