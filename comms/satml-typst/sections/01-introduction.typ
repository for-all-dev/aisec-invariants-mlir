= Introduction

// OUTLINE ONLY — each bullet becomes a paragraph.

- Hook: the compiler is inside every deployed model's trust boundary, and
  nobody audits it for confidentiality — it can _introduce_ leaks the source
  never had, and (surprise finding) _remove_ leaks the source did have.
- The gap: side-channel work targets hand-written crypto kernels; verified
  compilation targets correctness, not secrecy; DL compilers
  (Inductor, MLIR pipelines, Polygeist) have neither.
- Two-sided thesis of the paper:
  - *Measure* — a differential eager-vs-compiled methodology attributes each
    observed channel to source or compiler (the 2×2,
    `docs/research/leak_check.methodology.siddharth.md`).
  - *Verify* — per-pass checked specifications where a lowering is safe only
    if it both computes the same thing _and_ preserves non-interference
    (`prototypes/fcvd_ct`).
- Contributions list (draft):
  + A unified threat model: observer rings O0–O7 × leaked-asset axis,
    composing four independently developed frameworks
    (`docs/research/threat-models.agents.md`).
  + The differential measurement rig and activation-function corpus, with the
    `exp` channel *compiler-removed* as headline
    (`prototypes/leak_check`).
  + Two-property translation validation ("safe = congruent + non-interfering")
    instantiated on Polygeist's eight-step pipeline, with SMT semantics for
    the memref→LLVM slice (`prototypes/fcvd_ct`).
  + Negative-space honesty: the count-channel confound, retired probes, and
    model-blocked steps reported as first-class results.
- Roadmap paragraph.
