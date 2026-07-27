# Actor, principal, and ACL design examples

**Status: design examples, not yet part of the enforced corpus.**

These files illustrate a proposed interface for principals, coalitions,
declassification authority, and audience ACLs. They are deliberately kept
*outside* `../../mlir/` because:

- `c/check_harness.py` globs `mlir/*.mlir` only, so nothing here is subject to
  the four-valued scenario contract or the closed `EXPECTED_SCENARIOS` inventory.
- Every file here needs a record field that does not exist yet: a per-coalition
  result row. The current contract accepts exactly **one** `// observer/model:`
  per fixture (`check_harness.py`, the `observer` check), which cannot represent
  a downward-closed coalition family.

Each file parses and verifies under the pinned `mlir-opt` 17.0.6 and carries a
passing `RUN` line, so they are live documentation rather than dead text. The
`// coalition rows:` blocks are **aspirational**: no tool reads them today.

## Why per-coalition rows are required, not bureaucratic

Intuition says a larger coalition observes strictly more, so checking the
maximal coalition is the hardest case and suffices. That is false here, for two
independent reasons, and each has an example below.

**Release audiences break monotonicity.** A release authorized to audience
`{alice}` makes the release-equality premise hold for coalitions containing
alice: the value is legitimately theirs. For coalition `{bob}` the same release
is not authorized, the premise fails, and the *identical store* is a leak. So a
verdict can be `verified` at one coalition and `unsafe` at another with no
containment relation between them. This is why the specification forbids
deduplicating from coalition monotonicity, and why the report may not omit a
derived coalition. See `t1_audience_mismatch.mlir`.

**Joint visibility is not reconstructible from singletons.** An item may be
declared visible to `{alice,bob}` and to neither singleton, so the downward
closure cannot be rebuilt from per-principal rows. See
`t2_joint_visibility.mlir`.

## The four relations

A single `principal -> clearance level` map cannot express the requirements
these examples cover. Four independent relations can:

| Relation | Question | Drives |
| --- | --- | --- |
| `sps.visibility` | who may **observe** item x | the observation projection, hence low-equivalence and the bad-state predicate |
| `authorizers` | who may **authorize** a release under a policy | whether a release event is legitimate at all |
| `audience` | who a released value is **for** | the release-equality premise, per coalition |
| `sps.placement` | which host **executes** a function | host visibility and cross-host flow |

An authorizer is not automatically a reader, and a reader is not automatically
an authorizer. Keeping these separate is what makes "may declassify but may
never read" and "may never receive this item" both expressible.

## Files

| File | What it pins |
| --- | --- |
| `t1_audience_mismatch.mlir` | One release, two stores: `verified` for the authorized audience, `unsafe` for another coalition. Non-monotonicity. |
| `t2_joint_visibility.mlir` | An item visible only to `{alice,bob}`; safe at both singletons, unsafe jointly. |
| `t3_declassify_only_actor.mlir` | A principal that may authorize a release but may never read the item. |
| `t4_unauthorized_declassifier.mlir` | Byte-identical to t3 except one attribute value; the release is not legitimate, so the flow is raw. |
| `t5_clearance_violation.mlir` | A high item delivered to a principal with no visibility for it. |
| `t6_downward_closure.mlir` | The leak exists *only* at a derived coalition absent from the authored maximal list. |
| `t9_placement_incomplete.mlir` | A reachable function with no unique host; the placement premise is absent. |

One further case has no IR and is therefore described rather than written:
**equal-signature rows.** Two coalitions with identical complete signatures may
share one solver query, but must still produce two result rows; a shared-query
timeout must leave *both* rows unknown rather than becoming a safety fact. That
belongs in `integration/` as a report-level test once a report emitter exists.

## Adopting these

The minimal, backward-compatible change is to keep `// expected outcome:` as an
artifact-level aggregate and add a rows block:

```text
// coalition rows:
//   {}             verified  world-visible-observer
//   {alice}        verified  authorized-audience
//   {bob}          unsafe    wrong-audience-or-host
//   {alice,bob}    unsafe    joint-visibility-reveals-item
```

Aggregate rule: `unsafe` if any row is unsafe, else `unknown` if any row is
unknown, else `conditional` if any row is conditional, else `verified`. The
existing 45 fixtures then read as a single default row and none of them changes.

Natural first migration targets are `wrong_party_plaintext.{bad,fixed}.mlir` and
`wrong_host_fhe_reveal.{bad,fixed}.mlir`. Both presuppose a *complete* audience
and host policy, so nothing currently demonstrates that placement and audience
are consulted rather than hardcoded per fixture; and both encode the audience
entirely in SSA value names, which `mlir-opt` discards at parse.
