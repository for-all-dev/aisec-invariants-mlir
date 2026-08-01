# Manual fixture review guide

This guide is the priority-ordered queue for manually reviewing the
confidentiality fixtures in this harness. It keeps related bad, fixed, control,
and refusal cases together so that a checker cannot appear correct by always
reporting a leak or always refusing to decide.

The ranking is based on three factors, in this order:

1. **Applicability:** how often the situation occurs in real systems.
2. **Property breadth:** how many independent confidentiality properties the
   family exercises.
3. **Review leverage:** how many other fixtures or implementation decisions
   become easier to assess after this family is understood.

The ranking is a review order, not a severity claim. A lower-ranked,
target-specific case may still be critical for a deployment that uses that
target.

## Authority and result boundary

Before reviewing individual fixtures, read
[the Rev4 preflight workflow](mlir/REV4_PREFLIGHT_WORKFLOW.md) and keep these
boundaries explicit:

- C is provenance, executable behavior, and source-shape evidence.
- Each family/case folder pairs a review-sized MLIR shape with one small
  `snapshot.yaml` containing the relevant boundary and expected interpretation.
- Global `artifacts/` bitcode is a quarantined LLVM-17 candidate sequence;
  `artifact.ll` is its derived review form. It is not case-local frozen SPS
  bitcode.
- Prototype sidecars describe fixture intent but are not canonical Rev4
  interfaces.
- P4 and assembly tests expose deployment risk but do not change LLVM
  `ModelStatus`.
- Every current snapshot says `sps: not-run`. The checked-in legacy
  `expected-report.json` files are non-claimable candidate matchers.

Filename suffixes mean:

| Suffix | Review meaning |
| --- | --- |
| `.bad` | A leak, unsound shortcut, or required refusal is intentionally present. |
| `.fixed` | The paired repair should preserve intended functionality while removing the named observation. |
| `.control` | A positive or precision control that prevents an always-report or always-refuse implementation from passing. |
| `.unknown` | The correct future disposition is expected to remain blocked by a named missing premise. |
| `.model_proved.p4_open` | The modeled LLVM property is expected to be safe while deployment refinement remains open. |

## Property key

The ranked table uses these abbreviations:

| Key | Property |
| --- | --- |
| `FLOW` | Secret-derived payload or value reaches an observable sink. |
| `ADDR` | A secret changes a memory address or access pattern. |
| `CTRL` | A secret changes control, event order, termination, or loop progress. |
| `LAT` | A secret reaches an operation or helper with target-dependent latency. |
| `MEM` | Exact byte memory, overwrite, residual-state, or alias semantics matter. |
| `STRUCT` | World-visible structure such as allocation size, count, or bound status matters. |
| `RELEASE` | Declassification expression, guard, occurrence, or prefix ledger matters. |
| `AUTH` | Principal, host, audience, coalition, or placement authorization matters. |
| `BIND` | Independent ABI, policy, contract, carrier, or artifact binding matters. |
| `P4` | Backend, object, or final-binary evidence is required. |

## Review workflow for every family

Use the same sequence for every ranked section:

1. **Read `snapshot.yaml`.** Confirm the entry, relevant secret arguments,
   public observations, optional release/audience allowance, expectation, and
   short reason.
2. **Inspect the sibling MLIR.** Confirm the argument numbers and names, the
   decisive operation, and the `FileCheck` assertions agree with the snapshot.
3. **Execute the behavior mentally.** Write down the observable trace for two
   secret values while holding all declared public inputs equal.
4. **Compare every twin.** A bad/fixed pair must differ only in the intended
   repair. A control must genuinely reject the trivial always-report or
   always-refuse strategy.
5. **Read the C provenance header.** Confirm the source relationship and that
   the reduction still represents the behavior claimed by the snapshot.
6. **Inspect independent bindings.** When a semantic bundle exists, do not infer
   policy, audience, alias topology, or contracts from variable names or LLVM
   syntax.
7. **Check the result boundary.** Record only fixture intent and the plausible
   future disposition. Do not promote a preflight check to a current theorem
   result.
8. **Check P4 separately.** If target code generation matters, verify the exact
   target, compiler, flags, and stage. Do not generalize one assembly snapshot
   to other targets.
9. **Run the supporting tests.** A passing test confirms the checked shape, not
   the entire security argument.

For each section, record:

```text
Reviewer:
Date:
Status: accepted | changes-requested | blocked
Threat-model assumptions checked:
Open questions:
```

## Ranked review queue

| Rank | Fixture family | Applicability | Main properties |
| ---: | --- | --- | --- |
| 1 | Recipient, host, and release-audience authorization | Very high | `FLOW`, `AUTH`, `RELEASE`, `BIND` |
| 2 | Release causality, sanitization, and explicit oracles | Very high | `FLOW`, `CTRL`, `RELEASE`, `AUTH`, `BIND` |
| 3 | Cross-tenant and cross-request residual state | Very high | `FLOW`, `MEM`, `AUTH`, `STRUCT` |
| 4 | ABI alias-topology honesty | Very high | `FLOW`, `MEM`, `BIND` |
| 5 | Direct public outputs, lengths, logs, and counts | Very high | `FLOW`, `STRUCT` |
| 6 | Secret-dependent addresses and indexing | Very high | `ADDR`, `MEM`, `CTRL` |
| 7 | Loop bounds and world-structural allocation sizes | High | `CTRL`, `STRUCT`, `BIND` |
| 8 | Release-carrier preservation and conformance | Medium-high | `RELEASE`, `CTRL`, `BIND` |
| 9 | Relational precision and false-positive controls | High | `FLOW`, `CTRL`, `MEM`, `ADDR` |
| 10 | Backend-created branches, loads, and spills | High conceptually | `CTRL`, `MEM`, `LAT`, `P4` |
| 11 | Source-level variable-latency arithmetic | Medium-high | `LAT`, `FLOW`, `P4` |
| 12 | Target-profile helpers and target-specific timing | Target-specific | `LAT`, `CTRL`, `BIND`, `P4` |

