# Actor-Based IFC for Tensor MLIR — Competitive Landscape

*Compiled 2026-07-08 from a 105-agent deep-research sweep: 5 search angles → 23 primary sources → 114 extracted claims → top 25 adversarially verified (3-vote panels; 25/25 confirmed, 0 refuted), plus three live re-checks the same day.*

**Confidence legend** (marked per project):
- ✅ adversarially verified against primary sources (3-0 vote panels)
- 📄 primary-source extraction with verbatim quotes, no adversarial pass
- ○ background characterization from general knowledge — re-verify citations before putting in a paper

**The project being positioned:** actor/party-aware information-flow control for tensor-based MLIR — secrets as party-labeled types (FHE client/server: client secrets must never reach the server in cleartext), SMT-verified non-interference in the mlir-tv style, covering both secret mishandling and timing side channels (KyberSlash, Apple DIT/GoFetch). Generalizes `~/code/aisec-invariants-mlir` (taint-walk non-interference verifier over HEIR's `secret` dialect for model weights) and Quinn's self-composition translation-validation proposal.

---

## Verdict and comparison matrix

**The intersection is unoccupied; every individual axis is crowded.** No system combines tensor-level MLIR + party-labeled secrets + SMT-verified non-interference + timing obligations. Defensible novelty claim: *first information-flow verifier for tensor-level MLIR with party-labeled secrets and SMT-checked non-interference (including preservation under lowering), unifying FHE secret-placement and timing-channel obligations.*

| Project | Level | Secret types on tensors | Parties / placement | SMT / formal verification | Timing channels | Confidence |
|---|---|---|---|---|---|---|
| HEIR | MLIR (tensor) | ✔ `secret<T>` | ✗ | ✗ | ✗ | ✅ |
| HECO | MLIR (tensor) | ✔ `secret<T>`, `batchedsecret<T>` | ✗ | ✗ | ✗ | ✅ |
| SecretFlow-SPU | MLIR (tensor) | ✔ visibility-typed | ✔ named parties (asserted) | ✗ | ✗ | ✅ |
| Zama Concrete | MLIR | ✔ encrypted-int ops/types | ✗ | ✗ | ✗ | 📄 |
| mlir-tv | MLIR (tensor) | ✗ | ✗ | ✔ (functional refinement only) | ✗ | ✅ |
| PLDI'25 verif dialects / xdsl-smt | MLIR (scalar) | ✗ | ✗ | ✔ (functional only) | ✗ | ✅ |
| Trail of Bits ct.select | Clang/LLVM IR/backend | ✗ | ✗ | ✗ | ✔ preservation (selection only) | 📄✦ |
| CT-LLVM | LLVM IR | ✗ | ✗ | ✗ (dataflow) | ✔ detection | 📄 |
| ct-verif | LLVM IR | ✗ | ✗ | ✔ (product programs) | ✔ | ○ |
| Constantine / SC-Eliminator / CaSym | LLVM IR | ✗ | ✗ | partial | ✔ mitigation/detection | ○ |
| Pitchfork / Binsec/Rel | binary | ✗ | ✗ | ✔ symbolic | ✔ (incl. speculation) | ○ |
| TIMECOP / dudect / patched Valgrind | binary, dynamic | ✗ | ✗ | ✗ | ✔ detection | 📄/○ |
| FaCT | DSL → LLVM | ✔ (scalar/array) | ✗ | Z3 side-conditions only | ✔ by construction | 📄 |
| CT-Wasm / SecWasm | Wasm | ✔ (scalar) | ✗ | ✔ mechanized (CT-Wasm) | ✔ / ✗ | ○ |
| Jasmin | asm DSL | ✔ | ✗ | ✔ EasyCrypt | ✔ preservation | ○ |
| CompCert-CT | C → asm | ✗ (analysis input) | ✗ | ✔ Coq | ✔ preservation | ○ |
| Viaduct | custom language | ✗ (scalar labels) | ✔ label-driven placement | Z3 for cost only; UC paper proof | ✗ explicitly excluded | 📄 |
| AIRduct / Viaduct-HE | array IR | ✔ (arrays, planned) | ✔ | ✗ | ✗ | 📄✦ |
| EzPC / CrypTFlow | TF graph → DSL | ✔ (implicit) | ✔ 2PC/3PC | ✗ | ✗ | 📄 |
| Google FHE transpiler | C++ → XLS IR | ✗ (all-encrypted) | fixed client/server | ✗ | by construction | 📄 |
| EVA / CHET / nGraph-HE | tensor DSL/graph | ✔ (implicit, all-encrypted) | ✗ | ✗ | ✗ | ○ |
| MP-SPDZ | bytecode DSL | ✔ `sint`/`sfix` | ✔ runtime protocol | ✗ | ✗ | ○ |
| JIF / Fabric / DStar | Java / OS | ✗ | ✔ (labels, hosts) | ✗ | ✗ | ○ |
| **Proposed project** | **MLIR (tensor)** | **✔ party-labeled** | **✔ verified** | **✔ SMT non-interference** | **✔ obligations** | — |

✦ = re-checked live on 2026-07-08.

What this table forbids you from claiming: "first secret types on tensors" (HEIR/HECO/SPU), "first multi-party MLIR" (SPU), "first actor-based IFC compiler" (Viaduct), "first SMT on MLIR" (mlir-tv), "first constant-time compiler support" (FaCT/ToB). What no row has: *verification* of the security property itself — everyone compiles, optimizes, asserts, or preserves; nobody detects **and** proves.

---

## Part I — MLIR ecosystem ✅ (adversarially verified)

### 1. google/heir — the substrate ✅
**What:** Google's MLIR-based FHE compiler; the `secret` dialect is its scheme-agnostic entry point. `secret<T>` wraps any type incl. tensors (`!secret.secret<tensor<8xi16>>`, frontend `Secret[Tensor[1024, I16]]`); `secret.generic` lifts cleartext computation; lowered via `secret-distribute-generic` → BGV/CGGI scheme dialects.
**Parties:** none — binary secret/cleartext; public values aren't even labeled (referenced from enclosing scope). Paper greps: 'party'/'MPC'/'threat model'/'attacker'/'adversary' = 0. Client/server exists only as codegen (`lwe-add-client-interface` emits enc/dec helpers).
**Verification:** none of any kind — no SMT/Z3/CVC5 anywhere in the repo (checked at 2025-03-18 commit and at main, 3,388 files, 2026-07-08); correctness machinery is empirical (noise-debug instrumentation, plaintext reference backend, noise models). Zero occurrences of non-interference/leak/taint/timing/constant-time in design doc and paper.
**Timing:** not addressed.
**Notes:** absorbed HECO's complete functionality (insert-rotate, rotate-and-reduce). Adoption: Google TPU v6e, Intel HERACLES, Niobium BASALISC, Belfort FPGA; backends OpenFHE, Lattigo, TFHE-rs, Jaxite. Maintainer Jeremy Kun on the upstream-SMT RFC (2025-03-18): "I'd be interested in using this for HEIR, in the long term" → **most likely fast follower, best collaboration/upstreaming path**. LLVM-incubator status **not confirmed** — don't cite it as one. Talks all at FHE.org (2023/2024/2025), never LLVM Dev Mtg.
**Gap vs you:** no parties, no verification, no timing — you are the verification layer it lacks.
Sources: [secret dialect design](https://heir.dev/docs/design/secret/) · [arXiv:2508.11095](https://arxiv.org/abs/2508.11095) · [dialect docs](https://heir.dev/docs/dialects/secret/) · [talks page](https://heir.dev/docs/tutorials/)

### 2. HECO (ETH Zurich, USENIX Security 2023) ✅
**What:** end-to-end MLIR FHE compiler (dialects `heco::fhe/bfv/bgv/ckks` + `mlir::tensor/arith/affine`); Python frontend needs only `Tensor[8, Secret[int]]` annotations; headline contribution is automatic batching/SIMD (up to 3500× over naive).
**Secret types:** yes — `secret<T>`/`batchedsecret<T>` — but they drive batching optimization and scheme lowering, **not security checking**. 19-page paper: 0 hits for side channel/timing/constant-time/non-interference/information flow/taint/SMT. Confidentiality argument = "FHE is inherently data-independent."
**Parties:** single-actor outsourced compute; threshold-FHE appears only as an application scenario.
**Status:** consolidated into HEIR; original Python frontend deprecated (xDSL frontend); BGV/CKKS dialects paper-described but absent from released repo.
**Gap vs you:** strengthens the prior-art baseline for FHE secret types in MLIR; leaves verification, parties, timing empty.
Sources: [USENIX Sec'23](https://www.usenix.org/conference/usenixsecurity23/presentation/viand) · [arXiv:2202.01649](https://arxiv.org/abs/2202.01649)

### 3. SecretFlow-SPU (Ant Group, USENIX ATC 2023) — closest structural competitor ✅
**What:** MPC runtime + compiler; PPHLO is "a new MLIR dialect for MPC computations" derived from XLA HLO, consuming JAX/TF/PyTorch. Every tensor typed $\langle$ Shape, DataType, **Visibility** $\rangle$, visibility $\in$ {secret, public}: `tensor<4x!pphlo.sec<i32>>` (today `!pphlo.secret<i32>`, public implicit). Visibility-propagation rules ("one secret operand → secret result") and MPC optimizations as MLIR passes. Performance paper: up to 4.1× faster than MP-SPDZ.
**Parties:** yes — the only surveyed MLIR system with named parties. P1/P2 (Alice/Bob) contribute secret shares via `@ppd.device("P1")` decorators; pluggable 2/3/N-party protocols (Cheetah, ABY3, SPDZ2k) set the threat model at runtime.
**Verification:** none — visibility/placement is *user-asserted annotation*, never inferred or checked. Full-paper grep: 0 hits for SMT/solver/verif*/non-interference/theorem/timing/constant-time/information-flow/label/taint. Security rests entirely on the MPC protocols' proofs. Sole "channel" mention criticizes TEEs.
**Gap vs you:** the asserted-vs-verified distinction. Your differentiators: verified label flow, SMT-checked non-interference, FHE client/server placement, timing coverage.
Sources: [ATC'23 paper](https://www.usenix.org/conference/atc23/presentation/ma) · [github.com/secretflow/spu](https://github.com/secretflow/spu)

### 4. Zama Concrete 📄
**What:** Zama's MLIR-based FHE (TFHE) compiler with dedicated encrypted-integer ops (e.g. `add_eint`) — cited in HEIR's design doc as the design contrast (dedicated ops force reimplementing canonicalization; HEIR chose generic wrappers instead).
**Assessment:** encrypted values are type-distinguished, single client/server arrangement, no IFC verification component surfaced. Lighter coverage in this sweep — characterize in depth before citing as more than "MLIR FHE compiler with typed encrypted values."

### 5. mlir-tv (Bang, Nam, Chun, Jhoo, Lee — CAV 2022) — your methodological precedent ✅
**What:** "the first SMT-based translation validation for MLIR" (Z3 / cvc5), modeled on Alive2, targeting exactly your altitude: **tosa, linalg, tensor, memref, arith**. Checks per-input functional refinement $f_{\text{src}}(I) \sqsupseteq f_{\text{tgt}}(I)$ between a pass's before/after programs; already encodes `linalg.generic` and tensor ops into SMT.
**Security content:** zero — paper and README have no mention of secrets, IFC, non-interference, constant-time, actors. No security follow-up exists (v1.0.0 Oct 2024; follow-on work treats it as correctness-only TV).
**Gap vs you:** supplies the machinery (tensor/memref SMT encodings, refinement discipline) that Quinn's proposal extends to a relational 2-safety property; occupies none of the niche.
Sources: [CAV'22](https://link.springer.com/chapter/10.1007/978-3-031-13188-2_19) · [github.com/aqjune/mlir-tv](https://github.com/aqjune/mlir-tv)

### 6. First-Class Verification Dialects for MLIR (Fehr, Fan, Pompougnac, Regehr, Grosser — PLDI 2025) + upstream `smt` dialect ✅
**What:** semantic dialects (`smt`, `smt_int`, `smt_bv`) + three tools: translation validation (found 5 miscompilation bugs in MLIR's canonicalize), once-and-for-all peephole verification, dataflow transfer-function soundness proofs.
**Scope limits:** semantics only for **control-flow-free integer ops** — 26 arith + 20 comb ops, plus func/builtin/memref; no loops, no floats, **no tensor/linalg/tosa** (still true of xdsl-smt, July 2026). Zero genuine hits for information flow/non-interference/secret/side channel/constant-time/taint/hyperproperty/relational/2-safety/multi-party/FHE.
**Upstream milestone:** CIRCT's **SMT dialect merged into llvm/llvm-project 2025-04-11** ([PR #131480](https://github.com/llvm/llvm-project/pull/131480)) — bool/bitvector/int/array theories, quantifiers, `smt.check_sat`, SMT-LIB export (`verif` dialect stayed in CIRCT). RFC frames applications as LEC, BMC, "translation validation much like Alive2"; no IFC mention anywhere in the thread.
**Gap vs you:** scalar-level, functional-correctness-only — but it means SMT formula representation is now upstream MLIR infrastructure you get for free.
Sources: [PLDI'25 paper](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf) · [xdsl-smt](https://github.com/opencompl/xdsl-smt) · [SMT dialect docs](https://mlir.llvm.org/docs/Dialects/SMT/) · [upstreaming RFC](https://discourse.llvm.org/t/rfc-upstreaming-circts-verif-and-smt-dialects/85299)

### 7. Upstream MLIR taint/IFC status ✅
The 2022 dataflow-framework RFC mentions taint analysis only as unnamed "ongoing work" (a sparse+dense analysis client); nothing shipped since — no security dataflow pass in upstream MLIR surfaced anywhere in this sweep. The niche is empty upstream too.
Source: [dataflow framework RFC](https://discourse.llvm.org/t/rfc-a-dataflow-analysis-framework/63340)

---

## Part II — LLVM/Clang constant-time & side-channel tooling

### 8. Trail of Bits constant-time support (`__builtin_ct_select` / `llvm.ct.select`) 📄✦
**What:** the ecosystem's active upstream effort. Stack: Clang builtin → `llvm.ct.select` intrinsic → `ctselect` machine pseudo, expanded **post-register-allocation** to CMOV (x86-64) / CSEL (AArch64), bitwise ops on Arm32/i386, SelectionDAG bitwise fallback (RISC-V/Wasm/MIPS). Acts as an optimization barrier. DARPA-funded, with ETH Zurich's System Security Group; tested against HACL*, Fiat-Crypto, BoringSSL.
**Timeline:** RFC 2025-08-08 → LLVM Dev Mtg quick talk 2025-10-27 (Julius Alexandre) → blog 2025-12-02 → ✦ **[PR #166702](https://github.com/llvm/llvm-project/pull/166702) still open as of 2026-07-08**, root of a 7-PR stacked series (Clang frontend + per-arch backends). Not in any shipped LLVM release.
**Scope limits (their own words):** *preservation, not detection* — "not to detect when data-dependent timing variances are introduced"; keeps already-CT code CT through optimization. Selection only; **ct arithmetic — the KyberSlash class — explicitly future work** (`__builtin_ct<op>`, `__builtin_ct_expr`, memory/string ops). No secret types: reviewer efriedma-quic argued for a first-class "constant-time value" IR type (cf. Rust RFC 2859); deferred. **ARM DIT / Intel DOIT explicitly out of scope**, pushed to library/OS level.
**Evidence they cite:** "Breaking Bad" ETH study (compilers systematically break source-level CT; blog says 19 libraries/5 compilers, slides say 8 libraries/44,604 experiments — reconcile before citing); CVE-2022-4304 (OpenSSL RSA), CVE-2021-38153 (Kafka), CVE-2023-5388 (NSS); ML-KEM mod-3329 reduction appears as a motivating workload in the RFC thread.
**Gap vs you:** scalar altitude, preservation-only, no parties, no verification — complementary (a lowering target for your pipeline). Risk: if they land ct-arithmetic + a secret IR type, part of the "compiler prevents KyberSlash" story gets told at LLVM level.
Sources: [RFC](https://discourse.llvm.org/t/rfc-constant-time-coding-support/87781) · [blog](https://blog.trailofbits.com/2025/12/02/introducing-constant-time-support-for-llvm-to-protect-cryptographic-code/) · [Dev Mtg slides](https://llvm.org/devmtg/2025-10/slides/quick_talks/alexandre.pdf)

### 9. CT-LLVM (ePrint 2025/338, Feb 2025) 📄
**What:** LLVM plugin, thin layer over standard def-use + alias analyses. Property: no secret-dependent data-flow, control-flow, **or variable-timing operation** — KyberSlash's secret-dependent division is squarely in scope. Evaluated on 9 crypto libraries: soundly auto-analyzes ~36% of functions, proves 61% of those CT, found new vulnerabilities; explicitly targets compiler-introduced CT violations by checking post-compilation IR.
**Framing:** motivated by Jancar et al. (IEEE S&P 2022) — dozens of CT tools exist but are seldom used due to usability; CT-LLVM's pitch is usability, not property expressiveness.
**Gap vs you:** LLVM-IR dataflow, no SMT, no types, no parties, no tensors — and its ~36% auto-coverage is a quantifiable gap a type-level approach can attack.
Source: [ePrint 2025/338](https://eprint.iacr.org/2025/338)

### 10. KyberSlash countermeasures (Bernstein et al., ePrint 2024/1049, TCHES 2025) 📄
**What the attack was:** secret-dependent division timings in several Kyber/ML-KEM implementations *including the official reference code* (fixed in pq-crystals/kyber commit dda29cc); key recovery in minutes (KyberSlash2) to hours (KyberSlash1) on Cortex-A7 / Cortex-M4.
**Their countermeasures — your motivation section:** (1) a **patched Valgrind** detecting variable-time instructions on secret data (TIMECOP-style dynamic taint), run over 1000+ SUPERCOP implementations, multiple new findings — dynamic, binary-level, post-hoc; (2) an explicit proposal for a **formal-methods approach to guarantee absence of variable-time instructions** — i.e., the discoverers themselves call for exactly the static guarantee you're building.
Source: [ePrint 2024/1049](https://eprint.iacr.org/2024/1049)

### 11. Legacy constant-time tool landscape ○ (background — re-verify before citing)
| Tool | Approach | Level |
|---|---|---|
| ct-verif (USENIX Sec 2016) | product programs / self-composition via SMACK+Boogie, sound verification | LLVM IR |
| Constantine (CCS 2021) | control- and data-flow linearization (execute both paths) — mitigation | LLVM IR |
| SC-Eliminator (ISSTA 2018) | transform out cache-timing leaks | LLVM IR |
| CaSym (S&P 2019) | cache-aware symbolic execution | LLVM IR |
| Pitchfork (PLDI 2020, Cauligi et al.) | CT under speculation (Spectre-aware), symbolic | binary |
| Binsec/Rel (S&P 2020) | relational symbolic execution for CT | binary |
| TIMECOP (SUPERCOP) | Valgrind memcheck with secrets marked uninitialized | binary, dynamic |
| dudect (2017) | statistical timing measurement | binary, dynamic |
| DataFlowSanitizer | general dynamic taint labels | LLVM instrumentation |
| Clang Static Analyzer taint | source-level generic taint checker, not CT-aware | AST |
| Speculative Load Hardening | Spectre v1 mitigation flag | LLVM |
None are tensor-level, none model parties, none verify at MLIR altitude; the verification-capable ones (ct-verif, Binsec/Rel) operate on scalar IR/binaries where tensor structure is gone — which is exactly your "Why MLIR" argument (README's point: at LLVM the tensor is shattered into GEPs and the analysis becomes whole-program pointer analysis).

### 12. GoFetch / Apple DIT — a framing constraint, not a competitor 📄
GoFetch (USENIX Security 2024; Apple guidance = support article 120309) extracts keys from **correctly constant-time code**: the data memory-dependent prefetcher (DMP) issues secret-dependent accesses on the victim's behalf. End-to-end on M1; exploitable DMP activation on M2/M3; Intel Raptor Lake has a DMP too. Victims included CRYSTALS-Kyber and Dilithium.
**Consequence for your claims:** IR-level non-interference **cannot by itself** rule out this class. The compiler-enforceable obligation is "DIT/DOIT bit set around secret-handling code" (DIT disables the DMP only on M3). → Model DIT as an explicit obligation your actor-IFC emits/discharges; never claim IR-level IFC "prevents GoFetch."
Source: [gofetch.fail](https://gofetch.fail/)

---

## Part III — Secret-typed languages lowering through LLVM

### 13. FaCT (PLDI 2019) 📄
**What:** C-like DSL with a binary public/secret label lattice, compiled type-directed to constant-time LLVM bitcode. The type checker statically forces memory indices, loop bounds, and **operands of variable-time instructions (integer division!) to be secret-independent** — KyberSlash-class bugs rejected *by construction*, but only for code rewritten in FaCT.
**Limits:** the proven CT guarantee applies **only to unoptimized emitted IR**; clang-optimized output is only empirically checked with dudect. Z3 discharges public-safety side conditions (bounds, div-by-zero, shift width), not the security property (that's a paper proof, Thm 4.3). Evaluation: 7 hand-ported routines (~2400 LoC) from OpenSSL/libsodium/curve25519-donna. Scalar/array DSL — no tensors, parties, or MLIR.
Source: [PLDI'19](https://dl.acm.org/doi/10.1145/3314221.3314605)

### 14. CT-Wasm / SecWasm ○
CT-Wasm (POPL 2019): WebAssembly extension with secret types and mechanized (Coq) CT soundness — scalar Wasm, no placement. SecWasm (SAS 2022): general IFC for Wasm, no lowering-preservation story (as Quinn's proposal already notes).

### 15. Jasmin ○
Assembly-like verified crypto DSL (CCS 2017 +): EasyCrypt-verified, with **constant-time preservation proofs down to assembly** — the gold standard for the *preservation* property, but for hand-written scalar crypto kernels, not ML/tensor compilation, and not MLIR. Cite in the lowering-preservation related-work section.

### 16. CompCert-CT (POPL 2020) ○
Formally verified (Coq) proof that CompCert's passes **preserve cryptographic constant-time** — the strongest existing "non-interference-like property preserved under compilation" result. C-level, scalar, whole-compiler proof rather than per-run translation validation; the natural theory citation for Quinn's TV-of-NI framing (TV trades the once-and-for-all proof for per-compilation checking on a modern IR).

### 17. Rust ecosystem: `subtle`, `secret_integers`, RFC 2859 ○
Library-level CT idioms (`Choice` types) and a postponed "secret types" language RFC — referenced in the ToB RFC discussion as the design LLVM lacks. Evidence the demand exists at the language level; no verification, no tensors.

---

## Part IV — Actor/party-based IFC and privacy-preserving compilers

### 18. Viaduct (Cornell — Acay, Recto, Gancher, Myers, Shi; PLDI 2021) — closest conceptual competitor 📄
**What:** *the* prior art for your "actor-based" framing. Source programs carry information-flow labels; the compiler synthesizes secure distributed programs across **mutually distrusting hosts**, selecting protocols per component: cleartext/replication, ABY 2-party MPC, SHA-256 commitments, libsnark ZKP. Label inference via Rehof–Mogensen fixed point; claims to be the first system compiling secure distributed programs with an *extensible* suite of cryptography (new protocols = authority labels + interfaces).
**Gaps vs you (all load-bearing):**
- **Timing explicitly outside the threat model**: "the rule for conditional statements does not require branches to have the same timing behavior" → could not catch KyberSlash.
- **Z3 used only for protocol-selection cost optimization**, not verification; assurance is a paper UC-simulation proof about the compiler, with no checking of actual compiled output.
- **No FHE backend**; custom scalar imperative language (~20 KLoC Kotlin, ANF IR) — no tensors, no MLIR.
**Defensibility warning:** Viaduct's extensibility makes "Viaduct + FHE backend" a plausible fast-follow. Durable moats: MLIR/tensor substrate, SMT-verified NI of emitted code, timing obligations.
Source: [PLDI'21 paper](https://www.cs.cornell.edu/andru/papers/viaduct/viaduct.pdf)

### 19. AIRduct (FCS 2023 / arXiv:2409.01587) and Viaduct-HE (arXiv:2311.06142) 📄✦
**AIRduct:** array-based IR intended as Viaduct's new IR, targeting interactive programs mixing MPC, ZKP, **and FHE**; loop-free/conditional-free array programs as the mid-level abstraction for vectorization; variables carry storage formats describing distribution across hosts. Status: replication + ABY integrated; **ZKP/FHE aspirational**; full Viaduct integration WIP; never mentions MLIR; security still via the external UC proof; no timing.
**Viaduct-HE:** same lineage — array programs → vectorized HE with schedule/layout search; an *optimization* compiler, no IFC verification. ✦
**Read:** the Cornell group is visibly walking toward "arrays + FHE + labels." **This is the group most likely to converge on your niche. Move fast; cite generously; differentiate on verification + timing + MLIR.**

### 20. EzPC / CrypTFlow (Microsoft Research) 📄
**What:** end-to-end TF/ONNX → semi-honest MPC (Athos frontend; SCI 2PC; Porthos 3PC) — party-aware secure *tensor* compilation at ML-framework level, ImageNet-scale (ResNet-50, DenseNet-121). Own DSL as IR; repo has no mention of MLIR, LLVM, SMT, or timing analysis.
**Venue signal:** EuroS&P'19, S&P'20/'21/'22/'24, CCS'20, USENIX Sec'23, PoPETS'24 — the secure-ML compiler publication cluster.
Source: [github.com/mpc-msri/EzPC](https://github.com/mpc-msri/EzPC)

### 21. Google FHE transpiler (ePrint 2021/811) 📄
**What:** C++ → **XLS IR** (hardware-design IR, not MLIR) → booleanized TFHE circuits. Exactly one fixed client/server arrangement (all compute statically server-side, honest-but-curious); no per-value secret tracking (everything the server touches is encrypted); no verification (the plaintext debug backend "provides no security guarantees"); data-independence **by construction** (no secret-dependent branching is expressible). Self-positioned as usability/portability among FHE compilers (vs Cingulata, E3, ALCHEMY, Marble, RAMPARTS, nGraph-HE, SEALion, CHET).
Source: [ePrint 2021/811](https://eprint.iacr.org/2021/811.pdf)

### 22. EVA / CHET / nGraph-HE ○
Microsoft's CHET (PLDI 2019: tensor programs → CKKS for NN inference) and EVA (PLDI 2020: CKKS compiler with automatic rescaling/waterline management), Intel's nGraph-HE (HE backend for an ML graph compiler). Tensor-level FHE compilation *pre-MLIR*: encrypted-by-default, single client/server, no IFC labels, no verification. Historical baseline for "tensor FHE compiler."

### 23. MP-SPDZ ○
The standard MPC framework benchmark (CCS 2020): Python-ish `.mpc` DSL with `sint`/`sfix` secret types compiled to bytecode for ~40 protocol variants. Secret types + runtime party model, no static placement verification, no MLIR/SMT/timing. (SPU's paper benchmarks against it.)

### 24. JIF / Fabric / DStar ○
The IFC heritage line: JIF (Java + decentralized labels), Fabric (distributed JIF with placement), DStar (OS-level distributed DIFC). Conceptual ancestors of "labels drive placement across distrusting nodes" — cite as lineage; none touch compilers for tensors, MLIR, or timing.

---

## Part V — Venue fit

**US LLVM Dev Mtg, Oct 26–28, 2026 — strong fit for a quick talk + poster:**
- Precedent 1: Alexander Viand, "Building an End-to-End Toolchain for FHE with MLIR," **Quick Talks, 2022 LLVM Dev Mtg** — explicitly discussed unifying MLIR FHE efforts and upstreaming ([video](https://www.youtube.com/watch?v=vjtPWZRxAkI)).
- Precedent 2: Julius Alexandre (ToB), "Constant-Time Coding Support in LLVM," **Quick Talks, 2025 US LLVM Dev Mtg**.
- Your topic is the intersection of two already-accepted talk categories, and HEIR itself doesn't present at LLVM meetings (FHE.org instead) — the slot is open.

**Papers — where the neighbors landed:** mlir-tv → CAV; Viaduct, FaCT, CHET/EVA, verification dialects → PLDI; HECO, GoFetch → USENIX Security; SPU → ATC; KyberSlash → TCHES via ePrint; secure-ML compilers → IEEE S&P/CCS; Quinn's proposal targeted **CSF** (Barthe-style NI tradition, deadlines ~Feb/May/Aug) with TACAS/FMCAD backup.
**Recommended split:** ePrint/arXiv preprint early (normal in this space — KyberSlash, CT-LLVM, FHE transpiler all did); theory/verification paper → CSF; the actor-based tensor-IFC *system* paper → OOPSLA/PLDI (Viaduct's home turf) or IEEE S&P if led by the attack-prevention story (Chen et al. S&P'26 "compiler as ML attack surface" precedent).

---

## Part VI — Threats to novelty & preemptions

1. **HEIR fast-follow** — maintainer wants SMT "long term." → Engage early; position as the verification layer HEIR lacks; aim for co-authorship/upstreaming.
2. **Cornell trajectory** (Viaduct → AIRduct → Viaduct-HE) — arrays + FHE + labels, verification still missing. → Publish the MLIR+SMT+timing combination first; cite and differentiate explicitly.
3. **Trail of Bits ct-arithmetic** — would cover KyberSlash-class *preservation* at scalar LLVM. → Frame yours as detection + verification at tensor altitude with parties; theirs as a lowering target.
4. **GoFetch overclaim risk** — IR-level NI provably insufficient on DMP hardware. → Emit DIT/DOIT as explicit dischargeable obligations; scope claims to program-level behavior.
5. **SPU rebuttal ("we have secret tensors with parties")** — → asserted vs. verified: their visibility labels are unchecked user input; yours carry an SMT-backed non-interference theorem.

## Remaining homework
- Per-tool KyberSlash-catchability table (ct-verif, Constantine, Pitchfork, Binsec/Rel, TIMECOP, dudect, CT-LLVM) for the paper's related work — the ○-marked rows above need primary-source verification.
- Zama Concrete type system in depth; CIRCT hardware-IFC prior art; Jasmin/CompCert-CT proofs (for the lowering-preservation section).
- Confirm HEIR governance (incubator or not) before any "LLVM ecosystem" positioning sentence.
- Watch [PR #166702](https://github.com/llvm/llvm-project/pull/166702) — if ct.select lands before October, cite it as landed, not in-flight.

## Method note
Deep-research workflow, 2026-07-08: scope decomposition → 5 parallel search agents → 23 primary sources fetched → 114 falsifiable claims extracted → top 25 verified by 3-vote adversarial panels (25 confirmed, 0 refuted; one 2-1 on a wording nuance) → synthesis. Category 1 (MLIR ecosystem) is exhaustively verified; categories 2–5 rest on primary-source extraction with verbatim quotes; ○ entries are background knowledge. Absence claims (e.g. "zero occurrences of non-interference in the HEIR repo") are mechanical greps of papers/repos as of 2026-07-08 and can be invalidated by any future commit.
