# Formal verification of compiler-preserved security (per-program)

## Goal

Take a compiler + a program P, and decide **per program** whether P is secure
*before* compilation and *after* compilation. "Secure" = two properties:

1. **Functional equivalence** — the compiler did not change P's meaning
   (`-O0` binary computes the same function as `-O2` binary / source).
2. **Semantic non-interference** — P's public outputs do not depend on the
   secret beyond an explicit declassification policy.

Plus the side-channel channels (timing), covered by the layered A/B/C/D plan below.

This is **Task A** in the project's sense: per-instance validation via solvers.
It is NOT whole-compiler verification (∀ programs) — that requires a proof
assistant (Coq/Isabelle; cf. Jasmin, Sison–Murray) and is explicitly out of scope.

## Hard scope limits (load-bearing, not hedging)

- **No "100% for any code."** Symbolic execution is bounded (loops, path
  explosion, undecidability). Real guarantee: **proof for bounded / crypto-kernel
  scale**, bounded-depth verification otherwise. This is a property of the math,
  not of the tools.
- **Wall-clock time is not directly provable by any solver.** Variable-latency
  instructions (div/sqrt, denormals) and real cache are outside IR/binary
  semantics. Timing is handled only via its digital surrogate (constant-time) plus
  the B/C/D layers below.

## Tool map (two property tracks × before/after)

| Property | Tool | Level | Before | After |
|---|---|---|---|---|
| Functional equivalence | Alive2; bounded binary equivalence (SE + Z3) | IR / binary | `-O0` | `-O2` |
| Semantic non-interference (+ constant-time) | **Binsec/Rel** (+ Z3/bitwuzla) | **binary** | `-O0` bin | `-O2` bin |

Binsec/Rel works on **binaries**, so "before" and "after" are both binaries
(`-O0` vs `-O2`) — uniform, and strictly *after backend* (unlike ct-verif, which
stops at LLVM IR and misses backend-introduced leaks, e.g. `select`→branch).

## Layered timing plan A/B/C/D (no single tool does all four — verified)

Compose ourselves; reuse existing tools per layer. The software layers A and B
are implemented as a reusable package, [`ctverify/`](ctverify/) (API + CLI over
binsec, JSON verdicts); [`timing_a/`](timing_a/) and [`contract_b/`](contract_b/)
are worked-example corpora that drive it.

- **A — cheapest, formal (software only).** Forbid secret from reaching
  variable-latency instructions (taint/leakage property). Backed by hardware
  DOIT/DIT modes. Verifiable with the same relational engine.
- **B — strict, formal relative to a model.** Leakage contracts: verify software
  against a contract; verify hardware against the same contract (LeaVe for
  open-source RTL). Trust gap = contract vs silicon.
- **C — validate the model against real silicon.** Revizor / Scam-V: relational
  testing that the CPU does not leak beyond the contract. Implemented as an
  information estimate in [`silicon_c/`](silicon_c/) (over [`infoleak/`](infoleak/)):
  measure the kernel on this CPU and compare the measured bits to what the A/B
  contract allows — a `secure` contract that the silicon leaks past is a
  quantified **contract violation**.
- **D — final wall-clock net.** dudect / ct-fuzz: statistical timing measurement.
  Detection, never proof. Implemented in [`timing_d/`](timing_d/) as an
  **information estimate** — mutual information `I(secret; timing)` in bits,
  debiased against a permutation null, plus the dudect/TVLA t-test.

Verdict logic (per program, per property): run at `-O0` and `-O2`.
`PASS/PASS` → compiler preserved it. `PASS/FAIL` → compiler INTRODUCED the issue
(Z3 gives counterexample: input + instruction). `FAIL/*` → source already broken.

## Quadrant results (2×2 differential, `quadrants/`)

Complete matrix achieved. Same source, `-O0` (before) vs `-O2` (after), one
compiler = the compiler-preservation test. Run: `CC=gcc|clang bash quadrants/run.sh`.