This default order is application-first. When reviewing the compiler/verifier
implementation itself, promote ranks 4, 8, and 10 immediately after rank 2:
alias admission, carrier preservation, and level-boundary changes are the most
systemic implementation-soundness checks.

---

## 1. Recipient, host, and release-audience authorization

**Why this is first:** delivering the right value to the wrong principal is a
common failure across RPC systems, mailboxes, FHE services, multi-tenant
applications, and declassification APIs. This family also exercises the
distinction between payload equality and coalition authorization.

### Review these situations

| Situation | C evidence | MLIR evidence | Bundle | Intended distinction |
| --- | --- | --- | --- | --- |
| Release visible outside its declared audience | [audience_mismatch_bad.c](c/audience_mismatch_bad.c) | [audience_mismatch.bad.mlir](mlir/audience-mismatch/bad/audience_mismatch.bad.mlir) | [audience-mismatch](artifacts/audience-mismatch/) | Alice is authorized; Bob sees the same payload without being in the release audience. The future `{bob}` product row is the counterexample row. |
| Plaintext sent to the wrong party | [bad](c/wrong_party_plaintext_bad.c), [fixed](c/wrong_party_plaintext_fixed.c) | [bad](mlir/wrong-party-plaintext/bad/wrong_party_plaintext.bad.mlir), [fixed](mlir/wrong-party-plaintext/fixed/wrong_party_plaintext.fixed.mlir) | — | The bad case writes both mailboxes; the fixed case preserves the authorized mailbox and redacts only the unauthorized one. |
| FHE plaintext revealed on the wrong host | [bad](c/wrong_host_fhe_reveal_bad.c), [fixed](c/wrong_host_fhe_reveal_fixed.c) | [bad](mlir/wrong-host-fhe-reveal/bad/wrong_host_fhe_reveal.bad.mlir), [fixed](mlir/wrong-host-fhe-reveal/fixed/wrong_host_fhe_reveal.fixed.mlir) | — | The ciphertext handle remains public; only the authorized client may receive revealed plaintext. |

### Manual checks

- [ ] Name every principal, host, coalition, and sink before looking at the
  code.
- [ ] Confirm the bad and fixed functions preserve the same authorized output
  and return behavior.
- [ ] Confirm zero is a declared redaction sentinel rather than an accidental
  semantic change.
- [ ] In `audience-mismatch`, verify `release-table.json` declares audience
  `{alice}`, the LLVM entry has exactly one carrier call, and the ABI binds two
  distinct output roots.
- [ ] Verify the `{bob}` product row remains bad even though `{alice}` and
  `{alice,bob}` are safe.
- [ ] Do not infer authorization from pointer names, store order, or identical
  payload bytes.
- [ ] Keep FHE cryptographic correctness outside the reduced host-placement
  claim.

### Supporting tests

- [integration/equivalence.test](integration/equivalence.test)
- [integration/metatheory-c-shapes.test](integration/metatheory-c-shapes.test)
- [artifacts/interfaces-negative.test](artifacts/interfaces-negative.test)
- [artifacts/metadata.test](artifacts/metadata.test)

**Accept when:** each destination has an independently justified authorization
decision, and the fixed twins preserve the authorized behavior.

---

## 2. Release causality, sanitization, and explicit oracles

**Why this is second:** release policies are only sound when the expression,
guard, audience, and occurrence are correct at the time of each observation.
These fixtures cover failures that a simple “this value is eventually
released” analysis misses.

### Review these situations

| Situation | C evidence | MLIR evidence | Intended distinction |
| --- | --- | --- | --- |
| Observation occurs before an authorized release | [prefix_causal_release_bad.c](c/prefix_causal_release_bad.c) | [prefix_causal_release.bad.mlir](mlir/prefix-causal-release/bad/prefix_causal_release.bad.mlir) | A later legitimate release cannot retroactively authorize an earlier public store. |
| Padding validity is sanctioned but error detail is not | [bad](c/explicit_error_oracle_bad.c), [fixed](c/explicit_error_oracle_fixed.c) | [bad](mlir/explicit-error-oracle/bad/explicit_error_oracle.bad.mlir), [fixed](mlir/explicit-error-oracle/fixed/explicit_error_oracle.fixed.mlir) | Hold the authorized validity/status release equal; the bad case still reveals secret error detail. |
| CKKS plaintext is released before validation/sanitization | [bad](c/ckks_unsafe_release_bad.c), [fixed](c/ckks_unsafe_release_fixed.c) | [bad](mlir/ckks-release/bad/ckks_unsafe_release.bad.mlir), [fixed](mlir/ckks-release/fixed/ckks_unsafe_release.fixed.mlir) | The fixed reduction applies the public mask and certificate guard before the public sink. |

### Manual checks

- [ ] Draw the observation and release events in execution order.
- [ ] Confirm the ledger is prefix-causal; do not install whole-run release
  equality as an initial relation.
- [ ] Separate sanctioned release fields from unsanctioned detail fields.
- [ ] Verify the CKKS fixed case handles both `certificate_ok == 0` and
  `certificate_ok == 1`.
- [ ] Confirm the private return value may remain raw while the public stored
  value is sanitized.
- [ ] Treat the CKKS sanitizer as a structural toy model; production noise,
  circuit privacy, cryptographic correctness, and integrity sufficiency are
  outside the Rev4 confidentiality claim rather than deployment evidence.
