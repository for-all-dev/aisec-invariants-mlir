# Confidentiality evidence pipeline and Rev4 result contract

This document is a map from the current harness to the Rev4 theory. The labels
L0-L4 remain informal evidence-boundary vocabulary; they are not separate proof
modes and do not define an alternative result system.

## Current layers

| Layer | Current executable evidence |
| --- | --- |
| Shape | MLIR verifier plus `FileCheck` preserves a decisive operation and its dataflow. |
| Diagnostic | The unary scanner emits triage findings. `RelationalRequired` or silence can still lead only to a future product query. |
| Candidate pair | Hashing and exact `.bc`/derived `.ll` disassembly/reassembly catch fixture drift. |
| Future model | LLVM 22.1.8 normal-form audit, fresh parse, complete binding, audit-all product, solver validation, and replay are not implemented. |
| P4 risk | Assembly/code-generation tests expose target deltas but do not close paired refinement. |

The fixed observation semantics are `Theta_ct`: world-level control location,
event occurrence/site/order, termination, failure, bound status, and
definedness stay in lockstep while the obligation is active. Coalition
projection controls payload comparison only; fixtures do not select a weaker
observer.

The diagnostic is also deliberately weaker than the theorem machinery. It has
no proof-authoritative program-counter label, strong update, summary theorem,
or slice theorem. Its findings are review aids, and every required entry and
coalition still needs the whole-entry product.

## Exact result domains

```text
ModelStatus = Proved
            | Counterexample(ReplayableWitness)
            | Unknown(Reason)

DeploymentStatus = Open(OpenObligations)
                 | Closed(P4EvidenceBundle)

PolicyReviewStatus = Complete
                   | Findings(finite set ReleasePolicyLint)
                   | Incomplete(Reason)
```

`ModelStatus` is unique and artifact-scoped. Reports separately retain one
diagnostic record and one product disposition per `(entry, coalition)`. The
aggregation priority is replayable counterexample, then all open model
blockers, then `Proved` only when every premise and product closes.

Release handling is prefix-causal. A carrier occurrence updates only the
coalitions in its declared audience. For an outside coalition the carrier
payload is concealed, the obligation remains active, and a later visible
payload mismatch can reach the bad state. Whole-run release equality is not a
substitute for that ledger.

## Candidate bundle contract

The checked-in bundles are intentionally named candidate/oracle schemas:

- `artifact.bc`: LLVM-17 candidate bytes;
- `artifact.ll`: exact `llvm-dis` review form, which reassembles to those bytes;
- `artifact.json`: `sps-artifact-candidate-v1`, not normative
  `ArtifactIdentity`;
- `policy.json`, `abi.json`, `contracts.json`, and `release-table.json`:
  simplified `sps-fixture-*-v0` intent descriptors;
- `expected-report.json`: a `sps-fixture-oracle-v0` future expectation plus a
  current `Pending` record.

The future conformance capture must replace all simplified interfaces with the
complete canonical Rev4 objects and bind their digests into a full
`ArtifactIdentity`. Pretty-printed/sorted prototype JSON is not
`CanonInterfaceJSONV1`.

## Current future oracles

These are expected results only after LLVM 22.1.8 recapture, complete canonical
bindings, normal-form conformance, exact products, and replay. Every checked-in
oracle sets `claimable_from_checked_in_pair: false`.

| Bundle | Future model oracle | Important product/deployment fact |
| --- | --- | --- |
| `abi-alias-disjoint` | `Proved` | Complete Disjoint topology; product safe. |
| `abi-alias-mayalias-overlap` | `Counterexample(ReplayableWitness)` | Admitted equal-base realization exposes the High store at the world output. |
| `abi-alias-missing-binding` | `Unknown(AliasBindingMismatch)` | Missing complete topology blocks the product; distinct SSA roots imply nothing. |
| `alloca-size-high` | `Unknown(AllocaSizeNotWorldStructural)` | A public cap does not make the actual High-selected byte size equal. |
| `alloca-size-public` | `Proved` | Candidate admission records range, overflow freedom, and stack feasibility. |
| `audience-mismatch` | `Counterexample(ReplayableWitness)` | `{}`, `{alice}`, and `{alice,bob}` are product-safe; `{bob}` reaches Bad while its release obligation remains active. |
| `bound-exhausted-public` | `Unknown(LoopRemainder)` | Aligned reachable exhaustion is retained, never filtered into a proof. |
| `bound-secret-trip-count` | `Counterexample(ReplayableWitness)` | Counts 0 and 1 diverge at the first world-visible loop-control step. |
| `launder-scan` | `Proved` | LLVM product is safe for the attacker projection; `DeploymentStatus` stays Open for the x86 backend control delta. |

The alias triad, bound split, and alloca twins are paired deliberately. A corpus
containing only refusals or leaks can be satisfied by an always-refuse or
always-report checker; the positive twins guard against that failure mode.

## From candidate to reportable theorem

The required direction is:

```text
C / hand-reduced MLIR
        │ preflight only
        ▼
LLVM 17 candidate .bc ──llvm-dis──> derived .ll for review
        │ replace capture and descriptors
        ▼
LLVM 22.1.8 pinned late pipeline + normalizers + verifier + NF audit
        │ freeze bytes, hash, destroy module, fresh parse, re-audit
        ├──> P1-P3 exact model/product/replay
        └──> same fresh bytes directly to recorded core ISel
                                      │
                                      ▼
                         P4 MIR/object/final-binary evidence
```

Only the middle conformant object can receive a Rev4 `ModelStatus`. Only the
last paired evidence can close `DeploymentStatus`. Source diagnostics and P4
risk findings remain useful, but neither crosses those boundaries by itself.
