# LLVM Dev Mtg 2026 — Submission Kit

*Prepared 2026-07-13. Ready-to-paste proposal for the 2026 US LLVM Developers' Meeting. Companion to [[Actor-Based IFC for Tensor MLIR — Research Plan]], [[Actor-Based IFC for Tensor MLIR — Threat Model & Attack Harness]], [[Actor-Based IFC for Tensor MLIR — Competitive Landscape]].*

---

## ⏰ Hard facts (verified 2026-07-13 against the official CFP)

- **Deadline: July 14, 2026, end of day AoE** (≈ 5am PDT Wed July 15). ~36 hours from prep.
- **Notification: July 30, 2026.**
- **Meeting: October 26–28, 2026, Santa Clara, CA.**
- **Submit at: https://hotcrp.llvm.org/usllvm2026/** (blind to PC).
- CFP: https://discourse.llvm.org/t/2026-us-llvm-developers-meeting-call-for-proposals/91080

> ⚠️ The Research Plan assumed "CFP historically ~Aug." That was wrong — Next Action #1 ("verify CFP date") is now overtaken; the real deadline is July 14. Back-schedule M1 accordingly.

## 🚫 The one blocker before hitting submit

Research Plan Next Action #2: *settle scope/authorship with Quinn (and Lucid per NOTICE) — blocks all public artifacts.* **A HotCRP proposal with an author list IS that first public artifact.** Do not submit author names until cleared with Quinn. A minimal ask ("OK to co-submit an LLVM quick/technical talk?") is far smaller than settling full paper authorship and unblocks this without resolving everything.

---

## Format decision

**Submit a 20-minute Technical Talk, check "open to a shorter talk," and separately submit a Poster.**

- Rationale: the "open to shorter" checkbox makes the 20-min a free option — the PC down-converts to a Quick Talk rather than rejecting if they judge it thinner. Aim high, auto-fallback.
- The content (four-layer architecture + observation-function unification + party labels + preservation demo) is native to 20 min; 10 min forces gutting it to a single demo.
- Committing to **Tier 2** delivery (below) — the Clangover reproduction as hero demo — supports the Technical Talk maturity bar.
- Poster is a separate, non-competing, high-acceptance hedge.

---

## Title

**Primary:**
> **When Functional Equivalence Isn't Enough: Relational Security Verification and Translation Validation in MLIR**