- [ ] Check that a future release never excuses an earlier observation.

### Supporting tests

- [integration/equivalence.test](integration/equivalence.test)
- [integration/metatheory-c-shapes.test](integration/metatheory-c-shapes.test)
- [integration/c-function-coverage.test](integration/c-function-coverage.test)

**Accept when:** the released expression and guard are explicit, the authorized
and unauthorized fields are separated, and event order is part of the review.

---

## 3. Cross-tenant and cross-request residual state

**Why this is third:** pooling, cancellation, scratch reuse, and tenant
transitions are common in services and accelerators. These cases combine byte
memory, ownership changes, lifecycle state, and public outputs.

### Review these situations

| Situation | C evidence | MLIR evidence | Intended distinction |
| --- | --- | --- | --- |
| Prior GPU tenant remains in shared scratch | [bad](c/leftoverlocals_scratch_bad.c), [fixed](c/leftoverlocals_scratch_fixed.c) | [bad](mlir/leftoverlocals-scratch/bad/leftoverlocals_scratch.bad.mlir), [fixed](mlir/leftoverlocals-scratch/fixed/leftoverlocals_scratch.fixed.mlir) | The fixed case overwrites shared scratch with the next tenant's value before it is observed. |
| Canceled Redis response is reused by another request | [bad](c/redis_pool_reuse_bad.c), [fixed](c/redis_pool_reuse_fixed.c) | [bad](mlir/redis-pool-reuse/bad/redis_pool_reuse.bad.mlir), [fixed](mlir/redis-pool-reuse/fixed/redis_pool_reuse.fixed.mlir) | Cancellation must not make actor A's response become actor B's response. |

### Manual checks

- [ ] Identify the ownership transition and the exact byte/object that crosses
  it.
- [ ] Confirm the bad case actually carries old-owner data to the new owner.
- [ ] Confirm the fixed case overwrites or discards the residual state before
  reuse.
- [ ] Check the repair on both normal and cancellation/reuse paths.
- [ ] Do not infer strong updates or disjointness from different source names.
- [ ] Record that real GPU isolation, connection concurrency, and scheduler
  behavior remain deployment-level applicability questions.

### Supporting tests

- [integration/equivalence.test](integration/equivalence.test)
- [integration/c-function-coverage.test](integration/c-function-coverage.test)
- [integration/corpus-representation-coverage.test](integration/corpus-representation-coverage.test)

**Accept when:** ownership and lifecycle transitions are explicit and every
reuse path establishes the new owner's value before observation.

---

## 4. ABI alias-topology honesty

**Why this is fourth:** pointer arguments are ubiquitous, and assuming
separation from distinct SSA names is an unsound shortcut. The three fixtures
share the same load/store shape; only the independently bound ABI topology
changes the future disposition.

### Review the complete triad

| Case | C evidence | MLIR evidence | Bundle | Future matcher intent |
| --- | --- | --- | --- | --- |
| Missing topology | [abi_alias_unproved.c](c/abi_alias_unproved.c) | [abi_alias_missing_binding.unknown.mlir](mlir/abi-alias/missing-binding-unknown/abi_alias_missing_binding.unknown.mlir) | [abi-alias-missing-binding](artifacts/abi-alias-missing-binding/) | `Unknown(AliasBindingMismatch)` |
| `MayAlias` with equal-base realization | same source | [abi_alias_mayalias_overlap.bad.mlir](mlir/abi-alias/mayalias-overlap-bad/abi_alias_mayalias_overlap.bad.mlir) | [abi-alias-mayalias-overlap](artifacts/abi-alias-mayalias-overlap/) | `AuditAll` SAT remains `CandidateOnly`; accepted exact replay yields `Counterexample(receiptId)`. |
| Proved `Disjoint` control | same source | [abi_alias_disjoint.control.mlir](mlir/abi-alias/disjoint-control/abi_alias_disjoint.control.mlir) | [abi-alias-disjoint](artifacts/abi-alias-disjoint/) | `Proved`, after all still-missing Rev4 premises are implemented |

### Manual checks

- [ ] Confirm all three entries store the secret through `p`, load through
  `q`, and publish the loaded value.
- [ ] Verify no LLVM `noalias` attribute or distinct SSA name is treated as the
  independent ABI proof.
- [ ] Inspect `abi.json` in each bundle and compare `complete`, `relations`, and
  any required alias realization.
- [ ] In the may-alias case, replay `p == q` and confirm the public output
  changes with the secret.
- [ ] In the disjoint control, confirm initialized memory for `q` and complete
  pairwise topology are represented.
- [ ] Ensure an implementation distinguishes all three results; always-refuse
  and always-assume-disjoint are both wrong.

### Supporting tests

- [integration/metatheory-c-shapes.test](integration/metatheory-c-shapes.test)
- [artifacts/pairs.test](artifacts/pairs.test)
- [artifacts/generate-reproducible.test](artifacts/generate-reproducible.test)
- [artifacts/pairs-negative.test](artifacts/pairs-negative.test)
- [artifacts/interfaces-negative.test](artifacts/interfaces-negative.test)

**Accept when:** the reviewer can explain why identical LLVM bodies have three
different intended outcomes solely from independently bound ABI facts.

---

## 5. Direct public outputs, lengths, logs, and counts

**Why this is fifth:** these are the most recognizable confidentiality
failures. They cover public logs, checkpoint artifacts, wire lengths,
allocation counts, and iteration counts without requiring a complicated
release model.

### Review these situations

