# The A/B/C/D pipeline: what is checked, and how

A navigator for the per-program pipeline in
[`prototypes/formal_verif/`](../../prototypes/formal_verif/): how it decides
whether a program `P` is timing-safe **before and after compilation**, and where
the line falls between what can be **proven** and what can only be
**measured/detected**. The full technical plan and paper references are in
[`prototypes/formal_verif/README.md`](../../prototypes/formal_verif/README.md).

---

## TL;DR (owner's note)

1. **What can be verified**
   - **A** — Binsec compares paired traces, separated only by a secret, and
     proves the absence of leaks via SMT solvers.
   - **B** — Same, but less strict — the attacker sees not bytes but cache-lines.
2. **What can be detected**
   - **C** — Fixes the contract and runs the binary on the CPU, measuring the
     leakage in bits.
   - **D** — Measures the same leakage, but over time.

---

## The core idea

The pipeline answers two different questions and does not conflate them:

1. **"Is there a secret dependence in the code?"** — layers **A/B** answer this
   *formally*: a symbolic engine (binsec) either **proves** the absence of a leak
   in its model of the machine, or emits a **counterexample** (input +
   instruction).
2. **"Does the real hardware actually leak — and how many bits?"** — layers
   **C/D** answer this *by measurement*: run the actual binary on the actual CPU
   and estimate the leakage in **bits**.

> The line: **A/B = proof in a model. C/D = detection on silicon.** The formal
> layer does not see microarchitecture (denormal assist, cache, speculation); the
> measuring layer gives no proof (a null means "not caught above this floor", not
> "proven clean"). Both are needed — they catch different things.

---

## Overview

| Layer | Tool | What it checks | Guarantee type | Needs binsec/`-m32`? |
|---|---|---|---|---|
| **A** | binsec `-checkct` + [`ctverify`](../../prototypes/formal_verif/ctverify/) | secret never reaches a branch / address / var-latency op (mul, div) | **PROOF** (in the instruction model) | yes |
| **B** | binsec + [`ctverify`](../../prototypes/formal_verif/ctverify/) | `program ⊨ contract` at cache-line granularity | **PROOF relative to a contract** | yes |
| **C** | [`infoleak`](../../prototypes/formal_verif/infoleak/) `silicon` | does the silicon leak **beyond** the contract? | **DETECTION** (in bits) | no |
| **D** | [`infoleak`](../../prototypes/formal_verif/infoleak/) `measure` | how many bits leak via wall-clock: `I(secret;timing)` | **DETECTION** (in bits) | no |

In every layer the engine and the corpus are separated: the reusable engine
(`ctverify` / `infoleak`) is standalone, while `timing_a/`, `contract_b/`,
`timing_d/`, `silicon_c/` are worked-example corpora that drive it.

### How A differs from B

Both A and B are the **same engine** (`binsec -checkct`, relational symbolic
execution + SMT/Z3) on the same `-m32` binary; both compare two traces that
differ only in the secret. The difference is on the observer axis:

- **A changes the SET of channels** (what counts as a leak): to `control-flow,
  memory-access` it adds variable-latency arithmetic — `multiplication,
  dividend, divisor`. A **stricter** observer.
- **B changes the GRANULARITY of the address channel**: it coarsens
  `memory-access` from a byte to a **cache-line (64 B)** and restates the verdict
  as `program ⊨ contract`. A **more realistic** observer (a real cache attacker
  sees the line, not the byte).

---

## Layer A — variable-latency constant-time (formal, software-only)

**What it checks.** Classic constant-time forbids the secret from steering a
*branch* or a memory *address*. Layer A adds a third digital channel:
**variable-latency arithmetic** — integer division (the latency of `idiv`
depends on the operand) and, on some microarchitectures, multiplication.

**How.** `binsec -checkct` is a relational symbolic engine: it takes two traces
that differ only in the secret bytes and **proves** that the observable
(control flow, addresses, and in layerA the mul/div operands too) is identical.
The channels are enabled by a flag:

```
-checkct-features control-flow,memory-access,multiplication,dividend,divisor
```

**What you get.** `secure` = a proof (for straight-line / bounded code);
`insecure` = a counterexample. The point of the corpus is the **delta**:
`a_div_*` and `a_mul_operand` pass as `secure` under default CT (no branch/
address) and only turn `insecure` once layerA's features are enabled.

**Run / details:** [`timing_a/`](../../prototypes/formal_verif/timing_a/) ·
`bash timing_a/run.sh`