**Alternatives:**
- *Preserving Non-Interference Across MLIR Lowerings: A Relational Approach to Security Translation Validation*
- *Catching Constant-Time Regressions in the MLIR Pipeline*
- *TAPIR: Party-Labeled Information-Flow Verification for Tensor MLIR* (only if launching the project name now — naming is Next Action #9)

---

## PC-facing abstract *(paste into the private abstract field)*

Compilers routinely break source-level security properties. The Clangover finding (2024) showed a Clang optimization turning a branchless, constant-time idiom in the ML-KEM reference implementation into a secret-dependent branch — enough to recover a full key. KyberSlash showed secret-dependent division shipping in reference lattice-crypto code. As cryptographic and privacy-preserving ML workloads increasingly compile through MLIR (HEIR, HECO, SPU), the question becomes: can we check, at the IR, that these properties hold — and that lowering preserves them?

Existing MLIR translation validation (mlir-tv, the PLDI'25 verification dialects) checks *functional* refinement: does the lowered program compute the same values? This is structurally blind to security regressions. An `arith.select` and a `cf.cond_br` on the same condition denote the same function — refinement holds — but emit different observable behavior; the leak is invisible to equivalence checking. Security is not a property of one execution but a *relation* between two (a 2-safety hyperproperty), so it needs different machinery.

This talk presents a relational security analysis for MLIR built on existing infrastructure. We model confidentiality as non-interference over an instrumented trace semantics, parameterized by an observation function (party-visible outputs for placement leaks; execution traces for the constant-time model). A lightweight dataflow/label checker over HEIR's `secret` dialect, extended with party labels, catches the common cases; self-composition lifted through the upstream `smt` dialect handles value-dependent flows the type system cannot decide; and a translation-validation pass checks that each lowering *preserves* the relation — the piece equivalence-only TV cannot express. We demonstrate (1) a pass rejecting a secret-dependent `arith.divsi` (KyberSlash-shaped) and offering a Barrett-reduction repair, and (2) the Clangover constant-time regression — the branchless ML-KEM idiom that a compiler turned into a secret-dependent branch, enabling full key recovery — reproduced across an MLIR→LLVM lowering: equivalence-based validation accepts it as correct, our relational validator rejects it and localizes the offending pass with a concrete two-input witness.

**Audience:** MLIR pass and dialect authors, anyone working on translation validation or the `smt`/verification dialects, and the FHE/secure-ML ecosystem. **Takeaways:** how to build a 2-safety analysis at tensor altitude using the upstream dataflow framework and `smt` dialect; why equivalence-preserving translation validation misses an entire class of regressions and what to do instead; and where IR-level guarantees honestly stop (hardware data-memory-dependent prefetch, backend lowering below the last verified IR) — surfaced as explicit obligations rather than silent assumptions.

**Outline (20 min):** (1) Two shipped compiler-introduced leaks: Clangover's ML-KEM key recovery and KyberSlash — 3 min. (2) Why functional equivalence ≠ security; the 2-safety framing and one relational model parameterized by an observation function (outputs vs. execution trace) — 5 min. (3) The architecture on MLIR: party labels over the `secret` dialect, self-composition lifted through the upstream `smt` dialect, and translation validation of *preservation* — 6 min. (4) Live: a secret-dependent `arith.divsi` rejected with a Barrett repair, and the reproduced Clangover `select`→`branch` regression that equivalence-based validation accepts and relational validation rejects, localized to the pass with a two-input witness — 4 min. (5) Where IR-level guarantees honestly stop — hardware DMP, backend lowering — surfaced as explicit obligations; roadmap — 2 min.

---

## Website abstract *(paste into the public abstract field — one paragraph)*

Compiler optimizations can silently break the constant-time and confidentiality properties that cryptographic and privacy-preserving code depends on — as the Clangover key-recovery finding on ML-KEM showed. MLIR translation validation today checks that lowering preserves *what a program computes*, but security depends on *how* it computes: a select and a branch are functionally equal yet leak differently. This talk shows how to check security properties as relational (2-safety) properties over MLIR — using the upstream dataflow framework and `smt` dialect plus HEIR's `secret` dialect — and how to validate that lowering *preserves* them, with a live demonstration that reproduces the Clangover constant-time regression — the compiler-introduced branch that broke ML-KEM — showing it accepted by equivalence-based validation and rejected by relational validation.

---

## Form fields

- **Submission type:** Technical Talk (20 min).
- **Open to a shorter talk?** **Yes.**
- **Authors:** ⟨FILL ONCE AUTHORSHIP CLEARED — see blocker⟩. Blind to PC.
- **Speaker bio** ⟨replace⟩: "⟨Name⟩ works on compiler infrastructure for security and cryptographic workloads, building on MLIR and the HEIR ecosystem. ⟨affiliation / prior work — e.g., zero-knowledge proof systems, lattice crypto⟩." 2–3 sentences; logistics, not a CV.
- **Speaker photo:** ⟨attach⟩.
- **Panel moderator question:** N/A (not a panel).
- **PC conflicts:** pull the committee list from HotCRP and mark collaborators — check specifically for Cornell/Viaduct people and HEIR/Google (Jeremy Kun).
- **Submission complete checkbox:** must tick, or they may not review.
- **Optional extended PDF abstract:** skip unless a diagram adds crisp value; not expected for a technical talk. The only place a repo link would ever go — but **no GitHub link or working code is required to submit.** This is an abstract-based CFP; work is expected to mature by the meeting, not the deadline.

---

## Pre-written answers to PC questions *(speaker notes / rebuttals)*

1. **"What's the reusable MLIR lesson?"** → A recipe for 2-safety analysis on MLIR (self-composition + `smt` dialect) and the demonstration that equivalence-preserving TV is insufficient for security — applies to any correctness/security dialect, not just FHE.
2. **"Isn't this just a research paper?"** → Deliverable is an `mlir-opt`-style pass with lit tests; extends the upstream `secret` dialect, uses the upstream `smt` dialect. Live demo, not slides-only.
3. **"Built vs. promised?"** → M1 (L1 checker + preservation catch) is the demo; full relational SMT core and the real-upstream-bug hunt are ongoing (not promised for October).
4. **"Why MLIR and not LLVM IR?"** → At LLVM IR the tensor is shattered into GEPs and a secret-indexed lookup becomes whole-program pointer analysis; the channel is only legible as a structured op at tensor altitude.
5. **"Relation to ToB constant-time / HEIR?"** → Complementary: ToB's `ct.select` (PR #166702) is a lowering target that *discharges* our obligations; HEIR is the substrate we verify. We're the detection + preservation layer neither provides.

---

## Honesty guardrails (keep the security-literate reviewer onside)

- Clangover is an **"MLIR→LLVM security-preservation"** demo, not "an MLIR bug" — the transform is in the LLVM backend; honest claim is "the same bug *expressed in MLIR* is caught," not "rediscovered in the reference C."
- Never "prevents side-channel attacks" unqualified — scope to the constant-time leakage model; GoFetch/DMP is flagged-by-obligation, never prevented.
- Don't claim "first SMT on MLIR" (mlir-tv owns it) — we *extend* it to a relational property.
- Say **party-labeled / principal-based**, not "actor-based" (collides with actor-concurrency; Viaduct community says hosts/principals).

---

## October delivery contract (what the abstract commits me to build)

**Tier 1 — Floor (guaranteed; M1, now → mid-Aug, ~2mo buffer before meeting):**
L1 detecting secret-dependent `arith.divsi` + Barrett repair; party labels; two-owner example; five-pack green; preservation mechanism on a constructed `select`→`branch` regression with two-input witness.

**Tier 2 — Hero (committed 2026-07-13; the centerpiece):**
Reproduce the *real* Clangover break in an MLIR→LLVM pipeline — import the ML-KEM `poly_frommsg` idiom, lower the branchless select into a secret-dependent branch, have preservation-TV reject exactly that lowering where equivalence-TV accepts. Controllable because it reproduces a *documented* transform, not an unknown one.

**Tier 3 — NOT in the contract (December / M2; roadmap slide only):**
Finding a *novel* NI/CT-breaking lowering in upstream MLIR or HEIR. Aim for it; do not promise it.

---

## Sources

- CFP: https://discourse.llvm.org/t/2026-us-llvm-developers-meeting-call-for-proposals/91080
- Meeting site: https://llvm.org/devmtg/2026-10/
- Submit: https://hotcrp.llvm.org/usllvm2026/
- Precedents (both Quick Talks, our intersection): Viand, "Building an End-to-End Toolchain for FHE with MLIR" (2022); Alexandre/ToB, "Constant-Time Coding Support in LLVM" (2025).