| Situation | C evidence | MLIR evidence | Intended distinction |
| --- | --- | --- | --- |
| Secret logged and exported to a checkpoint | [bad](c/secret_logging_checkpoint_bad.c), [fixed](c/secret_logging_checkpoint_fixed.c) | [bad](mlir/secret-logging-checkpoint/bad/secret_logging_checkpoint.bad.mlir), [fixed](mlir/secret-logging-checkpoint/fixed/secret_logging_checkpoint.fixed.mlir) | The private state keeps the token; public log and checkpoint are redacted. |
| BREACH-style compressed wire length | [bad](c/breach_compressed_length_bad.c), [fixed](c/breach_compressed_length_fixed.c) | [bad](mlir/breach-compressed-length/bad/breach_compressed_length.bad.mlir), [fixed](mlir/breach-compressed-length/fixed/breach_compressed_length.fixed.mlir) | The bad length distinguishes a secret/guess match; the fixed wire length is constant. |
| Secret-dependent tensor/KV-cache size | [bad](c/dynamic_kv_length_bad.c), [fixed](c/dynamic_kv_length_fixed.c) | [bad](mlir/dynamic-kv-length/bad/dynamic_kv_length.bad.mlir), [fixed](mlir/dynamic-kv-length/fixed/dynamic_kv_length.fixed.mlir) | Public allocation and work counts are secret-dependent in the bad case and fixed at 64 in the repair. |

### Manual checks

- [ ] Enumerate every public sink separately; checking only one log, counter, or
  checkpoint is insufficient.
- [ ] Confirm private state or private return behavior is preserved by the
  repair.
- [ ] For BREACH, compare two secrets under the same public guess and body.
- [ ] For dynamic length, check both allocation count and iteration count.
- [ ] Verify fixed constants are declared public protocol choices and do not
  silently truncate required functionality.
- [ ] Check the MLIR stores the same values described by the C reduction.

### Supporting tests

- [integration/equivalence.test](integration/equivalence.test)
- [integration/c-to-mlir-import.test](integration/c-to-mlir-import.test)
- [integration/generated-import-pipeline.test](integration/generated-import-pipeline.test)

**Accept when:** every observable field is reviewed independently and the fixed
case preserves the private computation while normalizing only public metadata.

---

## 6. Secret-dependent addresses and indexing

**Why this is sixth:** secret indexing occurs in embeddings, lookup tables,
cryptography, and model inference. Equal loaded values do not make unequal
addresses safe under the fixed `Theta_ct` observation semantics.

### Review the pair

| Case | C evidence | MLIR evidence | Intended distinction |
| --- | --- | --- | --- |
| Direct secret table lookup | [secret_embedding_index_bad.c](c/secret_embedding_index_bad.c) | [secret_embedding_index.bad.mlir](mlir/secret-embedding-index/bad/secret_embedding_index.bad.mlir) | The secret chooses the GEP/load address. |
| Full public-index scan | [secret_embedding_index_fixed.c](c/secret_embedding_index_fixed.c) | [secret_embedding_index.fixed.mlir](mlir/secret-embedding-index/fixed/secret_embedding_index.fixed.mlir) | All 16 public addresses are visited; mask selection changes values, not addresses. |

### Manual checks

- [ ] Compare address traces, not only returned values.
- [ ] Verify the bad GEP index contains the secret after the explicit `& 15`
  domain reduction.
- [ ] Verify the fixed loop visits exactly the same 16 addresses for every
  secret.
- [ ] Check the equality mask has no secret-dependent branch in the reviewed
  source/IR boundary.
- [ ] Exercise indices with high bits set so the wrap behavior is reviewed.
- [ ] Do not claim a torch-mlir or backend theorem from the reduced source
  shape.

### Supporting tests

- [diagnostic/address.test](diagnostic/address.test), when `SPS_SCAN` is available
- [integration/equivalence.test](integration/equivalence.test)
- [integration/generated-import-pipeline.test](integration/generated-import-pipeline.test)

**Accept when:** the fixed address sequence is public and invariant, while only
the selected value remains secret-dependent.

---

## 7. Loop bounds and world-structural allocation sizes

**Why this is seventh:** bounds and allocation sizes affect control,
termination, stack behavior, and event traces. Public caps are not proofs that
actual secret-selected sizes or reachable remainder states are equal.

### Review the paired splits

| Case | C evidence | MLIR evidence | Bundle | Future oracle intent |
| --- | --- | --- | --- | --- |
| Secret loop trip count | [bound_exhausted_loop.c](c/bound_exhausted_loop.c) | [bound_secret_trip_count.bad.mlir](mlir/loop-bounds/secret-trip-count-bad/bound_secret_trip_count.bad.mlir) | [bound-secret-trip-count](artifacts/bound-secret-trip-count/) | Replay counts 0 and 1 as a control counterexample. |
| Public loop exceeds proof bound | same source | [bound_exhausted_loop.unknown.mlir](mlir/loop-bounds/public-bound-exhausted-unknown/bound_exhausted_loop.unknown.mlir) | [bound-exhausted-public](artifacts/bound-exhausted-public/) | Retain aligned reachable exhaustion as `Unknown(LoopRemainder)`; never delete it into a proof. |
| Secret-selected VLA size | [alloca_size_models.c](c/alloca_size_models.c) | [alloca_size_high_count.unknown.mlir](mlir/alloca-size/high-count-unknown/alloca_size_high_count.unknown.mlir) | [alloca-size-high](artifacts/alloca-size-high/) | `Unknown(AllocaSizeNotWorldStructural)` |
| Public, validated VLA size control | same source | [alloca_size_public.control.mlir](mlir/alloca-size/public-control/alloca_size_public.control.mlir) | [alloca-size-public](artifacts/alloca-size-public/) | Positive control, with range, overflow, and stack-feasibility obligations. |

### Manual checks

- [ ] Distinguish the secret-count counterexample from symmetric public bound
  exhaustion.