**Trust anchor:** the proof holds given hardware **DOIT/DIT** (fixed-latency mode
for the remaining instructions). Without it, A is necessary but not sufficient.

---

## Layer B — leakage contract at cache-line granularity

**What it checks.** `binsec` (memory-access) decides the `[ct]` contract: does a
load address depend on the secret at *byte* granularity — deliberately
conservative. A real cache attacker sees only **which 64-byte line** is touched.
Layer B restates the verdict as `program ⊨ contract` for a chosen granularity.

**How.** For a secret-dependent access `base + i·elem` (with a line-aligned
`base`) the verdict is **computed**, not asserted:

```
distinct_lines = |{ (i·elem) // 64 : i ∈ [0, index_count) }|
distinct_lines == 1  ⟹  secure   under [cache-line]   (all secrets share a line)
distinct_lines  > 1  ⟹  insecure under [cache-line]   (secret moves the line)
```

**What you get.** A byte-level leak that never crosses a line boundary is
`secure` under `[cache-line]`. Example: `b_codebook_small` (32 B) is
`[ct]`-insecure but `[cache-line]`-secure; `b_codebook_wide` / `b_embedding_row`
cross lines → insecure under both.

**Run / details:** [`contract_b/`](../../prototypes/formal_verif/contract_b/) ·
`bash contract_b/run.sh`

**Limit.** B proves the *software* satisfies the contract. Whether the *hardware*
honours the contract is layer C.

---

## Layer C — validate the contract against real silicon

**What it checks.** The contract from A/B is an *assumption* about the hardware.
The CPU may leak **more** than the contract allows (a microcode assist, a
prefetch, speculation). C tests that assumption on the actual chip.

**How.** The Revizor / Scam-V role ("does the CPU leak beyond the contract?"),
expressed through an **information estimate**: measure the kernel on this CPU
(via layer D) and compare the measured bits to what the contract **allows**.

- A contract verdict of `secure` → **0 bits** allowed. Any measured `I(S;T)`
  above the floor **refutes** the contract on this CPU.
- A contract verdict of `insecure` → leakage is already predicted: the
  measurement either **confirms** it or shows it is **not exploitable** at this
  config point.

**The four outcomes:**

| contract (A/B) | silicon leaks? | status | meaning |
|---|---|---|---|
| secure | no | `consistent` | the model holds |
| secure | **yes** | `contract-violated` | **silicon leaks beyond the model** |
| insecure | yes | `confirmed` | leaks as A/B predicted |
| insecure | no | `not-exploitable-here` | the contract was conservative |

**Headline.** `d_denormal` is formally handled as `secure` by A/B (a plain FP
multiplier; binsec sees nothing), yet subnormal operands take a ~39× microcode
assist → ~1 bit/query → **`contract-violated`**. This is the `[ct]`-vs-silicon
gap that B explicitly puts out of its own scope — now measured and counted in
bits.

**Run / details:** [`silicon_c/`](../../prototypes/formal_verif/silicon_c/) ·
`bash silicon_c/run.sh`

---

## Layer D — the wall-clock net as an information estimate

**What it checks.** The final safety net for everything the formal layers miss:
how many bits of the secret leak through **execution time** on the real CPU.

**How.** "Timing attacks via information estimates" — we compute the **mutual
information** `I(secret; timing)` in **bits** (`0` = no channel; `1` bit for a
2-class test = time fully reveals which secret ran). Honesty discipline:

1. **Interleaved classes.** The driver draws each measurement's class from a
   PRNG, so thermal/frequency drift is uncorrelated with the label and cannot
   fake a signal.
2. **Plug-in MI** from a quantile-binned histogram of the timing.
3. **Permutation-null debias.** Plug-in MI is biased **upward** on finite
   samples. Shuffle the labels (destroys any real dependence, keeps the
   distribution) and recompute — **the mean of that null IS the bias**; subtract
   it. The fraction of shuffles beating the observed MI is a distribution-free
   p-value.
4. **Verdict = effect size AND significance** (not a raw statistic).
5. **dudect / TVLA t-test** — an independent corroborating detector alongside.

**What you get.** `d_denormal` ~0.99 bits, `d_branch_earlyexit` ~0.99 bits, the
controls `d_ct_baseline` and `d_idiv_secret` **0.000 bits** (the debias cancels
the bias). `d_denormal` is invisible to A/B but visible to D — the reason the
layer exists.

