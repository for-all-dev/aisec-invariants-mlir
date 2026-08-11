= Case Studies and Evaluation

// OUTLINE ONLY. Candidates — cut to the two or three strongest at draft time.

- KyberSlash through the non-interference lens: what the proofs_l2_seabmc
  jobs admit and reject (`prototypes/proofs_l2_seabmc`, commit 8e0cf35
  "five more non-interference jobs, and what KyberSlash admits").
- End-to-end walk of one program through the verified Polygeist steps,
  reporting the four coordinates (observer, evidence kind, level,
  attribution) at each stage.
- Structure leaks as a distinct class: sparsity and dynamic shapes
  (`prototypes/mlir_leak`, `prototypes/Staging_NI`) — leaked by control
  structure, not values.
- Coverage accounting: steps checked / model-blocked, unproved operation
  counts, sweep breadth — the numbers the coverage counter regenerates.
