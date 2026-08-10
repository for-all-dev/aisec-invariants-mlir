// SaTML 2027 submission — OUTLINE STAGE, no prose yet.
// Template: charged-ieee (IEEE-style) until the official SaTML kit lands
// (announced for mid-August 2026; swap the show rule then).
// Submission deadline: 2026-09-29 AoE. See README.md for the full timeline.

#import "@preview/charged-ieee:0.1.4": ieee

#show: ieee.with(
  title: [Your Compiler Is Leaking Your Model: Measuring and Verifying
    Confidentiality Across Deep-Learning Compilation],
  abstract: [
    // OUTLINE — one sentence per slot, expand later.
    // 1. DL compilers (Inductor, MLIR pipelines, Polygeist) sit inside the
    //    trust boundary of every deployed model, unaudited.
    // 2. Threat model: unified observer-ring × asset grid over four existing
    //    frameworks (docs/research/threat-models.agents.md).
    // 3. Attack half: differential eager-vs-compiled measurement finds
    //    compiler-introduced AND compiler-removed side channels (leak_check).
    // 4. Defense half: per-pass checked specifications for a real pipeline,
    //    where "safe" = semantic congruence + non-interference (fcvd_ct).
    // 5. Headline results: exp activation channel COMPILER-REMOVED;
    //    Polygeist steps carrying checked two-property specs.
    _Abstract to be written from the outline above._
  ],
  authors: (
    // Order TBD with the fellows. SaTML is expected to be double-blind —
    // keep this block in a non-anonymous copy only, once policy is announced.
    (
      name: "Quinn Dougherty",
      organization: [Apart Research — Secure Program Synthesis Fellowship],
      email: "quinn@for-all.dev",
    ),
    (
      name: "Kapedalex (full name TBD)", // TODO
      organization: [Apart Research — Secure Program Synthesis Fellowship],
      email: "tbd@example.com", // TODO
    ),
    (
      name: "Siddharth Priya",
      organization: [Apart Research — Secure Program Synthesis Fellowship],
      email: "tbd@example.com", // TODO
    ),
    (
      name: "Shefali Sharma",
      organization: [Apart Research — Secure Program Synthesis Fellowship],
      email: "tbd@example.com", // TODO
    ),
    (
      name: "John Wu",
      organization: [Apart Research — Secure Program Synthesis Fellowship],
      email: "tbd@example.com", // TODO
    ),
  ),
  index-terms: (
    "compiler security",
    "side channels",
    "machine learning",
    "MLIR",
    "translation validation",
    "non-interference",
  ),
  bibliography: bibliography("refs.bib"),
)

#include "sections/01-introduction.typ"
#include "sections/02-threat-model.typ"
#include "sections/03-attack-leak-check.typ"
#include "sections/04-defense-fcvd-ct.typ"
#include "sections/05-case-studies.typ"
#include "sections/06-related-work.typ"
#include "sections/07-discussion.typ"
#include "sections/08-conclusion.typ"
