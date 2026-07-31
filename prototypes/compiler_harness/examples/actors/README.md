# Principal, coalition, audience, and placement design examples

These MLIR files are live design notes outside the enforced corpus. They parse
and pin shapes, but their comment rows are not verifier output. The main
machine-checked future-oracle example is the candidate bundle at
`../../artifacts/audience-mismatch/`.

## Why every derived coalition needs a row

Rev4 derives the downward closure of each maximal adversary coalition and
retains a separate product row for every `(entry, coalition)`, even when two
rows share a solver query through an identical complete signature.

Release audiences make maximal-only checking unsound. In t1 the release carrier
is for Alice. For coalitions containing Alice, the prefix-causal ledger retires
the matching obligation. For `{bob}`, the carrier payload is concealed and the
obligation remains active; the later Bob-visible store reaches the bad state.
The empty coalition sees neither channel, and the joint coalition contains
Alice. Thus only `{bob}` supplies the replayable product counterexample.

Joint visibility is independent. T2 uses one High input and a distinct output
whose payload is minimally visible only to `{alice,bob}`. Singleton projections
cannot reconstruct that joint basis.

## Confidentiality relations in Rev4

The relevant confidentiality inputs are distinct:

| Relation | Purpose |
| --- | --- |
| visibility basis | Determines which component/output payload fields a coalition compares. |
| release audience | Determines which coalition ledgers a carrier occurrence may retire. |
| function placement and host visibility | Binds execution and host-projected payloads. |

`authorizers` and `authorized_by` are not Rev4 confidentiality relations. The
former t3/t4 sketches moved to `../integrity/` as post-MVP authorization and
robust-declassification examples with no `ModelStatus` oracle.

## Files

| File | Design point |
| --- | --- |
| `t1_audience_mismatch.mlir` | Audience-specific prefix-causal ledger behavior; only `{bob}` reaches Bad. |
| `t2_joint_visibility.mlir` | A High input separated from a minimally jointly visible output. |
| `t5_clearance_violation.mlir` | Empty coalition cannot see a principal channel; `{alice}` can and reaches Bad. |
| `t6_downward_closure.mlir` | The maximal set includes Carol, so every one of its eight derived coalitions must be reported. |
| `t9_placement_incomplete.mlir` | Missing unique placement is a model blocker, not a replayable counterexample. |

T6 is a report-completeness test, not a claim that the leak occurs only in one
derived row: every coalition containing Carol sees the output, including the
maximal coalition. Omitting any derived row is still nonconforming.

## Status vocabulary for comments

Example rows use `ProductSafe`, `ReplayableCounterexample`, or `Blocked(reason)`.
They do not repeat `ModelStatus`; Rev4 has exactly one artifact-scoped model
result. A future actual report must also bind entry/coalition IDs, complete
signatures, query identities, replay records, and all global blockers.