- [ ] Confirm a proof engine keeps `BoundExhausted` as a reachable state rather
  than filtering the execution.
- [ ] Separate a semantic loop remainder from an engine resource limit.
- [ ] Trace the actual VLA byte-size operand; do not substitute a public upper
  bound.
- [ ] Verify the public VLA control binds range, overflow freedom, and stack
  feasibility rather than merely labeling the count public.
- [ ] Check stack-protector or compiler-added behavior does not silently enter
  the claimed frozen normal form.

### Supporting tests

- [diagnostic/branch.test](diagnostic/branch.test)
- [diagnostic/alloca.test](diagnostic/alloca.test)
- [diagnostic/public-control.test](diagnostic/public-control.test)
- [integration/metatheory-c-shapes.test](integration/metatheory-c-shapes.test)
- [artifacts/metadata.test](artifacts/metadata.test)

**Accept when:** secret divergence, aligned exhaustion, and proved-public bounds
produce three distinguishable review conclusions.

---

## 8. Release-carrier preservation and conformance

**Why this is eighth:** declassification cannot be bound reliably after the
compiler has erased, merged, duplicated, or replaced its carrier. This family
has broad theorem impact but applies specifically to systems with explicit
release APIs.

### Review the complete carrier triad

| Case | C evidence | MLIR evidence | Intended distinction |
| --- | --- | --- | --- |
| Carrier lost to inlining | [release_carrier.c](c/release_carrier.c) | [release_carrier_lost.bad.mlir](mlir/release-carrier/lost-bad/release_carrier_lost.bad.mlir) | Bare release-shaped arithmetic/stores cannot recover stable site identity or multiplicity. Expected refusal, not a leak verdict. |
| Marker-only workaround | same source | [release_carrier_marker_only.bad.mlir](mlir/release-carrier/marker-only-bad/release_carrier_marker_only.bad.mlir) | A policy string on a store is not authority, and the raw stored value is not the declared release expression. |
| Pinned outlined carrier | same source | [release_carrier_pinned.control.mlir](mlir/release-carrier/pinned-control/release_carrier_pinned.control.mlir) | Direct wrapper call survives with `noinline`, `nomerge`, `noduplicate`, and `nobuiltin`. |

### Manual checks

- [ ] Identify the call occurrence as the carrier; the later store is an
  ordinary output event.
- [ ] Verify exact static multiplicity and ordinal against the manifest.
- [ ] Verify argument roles, result type, expression, and guard.
- [ ] Confirm `tail`, `musttail`, `notail`, `invoke`, and `callbr` are not
  silently accepted by a direct-call-only profile.
- [ ] Confirm all four optimizer pins survive in LLVM IR.
- [ ] Treat marker-only recovery as two independent failures: missing carrier
  and wrong extensional expression.
- [ ] Verify `sps.*` MLIR attributes disappear during MLIR-to-LLVM translation;
  downstream authority must come from sidecars, not those attributes.
- [ ] Remember that a C `noinline` wrapper alone cannot express the full pin set.

### Supporting tests

- [integration/release-carrier-inline-survival.test](integration/release-carrier-inline-survival.test)
- [integration/bitcode-carrier-survival.test](integration/bitcode-carrier-survival.test)
- [integration/release-marker-lowering.test](integration/release-marker-lowering.test)
- [integration/policy-carrier-loss.test](integration/policy-carrier-loss.test)

**Accept when:** the reviewer can bind a stable direct call occurrence and can
explain why both a missing carrier and a hand-added marker must fail closed.

---

## 9. Relational precision and false-positive controls

**Why this is ninth:** soundness is not enough if the checker reports every
secret-derived value. These controls require exact relational reasoning while
the predecessor anti-control prevents an overbroad “identical successor”
shortcut.

### Review these cases together

| Case | C evidence | MLIR evidence | Intended distinction |
| --- | --- | --- | --- |
| Secret predecessor chooses public constants | [predecessor_choice_blockarg_bad.c](c/predecessor_choice_blockarg_bad.c) | [predecessor_choice_blockarg.bad.mlir](mlir/predecessor-choice/blockarg-bad/predecessor_choice_blockarg.bad.mlir) | The leak is carried by predecessor choice/block arguments even though the arm constants are public. |
| Identical successor control | [precision_controls.c](c/precision_controls.c) | [precision_identical_successor.control.mlir](mlir/precision-control/identical-successor/precision_identical_successor.control.mlir) | Both edges reach the same continuation without differing block arguments. |
| XOR cancellation | same source | [precision_xor_cancellation.control.mlir](mlir/precision-control/xor-cancellation/precision_xor_cancellation.control.mlir) | `secret ^ secret` is equal across lanes despite unary High dependence. |
| Public overwrite before reload | same source | [precision_overwritten_slot.control.mlir](mlir/precision-control/overwritten-slot/precision_overwritten_slot.control.mlir) | The secret store is fully overwritten before observation. |
| Offset-disjoint public reload | same source | [precision_offset_disjoint.control.mlir](mlir/precision-control/offset-disjoint/precision_offset_disjoint.control.mlir) | Secret byte 4 does not affect public byte 8. |

### Manual checks

- [ ] Review the predecessor edge and block-argument operands, not only SSA
  operand ancestry.
- [ ] Verify the identical-successor control has no differing edge payload.
- [ ] Evaluate XOR extensionally in both lanes.
- [ ] Require an exact strong overwrite before accepting the slot control.
- [ ] Check byte offsets and widths, not source field names.
- [ ] Ensure these controls request relational analysis rather than granting a
  diagnostic shortcut as proof.
- [ ] Confirm the predecessor anti-control remains bad after any proposed
  precision improvement.

### Supporting tests

