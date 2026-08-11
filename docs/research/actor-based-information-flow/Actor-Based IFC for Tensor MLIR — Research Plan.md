# Actor-Based IFC for Tensor MLIR — Research Plan

*Solidified 2026-07-10. Synthesizes [[Actor-Based IFC for Tensor MLIR — Competitive Landscape]] (105-agent sweep, 2026-07-08), [[Viaduct — Mechanics and Innovation Angles]], the existing verifier in `~/code/aisec-invariants-mlir`, and Quinn's fellowship proposal (`docs/SPS-proj-proposal_compiler-confidentiality.pdf`). Confidence markers follow the landscape note's convention; ○ = background knowledge added here, re-verify before citing.*

---

## 1. Thesis

**First information-flow verifier for tensor-level MLIR with party-labeled secrets and SMT-checked non-interference — including preservation under lowering — unifying FHE secret-placement and timing-channel obligations.**

The one-line pitch, per the landscape verdict: every axis is crowded, the intersection is empty. Everyone else *compiles, optimizes, asserts, or preserves*; **nobody detects and proves**.

The unification that makes this one project instead of two: **HEIR's own pipeline emits both sides of the threat model.** The server-side encrypted graph is where the *placement* problem lives (client secrets must not reach server placement in cleartext), and `lwe-add-client-interface` emits the *client-side* enc/dec kernels where KyberSlash-class *timing* bugs live (secret-dependent division in lattice arithmetic). One label system, one relational property, two observation functions — same compiler run.

## 2. Claim discipline