| case | gcc O0→O2 | clang O0→O2 |
|---|---|---|
| `q_oblivious` `(m&a)\|(~m&b)` | нет/нет | **нет/ДОБАВИЛ** |
| `q_removed`  `if(s)…` | есть/убрал | есть/оставил |
| `q_kept_mem` `tbl[s&0xF]` | есть/оставил (mem) | есть/оставил |
| `q_kept_cf`  data-dep loop | есть/оставил (cf) | есть/оставил |
| `q_intro2` multiply-select | нет/нет | **нет/ДОБАВИЛ** |
| `q_intro4` ternary mask | есть/убрал | **нет/ДОБАВИЛ** |

Findings:
- **All four quadrants demonstrated.** The hard "compiler-introduced" quadrant
  fires with **clang -O1..-O3**, not gcc (gcc is well-behaved on these).
- **Headline:** the textbook constant-time idiom `(m&a)|(~m&b)` (`q_oblivious`)
  is itself broken by clang -O2. Matches published reports (Reparaz; Trail of
  Bits `__builtin_ct_select`; LLVM constant-time RFC).
- **The introduced leak is memory-access, not a branch.** clang lowers the mask
  select to `cmove` of two stack *addresses* + `mov (%ecx)` — the load *address*
  depends on the secret (cache channel). No `jcc`, so branch-counting sees
  nothing; only the relational memory-access check catches it.
  **This is the concrete case for why formal > eyeballing the disassembly.**

## Status / next steps

1. [x] Install Binsec (opam) + Z3. `binsec -checkct` (relational engine `relse`)
   is in mainline — no separate Binsec/Rel artifact needed. See `setup_binsec.sh`.
   NOTE: `relse`/checkct decodes **x86-32 only** — build targets with `-m32`.
   Secrets are declared over globals; binary must be `-static` so `<exit>`
   (the `halt at`) resolves to a concrete address.
3. [x] Secret/public annotation wired via SSE script (`calibration/checkct.cfg`:
   `secret global` / `public global`).
2. [x] **Calibration PASSED** — controls behave correctly, verdicts trustworthy:
   | binary | verdict | note |
   |---|---|---|
   | `select_leaky` `-O0` | **insecure** | secret-dependent branch at 0x80498d5 (neg. control fires ✓) |
   | `select_leaky` `-O2` | secure | gcc lowered the `if` to `cmovne` → **compiler REMOVED the leak** |
   | `select_ct` `-O0` | secure | branchless mask (pos. control ✓) |
   | `select_ct` `-O2` | secure | stayed branchless (`cmove`) |
   First live differential result: the `-O2` row is the "compiler removed an
   authored leak" quadrant — proves the before/after diff works end to end.
4. [x] Differential harness + full 2×2 matrix — see Quadrant results above.
5. [x] **Functional-equivalence track** (`equiv/`) — done via binsec SSE.
   Build `fut@-O0` and `fut@-O2` into one binary (renamed symbols), `main` runs
   both on symbolic inputs and jumps to `DIFF` if they differ; `reach <DIFF>`
   unreachable ⟹ EQUIVALENT (a *proof* for straight-line code). Calibrated:
   positive → EQUIVALENT, negative (`a+b+c`) → NOT EQUIVALENT + counterexample.
   **Orthogonality result:** clang `-O0` vs `-O2` of `(m&b)|(~m&c)` is
   **EQUIVALENT** (meaning preserved) yet **CT-insecure** (introduced leak).
   Functional correctness ⊥ side-channel security — both now checked, separately.
   Alive2 = IR-level alternative if middle-end-only validation is ever wanted.
6. [ ] Extend corpus to real crypto kernels (memcmp, AES S-box lookup, mpz).

## Roadmap: A + B + C + D (full side-channel coverage)

No single tool does all four (verified) — we compose. What we have (CT core via
`binsec -checkct` + functional equivalence via SSE) is the **software foundation**
that layers A/B build on. Concrete next steps per layer:

### A — cheapest, formal, software-only (extend what works)
Forbid the secret from reaching variable-latency instructions; rely on hardware
DOIT/DIT for fixed latency of the rest. **Implemented: [`timing_a/`](timing_a/).**
- [x] Enable `-checkct-features` for **division/multiplication** operands
  (var-latency) — binsec already exposes these check points. Corpus + runner in
  `timing_a/`; the mul/div-secret kernels are `secure` under default CT and
  `insecure` only with the layer-A features (the coverage delta).
- [ ] Add a denormal/subnormal-operand check (or forbid FP-on-secret) — the
  ~25× channel binsec's model does not see. (Not formal here — a **layer D**
  concern; documented as A's scope limit.)
- [x] Document the DOIT/DIT assumption as the trust anchor for layer A — see
  `timing_a/README.md`.

### B — strict, formal relative to a leakage contract
**Software half implemented: [`contract_b/`](contract_b/).**
- [x] Pick a leakage contract (`[ct]`, then cache-line granularity).
- [x] Software side: re-express our checkct runs as "program ⊨ contract"
  (observation set = contract, not hard-wired). `contract.py` computes the
  `[cache-line]` verdict from binsec's byte-level leak + the access layout; a
  one-line table (`b_codebook_small`) is `insecure` under `[ct]` but `secure`
  under `[cache-line]`, a wide table / embedding-row gather leaks under both.
- [ ] Hardware side: **LeaVe** on an open-source RTL core (verify RTL ⊨ contract).
  Trust gap = contract vs silicon. (Out of scope — separate RTL tool.)

### C — validate the model against real silicon
**Implemented: [`silicon_c/`](silicon_c/)** (engine: [`infoleak/`](infoleak/)).
- [x] Validate the contract on the actual chip *through an information estimate*
  (the Revizor / Scam-V role: does the CPU leak beyond the contract?). Measure
  the kernel on this silicon and compare measured `I(secret;timing)` to the
  contract's allowance: a `secure` contract allows 0 bits, so any measured
  channel **refutes** it. Headline result on the Xeon 8168: `d_denormal` is
  `secure` under A/B (binsec sees no leak) yet leaks **~0.99 bits/query** →
  `contract-violated`. Controls: `d_ct_baseline` → `consistent`,
  `d_branch_earlyexit` → `confirmed`. **No binsec / no -m32** (C tests silicon).
- [ ] Full **Revizor** speculation-contract fuzzing (test-case *generation*) for
  black-box CPUs — the heavier version; `silicon_c/` covers the fixed-corpus,
  contract-vs-measurement half.

### D — final wall-clock net (detection, not proof)
**Implemented: [`timing_d/`](timing_d/)** (engine: [`infoleak/`](infoleak/)).
- [x] **dudect**-style measurement on the native binary, reported as an
  **information estimate** — `I(secret;timing)` in bits, debiased against a
  label-permutation null, plus the dudect/TVLA t-test. Catches the analog leaks
  invisible to A/B: `d_denormal` (subnormal-float assist, ~39× on this CPU,
  ~0.99 bits) while the `d_ct_baseline` control stays at 0.000 bits. This is the
  ~25× denormal channel `leak_check/` measured, now inside the formal pipeline.
- [ ] **ct-fuzz** (input generation to *maximise* the timing gap) as a stronger
  driver than the fixed two-class corpus.

Composition target: A (formal, software) + B (formal vs contract) + hardware
DOIT/DIT, with C validating the contract and D as the measured safety net —
today's practical maximum for wall-clock, since no solver proves physical time.
**A/B are formal proofs inside a machine model; C/D are measured, per-CPU
detection** that quantifies, in bits, what escapes that model — together the
full A+B+C+D coverage the roadmap set out.

## Documented references for compiler-introduced CT leaks
- Oscar Reparaz, "Compilers and constant-time code" — https://www.reparaz.net/oscar/misc/cmov
- Trail of Bits (2025), constant-time support for LLVM / `__builtin_ct_select` —
  https://blog.trailofbits.com/2025/12/02/introducing-constant-time-support-for-llvm-to-protect-cryptographic-code/
- LLVM RFC, "Constant Time Execution Guarantees in LLVM" —
  https://discourse.llvm.org/t/rfc-constant-time-execution-guarantees-in-llvm/86700