**Denormal formal fix (FTZ static check).** binsec does not merely fail to model
time — it does **not decode FP at all** (it cuts the path as `uninterpreted` →
`unknown`, not `secure`). So on FP code the formal layer is not "clean", it is
**silent**. You cannot prove timing, but you can prove the **configuration** that
kills the channel: building under flush-to-zero (FTZ) + denormals-are-zero (DAZ)
zeroes subnormals in hardware. `infoleak ftz` verifies that **statically** (it
scans for an `ldmxcsr` that sets the FTZ/DAZ bits) — slotting in right after
binsec. Verified on the Xeon 8168: a normal build → `ftz=none` and D measures
~0.99 bits; an FTZ build → `ftz=flushed` and D measures **0.000 bits**. The
static check predicts the channel is closed; D confirms it. (FTZ changes
numerics, so it is a deliberate build decision.)

**Run / details:** [`timing_d/`](../../prototypes/formal_verif/timing_d/) ·
`bash timing_d/run.sh`

**Limit.** Detection, not proof. A null means "no channel above this harness's
floor on this CPU at this N", not "proven constant-time". The estimate is a
**lower bound** on leakage at the chosen resolution.

---

## End-to-end verdict logic (before/after compilation)

Each property is run at `-O0` (before) and `-O2` (after):

- `PASS / PASS` → the compiler **preserved** security.
- `PASS / FAIL` → the compiler **INTRODUCED** the issue (binsec gives a
  counterexample).
- `FAIL / *`    → the **source** was already broken, not the compiler's fault.

The full 2×2 matrix (including "clang breaks `(m&a)|(~m&b)`") is in
[`quadrants/`](../../prototypes/formal_verif/quadrants/); functional equivalence
`-O0`↔`-O2` is in [`equiv/`](../../prototypes/formal_verif/equiv/).

---

## What the pipeline does NOT cover (honest blind spots)

One root cause: the formal layer (A/B) reasons about the **semantics of
instructions in a model of the machine**, not the **physics of their execution
on a specific chip**. Anything outside IR/binary semantics and/or that is a
property of the hardware+build cannot be proven — only measured.

| Class | Why invisible to A/B | Who catches it |
|---|---|---|
| **Denormal / subnormal FP** | binsec **does not decode FP at all** → `unknown`, not `secure`; subnormals take a ~39× microcode assist | **FTZ static check** (closes it formally) + D (confirms) |
| **Real var-latency magnitude** | A proves the *fact* "secret reached `idiv`" but not *how many cycles*; on this Skylake `idiv` is constant-latency, so A is **conservative** (flags what does not leak) | D measures (0 bits here) |
| **Cache timing / prefetcher** | B models the cache-line as a *contract*; whether this CPU honours that granularity is outside the model | C |
| **Speculation (Spectre-class)** | leakage on a speculative path outside architectural semantics | C (fully — Revizor) |
| **DVFS / frequency / thermal** | power physics, not semantics | D |
| **Power / EM** (CSI-NN) | not timing at all — an analog channel | nobody in ABCD (honest blind spot) |
| **Whole-compiler (∀ programs)** | that needs a proof assistant (Coq/Isabelle; Jasmin) — this is **per-program** validation | out of scope |

The flip side of honesty: the A/B proof is **also conditional** — it holds given
hardware DOIT/DIT (all remaining instructions run in fixed time). The moment that
fails on silicon, a formal `secure` stops transferring into a real guarantee, and
C/D close that gap. `d_denormal` is literally that: A/B say `secure`/`unknown`
while the chip leaks ~1 bit.

---

## Running it

All commands run from
[`prototypes/formal_verif/`](../../prototypes/formal_verif/) (each corpus's
`run.sh` `cd`s into its own directory):

```sh
# Everything at once (on a box with binsec + clang + torch):
bash run_all.sh

# Per layer:
bash timing_a/run.sh       # A  (needs binsec + -m32)
bash contract_b/run.sh     # B  (needs binsec + -m32)
bash timing_d/run.sh       # D  (needs only a C compiler + uv)
bash silicon_c/run.sh      # C  (needs only a C compiler + uv)

# Engine unit tests (no binsec / no CPU tuning):
( cd ctverify && uv run pytest )   # parser + contract math
( cd infoleak && uv run pytest )   # MI-estimator calibration + FTZ + layer-C logic
```

**Environment.** A/B: `binsec` (opam) + a `-m32` toolchain (`gcc-multilib`,
`libc6-dev-i386`), then `eval $(opam env)`. C/D: a plain C compiler + `uv` —
**neither binsec nor `-m32`** (C/D measure the native binary on real silicon).