- [diagnostic/known-imprecision.test](diagnostic/known-imprecision.test)
- [integration/metatheory-c-shapes.test](integration/metatheory-c-shapes.test)
- [integration/equivalence.test](integration/equivalence.test)

**Accept when:** all four controls avoid false positives without making the
predecessor-choice leak disappear.

---

## 10. Backend-created branches, loads, and spills

**Why this is tenth:** source or LLVM branchlessness does not guarantee a
constant target trace. This family is broadly relevant to compiled
constant-time code, but its conclusions are target- and stage-specific.

### Review these situations

| Situation | Main evidence | Intended distinction |
| --- | --- | --- |
| LLVM select becomes an x86 branch | [launder MLIR](mlir/launder-scan/model-clean-p4-open/launder_scan.model_proved.p4_open.mlir), [bad C](c/launder_scan_bad.c), [folded C](c/launder_scan_folded_bad.c), [barrier C](c/launder_scan_fixed.c), [candidate bundle](artifacts/launder-scan/) | The modeled LLVM trace can be safe while x86 introduces secret control; AArch64 retains `csel`. Deployment remains open. |
| Clangover source mask becomes target control | [source MLIR](mlir/clangover-poly-frommsg/source/clangover_poly_frommsg.source.mlir), [lowered bad](mlir/clangover-poly-frommsg/lowered-bad/clangover_poly_frommsg.lowered_bad.mlir), [lowered fixed](mlir/clangover-poly-frommsg/lowered-fixed/clangover_poly_frommsg.lowered_fixed.mlir), [vulnerable C](c/clangover_poly_frommsg_vulnerable.c), [fixed C](c/clangover_poly_frommsg_fixed.c), [helper C](c/clangover_ct_cmov.c) | The separately compiled helper provides the reviewed boundary; source value equivalence alone is insufficient. |
| Register allocation introduces stack traffic | [source](ext/spill.c), [opaque support](ext/spill_opaque.c), [LLVM input](ext/spill.ll), [debug LLVM input](ext/spillg.ll), [MIR snapshots](ext/) | Frozen LLVM has no local stores, but register allocation and frame lowering introduce spill stores, reloads, and stack offsets. |

### Manual checks

- [ ] Record the exact target triple, CPU/features, compiler version, flags,
  and backend stage.
- [ ] Compare control, address, and memory traces before and after instruction
  selection.
- [ ] For laundering, verify the exact checked-in bitcode is the input to direct
  MLIR import and both target code generators.
- [ ] Record that the laundering C function returns `i64` while the candidate
  MLIR model writes an owner-private sink. The C source motivates the compiler
  shape; it is not ABI-equivalent provenance for the candidate bytes.
- [ ] For Clangover, verify all 32 message-byte positions and the separately
  compiled helper boundary.
- [ ] For spills, compare `virtregrewriter` abstract stack slots with
  `prologepilog` concrete SP offsets.
- [ ] Do not turn assembly `FileCheck` into `DeploymentStatus: Closed`.
- [ ] Do not let a backend delta retroactively change the independent LLVM
  model intent.

### Supporting tests

- [integration/laundering-llvm-shape.test](integration/laundering-llvm-shape.test)
- [integration/bitcode-direct-consumers.test](integration/bitcode-direct-consumers.test)
- [p4-risk/laundering-x86-codegen.test](p4-risk/laundering-x86-codegen.test)
- [integration/clangover-frozen-ir-branchless.test](integration/clangover-frozen-ir-branchless.test)
- [p4-risk/clangover-x86-codegen.test](p4-risk/clangover-x86-codegen.test)
- [p4-risk/register-allocation-spill.test](p4-risk/register-allocation-spill.test)
- [integration/refusal-rate.test](integration/refusal-rate.test)

**Accept when:** LLVM and backend claims remain separate, and every target claim
is tied to the exact bytes, target, and code-generation stage reviewed.

---

## 11. Source-level variable-latency arithmetic

**Why this is eleventh:** secret division is a common constant-time hazard, but
these particular reductions are cryptographic and their final latency remains
target-dependent.

### Review the KyberSlash pairs

| Situation | C evidence | MLIR evidence | Intended distinction |
| --- | --- | --- | --- |
| `poly_tomsg` secret division | [bad](c/kyberslash1_poly_tomsg_vulnerable.c), [fixed](c/kyberslash1_poly_tomsg_fixed.c) | [bad](mlir/kyberslash1-poly-tomsg/bad/kyberslash1_poly_tomsg.bad.mlir), [fixed](mlir/kyberslash1-poly-tomsg/fixed/kyberslash1_poly_tomsg.fixed.mlir) | Replace secret `udiv` with reviewed reciprocal/shift arithmetic. |
| `poly_compress` secret division | [bad](c/kyberslash2_compress_vulnerable.c), [fixed](c/kyberslash2_compress_fixed.c) | [bad](mlir/kyberslash2-compress/bad/kyberslash2_compress.bad.mlir), [fixed](mlir/kyberslash2-compress/fixed/kyberslash2_compress.fixed.mlir) | Same operation-class distinction under a different rounding expression. |

### Manual checks

- [ ] Confirm the divisor and numerator relationship in the bad source.
- [ ] Verify the fixed constants and shifts implement the same result for all
  coefficients in the declared domain.
- [ ] Check no `udiv` remains in the reviewed fixed LLVM shape.
- [ ] Review overflow, width, truncation, and rounding behavior.
- [ ] Keep source-operation triage separate from target latency guarantees.

### Supporting tests

- [integration/kyberslash-codegen.test](integration/kyberslash-codegen.test)
- [diagnostic/latency.test](diagnostic/latency.test), when `SPS_SCAN` is available
- [integration/equivalence.test](integration/equivalence.test)

