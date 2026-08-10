= Threat Model

// OUTLINE ONLY. Source of truth: docs/research/threat-models.agents.md
// and docs/research/formal_verif.threat-model.agents.md.

- Four frameworks compose; we do not pick one
  (leak class × observer ring; evidence layers A–D; evidence levels L0–L4;
  the differential 2×2 attribution).
- The observer-ring vocabulary (canonical grid:
  `prototypes/fcvd_ct/artifact/attacker_profile.py`):
  - O0 public transcript → O7 invasive observer, ordered by directness of
    reach; "proved at O2, carried outward to O1" is meaningful because of the
    ordering; O6-and-inward is moot rather than uncovered.
- The asset axis the rings do not carry: weights (static — repetition wins) vs
  activations/prompts (fresh per query — one-shot channels only) vs
  structure (sparsity, shapes, architecture — leaked by control structure,
  not values).
- What "secure" means in this paper: a claim is fully specified only with all
  four coordinates (observer, evidence kind, evidence level, attribution).
- Scope / non-goals: integrity of weights, TEE partitioning, and running the
  compiled model are out (issues #29, #34, #36).
