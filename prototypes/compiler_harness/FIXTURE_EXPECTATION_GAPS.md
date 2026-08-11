# Fixture expectation gaps and proposed `expected` schema

Measured 2026-08-02. Scope: the executable reference slice (`SPS/reference/`,
vendored at `contracts/vendor/sps-reference-rev4/reference/`) and the two
harness-side expectation layers (Snapshot V3, lecture cases).

Companion to [FIXTURE_REVIEW_GUIDE.md](FIXTURE_REVIEW_GUIDE.md) and
[contracts/FIXTURE_TIERS.md](contracts/FIXTURE_TIERS.md). This document is about
what the `expected` blocks *assert*, not about tier authority.

---

## 1. The measurement

Baseline is green: 19 fixtures, 12 unit tests, `10/61 profile families executable`.

A mutation run against `sps_ref/product.py` and `sps_ref/replay.py` — single-line
edits, suite re-run after each, sources restored and hash-verified:

**12 of 15 mutants survive the entire suite.**

| Survives | Mutation |
|---|---|
| ✗ | `product`: drop the `EventAlignment` cause row |
| ✗ | `product`: drop the `SiteOrderAlignment` cause row |
| ✗ | `product`: drop `visit` from `SiteOrderAlignment` |
| ✗ | `product`: drop `within_ordinal` from `_static_mismatch` |
| ✗ | `product`: drop `release_ordinal` from `_structural_terms` |
| ✗ | `replay`: off-by-one on the first-bad ordinal |
| ✗ | `replay`: drop `visit` / `within_ordinal` / `release_ordinal` / `audience` / `footprint` from `_structural_key` (5 mutants) |
| ✗ | `replay`: skip the dual-construction cross-check entirely |
| ✓ | `product`: retire unconditionally on an authorized release |
| ✓ | `product`: ignore audience when deciding authorization |
| ✓ | `replay`: continue past the first bad step |

The three that die all flip `status` sat↔unsat. Everything that survives is an
**alignment coordinate** — precisely the `Site`, `DynamicVisit`,
`WithinStepOrdinal` triple that §11 `SiteOrderAlignment` compares *in order*,
and precisely what MT-CM4 proves local per-template checks cannot recover.

### 1a. Not all survivors are coverage gaps — read §1b before acting

A surviving mutant is only a coverage gap if some fixture *could* kill it.
Follow-up measurement (§1b) shows the survivors split into two very different
classes, and roughly half are **equivalent mutants** that no expectation field
can ever kill. Do not size the work off the raw 12/15 number.

Two structural consequences:

- Every one of the 9 `noninterference` fixtures produces
  `firstBadCause: "ProjectedPayloadMismatch"` or `null`. **No fixture has ever
  produced `EventAlignment` or `SiteOrderAlignment`**, on either the SMT side
  (`product.py`) or the independent replay side (`replay.py::_compare_traces`).
  Both implementations of those branches are dark.
- The dual-construction cross-check (symbolic vs. concrete trace agreement) can
  be deleted with no test failure. That is the generate-and-check discipline in
  `MODULES.md` I1, currently unenforced.

Reproduce: the mutation driver is in the session scratchpad; see §7 to land it
as a make target.

---

## 1b. Which survivors are actually killable

`build_product` raises unless both lanes are the **same program**, and events are
constructed in the same static order. So every *static* event field is equal
between lanes **by construction**, not by accident.

Measured across all 10 product-building fixtures — for every event, comparing
L against R on `kind`, `site`, `within_ordinal`, `output_id`, `release_id`,
`audience`, `footprint_bytes`, `transfer_source`, `transfer_destinations`,
`bound_id`, `snapshot_names`:

> **zero static differences, in every fixture.** `_static_mismatch` is a
> compile-time `False` folded into the `SiteOrderAlignment` term.

That splits the survivors:

| Class | Coordinates | Killable? |
|---|---|---|
| **Equivalent mutants** | `audience`, `site`, `footprint_bytes`, `output_id`, `release_id`, `transfer_*`, `bound_id`, `snapshot_names`, `within_ordinal` | **No.** Cannot differ while both lanes run one program. Asserting them per-lane echoes a static input back as an expectation. |
| **Real gap, fixture-fixable** | `present` → `EventAlignment` | **Yes — proven live**, see below. |
| **Real gap, model-blocked** | `visit` → `SiteOrderAlignment` | **Not reachable in the current IR.** |

**`EventAlignment` is reachable today.** All 10 product fixtures have
`present`, `visit` and `release_ordinal` as input-*independent* constants — the
whole corpus is straight-line. `bad-circuit-secret-branch` does have an `if`,
but with **empty `then`/`else` arms**, so nothing is conditionally present. Move
an event-emitting statement (`releaseAttempt`, `transfer`) into a secret-guarded
arm and `EventAlignment` fires immediately:

```
host-release-unauthorized-visible, release wrapped in a secret if
  events = [BranchSuccessor, Release, Termination]
  live   = {ProjectedPayloadMismatch: [0], EventAlignment: [1]}   ← was unreachable
```

A `store` will not do it — stores mutate a root and surface at terminal closure;
they emit no event of their own.

**`SiteOrderAlignment` is not reachable**, and this is a model limit rather than
a missing fixture. `visit` only advances on a repeated site, and every route is
closed:

- duplicate sites → `SchemaError: duplicate stable site`;
- secret-dependent trip count → `UnsupportedError: reference loop iterations
  must be Low` (the declared `secret-dependent-loop-bound` refusal);
- High branch inside a Low-bounded loop → `visit` *does* become symbolic on
  copy 2 (`visit.op=ite`), but the same condition guards every copy, so presence
  at copy N implies presence at copy 1. `both ∧ visit_L ≠ visit_R` stays
  unsatisfiable.

Reaching it needs a loop induction variable in the expression language, or
per-copy varying conditions. That is a program-model change, not a P0 item.

### Consequence for the schema below

`projectedTrace` as a full 15-key per-event record is **over-specified**. Nine of
its keys are provably lane-invariant. Record the witness-varying coordinates and
the event identity; drop the static echo. §2.1 is corrected accordingly.

---

## 2. Per-kind `expected` schema

Current inventory: 19 fixtures across 7 kinds — `noninterference` ×9,
`refusal` ×4, `model-wire` ×2, `artifact-mutation` ×1, `bit-encoding` ×1,
`expand` ×1, `product-profile-refusal` ×1.

### 2.1 `noninterference` (×9)

```jsonc
// before
"expected": { "status": "sat", "firstBadCause": "ProjectedPayloadMismatch", "replayAccepted": true }
```

```jsonc
// after
"expected": {
  "status": "sat",
  "firstBadCause": "ProjectedPayloadMismatch",
  "replayAccepted": true,

  "firstBadEventOrdinal": 1,
  "firstTrueBadRow": 5,
  "canonicalReferencePONFDigest": "<64 hex>",
  "eventShape": ["BranchSuccessor@branch.site", "Release@release.site",
                 "Termination@return.site"],
  "divergence": { "presence": [], "visit": [], "releaseOrdinal": [] }
}
```

| Field | Source | Kills |
|---|---|---|
| `eventShape` | `kind@site` per event, one lane | a dropped or reordered event in the static inventory |
| `divergence` | ordinals where `present` / `visit` / `release_ordinal` differ between lanes under the witness | the `present`-side `_structural_key` survivor; empty today for every fixture, which is itself the finding |
| `firstBadEventOrdinal` | already on `ReplayRecord`, serialized, **zero consumers** | first-bad returning literal `0`; off-by-one |
| `firstTrueBadRow` | index of first true cause row under the witness | separates the visibility-gated payload row from the ungated structural row — both stringify to `ProjectedPayloadMismatch` at the same ordinal |
| `canonicalReferencePONFDigest` | `ponf.py` canonical digest | narrowing/retirement reordering that leaves every other field byte-identical |

Disciplines:

- **Do not record the full per-event object.** Nine of its fifteen keys are
  lane-invariant by construction (§1b). `audience`, `footprintBytes`,
  `observationHosts`, `transfer*`, `outputId`, `releaseId`, `boundId`,
  `snapshotNames`, `withinOrdinal` in a per-lane trace are a static echo, not an
  oracle, and their mutants are unkillable.
- **`divergence` is the honest replacement.** It states the one thing a
  two-lane comparison can actually witness, and today it is `{[], [], []}` for
  all 10 fixtures — a one-line, reviewable statement of exactly the hole.
- **`firstTrueBadRow` must ship with its negative half** — assert every row at a
  lower event ordinal evaluates *false*. Spec ~L8592: *"every earlier
  `trueBadSources` list is empty."* Without it this is an *a*-bad claim, not a
  *first*-bad claim, and it does not enforce the absorbing rule.
- **One digest, not five.** The other four are inside its own preimage.

**`audience` specifically.** It has two roles, with opposite coverage. As a
`_structural_key` coordinate it is dead (above). As the authorization predicate
`audience & coalition.principals` it is live *and already covered* — the
"treat wrong-audience release as authorized" mutant dies on
`host-release-unauthorized-visible`. So audience needs no further breakdown in
the trace. If you want more audience assurance, assert the **derived decision**
(which release was deemed authorized, against which coalition, and whether it
retired the pair), not the static set echoed per lane.

### 2.2 `refusal` (×4) — weakest tier

```jsonc
// before
"expected": { "reason": "ReferenceSchemaMismatch" }

// after
"expected": {
  "reason": "ReferenceSchemaMismatch",
  "refusalLocus": { "space": "programJson",
                    "path": "$.input.program.statements[0].sourceHost" }
}
```

`refusalLocus` is currently the *only* thing that would distinguish two
byte-identical `ReferenceSchemaMismatch` fixtures testing different normative
rules.

Take `str(exc).split(": ", 1)[0]`. **Do not take the tail** — it interpolates a
witness binding (`{'L.input.secret': 0}`), which is restricted evidence and must
not enter a fixture.

Push "nothing was emitted" (§15 step 9) to a **runner-level invariant** — no
`ReplayRecord`, no `ReferenceProduct`, no PONF artifact constructed — not a
per-fixture literal.

### 2.3 `artifact-mutation` (×1 + 1 new) — highest value per line

```jsonc
// existing fixture
"expected": { "reason": "ReferenceSchemaMismatch", "caughtBy": "structural-seal" }

// NEW companion: mutation "replace-first-bad-expression-with-false-then-reseal"
"expected": { "reason": "ReferenceSchemaMismatch", "caughtBy": "semantic-reconstruction" }
```

The self-digest check fires before goal reconstruction, so **many independent
mutations all land on the same string**. Resealing the artifact fans them out
and reaches the goal-reconstruction, row-table-equality and field-equality
checks that are otherwise unreachable.

Two constraints: make the slug table **total** with a hard fail on any unmapped
message, and keep slugs **coarse** (`structural-seal` / `semantic-reconstruction`)
so they do not pin a check *order* that §15 leaves free.

### 2.4 Remaining kinds

| Kind | Add | Why |
|---|---|---|
| `product-profile-refusal` | `replayUnderlyingReason` | `getattr(exc.__cause__, "reason", None)` — already computed via `raise … from exc`. §15 step 4 requires preserving distinct stable reasons; collapsing many raise sites into one string is the erasure it forbids. Re-home onto a refusal that is not an open item — this fixture dies when `partial-release-footprint` closes. |
| `model-wire` (×2) | `rejectionClass: "Reordered"` | Free-text → the spec's closed rejection vocabulary. Add a third fixture for the `#b` ground-literal spelling, currently uncovered. |
| `bit-encoding` (×1) | *(nothing in-place)* | Add a **sibling fixture** at `LittleEndian`. The byte reversal has zero coverage — the existing vector is one byte, where reversal is the identity. |
| `expand` (×1) | `formatId`, `expandedCFGTableDigest`, full `nodes[]` (drop `nodeKinds`, subsumed) | Sole authority for the expansion object, so it keeps its structural literal. Assert `width_for` against the spec formula max(1, ⌈log₂(N+1)⌉) **in code**, not as a literal. |