**Accept when:** functional equivalence and removal of the named variable-time
operation are both checked, without claiming final-target timing closure.

---

## 12. Target-profile helpers and target-specific timing

**Why this is last among semantic fixtures:** the principles are important, but
the concrete conclusions depend on RV32I profiles, helper implementations, and
specific compiler behavior. Review these after the target-independent
properties above.

### Review the wolfSSL target models

| Situation | C evidence | MLIR evidence | Intended distinction |
| --- | --- | --- | --- |
| CVE-2026-3580 table-selection lowering | [bad](c/wolfssl_3580_mask_vulnerable.c), [fixed](c/wolfssl_3580_mask_fixed.c) | [source](mlir/wolfssl-3580-mask/source/wolfssl_3580_mask.source.mlir), [target bad](mlir/wolfssl-3580-mask/target-bad/wolfssl_3580_mask.target_bad.mlir), [target fixed](mlir/wolfssl-3580-mask/target-fixed/wolfssl_3580_mask.target_fixed.mlir) | Source masking does not by itself prove the RV32 target lacks a secret branch. |
| CVE-2026-3579 multiply on RV32I without M | [bad](c/wolfssl_3579_mul_vulnerable.c), [fixed](c/wolfssl_3579_mul_fixed.c) | [source](mlir/wolfssl-3579-mul/source/wolfssl_3579_mul.source.mlir), [unknown helper](mlir/wolfssl-3579-mul/target-unknown/wolfssl_3579_mul.target_unknown.mlir), [affected helper contract](mlir/wolfssl-3579-mul/target-bad/wolfssl_3579_mul.target_bad.mlir), [constant-latency test profile](mlir/wolfssl-3579-mul/target-constant-latency/wolfssl_3579_mul.target_constant_latency.mlir), [fixed loop](mlir/wolfssl-3579-mul/target-fixed/wolfssl_3579_mul.target_fixed.mlir) | A helper call is unknown without a contract; different explicit target profiles lead to different review conclusions. |

### Manual checks

- [ ] Verify RV32I target flags and the absence of the M extension.
- [ ] Treat an external helper with no timing summary as unknown, not safe.
- [ ] Check every timing contract is bound to a named target profile and helper
  identity.
- [ ] Verify the fixed multiply loop has a public fixed count and fixed
  operation schedule.
- [ ] Distinguish the synthetic constant-latency test profile from a real
  deployment claim.
- [ ] For CVE-2026-3580, review the actual GCC assembly when the optional
  cross-compiler is available.
- [ ] Do not treat hand-minimized target MLIR as literal compiler output.

### Supporting tests

- [p4-risk/wolfssl-3579-rv32-codegen.test](p4-risk/wolfssl-3579-rv32-codegen.test)
- [p4-risk/wolfssl-3580-rv32-gcc.test](p4-risk/wolfssl-3580-rv32-gcc.test)
- [integration/generated-import-pipeline.test](integration/generated-import-pipeline.test)
- [integration/equivalence.test](integration/equivalence.test)

**Accept when:** every helper and timing conclusion is explicitly
target-profile-bound, and missing summaries remain unknown.

---

## Cross-cutting artifact review

Perform this review for each of the nine semantic bundles referenced above.
Review bundle members in this order:

1. `artifact.json`
   - candidate-only schema and role;
   - source MLIR path and hash;
   - candidate bitcode and derived LLVM hashes;
   - exact recorded producer tools;
   - `not_authoritative: true` and the complete missing-premise list.
2. `artifact.bc` and `artifact.ll`
   - `.bc` is the source of truth;
   - `.ll` is exact `llvm-dis` output;
   - source MLIR lowers to the exact candidate bytes;
   - fresh parsing and canonical-writer expectations are not confused with
     Rev4 `NFConforms`.
3. `abi.json`
   - entry exists exactly once;
   - argument indices and arity match LLVM;
   - every root is pointer-typed and every scalar is non-pointer;
   - alias topology and initialized regions are complete for the intended case.
   - extents and initialized widths cover the actual LLVM loads and stores.
4. `policy.json`
   - placement and coalition universe match the scenario;
   - declared principals, outputs, components, and release IDs are internally
     consistent;
   - policy facts are independent inputs, not inferred from IR annotations.
5. `release-table.json` and `contracts.json`
   - callee, ordinal, multiplicity, expression, guard, and audience match the
     actual direct calls;
   - mechanism ABI matches the LLVM declaration or definition.
   - release audiences name declared principals and footprints name declared
     components;
   - the release value expression and mechanism relation agree extensionally,
     not merely by sharing a name.
6. `expected-report.json`
   - current state is `Pending`;
   - `claimable_from_checked_in_pair` is false;
   - the future oracle is plausible for every product row;
   - model, deployment, and policy-review axes remain independent.

Run:

```sh
make check-artifacts
python3 tools/artifact_bundle.py check --llvm-bin /path/to/recorded/llvm/bin
```

Supporting tests:

- [artifacts/metadata.test](artifacts/metadata.test)
- [artifacts/pairs.test](artifacts/pairs.test)
- [artifacts/generate-reproducible.test](artifacts/generate-reproducible.test)
- [artifacts/pairs-negative.test](artifacts/pairs-negative.test)
- [artifacts/interfaces-negative.test](artifacts/interfaces-negative.test)

## Cross-cutting representation and coverage review

These tests do not establish a semantic verdict. Review them after the scenario
families to confirm that no representation silently escapes the harness.

