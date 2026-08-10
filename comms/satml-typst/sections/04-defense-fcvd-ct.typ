= Verifying: Two-Property Translation Validation for a Real Pipeline

// OUTLINE ONLY. Source of truth: prototypes/fcvd_ct,
// docs/research/polygeist-verification.agents.md (the loop journal),
// docs/research/fcvd-selfcomposition.agents.md,
// docs/research/fcvd-verification-stages.agents.md.

- Why Polygeist: most translatable corpus of the six compilers mapped
  (61.9% of operation mentions vs 53.4% HEIR, 17.3% torch-mlir); speaks the
  shared dialects (affine, scf, memref, arith) — the compiler most likely to
  be verified end-to-end rather than in patches.
- The property: a lowering is VERIFIED only if *both halves* hold —
  semantic congruence (computes the same thing) and non-interference
  (self-composition; hole congruence includes poison bits).
- The method: one checked specification per pass, transcribed from the pass
  source with a citation, each preserving verdict paired with a falsifying
  control; append-only journal; coverage counter re-checks every verdict.
- Pipeline status table (regenerate from live data at submission):
  eight steps from `tools/cgeist/driver.cc` — mem2reg, loop-restructure,
  affine-cfg, canonicalize-for, lower-affine, parallel-lower,
  scf-to-openmp, polygeist-to-llvm; note which are checked vs model-blocked
  (the two parallel steps).
- Scaling the check: the taint prefilter before the solver; SMT semantics
  for LLVM memory ops closing the memref→LLVM slice.
- Per-program vs per-pass proofs: macro-templates cover a translation only if
  both halves hold; affine.load/store with identity maps as the
  cheapest-and-most-used translations.