### 2.5 Harness-side layers

**Snapshot V3** (62 snapshots: 26 Proved / 25 Counterexample / 11 Unknown):

- Make `reference:` **mandatory** when `status: Counterexample`. **23 of 25
  Counterexample snapshots have no sidecar**, so their `bad_state` is compared
  by nothing.
- Require `id:` on `Output`/`Error`/`Release`/`BoundExhausted` selectors.
  **46 of 64 event selectors omit it**, which is why many Proved fixtures share
  a byte-identical `[(Output, valueBytes)]` block.
- `checkpoint_runner.py` filters projections with `item not in (None, False)`.
  In Python `0 == False`, so this silently swallows any integer-`0` field.
  Harmless today (no integer fields); it will bite the moment an ordinal is
  added. Change to an explicit `is not None` / `is not False`.

**Lecture cases:** add `branch_condition_source` and replace the binary ordering
test with a total predicate table with a `KeyError` default. Several ordering
strings currently collapse to one predicate and some cases never read the field
at all. Both are checker refactors, not schema changes.

---

## 3. Three gaps no expectation field can close

These need new **fixtures** and are larger than everything above.

1. **No product fixture has a Low input.** Verified: 13 `High`, 1 `Low`, and the
   single Low input is in `loop-canonical-expand` (`kind: expand`, builds no
   product). So `low_constraints == ()` in every product ever built — the LowEq⁰
   premise, the entire left-hand side of the 2-safety statement, is never
   exercised.

2. **Retirement never absorbs anything.** `release-authorized-retire` is UNSAT,
   so no replay runs. An authorized *unequal* release followed by a
   coalition-visible Output leak currently reports
   `accepted=false, badCause=null` — byte-identical to a clean program. R8.2 and
   R8.6 are unfalsifiable.

3. **MT-CM3 has no fixture anywhere.** A visible leak at ordinal 0 followed by an
   *equal* authorized release at ordinal 1 must remain Bad. Directly
   constructible in the slice today.

Beyond these: §20 is a normative acceptance table of **21 (condition →
disposition) rows**. Nearly all have no fixture.

---

## 4. Do not add

- Any witness value or `valueBytes`; `receiptId` values; solver `detail`; cvc5
  availability.
- The four digests subsumed by the canonical PONF digest.
- Absence-assertions for `UBRisk` / `Failure` / `Error` — three of those
  constructors do not exist in the slice, so the assertion is unfalsifiable.
- `refusalPhase` / `constructionProgress` / `coFaultOrdering` — these pin
  first-fire order where §15 requires accumulating a `Blockers` **set**, and two
  of them would harvest `tb_frame.f_locals`.
- A `left == right` CFG digest (tautological — one program, one pure function).

---

## 5. The caveat that governs all of it

Every golden above is produced by the code it polices. It detects **drift, not
wrongness**. If `product.py` has always appended rows in the wrong order, a
pinned cause table freezes the wrong order forever, and the first maintainer to
hit a failure regenerates it.

Only a small set of values are fixed by the spec *independently of the
implementation* and can therefore falsify a wrong implementation rather than a
changed one:

- `widthFor(N) = max(1, ⌈log₂(N+1)⌉)`
- the `PONFBadCauseV2` literal cause order (§21.4)
- the §7.2 within-transition order: opcode events → exactly one `Latency` →
  `terminalOutputOrder` Outputs → `Termination` last
- the `rawSolverResult` → `queryDisposition` legality table (§21.6)
- policy lint fires ⇒ `PolicyReviewStatus: Findings` (§20)
- the §2.1 empty-release-table canonical bytes and their SHA-256 — **the one
  non-self-produced golden in the entire system, and the slice does not carry
  it**

Assert those in runner code as spec constants. Label everything else a drift
detector, and make the runner print a structural diff on digest mismatch — or
the first failure becomes a bulk regeneration.

---

## 6. Note on the observation model