| Review purpose | Tests |
| --- | --- |
| Every C fixture executes and the bad/fixed values are asserted | [c-function-coverage.test](integration/c-function-coverage.test), [equivalence.test](integration/equivalence.test) |
| Every checked-in C, MLIR, LL, BC, and MIR input is parsed or explicitly refused | [corpus-representation-coverage.test](integration/corpus-representation-coverage.test) |
| Target-specific C producer DAG creates ten LL and ten imported MLIR outputs | [generated-import-pipeline.test](integration/generated-import-pipeline.test) |
| C provenance and MLIR annotation manifests remain complete | [integration metadata](integration/metadata.test), [MLIR metadata](mlir/metadata.test) |
| Direct Clang bitcode and canonical-writer boundaries remain explicit | [bitcode-canonical-roundtrip.test](integration/bitcode-canonical-roundtrip.test), [bitcode-producer-normalization.test](integration/bitcode-producer-normalization.test) |
| Accepted and rejected normal-form fragments remain separated | [hash-release-fragment-boundary.test](integration/hash-release-fragment-boundary.test) |
| Textual LLVM observation/refusal parsing covers calls, atomics, and debug provenance | [refusal-rate.test](integration/refusal-rate.test) |

### Normal-form release-body boundary

Review these non-scenario fixtures as an accepted/refused fragment pair:

- [argmax_release_body.c](c/argmax_release_body.c) is the positive control. Its
  bounded loop, public-offset loads, comparisons, and selects remain inside the
  intended integer surface.
- [sha256_round_release_body.c](c/sha256_round_release_body.c) is not a leak
  case. Rotation canonicalizes to `llvm.fshl.i32`, so it is deliberately
  outside the current fragment and must be refused.
- [hash-release-fragment-boundary.test](integration/hash-release-fragment-boundary.test)
  pins the accepted/refused distinction.
- [bitcode-canonical-roundtrip.test](integration/bitcode-canonical-roundtrip.test)
  confirms canonical writer idempotence does not erase either the accepted
  shape or the rejected intrinsic.
- [bitcode-producer-normalization.test](integration/bitcode-producer-normalization.test)
  records the LLVM-17-specific initial writer normalization.

Manual checks:

- [ ] Argmax initializes its running maximum from `logits[0]`, including an
  all-negative input domain.
- [ ] Strict `>` preserves the lowest-index tie rule.
- [ ] The loop and load offsets are public; the chosen index is not used for a
  secret-dependent reload.
- [ ] SHA rotation produces `llvm.fshl.i32`.
- [ ] The SHA case is recorded as out-of-fragment, never as a confidentiality
  counterexample.
- [ ] Writer idempotence is not called Rev4 canonicality or `NFConforms`.

Run the complete baseline before and after a manual review batch:

```sh
make check
```

A normal run may leave capability-gated tests unsupported when `SPS_SCAN` or
the optional RV32 GCC cross-compiler is absent. Unsupported is not equivalent
to passed.

## Completeness ledger

The ranked semantic queue accounts for all 53 checked-in MLIR fixture files:

| Rank | Family | MLIR files |
| ---: | --- | ---: |
| 1 | Recipient/host/audience authorization | 5 |
| 2 | Release causality/sanitization/oracles | 5 |
| 3 | Cross-tenant residual state | 4 |
| 4 | ABI alias topology | 3 |
| 5 | Direct public outputs | 6 |
| 6 | Secret-dependent addresses | 2 |
| 7 | Bounds and allocation sizes | 4 |
| 8 | Release carriers | 3 |
| 9 | Relational precision | 5 |
| 10 | Backend-created observations | 4 |
| 11 | Variable-latency arithmetic | 4 |
| 12 | Target-profile helpers | 8 |
|  | **Total** | **53** |

The cross-cutting review additionally covers:

- 44 C reduction/helper files plus the equivalence driver;
- 9 candidate semantic bundles and their 9 `.bc`/derived `.ll` pairs;
- 2 additional checked-in LLVM inputs and 1 release-marker LLVM input;
- 7 MIR snapshots;
- generated target-specific LL/MLIR outputs; and
- the artifact, integration, diagnostic, and P4 test strata.

The complete lit inventory is 114 tests: 53 MLIR shapes, 2 MLIR snapshot tests,
35 integration tests, 5 artifact tests, 5 P4-risk tests, 6 diagnostic tests,
and 8 SPS report/future-verifier tests.

### Known out-of-inventory evidence

The automatic representation inventory intentionally does not validate every
file under `ext/`. Review these manually before using them as evidence:

- [spill.s](ext/spill.s) is checked-in assembly context but is not regenerated,
  hash-bound, or consumed by a lit test.
- `ext/spill_run`, `ext/spill_g`, and `ext/spill_g.o` are local Mach-O
  experiments, not theorem inputs.
- Any accompanying dSYM data is likewise outside the harness inventory.
- [spill.c](ext/spill.c) and [spill_opaque.c](ext/spill_opaque.c) explain the
  experiment but are outside the automatic `c/*.c` coverage glob.

Treat the dynamically regenerated `virtregrewriter` and `prologepilog` MIR in
[register-allocation-spill.test](p4-risk/register-allocation-spill.test) as the
current regression evidence. Treat the other checked-in MIR stages as
explanatory, parse-checked snapshots.

## Final manual sign-off

Do not sign off the fixture set until all of the following are true:

- [ ] Every ranked family has a reviewer, date, decision, and notes.
- [ ] Every bad case has a concrete trace or named fail-closed reason.
- [ ] Every fixed/control case blocks a trivial always-report or always-refuse
  implementation.
- [ ] C intent, MLIR shape, and sidecar bindings agree.
- [ ] The nine candidate bundles pass integrity and interface checks.
- [ ] Target-specific claims are tied to exact targets and stages.
- [ ] Unsupported optional tests are recorded explicitly.
- [ ] No diagnostic, preflight shape, expected oracle, or P4 snapshot is
  presented as a current Rev4 theorem result.
