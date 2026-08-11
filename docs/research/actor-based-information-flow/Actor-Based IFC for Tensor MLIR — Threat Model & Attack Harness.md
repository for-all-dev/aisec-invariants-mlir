# Actor-Based IFC for Tensor MLIR — Threat Model & Attack Harness

*Written 2026-07-10. Defines the precise security envelope, the attack classes in and out of scope, the flagship demonstrations, and the four-corpus benchmark harness. Companion to [[Actor-Based IFC for Tensor MLIR — Research Plan]] (architecture L1–L4, observation functions) and [[Actor-Based IFC for Tensor MLIR — Competitive Landscape]] (prior art). Every CVE and paper in the flagship set and corpus was verified against NVD / USENIX / vendor advisories on 2026-07-10.*

**Confidence legend:**
- ✅ verified this session against primary source (NVD, USENIX, vendor advisory, or repo commit)
- 📄 primary-source extraction, characterization not independently re-checked
- ○ background knowledge / not separately verified this session — re-verify before citing in a paper

---

## 0. The one principle that keeps this honest

Do **not** promise "all low-level and cryptographic attacks." That category includes memory corruption, weak randomness, fault injection, protocol mistakes, speculative execution, power analysis, and cryptanalysis — no single IFC compiler honestly covers those. Overclaiming is what drops the project's credibility with a security audience.

**The precise claim (the security envelope):**

> We cover the complete class of confidentiality violations expressible as secret-dependent **outputs, placements, execution paths, operation counts, memory behavior, target-variable-latency operations, and sanctioned release events** — and we validate that **compilation preserves** those properties.

That is a large, real slice of the vulnerability space with a crisp boundary. The headline the evaluation should earn:

> One relational MLIR security model detects shipped source-level timing bugs, compiler-introduced constant-time regressions, tensor-index side channels, and cross-party FHE placement violations — while identifying hardware and backend assumptions as explicit outstanding obligations.

That is far stronger than a long, disconnected list: it shows a *small number of principled invariants* explaining a *broad, real* vulnerability corpus.

---

## 1. The observation-event model (the extended Oᶜᵗ)

The Research Plan's three observation functions stand: Oᵒᵘᵗ (party-visible outputs/placement), Oᶜᵗ (execution trace), Oʰʷ (hardware effects, obligation-only). This doc **expands the event alphabet** of Oᶜᵗ beyond the original branch/address/variable-latency triple to everything observable at tensor and heterogeneous-compute altitude:

```
event ::=
    branch(outcome)
  | call(target)
  | memory(address, width, read-or-write)
  | variable_latency(opcode, relevant-operands)
  | allocation(size)
  | shape(dimensions)
  | kernel_launch(kernel-id)
  | transfer(source-host, destination-host, size)
  | error(error-class)
  | release(principal, policy-id, value)
```

**The relational property.** For observer/party p, two executions agreeing on p's public inputs must produce indistinguishable event traces, modulo explicitly authorized release events:

$$\forall\, i_1, i_2 \ :\ \ i_1 \approx_p i_2 \implies \text{Trace}_p(P, i_1) \sim \text{Trace}_p(P, i_2) \quad (\text{mod authorized } \textsf{release})$$

This stays consistent with the established path-/address-/operand-based leakage models (ct-verif, FaCT ○) and adds the events that matter at our altitude. Three refinements are load-bearing:

1. **Finite secret-dependent loop counts are in scope.** Exclude non-termination as a progress channel, but *not* ordinary variable iteration counts — Minerva recovered ECDSA keys from nonce-bit-length-dependent scalar-multiplication loops ○, and wolfSSL [CVE-2024-1544](https://nvd.nist.gov/vuln/detail/CVE-2024-1544) ✅ is control-flow leakage in ECDSA nonce reduction.
2. **Variable-time operations are target-specific.** `div` is the baseline, but a nominally ordinary 64-bit multiply becomes a variable-time helper (`__muldi3`) on a target lacking native support — wolfSSL [CVE-2026-3579](https://nvd.nist.gov/vuln/detail/CVE-2026-3579) ✅. There is **no universal "multiply is safe" rule**; query a target profile.
3. **Tensor metadata needs separate labels.** Shape, length, sparsity pattern, indices, layout, and routing can carry different confidentiality than element contents. A whole-tensor secret bit is safe but blunt; metadata flow is where tensor-native leaks live.

**Four label facets** (initially analysis facts, first-class MLIR types deferred to v2):

$$\text{element-value label} \ \mid\ \text{index/shape label} \ \mid\ \text{layout/sparsity label} \ \mid\ \text{placement label}$$

---

## 2. Attacks we PREVENT — catalog A–J

Each class lists mechanism, the architecture layer that catches it (L1 checker / L2 SMT / L3 preservation-TV / L4 obligation, per the Research Plan), the observation function, real instances with confidence markers, and the repair story.

### A. Unauthorized explicit flow & placement — [L1, Oᵒᵘᵗ]
Plaintext client secret placed on an FHE server; provider weights sent to the client; decrypted intermediate to the wrong party; secret into logging/tracing/telemetry/debug; secret returned through an error object; host↔device copy into an unauthorized address space; bufferization/aliasing making a secret buffer party-readable; secret through an untrusted FFI/crypto-library call; accidental export in checkpoints/serialized tensors.
**Mechanism:** party-label flow checking + declared host authority + trust-boundary contracts. This is what HEIR *assumes* and SPU *asserts* but nobody *checks*.

### B. Secret-dependent branches & instruction paths — [L1, Oᶜᵗ]
`scf.if` / `cf.cond_br` / `switch` / indirect-call target derived from secret; conditional subtraction / modular correction; secret-dependent rejection-sampling; padding-validation branches; secret-dependent kernel selection; **compiler conversion of a mask/select/CMOV idiom into a branch**.
**Real:** Clangover ✅, HQC [CVE-2025-52473](https://www.tenable.com/cve/CVE-2025-52473) ✅, wolfSSL [CVE-2026-3580](https://nvd.nist.gov/vuln/detail/CVE-2026-3579) ✅ (`bnez`).
**Repair:** mux to `arith.select`/masked ops **only when both paths are pure or their effects can be safely masked**. An arbitrary side-effecting secret branch cannot simply be rewritten.

### C. Secret-dependent loop counts, recursion, early exits — [L1, Oᶜᵗ]
Loop bounds from key bits / secret bit-length; "while nonzero" big-integer normalization; variable-count modular reduction; secret-state-dependent rejection loops; leading-zero removal; early return on mismatch; scalar-multiplication loops stopping at the MSB set bit; variable recursion depth.
**Real:** Minerva ○, Raccoon ○, wolfSSL [CVE-2024-1544](https://nvd.nist.gov/vuln/detail/CVE-2024-1544) ✅ (ECDSA nonce reduction, MSB bias, 15 bits on SECP160R1, CCS'24), padding-oracle implementations.
**Repair:** public maximum bound + masked iterations, else reject.

### D. Variable-latency arithmetic & library helpers — [L1 + L3, Oᶜᵗ, target-parameterized]
Integer `div`/`rem`/`mod`; compiler-generated division/multiplication helpers; target-specific multiply/shift/count when operand-dependent; big-integer normalization/carry; FP conversions / exceptional-value paths where the target documents data-dependent behavior; library calls not declared constant-time; hidden helpers introduced during legalization.
**Real:** KyberSlash ✅, Divide and Surrender ✅ (HQC modulo → `div`, USENIX Sec'24, HQC-128 in <2 min on AMD Zen2 via DIV-SMT), wolfSSL [CVE-2026-3579](https://nvd.nist.gov/vuln/detail/CVE-2026-3579) ✅ (`__muldi3`), wolfSSL [CVE-2025-12888](https://nvd.nist.gov/vuln/detail/CVE-2025-12888) ✅ (X25519 on Xtensa ESP32), [CVE-2024-1544](https://nvd.nist.gov/vuln/detail/CVE-2024-1544) ✅.
**Key lesson:** `arith.muli %secret, %secret` may be safe on one target and unsafe on another → the target profile must ask *what does this lower to, is that implementation operand-independent, and is it inside the verified region or an obligation?* This is the cleanest justification for **target-parameterized operation profiles**.

### E. Secret-dependent memory behavior — [L1, Oᶜᵗ]
Secret influence on load/store address, tensor index, gather/scatter index, stride/offset, indirect-call table index, cache-line/page/bank selection, which buffers are touched, load/store width, software-inserted prefetch addresses, sparse index arrays / compressed metadata.
**Real:** AES T-tables ○ (Bernstein '05, OST'06), wolfSSL [CVE-2024-1543](https://nvd.nist.gov/vuln/detail/CVE-2024-1543) ✅ (AES T-table, sub-cache-line, SGX-like), [CVE-2021-24116](https://nvd.nist.gov/vuln/detail/CVE-2021-24116) ○ (base64 PEM-decode lookup leaking key material), the LLM embedding attack (§4-6).
**Default:** exact-address equality. Weaker cache-line/page observers are optional profiles, not the headline guarantee.

### F. Secret-dependent tensor metadata & execution schedules — [L1, Oᶜᵗ + Oᵒᵘᵗ]
*The underdeveloped opportunity.* Secret influence on dynamic dimensions, allocation sizes, sparse structure, nonzero count, batching/compaction, kernel count/identity, CPU/GPU/NPU selection, autotuning choice, host↔device transfer count/size, sequence length, early-exit network depth, beam width, expert routing, compression/serialization length.
**Real:** the LLM cache work ✅ already shows token-position leakage through autoregressive execution timing. Some of these are timing events, others host-visible outputs. This is what LLVM-level CT tools structurally cannot express — the substance behind "tensor-level."

### G. Equality checks, error handling, protocol oracles — [L1 + robust declassification, Oᶜᵗ]
`memcmp`/`Arrays.equals` on secrets; early-exit MAC / auth-tag / password / PSK / signature comparison; distinguishable padding errors; distinct error codes/exception classes; different cleanup paths for valid vs invalid ciphertexts; length-dependent rejection; variable-time RSA unpadding / implicit-rejection.
**Real:** wolfSSL [CVE-2025-11932](http://www.mail-archive.com/debian-bugs-closed@lists.debian.org/msg823569.html) ✅ (TLS 1.3 PSK binder non-constant-time), Kafka [CVE-2021-38153](https://nvd.nist.gov/vuln/detail/cve-2021-38153) ✅ (non-CT credential check), OpenSSL [CVE-2022-4304](https://github.com/openssl/openssl/discussions/22374) ✅ (RSA decryption Bleichenbacher oracle, all padding modes), NSS CVE-2023-5388 ○, Lucky13 ○, the Marvin family ○.
**This is the ideal robust-declassification case:** the protocol may intentionally release *one bit* (valid/invalid), but the trace must reveal nothing beyond it — allowed: the validity result; forbidden: mismatch position, padding class, intermediate error, cleanup path.

### H. Compiler-introduced security regressions — [L3, Oᶜᵗ/Oᵒᵘᵗ] — **the novelty center**
Every transformation that changes observability without changing functional output: select/mask → branch; branchless compare → early exit; fixed loop → data-dependent loop; arithmetic expansion → variable-time helper; modulo-strength-reduction → division; vectorization / de-vectorization; loop unswitching; if-conversion and its reverse; DCE of masks/blinding/dummy-accesses/clearing; library-call introduction; bufferization exposing intermediates; sparse lowering introducing value-dependent iteration; dynamic-shape specialization; fusion changing memory footprint; outlining across a party/trust boundary.
**Real:** Clangover ✅, HQC [CVE-2025-52473](https://www.tenable.com/cve/CVE-2025-52473) ✅, wolfSSL [CVE-2026-3580](https://nvd.nist.gov/vuln/detail/CVE-2026-3579) ✅ and [CVE-2026-3579](https://nvd.nist.gov/vuln/detail/CVE-2026-3579) ✅, wolfSSL [CVE-2025-13912](https://www.tenable.com/plugins/nessus/295004) ✅ (multiple CT routines broken by Clang 18 on AArch64: `sp_read_radix`, `sp_div_2_mod_ct`, `sp_addmod_ct`, `wc_AesGcmDecrypt`), [CVE-2025-12888](https://nvd.nist.gov/vuln/detail/CVE-2025-12888) ✅. This is where *functionally equivalent* $\neq$ *security preserving*, and where mlir-tv-style equivalence checking is provably blind.

### I. Declassification, cryptographic release, circuit privacy — [L1 NMIFC + L4 obligation, Oᵒᵘᵗ]
Unrestricted `declassify`; attacker-influenced declassification guards; decryption on an unauthorized host; release before authentication; release before CKKS sanitization; revealing an intermediate rather than the approved final result; reusing a declassification result for a broader audience; output ciphertext lacking circuit-privacy sanitization; encrypted→plaintext switch without an authorized policy edge.
**Real:** CKKS approximate-decryption key recovery — Li–Micciancio EUROCRYPT'21 ○ (seminal: sharing a CKKS decryption leaks the secret key) and Guo–Nabokov–Suvanto–Johansson USENIX Sec'24 ✅ (**one shared OpenFHE decryption** recovers the key under non-worst-case noise flooding).
**The compiler proves ordering and policy compliance; it cannot invent the cryptographic security theorem** — the sanitizer's sufficiency needs an external noise-bound certificate. Also distinguish client-data privacy from **server-function privacy**: ordinary FHE does not hide the server's function; circuit privacy needs extra sanitization/protocol support.

### J. Secret lifetime, initialization, residual state — [L4 obligation] — *stretch, not v1 theorem*
Reading uninitialized tensor/GPU scratch; reusing secret buffers across principals; failing to clear local/shared memory before kernel exit; DSE removing zeroization; register spills across protected-region boundaries; secret contents retained in debug snapshots; allocation pools returning uncleared buffers; secrets in crash dumps.
**Real:** LeftoverLocals ○ (ToB, uninitialized GPU local memory exposes another kernel's LLM inputs/weights/intermediates), the dead-store-elimination-of-scrubbing literature ○.
**Frame as an erasure/initialization obligation**, not forced into v1 non-interference:

$$\textsf{secret scratch alloc} \implies \text{init-before-read} \ \wedge\ \text{cleared-before-domain-transition} \ \wedge\ \text{clear-preserved-by-lowering}$$

---

## 3. Attacks we CANNOT prevent — flag, never claim

Precisely saying "unknown / obligation outstanding" is more credible than broad green checkmarks.

| Class | Real anchor | Our honest output |
|---|---|---|
| **DMP / data-memory-dependent prefetch** | GoFetch ✅ ([Apple 120309](https://support.apple.com/en-us/120309)) — leaks from *already-correct* CT code | verified under sequential software-trace model **+ DIT/DOIT obligation emitted** (Oʰʷ). Never "IFC proved this safe against GoFetch." |
| **Speculative execution** | Spectre/Pitchfork/Binsec-Rel ○ | out of scope v1; Oˢᵖᵉᶜ future extension (needs speculative semantics, mistraining, transient obs) |
| **Physical / software-visible-physical** | power, EM, acoustic, Hertzbleed (frequency/thermal) ○, glitching, DFA, Rowhammer, optical probing | out of model permanently — a constant *instruction* trace is not a constant *power* trace |
| **Below the last verified IR** | wolfSSL [CVE-2026-3579](https://nvd.nist.gov/vuln/detail/CVE-2026-3579)/[3580](https://nvd.nist.gov/vuln/detail/CVE-2026-3579) ✅ (compiler-inserted helper / branch **below** MLIR) | obligations for register alloc, scheduling, relaxation, assembler, microcode, hand-asm, OpenFHE/Lattigo/TFHE-rs, runtime/drivers |
| **Different-project crypto bugs** | weak/reused randomness, nonce reuse (no timing cause), insecure keygen, weak params, invalid-curve, memory corruption, UAF, integer overflow, cryptanalysis, protocol downgrade, cert-validation, auth bypass, fault resistance, key lifecycle | explicitly out — folding these in dilutes the coherent non-interference story |

---

## 4. Flagship demonstrations (ranked) — the harness heroes

1. **Clangover / ML-KEM `poly_frommsg`** ✅ — *innovation crown.* Clang 15–18 turned a branchless CT idiom in the ML-KEM reference into a secret-dependent branch; ML-KEM-512 key recovery in <10 min. **Desired result:** source/imported MLIR passes Oᶜᵗ; equivalence-checking *accepts* the optimization; **our relational validator rejects the lowered program**; witness reports first diverging branch + secret input pair; vulnerable/patched form a regression pair. Call it an "MLIR→LLVM security-preservation" demo unless the transform occurs in the MLIR pipeline itself — do not overclaim it as an "MLIR bug."
2. **wolfSSL [CVE-2026-3580](https://nvd.nist.gov/vuln/detail/CVE-2026-3579)** ✅ — masking → `bnez` in `sp_256_get_entry_256_9`, GCC `-O3`, RISC-V RV32I, breaks ECC scalar-mult resistance. Different algorithm, compiler, architecture, and primitive from Clangover — same theorem. *(Reported by Calif.io with Claude/Anthropic Research — a compiler-CT bug already found with an LLM; your project systematizes this.)*
3. **wolfSSL [CVE-2026-3579](https://nvd.nist.gov/vuln/detail/CVE-2026-3579)** ✅ — 64-bit multiply lowered to variable-time `__muldi3` on RV32I, hitting `sp_256_mul_9`/`sp_256_sqr_9`. Proves **checking source opcodes is insufficient**; the cleanest justification for target-parameterized profiles.
4. **KyberSlash in the actual pq-crystals source** ✅ — *usefulness crown.* Import the vulnerable arithmetic kernel from real pre-fix source (Polygeist / C→MLIR), sidecar-annotate secrets, **reject the secret-dependent division**, import patched revision, show Barrett-style arithmetic passes, verify lowering doesn't reintroduce division. Materially stronger than a hand-made analogue.
5. **HQC — both directions** ✅ — Divide and Surrender (modulo → variable-time `div`, USENIX Sec'24) *and* [CVE-2025-52473](https://www.tenable.com/cve/CVE-2025-52473) (Clang 17–20 introduced secret branches > `-O0`). With KyberSlash + Clangover this establishes two failure directions: *unsafe source arithmetic → unsafe target* and *safe-looking source idiom → unsafe target*.
6. **Secret token embedding lookup** ✅ — *proof that tensor altitude is substantive.* "I Know What You Said" (USENIX Sec'25, arXiv 2505.06738): token values inferred from embedding-op cache patterns, positions from autoregressive timing; reconstructed input/output text (edit distance 17.3%/5.2%) on Llama/Falcon/Gemma. Test op: `%e = tensor.extract %table[%secret_token]` (or gather). Vulnerable = direct indexed lookup; accepted = oblivious full scan / HW oblivious primitive / trusted encrypted backend. Extend to secret gather/scatter, secret Top-K, MoE routing, secret sequence length, secret sparsity, zero-skipping, beam-search pruning.
7. **Two-owner FHE placement** — *cleanest party-label demo.* Weights readable only by provider; inputs only by user; server operates only on protected representations; neither plaintext crosses; only the authorized output releases. **Negative mutations:** remove a client→server `conceal`; place an intermediate plaintext on the server; send a decrypted activation to the provider; insert a debug/trace callback; bufferize into a server-readable scratch buffer; call a library function whose contract doesn't preserve encryption. Tests explicit flow, placement, alias exposure, library boundaries, and declassification in one pipeline.
8. **CKKS reveal without adequate sanitization** ✅ — *policy-checked declassification.* `decrypt` $\neq$ `declassify`. Releasable only after an approved `aisec.sanitize_ckks %r { bound_certificate, policy }` → `aisec.declassify`. Label checker verifies the sequencing; the noise-bound sufficiency is an external certificate (Guo et al. USENIX Sec'24: one OpenFHE decryption suffices when the bound is non-worst-case).
9. **Secret lifetime / compiler-eliminated clearing** ○ — *stretch.* DSE removing key/tensor zeroization; LeftoverLocals-style uninitialized GPU local memory. L4 erasure obligation, not central theorem.

---

## 5. The benchmark harness — four corpora

Keep the four corpora **clearly separated**, and label every case honestly as *actual source imported* / *faithful reduced reproduction* / *seeded analogue* — never blur them.

### Corpus 1 — real vulnerable/fixed source pairs
| # | Case | Class | Verified |
|---|---|---|---|
| 1 | ML-KEM Clangover `poly_frommsg` | B/H | ✅ |
| 2 | pq-crystals KyberSlash vuln/patched | D | ✅ |
| 3 | HQC Divide-and-Surrender modulo kernel | D | ✅ |
| 4 | HQC secret-branch [CVE-2025-52473](https://www.tenable.com/cve/CVE-2025-52473) vuln/patched | B/H | ✅ |
| 5 | wolfSSL RV32I mask→branch [CVE-2026-3580](https://nvd.nist.gov/vuln/detail/CVE-2026-3579) | H | ✅ |
| 6 | wolfSSL RV32I `__muldi3` [CVE-2026-3579](https://nvd.nist.gov/vuln/detail/CVE-2026-3579) | D/H | ✅ |
| 7 | wolfSSL ECDSA nonce reduction [CVE-2024-1544](https://nvd.nist.gov/vuln/detail/CVE-2024-1544) | C | ✅ |
| 8 | wolfSSL AES T-table [CVE-2024-1543](https://nvd.nist.gov/vuln/detail/CVE-2024-1543) | E | ✅ |
| 9 | wolfSSL PSK binder [CVE-2025-11932](http://www.mail-archive.com/debian-bugs-closed@lists.debian.org/msg823569.html) | G | ✅ |
| 10 | wolfSSL base64 PEM lookup [CVE-2021-24116](https://nvd.nist.gov/vuln/detail/CVE-2021-24116) | E | ○ |
| 11 | Kafka-style early-exit secret compare [CVE-2021-38153](https://nvd.nist.gov/vuln/detail/cve-2021-38153) | G | ✅ |
| 12 | OpenSSL/NSS RSA decryption oracle [CVE-2022-4304](https://github.com/openssl/openssl/discussions/22374) | G | ✅ |
| + | wolfSSL LLVM-breaks-CT [CVE-2025-13912](https://www.tenable.com/plugins/nessus/295004); Xtensa X25519 [CVE-2025-12888](https://nvd.nist.gov/vuln/detail/CVE-2025-12888) | H/D | ✅ |

### Corpus 2 — compiler-preservation
For each secure source idiom, compile over a matrix of compiler versions × opt levels × MLIR pipelines × LLVM lowering configs × architectures. Seed: mask→branch; select→branch; constant-count loop→early-exit; full-scan gather→indexed; CT-compare→`memcmp`; multiply→runtime helper; modulo→division; zeroization removed by DSE; fixed tensor schedule→sparse/value-dependent; bufferization exposing an unauthorized memref. **The validator must report the first pass after which the property fails** — far more useful than "the final binary is unsafe."

### Corpus 3 — tensor- & party-native (what LLVM-level tools can't express)
Secret-token embedding; secret Top-K; secret gather/scatter; secret sparsity; secret sequence length; MoE routing; two-owner private inference; missing FHE `conceal`; debug reveal; client decryption misplaced on server; model-output release to wrong party; CKKS release without sanitization; absent circuit-privacy obligation.

### Corpus 4 — negative-control obligations (the tool must REFUSE to certify)
GoFetch without a DIT/hardware obligation; opaque backend library calls; unverified assembly; speculative-execution claims; power/EM claims; fault resistance; GPU memory isolation dependent on driver/hardware. A tool that says "unknown / obligation outstanding" is more credible than one that green-checks everything.

---

## 6. What every diagnostic must contain

Not a raw SMT model — a runnable, localized witness:

```
observer:        server
secret owners:   client
public inputs:   ...
secret input 1:  ...
secret input 2:  ...
first divergence:
  source op:     arith.select at foo.mlir:82
  target op:     cf.cond_br at lowered.mlir:144
  lowering pass: convert-scf-to-cf
  event 1:       branch(false)
  event 2:       branch(true)
target profile:  riscv-rv32i
security result: O^ct violation
```

- **Placement:** `secret source → aliases/operations → unauthorized host`
- **Declassification:** `release operation → missing policy/sanitizer/certificate`
- **Obligation:** `property verified only if __muldi3 has operand-independent timing`

Witness quality (first-pass localization + a concrete secret input pair) is itself a major adoption contribution.

---

## 7. Evaluation target that makes the paper compelling

A strong first system evaluation demonstrates: 10–15 real vulnerable/fixed pairs (not only synthetic mutations); ≥4 root-cause classes; ≥3 target profiles including RV32I; actual C import for at least KyberSlash; ≥1 real tensor-native leak; one two-owner FHE artifact; one CKKS policy violation; ≥1 security regression introduced by a *real* compiler pipeline; first-pass localization; runnable counterexamples; fixed versions accepted with a measured false-positive rate; low annotation burden on ordinary HEIR examples.

---

## 8. Sources (verified 2026-07-10 unless marked ○)

**Compiler-introduced CT (class H heroes):** [Clangover / poly_frommsg](https://pqshield.com/pqshield-plugs-timing-leaks-in-kyber-ml-kem-to-improve-pqc-implementation-maturity/) ✅ · wolfSSL [CVE-2026-3579](https://nvd.nist.gov/vuln/detail/CVE-2026-3579), [CVE-2026-3580](https://cve.imfht.com/detail/CVE-2026-3580?lang=en), [CVE-2025-13912](https://www.tenable.com/plugins/nessus/295004), [CVE-2025-12888](https://nvd.nist.gov/vuln/detail/CVE-2025-12888) ✅ · HQC [CVE-2025-52473](https://www.tenable.com/cve/CVE-2025-52473) ✅.
**Source-level var-time/branch/loop/mem:** [KyberSlash](https://kyberslash.cr.yp.to/) ✅ ([ePrint 2024/1049](https://eprint.iacr.org/2024/1049)) · [Divide and Surrender (USENIX Sec'24)](https://www.usenix.org/conference/usenixsecurity24/presentation/schr%C3%B6der) ✅ ([ePrint 2024/299](https://eprint.iacr.org/2024/299)) · wolfSSL [CVE-2024-1544](https://nvd.nist.gov/vuln/detail/CVE-2024-1544), [CVE-2024-1543](https://nvd.nist.gov/vuln/detail/CVE-2024-1543), [CVE-2025-11932](http://www.mail-archive.com/debian-bugs-closed@lists.debian.org/msg823569.html) ✅ · [CVE-2021-24116](https://nvd.nist.gov/vuln/detail/CVE-2021-24116) ○ · Minerva, Raccoon, Lucky13, AES T-tables, Marvin, NSS CVE-2023-5388 ○.
**Protocol oracles:** Kafka [CVE-2021-38153](https://nvd.nist.gov/vuln/detail/cve-2021-38153) ✅ · OpenSSL [CVE-2022-4304](https://github.com/openssl/openssl/discussions/22374) ✅.
**Tensor-native:** ["I Know What You Said" (USENIX Sec'25)](https://www.usenix.org/conference/usenixsecurity25/presentation/gao-zibo) ✅ ([arXiv 2505.06738](https://arxiv.org/abs/2505.06738)).
**Crypto release / CKKS:** [Guo et al. (USENIX Sec'24)](https://www.usenix.org/conference/usenixsecurity24/presentation/guo-qian) ✅ · Li–Micciancio EUROCRYPT'21 ○.
**Cannot-prevent anchors:** [GoFetch / Apple 120309](https://support.apple.com/en-us/120309) ✅ · LeftoverLocals ○ · Hertzbleed ○ · Spectre/Pitchfork/Binsec-Rel ○.
**Internal:** [[Actor-Based IFC for Tensor MLIR — Research Plan]] · [[Actor-Based IFC for Tensor MLIR — Competitive Landscape]] · [[Viaduct — Mechanics and Innovation Angles]].