| Claim | Status |
|---|---|
| First secret types on tensors | ✗ forbidden — HEIR/HECO/SPU |
| First multi-party MLIR | ✗ forbidden — SPU |
| First label-driven placement compiler | ✗ forbidden — Viaduct (and Jif/split before it) |
| First SMT on MLIR | ✗ forbidden — mlir-tv, PLDI'25 dialects |
| First constant-time compiler support | ✗ forbidden — FaCT, ToB ct.select |
| "Prevents side-channel attacks" (unqualified) | ✗ forbidden — GoFetch breaks CT code; scope to the CT leakage model |
| **First *verified* (not asserted) party-labeled NI at tensor altitude** | ✔ defensible |
| **First NI/CT *preservation* checking across MLIR lowerings** | ✔ defensible (hedge per Quinn's R1: post systematic-review depth) |
| **Static answer to Bernstein et al.'s explicit call** (ePrint 2024/1049 proposes "formal-methods approach to guarantee absence of variable-time instructions") | ✔ defensible — they asked for exactly this |

Positioning triad for related work: **SPU asserts, FaCT/Jasmin construct (in their own DSLs), ToB/CompCert-CT preserve — we verify the artifact and preserve through lowering.**

**Terminology decision:** say **party-labeled / principal-based IFC**, not "actor-based," in papers. "Actor" collides with the actor concurrency model and with actor-IFC languages in the PL literature (e.g. Troupe ○), and Viaduct's community says "hosts/principals." Keep "actor" only as informal vault shorthand.

## 3. Formal core — one property, three observation functions

One relational definition, parameterized by what party p can observe. For program P with party-labeled inputs:

$$\forall\, i_1, i_2 \ :\ \ i_1 \approx_p i_2 \implies O_p(P,\, i_1) = O_p(P,\, i_2)$$

(inputs agreeing on everything p may see produce p-indistinguishable executions), with three instantiations of $O_p$:

1. **$O^{\text{out}}$ — output/placement observation** (classic NI, Quinn's property): values delivered to hosts p controls. Violations = secrets mishandled across the trust boundary.
2. **$O^{\text{ct}}$ — trace observation** (constant-time model): $O^{\text{out}}$ plus, for every op executing on a host p can time: branch outcomes, memory addresses, and operands of **variable-latency ops** (div/rem baseline; target-parameterized ○ — e.g. early-termination multipliers on Cortex-M ○). Violations = KyberSlash class.
3. **$O^{\text{hw}}$ — hardware-assisted observation**: $O^{\text{ct}}$ plus DMP-visible footprint (GoFetch). **Not verified — discharged by obligation**: the verifier emits "DIT/DOIT must be set for this region" as a first-class fact; hardware/OS honoring it is an assumption, stated as such.

Everything reduces to the same machinery: self-composition at the MLIR level (Barthe et al. self-composition; ct-verif's leakage-model framing ○) lifted through mlir-tv's existing linalg/tensor/arith SMT encodings. The L1 type/dataflow checker is a sound over-approximation of the same property; the data-independent-lowering subset (Quinn's technique 2) certifies preservation *without* SMT and generalizes verbatim to $O^{\text{ct}}$ (rewrite rules that introduce no secret-dependent branch, address, or variable-latency operand).

This unification — output-NI and CT as the *same theorem at two observation functions*, checked by the same tool — is the theory paper's spine.

## 4. Threat model v1 (pin this; every reviewer fight starts here)

- **Parties**: named principals; hosts declared with authority labels, Viaduct-style minimal $\langle \text{confidentiality}, \text{integrity} \rangle$ pairs (integrity kept only for NMIFC declassification, §5 L1).
- **Adversary**: honest-but-curious parties read *everything* placed on their hosts, plus instruction-granularity timing of ops on their hosts ($O^{\text{ct}}$). Malicious *integrity* (wrong results, availability) out of scope in v1.
- **Compiler**: untrusted — buggy or malicious passes alike; we check the emitted artifact (Chen et al. S&P'26 is the motivating precedent that this surface is real).
- **Hardware**: sequential ISA semantics. Speculation excluded (v1); DMP handled by obligation only.
- **TCB**: MLIR core semantics + L1 checker + self-composition transform + mlir-tv encoder + Z3/cvc5, and everything below the last verified IR. Shrinks over time: ToB ct intrinsics as lowering targets (backend), Lean-mechanized checker (Quinn's OP-6 stretch).
- **Explicitly out of scope**: network traffic analysis (message sizes, round patterns), power/EM/frequency channels (Hertzbleed ○), OS/runtime co-residency, key management.

## 5. Architecture — four layers

**L1 — Label checker (exists in embryo; M1 extends it).** The `--aisec-verify-non-interference` taint walk generalizes to:
- **Party labels** as attributes over HEIR's `secret` dialect (v1: `aisec.owner = ["client"]`, `aisec.placed = "server"` — attributes + analysis, not a new type system; a first-class `!ifc.labeled<T, ℓ>` type is a v2 decision, deliberately deferred).
- **Placement checking**: every op's operands must be readable by its host's authority; cross-host edges are the check points. This is exactly what SPU *asserts* and never checks.
- **Variable-time-op rule**: secret operand $\land$ variable-latency op $\implies$ error, or auto-rewrite where sound (div-by-public-constant → Barrett multiply-shift — "secure strength reduction," detection *and repair*).
- **Secret-guarded control flow / secret indexing**: `scf.if` on secret $\implies$ mux to `arith.select`/masked ops (one transform serving both MPC/FHE executability and CT — the Viaduct guard-visibility move, note §2.5); `tensor.extract`/gather with secret index $\implies$ reject or oblivious rewrite. Tensor-native bug class: **embedding lookup on secret token IDs is a cache side channel** — connects the ML story to the CT story.
- **NMIFC declassification**: `aisec.declassify` upgraded from unconditioned escape hatch to robust declassification (declassify guards must be high-integrity, reflection-operator rules from Cecchetti–Myers–Arden via Viaduct). CKKS discipline encodable here: reveal of an approximate-FHE result requires a noise-flooding sanitize step ○ (Li–Micciancio Eurocrypt'21 ○) before it counts as declassifiable.

**L2 — Relational SMT (Quinn's core).** Self-composition at the IR level (not the formula level), labels threaded through `secret.generic`, lifted through mlir-tv's encoder; SAT models lifted back to **concrete leaking input pairs** (attack witnesses — the practical artifact). Reserved for what L1 can't decide: value-dependent flows, masking/blinding idioms, declassify-correctness. **Architecture lesson from Viaduct: infer labels cheaply (Rehof–Mogensen fixed point, ms), reserve SMT for verification** — never burn the solver on inference.

**L3 — Translation validation of preservation.** After each lowering, re-check the relational property on the lowered IR (the property mlir-tv vanilla *cannot* see: an NI leak is not an equivalence bug — pre- and post-lowering programs compute the same function of the secret). Corpus per Quinn: bufferization (known-tricky: aliasing exposes weights), linalg→loops, secret→cleartext rewrites, `secret.generic` outlining/inlining, tensor insert/extract canonicalizations. The **data-independent subset theorem** certifies the boring majority syntactically; SMT handles the rest. Headline hunt: $\geq 1$ real NI/CT-breaking lowering in upstream MLIR or HEIR.

**L4 — Obligations ledger.** Facts the IR level cannot discharge, emitted as structured, checkable artifacts rather than silent assumptions: DIT/DOIT required around secret regions (GoFetch); ct.select-style lowering required for muxes (discharged when ToB's `llvm.ct.select` lands — [PR #166702](https://github.com/llvm/llvm-project/pull/166702), watch); library-backed boundaries (OpenFHE/Lattigo/TFHE-rs calls) marked as trust edges.

## 6. What it solves — problems × attacks × layer

1. **Cross-party secret placement violations (the FHE client/server problem).** Client secrets typed so they cannot reach server placement in cleartext; every egress via `conceal` (encrypt) or checked declassify. Catches missing-encrypt paths, debug reveals, misrouted tensors. Today HEIR *assumes* this, SPU *asserts* it, nobody *checks* it. [L1]
2. **KyberSlash-class variable-time arithmetic on secrets** (kyberslash.cr.yp.to; pq-crystals fix dda29cc). Secret-operand div/rem rejected at type level or rewritten to Barrett form; kept true through lowering by L3. Directly answers Bernstein et al.'s call for the static guarantee (their own countermeasure — patched Valgrind — is dynamic and post-hoc). [L1 + L3]
3. **Two-owner confidentiality — expressible for the first time at this altitude.** Private inference: model weights secret *to the provider*, user inputs secret *to the user*, mutually. HEIR/HECO's binary `secret<T>` is one bit and structurally cannot say this; party labels can. Subsumes the original aisec model-weights problem as a special case and covers the embedding-extraction threat model already in the repo docs. [L1]
4. **Secret-dependent control flow and memory access at tensor granularity.** Secret-guarded branches muxed; secret-indexed gathers (embedding lookups) made oblivious or rejected — a bug class *visible only at tensor altitude* (at LLVM it's shattered into GEPs; the README's whole "Why MLIR" argument). [L1 + rewrites]
5. **Compiler-introduced leaks.** Lowering/canonicalization that breaks source-level NI or CT — the Breaking Bad phenomenon, the CVE class ToB cites (CVE-2022-4304 etc.), Chen et al.'s compiler-as-attack-surface for ML. Checked per-compilation on the artifact, so buggy and malicious passes are caught alike. Nobody does this at MLIR; CompCert-CT does it once-and-for-all for C, at the cost of freezing the compiler. [L3]
6. **Unchecked declassification.** Robust-declassification typing means the *annotation itself* is policy-checked (attacker-influenceable guards rejected); CKKS reveal-without-sanitization expressible as a violation. Upgrades today's trust-the-annotation hole. [L1]
7. **Silent hardware assumptions made explicit.** DIT/DOIT and ct-lowering requirements become dischargeable obligations in the artifact — auditable by security engineers, dischargeable progressively as upstream support lands. GoFetch response without overclaiming. [L4]
8. **A CI-shaped deliverable.** Jancar et al. (S&P'22, via CT-LLVM's framing): CT tools exist and go unused for usability reasons. An `mlir-opt` pass that fails the build with a type error and a concrete leaking input pair is the usability answer — CI-grade regression for security properties, per Quinn's applications section. [all layers]

## 7. What it cannot solve — say these in the paper before reviewers do

1. **GoFetch/DMP itself** (Apple 120309). IR-level NI is *provably insufficient* on DMP hardware — correctly constant-time code still leaks. We emit DIT/DOIT obligations; we cannot verify silicon honors them, and DIT disables the DMP only on M3+ per the landscape note. Of the three motivating attacks, this one is *mitigated-by-obligation*, never *prevented*. Do not let a single sentence claim otherwise.
2. **Speculative execution.** Sequential semantics; Spectre-class transient leakage is Pitchfork/Binsec-Rel territory. A speculative observation function $O^{\text{spec}}$ is future work, not v1.
3. **Physical channels.** Power, EM, acoustic, DVFS/frequency (Hertzbleed ○ — constant-cycle $\neq$ constant-power). Out of model, permanently.
4. **The gap below the verified IR.** Backend/register-allocation/ISA-level variation (the reason ToB expands ct.select *post-RA*), hand-written assembly, and — critically for the FHE story — **HEIR's library backends**: what lowers to OpenFHE/Lattigo/TFHE-rs calls exits the verified region at the call boundary. Guarantees stop at the IR we can see; obligations mark the edges.
5. **Policy garbage-in.** Wrong labels or over-broad declassification make the theorem vacuously true. NMIFC constrains the *structure* of declassification, not its semantic wisdom; no quantitative bound on what sanctioned declassifies leak (bandwidth-bounded egress certificates remain future work, per the README non-goals).
6. **Crypto-scheme-inherent leakage.** We verify flow assuming ideal crypto. Weak parameters, nonce reuse, CKKS approximate-decryption leakage ○ (partially addressable as label discipline, but the noise *analysis* stays empirical/HEIR-side), ciphertext sizes, round counts, traffic patterns — all outside.
7. **Integrity and availability.** Semi-honest server can compute the wrong function; no verifiable computation (ZK/vFHE) in v1 — though Viaduct's protocols-as-authority-labels table gives the extension point, and that's adjacent to my SNARK work. Termination/progress channels excluded (as Viaduct excludes them).
8. **Verification coverage is bounded, per-compilation.** SMT layer: small kernels, bounded loops, timeout $\implies$ unknown (report honestly, fall back to bounded depth per Quinn's disconfirming-evidence plan). Dynamic shapes, unsupported dialects $\implies$ reject or annotate. The type layer over-approximates $\implies$ false positives with declassify as the pressure valve. This is the deliberate trade against CompCert-CT: per-run checking on a living compiler instead of a frozen verified one.
9. **The adoption boundary: only code that flows through MLIR.** The actual pq-crystals C code is out of reach — the honest demo claim is "the same bug *expressed in MLIR* is caught," not "we'd have caught KyberSlash in the reference repo." Motivation framing: as crypto and ML pipelines increasingly compile through MLIR (HEIR on TPU v6e, Intel HERACLES, Niobium, Belfort per the landscape note), the IR becomes the right choke point; a Polygeist-style C frontend ○ is the future-work bridge.
10. **Runtime/OS reality.** Secrets in swap, scheduler co-residency, cold-boot, key storage — compiler-invisible.

## 8. Milestones → venues

**M1 — Party labels + timing rules (now → mid-Aug 2026).**
Extend the existing L1 pass: owner/placement attributes + placement check; variable-time-op rule (+ Barrett rewrite); secret-guard mux; secret-index rule; NMIFC declassify check. Regression five-pack: KyberSlash pair (vulnerable/patched poly kernel in MLIR), FHE placement leak, two-owner private inference, secret-guarded branch, secret gather.
→ **US LLVM Dev Mtg Oct 26–28 quick talk + poster** (CFP historically ~Aug ○ — *verify the date this week and schedule backward*); ePrint tech report alongside (normal in this space — KyberSlash, CT-LLVM did exactly this).
Exit criteria: five-pack green (correct accept/reject each), talk submitted, HEIR commit pinned.

**M2 — Relational SMT core (Aug → Dec 2026).**
Quinn's L2/L3: self-composition through `secret.generic`, labels in the encoding, counterexample lifting, $O^{\text{ct}}$ observation function, ~10-lowering corpus. Target: $\geq 1$ real NI/CT-breaking lowering found (the headline).
Exit criteria: relational validator beats both baselines (mlir-tv vanilla, pre-lowering-only) on the seeded corpus; one real finding or an honest A4 report.

**M3 — Theory + subset theorem (Dec 2026 → Feb 2027).**
Data-independent-lowering subset characterization (+ Lean mechanization only if it's winning — Quinn's OP-6 is the pivot reserve, not the plan). Unified observation-function framework written up.
→ **CSF, Feb 2027 round** (Aug 2026 is too tight for real SMT results; rounds are Feb/May/Aug). Backup: TACAS (Oct submission) / FMCAD.

**M4 — Placement inference (2027, stretch).**
Viaduct-style cost-driven placement at tensor-op granularity — FHE-aware costs (ciphertext ops, multiplicative depth/noise, bootstrapping, client↔server bandwidth); protocols-as-authority-labels table including the FHE row Viaduct never wrote.
→ **System paper: OOPSLA/PLDI** (Viaduct's turf, their reviewers) **or IEEE S&P** if led by the attack-prevention story (Chen et al. precedent).

## 9. Evaluation plan (Viaduct's RQ template + Quinn's design)

| RQ | Measure | Benchmark |
|---|---|---|
| Detection | recall / false-positive rate | seeded-leak mutation corpus (drop conceal, early reveal, secret branch, secret div, secret gather) + the repo's 9 traces converted to real lit tests |
| Real-bug yield | count, with counterexample witnesses | ~10-lowering corpus, upstream MLIR + HEIR |
| Expressiveness | annotation count; annotation-erasure experiment | HEIR examples, MobileNetV2 block, two-owner inference, Kyber-shaped kernels |
| Scalability | L1 wall time (expect linear); SMT time / timeout rate vs kernel size; % of corpus in the data-independent subset | same |
| vs. baselines | mlir-tv vanilla misses NI-class leaks (Quinn's prior); CT-LLVM's ~36% auto-coverage as the type-level contrast ○; TIMECOP/dudect dynamic-vs-static; **SPU asserted-vs-verified demo** — a mislabeled SPU-style program that runs happily there and is rejected here | constructed examples |

## 10. Risk register

| Risk | Move |
|---|---|
| HEIR fast-follow (Kun wants SMT "long term") | Engage *early*, position as the verification layer HEIR lacks, aim to upstream/co-author — after authorship is settled (below) |
| Cornell convergence (Viaduct → AIRduct → arrays+FHE+labels) | Publish the MLIR+SMT+timing combination first; cite generously; their reviewers referee us |
| ToB lands ct-arithmetic + secret IR type | Frame as complementary lowering target that *discharges our obligations*; our altitude (tensors, parties, verification) unaffected |
| GoFetch overclaim | $O^{\text{hw}}$ is obligation-only, forever; §7.1 language is load-bearing |
| **Authorship/IP with Quinn & Lucid** | Proposal is Quinn's; repo NOTICE credits Lucid. Agree roles/authorship *before* the first public artifact (ePrint/talk). Cheap now, expensive later |
| mlir-tv soundness/bitrot (A1) | Trusted base, flag divergences; smoke-test its linalg encoding immediately |
| HEIR churn (A2) | Pin commit now; maintain minimal `secret`-dialect mirror if upstream churn blocks |
| SMT blowup (A4/disconfirming) | Subset theorem carries the paper if SMT underdelivers; bounded-depth fallback; report limits honestly |
| CFP timing | Verify Dev Mtg CFP date this week; M1 scoped to fit |

## 11. Next actions (by 2026-07-24)

1. Verify LLVM Dev Mtg 2026 CFP deadline; back-schedule M1.
2. Settle scope/authorship with Quinn (and Lucid, per NOTICE) — blocks all public artifacts.
3. Implement party-label attributes + placement check over `VerifyNonInterference.cpp`.
4. Variable-time-op rule with target-parameterized op list; Barrett rewrite skeleton.
5. Author the regression five-pack as lit tests (start by converting the 9 hand traces).
6. Pin HEIR commit; get mlir-tv building; smoke-test its encoder on a small linalg kernel.
7. Open the HEIR discussion issue (verification layer, referencing the upstream-SMT RFC interest) — after item 2.
8. Roll the landscape note's "Remaining homework" into the related-work backlog (KyberSlash catchability table, Concrete depth, HEIR governance check, watch PR #166702).
9. Pick a project name before anything public (candidate: TAPIR — Tensor A̶c̶t̶o̶r̶ Party IR — naming the party-labeled verifier something pronounceable).

## 12. Path to 8–9 — what actually moves the scores (added 2026-07-10)

Current honest grades: innovation $\approx$ 7 (defensible first combination + 2–3 genuinely new components), usefulness $\approx$ 6.5–7 (HEIR ecosystem + research community now; broad value rides the MLIR adoption curve). The gap to 9 is not architecture — it's **evidence type**: a demonstrated attack class, a reused theorem, or adoption by a system that matters.

**Innovation levers (ranked):**
1. **Demonstrate the attack.** Promote M2's "$\geq 1$ real NI/CT-breaking lowering" from confirming evidence to centerpiece. Full version: correctly-CT MLIR kernel → standard pipeline → measurable secret-dependent timing on real hardware → key-bit recovery. Hunt where equivalence-TV is provably blind: (a) trace-level breaks (select→branch, introduced data-dependent control flow), (b) refinement gaps (bufferization resolving uninit memory/aliasing secret-dependently), (c) observability-boundary changes (secret intermediates exposed as buffers). Fallback demo if upstream MLIR is clean: the MLIR→LLVM -O3 boundary (Breaking Bad class), caught by the obligations ledger. This is the CSF→S&P upgrade; the Alive2/Chen-et-al. precedent — the bugs make the fame, not the tool.
2. **Subset theorem as reusable infrastructure.** Syntactic criterion on arbitrary PatternRewriter rules $\implies$ preservation for *every* observation function in the family; mechanize on lean-mlir; ship as a linter pass authors run. Pitch: "the Alive2 discipline for hyperproperties." Also the hedge if the bug hunt comes up dry.
3. **First verified two-owner artifact.** Real small model, weights $\perp$ inputs mutually secret, machine-checked end-to-end — the capability HEIR/HECO/SPU structurally can't express.

**Usefulness levers (ranked):**
1. **Catch the real KyberSlash in the real C.** Polygeist-import pq-crystals `poly.c`, flag the exact division dda29cc fixed, show the patch passes. Kills limit §7.9 in one demo. Then Bernstein-style scale: PQClean/SUPERCOP arithmetic-kernel subset, report "scanned N, flagged M." **Spike Polygeist fidelity 1–2 weeks, early** — risk retirement before narrative commitment.
2. **One real project running it in CI.** HEIR non-blocking CI job over their examples is already a citable adoption fact; gated on the Quinn/Lucid authorship item.
3. **Annotation burden + runnable witnesses.** Inference-by-default targeting 1–3 annotations on real pipelines (beat Viaduct's 3–12); FP rate as first-class metric; counterexamples as runnable harnesses (input pair + observable diff), not SAT models. Discharge the ledger end-to-end once (DIT on Apple silicon; ct.select when ToB lands) — ToB as distribution channel, same audience.

**Doesn't move either score:** full FLAM generality, more dialect coverage, placement inference (M4), deeper related work, mechanizing the tool instead of the theorem.

**Reordering consequence:** M2 bug hunt gets real calendar time as the centerpiece; Polygeist spike enters M1–M2; HEIR engagement moves directly behind the authorship conversation. Outcome-contingent honesty: bug must exist, Polygeist must work on the kernels, HEIR must say yes — three empirical bets, theory paper as the floor.

## 13. Target vulnerability catalog — the 9/9 kill list (added 2026-07-10)

*Full threat-model + attack taxonomy (classes A–J), cannot-prevent list, and 4-corpus benchmark harness now live in [[Actor-Based IFC for Tensor MLIR — Threat Model & Attack Harness]]. Summary kill list below.*

**Strategic principle:** the two scores need different vuln sets. Innovation ← compiler-introduced (pass breaks source CT, invisible to equivalence-TV) OR structurally-inexpressible-elsewhere (multi-owner). Usefulness ← real CVEs in real code, caught statically.

**Load-bearing reframe:** lattice PQC *is* tensor computation — NTT, poly mult, coefficient-wise Barrett/Montgomery reduction are linalg/vector/tensor ops. So KyberSlash / Clangover / HQC live natively at tensor-MLIR altitude. "Why tensor MLIR" is therefore not only ML model weights — the *cryptography itself* is tensor-shaped, and the timing bugs are in the vectorized arithmetic. Upgrades usefulness from "ML-privacy tool" to "where PQC constant-time verification belongs."

**Flagship demos (these *are* the 9/9, not the full coverage):**
1. **Clangover at MLIR** (innovation crown) — real 2024 compiler-introduced ML-KEM leak: Clang lowered constant-time `poly_frommsg` cmov → secret-dependent branch, full ML-KEM-512 key in ~10 min on Intel. Reproduce the select→branch break in an MLIR pipeline; L3 preservation rejects it. Equivalence-TV is blind to it. ✅ verified 2026-07-10. [L3, $O^{\text{ct}}$]
2. **KyberSlash in real pq-crystals C** (usefulness crown) — Polygeist-import `poly.c`, flag the division dda29cc fixed, show patch passes; scale over PQClean/SUPERCOP arithmetic kernels ("scanned N, flagged M"). [L1+L3, $O^{\text{ct}}$]
3. **Two-owner private inference** (structural novelty) — weights $\perp$ inputs mutually secret, machine-checked; HEIR's one-bit `secret<T>` can't express it. [L1, $O^{\text{out}}$]
4. **Embedding lookup on secret token IDs** (tensor-native bridge) — `tensor.gather` on secret index = cache channel that only exists at tensor altitude (LLVM shatters it to GEPs); unifies ML-privacy + crypto-CT in one op. [L1, $O^{\text{ct}}$]
5. **HQC CVE-2025-52473** (generality) — second, 2025, Clang-optimization-dependent PQC branch leak, full key recovery, fixed liboqs 0.14.0; proves not a Kyber one-off. ✅ verified 2026-07-10. [L1+L3, $O^{\text{ct}}$]

**Full catalog (7 classes):**
| # | Class | Instances | Layer / ObsFn | Score |
|---|---|---|---|---|
| 1 | Var-time **arithmetic** (div/rem/mod on secret) | KyberSlash1/2 ✅, Barrett/Montgomery bugs | L1+L3 / $O^{\text{ct}}$ | Usefulness |
| 2 | Secret **control flow / branch** | Clangover ✅, HQC CVE-2025-52473 ✅, Dilithium/Falcon rejection sampling ○, Lucky13 ○, conditional subtraction | L1 mux / $O^{\text{ct}}$ | Both |
| 3 | Secret **memory access / cache** | AES T-tables ○, embedding-on-secret-tokens, RSA modexp tables ○, secret gather | L1+oblivious rewrite / $O^{\text{ct}}$ | Both |
| 4 | **Compiler-introduced** (lowering breaks CT) | Clangover ✅, HQC ✅, Breaking Bad ○, Chen et al. ✅; DCE-removes-mask, strength-reduction, bufferization-exposes-buffer | **L3** / $O^{\text{ct}}, O^{\text{out}}$ | **Innovation crown** |
| 5 | **Cross-party placement** | FHE client→server cleartext, missing-encrypt egress, debug reveal, two-owner, model-weight leak | L1 / $O^{\text{out}}$ | Both |
| 6 | **Declassification** bugs | unconditioned declassify, CKKS approx-decrypt leakage ○, robust-declass violation | L1 NMIFC / $O^{\text{out}}$ | Innovation |
| 7 | **Hardware-assisted** (flag only) | GoFetch ✅ (Apple 120309), Augury ○ | L4 obligation / $O^{\text{hw}}$ | honesty |

**Must-refuse (overclaim = score drops to 6):** GoFetch/DMP (flag, never prevent — defeats correct CT code; DIT only on M3+), speculation/Spectre (v1 out), physical/power/EM/HertzBleed (constant-cycle $\neq$ constant-power), traffic analysis (ciphertext sizes/rounds — ideal-crypto assumption), below-IR (regalloc, hand asm, OpenFHE/Lattigo/TFHE-rs backends — where Clangover itself happened; L4 + ToB ct.select lowering target address this).

**Bottom line:** 9/9 rests on Class 4 (innovation) + Class 1 (usefulness), heroes Clangover + KyberSlash — both confirmed real, key-recovering, post-quantum, tensor-expressible. Not hypothetical bugs: the ones that shipped in NIST-standardized reference code. Classes 2/3/5 = eval breadth; 6 = smaller innovation nugget; 7 = reviewer-trust discipline.

Sources verified this session: [Clangover / poly_frommsg](https://pqshield.com/pqshield-plugs-timing-leaks-in-kyber-ml-kem-to-improve-pqc-implementation-maturity/) · [HQC CVE-2025-52473](https://www.tenable.com/cve/CVE-2025-52473).

## 14. Sources

Internal: [[Actor-Based IFC for Tensor MLIR — Competitive Landscape]] · [[Viaduct — Mechanics and Innovation Angles]] · `~/code/aisec-invariants-mlir` (README, `docs/SPS-proj-proposal_compiler-confidentiality.pdf`, `docs/embedding-model-extraction-threat-model.md`).
External anchors already verified in the landscape note: HEIR secret dialect · mlir-tv (CAV'22) · PLDI'25 verification dialects + upstream `smt` dialect · ToB ct.select PR #166702 · CT-LLVM (ePrint 2025/338) · KyberSlash countermeasures (ePrint 2024/1049) · GoFetch/Apple 120309 · Viaduct PLDI'21 + CSF'24 proof + AIRduct/Viaduct-HE · SPU (ATC'23) · Chen et al. (S&P'26).
Added here, ○ re-verify before citing: Barthe et al. self-composition (CSFW'04) · ct-verif leakage models (USENIX Sec'16) · Li–Micciancio CKKS attack (Eurocrypt'21) · Hertzbleed (USENIX Sec'22) · Jancar et al. usability study (S&P'22) · Troupe · Polygeist · Cortex-M early-termination multipliers.