`tools/checkpoint_model.py` pins `EVENT_FIELDS` to exactly the Θ_ct constructors
of spec §7, with a deliberate comment that site/occurrence coordinates are *not*
selectors. `fixtures/README.md` states selectors "never contain event payloads or
full traces."

That boundary is correct and should hold. The gap this document describes is not
that traces should become fixture payloads — it is that the **ordering
coordinates** (`Site`, `DynamicVisit`, `WithinStepOrdinal`), which §7 makes part
of one trace rather than separate optional checks, are currently asserted by
nothing on either the SMT or the replay path.

---

## 7. Ranking

**P0 — landed 2026-08-02.** Mutation score went from 3/15 killed to 9/16; the
7 survivors are all documented equivalent mutants.

- [x] **`release-presence-secret-branch`** — releases a constant inside a
      secret-guarded branch. Sole fixture in which `EventAlignment` is
      satisfiable. Note the correction in §1b: it cannot be `firstBadCause`,
      so it is asserted via `satisfiableCauses`.
- [x] `noninterference`: `eventShape`, `satisfiableCauses`,
      `firstBadEventOrdinal`, `firstTrueBadRow` (+ negative half),
      `canonicalReferencePONFDigest`. `divergence` was dropped —
      `satisfiableCauses` subsumes it and ties directly to the cause taxonomy.
- [x] `refusal`: `refusalLocus` (locus half only; the detail half interpolates
      a witness binding)
- [x] `artifact-mutation`: `caughtBy` + `bad-circuit-mutation-resealed`
- [x] `product-profile-refusal`: `replayUnderlyingReason`
- [x] `expand`: `formatId` / `entryId` / `nodes` / digest, plus `width_for`
      asserted against the spec formula in code
- [x] Snapshot V3: `reference:` mandatory for `Counterexample`, with the 23
      pre-existing cases in an explicit `COUNTEREXAMPLE_REFERENCE_EXEMPT` list
      that errors if a listed case later complies
- [x] `checkpoint_runner.py` falsy-filter fix (identity comparison)
- [x] `make check-mutants` — see the note below on why the target is not
      "survivors pinned at 0"

**Why `check-mutants` is not pinned at 0.** Roughly half the survivors are
*equivalent mutants*: `build_product` requires both lanes to compile one
program, so mutations that drop a static field from a lane comparison cannot
change any observable behaviour, at any level of expectation detail. Pinning 0
would be unsatisfiable. The target instead pins an explicit
`EXPECTED_SURVIVORS` allowlist, each entry carrying its structural reason, and
fails on **either** a new survivor **or** an allowlisted mutant that starts
dying (which means the list is stale). That second direction immediately caught
three entries I had wrongly pre-classified as unkillable — the canonical PONF
digest covers `auditBadCauseRows`, so any cause-expression edit is detected.

**P1**

- [ ] Low-input fixture, retire-then-leak fixture, MT-CM3 fixture
- [ ] `#b` ground-literal and `LittleEndian` sibling fixtures
- [ ] `model-wire` `rejectionClass`
- [ ] Lecture `branch_condition_source` + total ordering table
- [ ] Snapshot `id:` required on identified event kinds

**P2**

- [ ] Branch- and loop-body expand fixtures
- [ ] The §20 acceptance-table sweep (21 rows)
- [ ] **Program-model work to make `SiteOrderAlignment` reachable at all** — a
      loop induction variable in the expression language, or per-copy varying
      conditions. Until then MT-CM4's ordering coordinate has no witness in the
      reference slice, and that limitation should be stated explicitly in
      `assurance-status.json` rather than left implicit.

---

## Provenance

Verified by direct measurement in this session: the mutation-survival table;
fixture kind/count inventory; the High/Low input split; the 62-snapshot status
split and sidecar coverage; event-selector `id` coverage; the falsy filter; §20
row count; §7 and §11 spec text.

Line numbers, digest literals, and the internal ordering of checks inside
`ponf.py` / `smt.py` come from an agent survey and should be re-confirmed at
implementation time — the fixture corpus changed during this session (56 → 62
snapshots), so re-measure before relying on any count here.
