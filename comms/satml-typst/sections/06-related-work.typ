= Related Work

// OUTLINE ONLY. priorlit/ currently holds one summary (csi_nn_paper) —
// this section needs the DBLP/Scholar sweep tracked in issue #23.

- Side-channel extraction of model internals: CSI-NN @batina2019csinn and
  successors; where our asset/observer grid places them.
- Timing leaks in compiled crypto: KyberSlash @kyberslash2024; constant-time
  verification (ct-verif, Binsec/Rel lineage) — hand kernels, not compilers.
- Compiler correctness: CompCert, Alive2, translation validation @lopes2021alive2
  — correctness without secrecy; our two-property extension.
- Secure compilation / full abstraction — the theory frame our per-pass
  specs approximate.
- MLIR @lattner2021mlir and Polygeist @moses2021polygeist as substrate;
  MLIR-TV and dialect-level verification efforts
  (`docs/research/mlir-tv-custom-dialect.agents.md`).
- IFC dialects claim-check ("first MLIR IFC dialect", issue #23).
