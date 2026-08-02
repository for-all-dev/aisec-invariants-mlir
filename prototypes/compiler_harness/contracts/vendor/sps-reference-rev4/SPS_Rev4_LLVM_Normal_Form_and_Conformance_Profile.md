# SPS Revision 4.1 LLVM Normal Form and Conformance Profile

**Profile identifier:** `SPS-LLVM-NF-v2`  
**Pinned LLVM baseline:** `llvmorg-22.1.8`  
**Pinned upstream commit:** `ca7933e47d3a3451d81e72ac174dcb5aa28b59d1`  
**Status:** normative conformance profile incorporated by the sole SPS rev-4 normative specification  
**Normative owner:** [[SPS_Rev4_Normative_Specification]]  
**Proof companion:** [[SPS_Rev4_Metatheory_and_Written_Proofs]]  
**Issue and acceptance record:** [[SPS_Rev4_Issue_Resolution_and_Research_Roadmap]]

---

## 0. Authority, purpose, and conformance language

This document defines the LLVM artifact profile accepted by SPS rev-4. It has one
normative export:

$$
\operatorname{NFConforms}(T,I),
$$

where:

- $T$ is the parsed, frozen LLVM module analyzed by SPS; and
- $I$ is its `ArtifactIdentityV2`.

`SPS_Rev4_Normative_Specification.md` is the sole definition of SPS policy,
admission, observations, release authorization, relational products, security,
and the final theorem. That specification incorporates this profile through
`NFConforms(T,I)`. This profile does **not** define a second confidentiality
theorem, a competing policy language, or a competing `Product_A` or `Bad_A`
judgment.

This document presents the sole active Rev4.1 profile. Its profile,
identity/configuration, report, replay, blocker, and aggregation roots are the
V2 roots published in `interfaces/rev4.1`. The accepted root set is closed;
any unlisted root or format identifier is rejected without conversion.
Mathematical helper identifiers are not wire-format roots unless the Rev4.1
registry lists them as roots.

In particular, `SPS-PolicyExpr-NF-v2`, `SPS-PONF-v2`,
`BuildPONF_v2`, and `ReleaseConforms_e(q,T)` are imported from the sole
normative specification. Requirements below bind LLVM carriers and proof
records to those imported objects; they do not add another normative export to
this profile.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, and **MAY** are to be interpreted as normative
requirements.

The profile is deliberately fail-closed:

> A `Proved` `ModelStatus` is available only for the exact pinned normalized
> artifact that passes every conformance, definedness, closure, and public-bound
> adequacy check. An unclassified instruction, type, intrinsic, attribute,
> metadata item, call, vector form, unproved public-bound adequacy, insufficient
> engine cap, incomplete product construction, or coverage failure contributes
> `Unknown`; it is never
> silently modeled as harmless. A satisfiable control, status, definedness, or
> observation divergence that reaches `Bad_A` under exact replay is instead a
> `Counterexample(receiptId)`.

Functional correctness between a source program, a pre-normalized LLVM module,
and $T$ is a separate compiler-correctness claim. SPS proves properties of the
exact $T$ named by $I$.

### 0.1 Repair identifiers

The following stable identifiers name the repairs embodied by this profile.

| ID | Repair |
|---|---|
| `NF-R1` | Exact final-IR freeze immediately before the first IR-to-MIR translator |
| `NF-R2` | Complete artifact, toolchain, target, pipeline, alloca-size, public-alias-topology, and manifest binding |
| `NF-R3` | Exhaustive scalar LLVM normal form with residual-surface rejection and a syntactically empty prohibited-FP inventory |
| `NF-R4` | Semantics-weakening annotation removal with ABI preservation |
| `NF-R5` | `freeze` removal only under a checked non-undef/non-poison fact |
| `NF-R6` | Closed direct-call analysis-time inlining with explicit call budgets |
| `NF-R7` | Normative public-bound expansion with exact exhaustion behavior and a separate engine cap |
| `NF-R8` | Exact byte memory, world-structural allocation size, exact-byte address observations, and definedness, with non-authoritative diagnostic ghost facts |
| `NF-R9` | Mechanical product prerequisites, domain/activation queries, and source-independent replay coverage |
| `NF-R10` | Fail-closed conformance and counterexample-before-Unknown-before-Proved result mapping |
| `NF-R11` | Pointer equality accepted only for byte-identical canonical `AllocationKey` terms, then exact modular `OffsetKey` equality |
| `NF-R12` | Explicit separation of LLVM `undef`-producing loads from LLVM UB-risk transitions |
| `NF-R13` | Target-bound timing/Spectre diagnostics, final-machine control-delta P4 evidence, and explicit stack-protector refusal telemetry |

---

# 1. Fixed LLVM baseline

## 1.1 Exact upstream coordinate

`SPS-LLVM-NF-v2` recognizes only the following upstream baseline:

```text
repository: https://github.com/llvm/llvm-project
tag:        llvmorg-22.1.8
commit:     ca7933e47d3a3451d81e72ac174dcb5aa28b59d1
```

A build from another commit does not conform merely because it reports version
`22.1.8`. A patched SPS compiler MUST additionally record the patch-tree commit,
compiler executable hash, and linked LLVM library hashes in the closed build
evidence below. The exact binary/library digests bind build and assertions
modes without adding open descriptive fields. The one selected target is
bound by `TargetConfigurationEvidenceV2`, and every pass plugin actually used
is bound by its `PassTraceRowV2.pluginDigest`; compiled-in but unselected
targets and loadable-but-unused plugins are not semantic inputs and are not
identity fields.

LLVM 22.1.8 uses the legacy pass manager for the code-generation pipeline. The
profile therefore binds the ordered legacy code-generation pass trace, including
target-specific overrides, rather than relying on an `-O2` label or a textual
pipeline approximation.

## 1.2 Version isolation

The following are versioned as one inseparable semantics pack:

```text
SPS-LLVM-NF-v2
LLVM 22.1.8 commit
SPS compiler patch commit
normalizer implementation hash
normal-form auditor implementation hash
LLVM semantics table hash
Rev4.1 interface-package digest
canonical bitcode writer mode
```

Changing any item requires a new conformance run. An LLVM upgrade requires a new
profile identifier unless a rev-4 normative update explicitly declares the new
coordinate equivalent.

---

# 2. Artifact objects and identity

## 2.1 Frozen bytes and parsed module

Let:

$$
B=\operatorname{CanonicalBitcode}(N)
$$

be the frozen bitcode bytes emitted from the final normalized module $N$, and
let:

$$
T=\operatorname{Parse}_{22.1.8}(B).
$$

The canonical writer MUST use the pinned LLVM 22.1.8 bitcode writer with:

- use-list preservation disabled;
- ThinLTO and regular-LTO summaries absent because LTO is already complete;
- no timestamp, temporary path, random seed, or process identifier injected by
  the SPS capture pass;
- every semantic module flag, attribute, metadata item, global, declaration,
  function body, target triple, and `DataLayout` retained; and
- the exact writer options included in $I$.

Debug metadata MAY be retained. If retained, it is part of $B$ and its hash even
though it is ignored by the model semantics.

## 2.2 `ArtifactIdentityV2`, evidence, and proof configuration

The closed schemas in `interfaces/rev4.1` are the wire-format authority. The
active identity root is `ArtifactIdentityV2`; the only admissible preimage
closure is `ArtifactIdentityEvidenceV2`; and the only proof-configuration root
is `ProofConfigurationV2`. Their fixed literals are:

```text
ArtifactIdentityV2.formatId             = "SPS-ArtifactIdentity-v2"
ArtifactIdentityV2.profileId            = "SPS-LLVM-NF-v2"
ArtifactIdentityV2.normalFormVersion    = "SPS-LLVM-NF-v2"
ArtifactIdentityV2.finalWeakenerId      = "SPSFinalWeaken_v2"
ArtifactIdentityV2.releaseTableFormatId = "SPS-ReleaseTable-v2"
ProofConfigurationV2.formatId           = "SPS-Proof-Configuration-v2"
ProofConfigurationV2.aggregationSemantics
                                         = "SPS-Model-Aggregation-v2"
ProofConfigurationV2.replayAcceptanceSemantics
                                         = "SPS-Replay-Acceptance-v2"
```

`ArtifactIdentityV2` binds the canonical bitcode hash and one separately named
digest for every compiler, target, ABI, policy, release, contract, placement,
alias, allocation, stable-IR, transition, observation, timing, diagnostic,
entry-scope, bound, precondition, PONF, interface, query-schedule, marker,
intrinsic, replay, aggregation, and proof-configuration input. It contains no
generic manifest digest and no extension map.

`ArtifactIdentityEvidenceV2` carries that exact identity and identity digest,
the exact canonical bitcode, and one required closed named envelope for every
digest preimage. It additionally carries `ProofConfigurationV2`,
`QueryScheduleDerivationV2`, `ReleaseMarkerBindingArtifactV2`,
`ReleaseMarkerMachineMapV2`, `LLVMReleaseIntrinsicDefinitionV2`,
`AggregationSemanticsV2`, and `ReplayAcceptanceSemanticsV2`. Each canonical
envelope contains exact canonical bytes and their SHA-256 digest. The verifier
strictly parses and artifact-specifically validates those bytes; canonical,
self-hashed arbitrary JSON is not evidence.

Every preimage digest is recomputed before query construction and must equal
the corresponding `ArtifactIdentityV2` field. The bitcode preimage must parse
to the same frozen $T$. The decoded policy, ABI, release table, contracts,
placement, stable bindings, timing objects, and profile configuration must
also satisfy the normative cross-field rules. These checks are
`XF-IDENTITY-001` and `XF-PAYLOAD-001`; a suffix match, unnamed object, omitted
default, or generic `(fieldId,bytes,digest)` bag is forbidden.

`ProofConfigurationV2` binds the exact aggregation and replay-acceptance
semantics records and digests, the complete ordered `QueryKindV2` and
`PublicReasonClassesV2` inventories, `RequiredQueryScheduleV2`, resource
limits, the restricted-store contract digest, and the exact verifier build.
Its resource limits and options use the exact `ResourceLimitsV2` and
`OptionV2` leaf schemas.

The required schedule is derived from the decoded typed policy, ABI, V2
release table, contract table, entry-scope, timing, and profile-configuration
inputs. `QueryScheduleDerivationV2`,
`ArtifactIdentityV2.queryScheduleDerivationDigest`, and
`ProofConfigurationV2.requiredQuerySchedule` must bind that same independently
recomputed result. Authored matching bytes do not substitute for derivation.

A parse, canonicalization, unsupported-version, or identity/configuration
failure before this closure is completely bound produces
`ConfigurationRejectedV2` with no `ModelStatus`. A later disagreement between
bound evidence and independent reconstruction contributes the precise V2
`Unknown` blocker. Any identity, proof configuration, report, or release-table
root outside the current registry is rejected.

## 2.3 `FreezeCoordinate`

`FreezeCoordinateV2` is:

```text
FreezeCoordinateV2 {
  llvmCommit: "ca7933e47d3a3451d81e72ac174dcb5aa28b59d1",
  targetPassConfigConcreteClass: stable identifier,
  legacyCodegenPipelineId: stable identifier,
  lastIRMutatorPassId: stable identifier,
  lastIRMutatorOrdinal: natural,
  llvmVerifierPassId: stable identifier,
  normalFormAuditPassId: "SPSNormalFormAudit_v2",
  freezeCapturePassId: "SPSFreezeCapture_v2",
  firstIRToMIRPassId: stable identifier,
  firstIRToMIROrdinal: natural,
  orderedPipelineDigest: Digest
}
```

For the pinned baseline, the required logical predecessor sequence is:

```text
target addPreISel
ObjCARCContract
CallBr preparation
SafeStack
StackProtector
SPSFinalWeaken_v2
LLVM IR Verifier
SPSNormalFormAudit_v2        # read-only
SPSFreezeCapture_v2          # read-only
first selected core ISel pass
```

Target-specific passes may add members before `SPSFinalWeaken_v2`; they MUST
appear in the trace. No pass may be inserted between `SPSFreezeCapture_v2` and
the first IR-to-MIR translator unless it is proven read-only, named in the
profile implementation, and present in the recorded trace.

---

# 3. Exact compiler and freeze pipeline

## 3.1 Preconditions

Before entering the pinned code-generation pipeline:

1. all regular LTO or ThinLTO importing, internalization, optimization, and
   symbol resolution MUST be complete;
2. the final target triple, `DataLayout`, CPU, feature set, relocation model,
   code model, and selector mode MUST be fixed;
3. no later linker plugin may run LLVM IR optimization;
4. the release and contract tables MUST already be fixed;
5. release wrapper preservation attributes MUST already be present; and
6. the stack-protector preflight MUST establish that no function definition to
   be serialized into $B$ carries `ssp`, `sspstrong`, or `sspreq`.

The canonical preflight result, including zero counts and stable-site digests
for all three attributes, MUST hash to
`I.stackProtectorPreflightDigest` and is bound into the profile
configuration. A nonzero count stops the run with
`Unknown(UnsupportedStackProtector)`. The implementation MUST NOT delete one of
these attributes to make the module pass. This restriction does not remove the
pinned `StackProtector` pass from the pipeline.

## 3.2 Phase A: ordinary LLVM late IR

The patched compiler runs the complete target-specific implementation of
`TargetPassConfig::addIRPasses()`. In LLVM 22.1.8 this family may include, among
other passes:

- `CanonicalizeFreezeInLoops`;
- loop strength reduction;
- `MergeICmps` and target-dependent `ExpandMemCmp`;
- GC and exception-related lowering;
- unreachable-block elimination;
- constant hoisting;
- vector-library replacement;
- partial libcall inlining;
- entry/exit instrumentation;
- target-dependent scalarization of unsupported masked memory intrinsics;
- reduction expansion;
- select optimization; and
- target-specific additions and substitutions.

This list is explanatory, not an alternative to the recorded pass trace.

## 3.3 Phase B: pre-CodeGenPrepare structural normalization

Immediately after the target-specific `addIRPasses()` returns, the compiler runs:

```text
SPSPreCGPNormalize_v2
```

This is the only pass in the profile permitted to perform general fixed-vector
and masked-memory structural lowering. It is placed before CodeGenPrepare so
that LLVM can prepare the generated scalar CFG for the target.

The compiler then runs its complete pinned target sequence for:

```text
CodeGenPrepare
exception-handling preparation
target addPreISel
ObjCARCContract
CallBr preparation
SafeStack
StackProtector
```

The actual order and target overrides MUST equal the pass trace bound into $I$.
For the pinned `TargetPassConfig.cpp`, `addCodeGenPrepare()` precedes
`addPassesToHandleExceptions()`; the upstream source also states that
CodeGenPrepare is to run before exception-handling preparation. The sequence
above is therefore intentional. The recorded concrete trace remains
authoritative if a target override adds or substitutes a pass.

`StackProtector` remains mandatory at its pinned coordinate although this
profile forbids stack-protected functions. Its closed
`PassTraceRowV2.mutatesIR` MUST
be `false`; `true` is `Unknown(UnsupportedStackProtector)`. The separate
preflight object proves that all three SSP attribute inventories are empty,
and the final residual audit independently rejects generated protection
artifacts. A residual
stack-protector intrinsic, guard access, generated failure edge/call, or other
pass-attributed protection artifact receives the same result; it is never
silently treated as ordinary accepted IR. The profile has no unmodeled changed-function
or changed-site pass-effect record.

## 3.4 Phase C: last mutation, verification, audit, and freeze

After every standard and target-specific IR mutator, the compiler runs:

```text
SPSFinalWeaken_v2             # last permitted IR mutation
LLVM IR Verifier
SPSNormalFormAudit_v2         # no mutation
SPSFreezeCapture_v2           # no mutation
```

`SPSFinalWeaken_v2` MUST NOT introduce:

- an `alloca`;
- a call or invoke;
- an exception edge;
- a vector value;
- an atomic or volatile operation;
- a new loop or backedge;
- an indirect branch; or
- an instruction outside the normal form in Section 6.

The auditor and capture pass MUST be registered and instrumented as read-only.
The build MUST fail if pass instrumentation detects mutation.

## 3.5 Phase D: exact-byte replay into core ISel

The strong conformance mode required by this profile is:

1. serialize $B$;
2. compute and record `SHA-256(B)`;
3. destroy the mutable pre-freeze module;
4. parse $B$ in a fresh LLVM context;
5. rerun the LLVM verifier and the read-only normal-form audit;
6. confirm the parsed module serializes to the same hash under the canonical
   writer;
7. run P1–P3 over that parsed module; and
8. pass a fresh parse of the same $B$ to a patched
   `codegen-from-sps-frozen` pipeline whose first IR-consuming transform is the
   recorded core instruction selector.

The replay pipeline MAY install analyses required by the selector. Such analyses
MUST be read-only. It MUST NOT rerun `addIRPasses`, CodeGenPrepare, exception
preparation, `addPreISel`, stack protection, or the SPS normalizer.

SelectionDAG, GlobalISel, and FastISel are different coordinates. Enabling
GlobalISel fallback is also a different coordinate. The selected mode and
fallback behavior MUST match $I$.

P4 begins at the recorded first IR-to-MIR translator. For SelectionDAG this is
the target SelectionDAG instruction-selection pass; for GlobalISel it is
`IRTranslator`.

---

# 4. Manifest bindings

## 4.1 Required manifest record

The sole profile manifest root is `SPSLLVMNFManifestV2`:

```text
SPSLLVMNFManifestV2 {
  formatId: "SPS-LLVM-NF-Manifest-v2",
  profileId: "SPS-LLVM-NF-v2",
  llvmBaseline: "llvmorg-22.1.8",
  llvmUpstreamCommit: "ca7933e47d3a3451d81e72ac174dcb5aa28b59d1",
  intrinsicName: "llvm.sps.release",
  finalWeakenerId: "SPSFinalWeaken_v2",
  releaseTableFormatId: "SPS-ReleaseTable-v2",
  releaseMarkerBindingsDigest: Digest,
  releaseMarkerMachineMapDigest: Digest,
  intrinsicDefinitionDigest: Digest,
  aggregationSemanticsDigest: Digest,
  replayAcceptanceSemanticsDigest: Digest,
  artifactIdentity: ArtifactIdentityV2,
  artifactIdentityEvidence: ArtifactIdentityEvidenceV2
}
```

The generated Rev4.1 schema, not this display, fixes exact field order and
wire shape. The nested identity/evidence objects are the complete input
closure; the manifest has no parallel authoring fields and no second source of
policy, ABI, release, contract, placement, timing, or profile configuration.
All repeated literals and digests must byte-agree with the nested closure.

For the validation rules below, `policy`, `abi`, `releases`, `contracts`,
`placements`, `observationSemantics`, `latencyClasses`,
`timingEnvironment`, `entryScopes`, `globals`, `preflightTaskSchedule`, and
`profileConfiguration` denote the strictly decoded payloads of their named
canonical envelopes inside `artifactIdentityEvidence`. They are shorthands,
not additional manifest fields. Missing, duplicate, unknown, noncanonical, or
cross-view-inconsistent material is rejected before identity binding.

`entries` is exactly `dom(policy.entries)` in canonical ID order.
`profileConfiguration.loopBoundBindings` has exactly one row per
accepted loop, in canonical `LoopId` order, with
`boundId=loopBoundIds[loopId]` and
`engineCap=loopEngineCaps[loopId]`; all three domains are identical.
For every accepted alloca site `s`,
`allocaSizeIds[s]=s`; the corresponding
`profileConfiguration.allocaSizeBindings` row is exactly
`{allocaSiteId:s,expressionSiteId:s}`, and
the decoded `allocaSizeBindings.bindings[s]` is the exact
`policy.allocaSizeBindings[s]` expression. The domains of all four views are
the same complete accepted-alloca-site set. The profile has no indirection to another
site, fallback expression, or omitted site.
`entryScopes` is recomputed from the reparsed acyclic direct-call graph and
exact contract/release bindings; each row contains the entry function itself
and its complete reachable closure, with no stale or author-selected member.
`globals` is exactly the reparsed global-definition inventory. Mutable,
external, interposable, thread-local, declaration-only, or non-address-space-
zero globals are rejected. Each row's initializer length, alignment,
host, and applicable-entry closure are independently recomputed and its host
equals `placements.globalHost[globalId]`.
Every global storage leaf is integer, floating raw bits, or an explicit byte
array; pointer/relocation leaves and layouts with implicit or semantic padding
are rejected. `initializerBytes` fixes every storage byte, so PONF may set
every global `Init` bit true without inventing padding.

`integerWidths` is the canonical sorted inventory of every accepted integer
width in the frozen module/interfaces; `floatTypes` is the literal displayed
list, not an implementation set. Every latency-emitting non-debug stable site
has exactly one `siteSchemas` row. Its configuration sources are typed,
world-visible, and canonical. A schema with
`timingOccurrenceId=Some(o)` is valid iff `timingEnvironment.occurrences[o]`
exists, its `site` is exactly that `siteId`, and its
`configurationSources` byte-equal the schema sources; each timing occurrence
is named by exactly one such site schema. For a schema with `None`, every
admitted configuration has exactly one table row with
`timingChoiceId=None`. For `Some(o)`, every admitted inactive configuration
under normative `TimingActiveV2` has exactly one `None` row and no `Some` row;
every admitted active configuration has exactly one `Some(c)` row for each
and only each `o.allowedChoiceIds` member and no `None` row. Active profile
rows are in a bijection with `timingEnvironment.latencyMeaning` after replacing
`timingOccurrenceId=o` by its unique `siteId`; configuration tuples, choice
IDs, and latency class IDs must byte-equal. Every row class resolves in
`timingEnvironment.latencyClasses`. Missing, duplicate, extra, or disagreeing
rows are `Unknown(ManifestMismatch)`. Row order is
`(siteId, canonical values, choice option)`, with `None` before `Some` and
`Some` values in canonical choice-ID order.

`policy`, `abi`, `releases`, `contracts`, and `placements` are the exact
authoritative structures incorporated by the normative specification. Their
canonical serializations MUST match the corresponding fields of
`artifactIdentity`; in particular, placement is not inferred from LLVM names
or entry scopes. `placements` is total for every reachable function,
instruction, and boundary required by the normative `FunctionPlacementTable`.
For every contract boundary its source equals the bound call instruction host
and its destination set is exactly one manifest host; same-host means equality,
while cross-host request/response directions are respectively
source-to-destination and destination-to-source. Empty/multicast/foreign or
owner-inconsistent rows are rejected.
The canonical profile-only tuple described in Section 2.2 MUST match
`artifactIdentity.profileConfigurationDigest`.
Missing, ambiguous, or digest-inconsistent placement is
`Unknown(PlacementMismatch)`.

The canonical selected public-alias IDs plus exact ABI topology bindings MUST
match `artifactIdentity.aliasTopologyDigest`; every normative alloca byte
expression MUST match `artifactIdentity.allocaSizeBindingsDigest`; and the
canonical empty FP-result rule table MUST
match `artifactIdentity.fpNaNPayloadSemanticsDigest`. The reparsed stable-ID
table and closed transition dispatcher MUST match
`artifactIdentity.stableIRBindingTableDigest` and
`artifactIdentity.transitionRuleTableDigest`. These dedicated
digests do not replace the policy/ABI or profile cross-binding digests. A
mismatch is `Unknown(ArtifactMismatch)` or the more specific binding reason
from Sections 4.2, 10.6, or 11.2.1.

If `policy.invocationClaim` is `AdaptiveSequence(id)`, `id` MUST resolve
uniquely in the policy's canonical `persistentInvariants` table and that
declaration MUST match the policy digest. Each reachable mechanism contract's
paired-choice table MUST be the universal singleton relation over
`UnitChoiceV2`, and its exact `ContractFunctionV2` must contain one well-typed
total output expression for every derived output field.
Every timing coupling must satisfy the normative fiber-totality query without
referencing program data. Missing invariant bindings, nondeterministic
mechanisms, or partial/filtered coupling relations use the corresponding stable
fail-closed reason.

The canonical observation-semantics table, latency-class table, and
timing-environment contract MUST hash to
`artifactIdentity.observationSemanticsDigest`,
`artifactIdentity.latencyClassTableDigest` and
`artifactIdentity.timingEnvironmentContractDigest`. They are part of the
fixed ideal observation configuration and the P4 deployment coordinate. The
latency-class table does not assert that a concrete instruction has that
latency; paired P4 evidence must establish the real-to-ideal observation
mapping. The timing-environment contract exhaustively identifies any modeled
public noise, jitter, binning, and coupled environment choices. Omitted or
unbound timing behavior cannot be supplied later as an informal P4 assumption;
the absence of such behavior is encoded by an explicit empty contract with its
own digest, not by omitting the field.

The serialized object MUST implement the normative
`TimingEnvironmentContract` schema exactly: finite choice domain, total public
occurrence specifications, deterministic latency meaning, every derived
coalition's total paired coupling when an occurrence exists (and the exact
empty coupling map otherwise), and version/observation boundary. The
profile validator rejects a secret-dependent occurrence guard, incomplete
coalition map, unbound stable site, or schema/digest mismatch before analysis.

The canonical `abi` object MUST use the normative `EntryABIV2`,
`OutputBindingV2`, `returnClassBindings`, `terminalOutputOrder`, and
`contractEventOutputOrder`
schemas. ABI roots have fixed lengths, and each manifest-allowed
application return class's
`CallerReadableRootSlices(ABI,e,c)` is computed as the normative full-root list
rather than parsed from an authored field. Independent validation enumerates the top-level return bits,
every byte of every ABI root, and every declared contract-event byte, then
requires a disjoint exactly-once output binding and schedule cover. Every
top-level `ret` classified `DeclaredFailure(errorFieldId)` first emits its
bound `Failure` and exact-payload `Error`; every top-level `ret` then emits its
bound latency event, complete terminal output schedule, and `Termination` in
that order. The entry's `declaredErrorFields` domain and each return/error
source binding must exactly match those allowed classes. Every reparsed
top-level `ret` has exactly one static allowed class in
`returnClassBindings`; a value-dependent mixed-class return site is rejected
rather than implementation-classified. Helper returns emit
no terminal output. An omitted, duplicated, misordered, or uninitialized output cannot
enter relational checking and uses the normative output-closure reason.
Output location validation includes the producing site and the canonical ABI
endpoint: `returnObservationHost` for return bits and each root's `host` for
writeback bytes.

`HostVisible` is exactly the declared `Theta_ct` event-interface observer. It is
not debugger, arbitrary-register, whole-process-memory, kernel, DMA, or
physical-host compromise; a claim against those stronger observers remains a
P4 obligation. Within this exact observer, every cross-host `Transfer` carries
and projects `valueBytes` at a visible endpoint. A `Release` value is projected
when either its audience authorizes it or its event location is visible, but
only audience authorization may retire the ledger; a wrong-audience
location-visible difference is a normal active `Bad_A`.

Every reachable natural loop has exactly one `loop_bound_ids[L]` resolving to
`policy.publicBounds`. The corresponding public bounded expression supplies
the normative semantic bound. `K_call`, `K_loop`, `K_paths`, `K_bytes`, the
solver bounds, `K_evidence_bytes`, and
`K_restricted_diagnostic_bytes` are finite engine/resource limits only; they are not semantic
assumptions and do not replace a public bound or precondition.
Missing, multiple, unresolved, or digest-inconsistent loop-bound bindings are
`Unknown(PublicBoundBindingMismatch)`.

Every accepted `alloca` site likewise has exactly one
`alloca_size_ids[s] = a_s` resolving to the same stable site in the normative
`policy.allocaSizeBindings` table and therefore to one total
`WorldStructuralByteExpression`. A literal-size `alloca` uses a literal
world-structural expression; it is not exempt. For every admitted execution
reaching $s$, the implementation MUST prove that evaluating the expression at
$a_s$ yields exactly the number of bytes allocated by LLVM—the checked product
of the runtime element count and
the pinned `DataLayout` allocation size of the element type—and that the value
is at most `2^offsetWidth` and therefore fits the normative
`BV(offsetWidth+1)` `SizeKey`. The implementation uses the sole
overflow-free wide multiplication and lossless conversion macro in normative
section 21.3; it never multiplies at pointer width or truncates, saturates, or
uses a host integer. The expression may depend only on the
normative `PublicStructuralState`: entry-applicable world-visible components
and already evaluated public bounds. The fixed alias topology is static
identity context, not an expression input, and occurrence counters are
forbidden. The imported PolicyExpr grammar has no ledger-reference node. It
may not depend on a coalition-relative
member value, a `High`
component, an inferred range, the engine cap `K_bytes`, or an equality assumed
between product lanes. Missing,
multiple, non-total, non-world-structural, overflow-unproved, or exact-equality-
unproved bindings are `Unknown(AllocaSizeNotWorldStructural)`.
Before PONF construction, every immutable-global extent, ABI-object-class
extent, and declared maximum world-structural dynamic extent is also computed
as a mathematical natural and required to be at most `2^offsetWidth`; a
larger extent is `Unknown(ResourceLimit)`, never a modular byte-row domain.
The map's domain is exactly the accepted alloca sites in the claimed entry
closures, it is injective on stable site identity, and its image is exactly the
reachable subset of `policy.allocaSizeBindings`; stale or aliased site IDs fail
the same binding rule.
The map/domain/type/vocabulary checks are `NFConforms` gates. The universal
actual-byte equality and overflow-freedom proof is the separate
`WorldStructuralAlloca_e(T)` model-aggregation gate implemented in Section
10.6. Thus an unresolved execution elsewhere blocks `Proved` with the reason
above but does not invent semantics or prevent an otherwise exact earlier
prefix from satisfying `ReplayCovered`.

The `observation_semantics` table MUST select the sole address mode
`StableAllocationExactByteOffsetV2`. A memory observation identifies the stable
allocation class required by the ABI/global/local-allocation binding and the
exact first byte offset and width of the access. There is no cache-line,
page, bucket, user-selected granularity, or other coarsening parameter in
`SPS-LLVM-NF-v2`. A missing or different address mode, or a table that merges
distinct byte offsets, is `Unknown(UnsupportedAddressObservationProfile)`.

## 4.2 ABI roots

Each pointer ABI root MUST declare:

```text
ComponentId or public runtime role
logical region identity
exact fixed byte length
required alignment
read/write permission
initialization state
host and address space
allowed aliases
lifetime owner
```

The default address space is address space zero. Any other address space is out
of profile.
Every root is live at entry. `Initialized`/`Uninitialized` determines every
initial `Init` bit; `ReadOnly`/`WriteOnly`/`ReadWrite` gates every LLVM and
contract access. Potentially overlapping roots must agree on host, permission,
initialization, lifetime owner, and address space. Ordinary loads/stores must
target an allocation on the instruction host; the profile rejects implicit remote
memory rather than hiding transferred value bytes in a `Memory` event.

Two ABI pointer roots are not assumed disjoint merely because they have
distinct SSA names, distinct argument positions, LLVM `noalias`, or a fact
reconstructed from $T$. Distinct allocation identities for distinct ABI roots
come only from the one normative `ExactRootAliasTopologyV2`: roots in one
equivalence class are full-object identical and roots in different classes
are disjoint. There is no second authored alias relation, predicate, or
runtime selector.

`publicAliasTopology` is a canonical profile index mechanically derived from,
and required to equal, `policy.publicAliasTopologyIds` and
`abi.aliasTopologyBindings`; it is not a third authoring authority. The
profile admits one fixed full-object partition per entry:

```text
PublicAliasTopologyBindingIndexV2 {
  bindings:
      total map (EntryId,AliasTopologyId) -> ExactRootAliasTopologyV2
}
```

For every entry, `policy.publicAliasTopologyIds[entry]` is a singleton and the
index has exactly its one matching binding. The topology's `overlaps` list is
empty. Each equivalence class denotes roots with one identical allocation,
base offset zero, and identical size/alignment/host/permission/
initialization/lifetime/address-space metadata; distinct classes are
disjoint. The sole topology ID is static artifact-identity material and has no
runtime value or selector. The verifier recomputes the actual class partition in both lanes and
requires exact equality to the binding. `MayAlias` clauses must be completely
resolved by that partition; no lane-varying topology, partial overlap,
nonzero relative base, or profile-only root set exists. Missing
coverage, metadata disagreement, an impossible topology, table/domain/digest
disagreement, or failure of this check is
`Unknown(AliasBindingMismatch)`. The PONF allocation table has exactly one
`ABIObjectClass` row per equivalence class, keyed by its first root; every
member root maps to that row at offset zero.

An accepted local `alloca` creates its own fresh allocation object. A pointer
derived from an ABI root or local object retains that base object's identity;
this local object rule never promotes two ABI roots to disjoint objects.

## 4.3 Entry separation

Each manifest entry is checked with a fresh analysis state, fresh memory state,
fresh event trace, and fresh release ledger. Facts or release occurrences from
one entry MUST NOT be reused to prove another entry.

Cross-entry composition, if required, is owned by the rev-4 normative
specification.

## 4.4 Release carrier binding

A release identity is supplied only by the V2 sidecar, never by an intrinsic
operand, symbol spelling, metadata node, store, or numeric literal in the IR.
For every release row the profile requires:

1. one `ReleaseMarkerBindingRowV2` that binds its stable `ReleaseId` and
   `SiteId` to `ReleaseImplementationBindingV2.wrapperFunction` and
   `emitMarkerInstructionId`;
2. exactly one instruction at that stable ID, and that instruction is
   `llvm.sps.release`;
3. no result and exactly the depth-first, left-to-right integer payload leaves
   declared by the V2 release row, with identical arity, order, and widths;
4. no release-ID, site-ID, ordinal, or other locator operand;
5. exact equality among the marker-binding, stable-IR, release-table, and
   machine-map instruction domains;
6. verifier-derived occurrence ordinals and cross-release order matching the
   canonical expanded transition order; and
7. the checked local extensional obligation for every applicable entry used by
   `ReleaseConforms_e(q,T)`.

The intrinsic is zero-result, variadic over integer leaves, non-speculatable,
and defined with `IntrHasSideEffects`, `IntrNoMem`, `IntrNoDuplicate`, and
`IntrNoMerge`. Those are compiler-retention properties; the intrinsic has no
application-visible memory effect. Semantic expansion replaces it one-to-one
with the unchanged `ReleaseBoundaryV2` model node.

The release-table AST remains the independently authored policy. It MUST NOT
be inferred from the wrapper, intrinsic, operands, metadata, or body. The
frozen intrinsic supplies only the bound implementation occurrence and payload
SSA values; the canonical V2 release row supplies guard, audience, footprint,
multiplicity, and permitted meaning. `ReleaseConforms(q,T)` remains the
entry-indexed conjunction of the applicable obligations.

A missing, duplicate, malformed, ill-typed, stale, wrongly bound, or
domain-inconsistent intrinsic is `Unknown(ReleaseCarrierMismatch)`. A
structurally valid carrier whose semantic equivalence cannot be completed uses
`Unknown(ReleaseConformanceUnknown)` or the more specific closed
solver/resource reason. A supported mismatch is a counterexample only after
independent replay reaches the first corresponding release-bad state.

---

# 5. Deterministic normalization

## 5.1 Required normalizer properties

For fixed $I$ and input module, both SPS normalization passes MUST be:

- deterministic;
- free of profile-external configuration;
- idempotent on their own output;
- verifier-clean;
- independently versioned and hashed;
- covered by positive, negative, and metamorphic tests; and
- followed by the exhaustive audit in Section 7.

Passing a stock LLVM scalarizer is not evidence that the module is in normal
form. Conformance depends on the residual audit.

## 5.2 Fixed-vector source envelope

This subsection describes only the input accepted by
`SPSPreCGPNormalize_v2`. It does not add vector semantics to frozen $T$.
Successful normalization eliminates every fixed-vector value and operation;
the Section 6 audit rejects every residual vector, including a residual form
that would have been supported as pre-normalization input.

`SPSPreCGPNormalize_v2` MAY accept a pre-normalization vector only when all of
the following hold:

- it is a fixed vector `<N x τ>`;
- `1 <= N <= max_vector_lanes_before_normalization`;
- `τ` is an accepted integer, `float`, or `double` scalar;
- it does not cross an externally visible or contract boundary;
- it is absent from function signatures, varargs, globals, aliases, inline
  assembly, and operand bundles;
- it is not scalable;
- it is not atomic or volatile;
- every operation on it is in the transformation table below; and
- every use is transformed, leaving no residual vector-typed value.

| Pre-normalization operation | Required lowering |
|---|---|
| Vector `phi` | one scalar `phi` per lane |
| Lane-wise integer/FP operation | the corresponding scalar operation per lane |
| Scalar-condition vector `select` | one scalar `select` per lane |
| Vector-condition `select` | lane-condition scalar `select` per lane |
| `insertelement` | lane replacement; dynamic index becomes a bounded select chain |
| `extractelement` | selected lane; dynamic index becomes a bounded select chain |
| Constant `shufflevector` | exact constant lane map |
| Non-atomic, non-volatile vector load | one scalar load per lane |
| Non-atomic, non-volatile vector store | one scalar store per lane |
| Contiguous `llvm.masked.load` | guarded active-lane loads plus passthrough lanes |
| Contiguous `llvm.masked.store` | guarded active-lane stores |

The lane alignment at byte offset $o$ is computed with LLVM 22.1.8
`commonAlignment(A,o)` from the original alignment $A$. It is not copied
blindly to every lane.

A masked-off lane MUST perform no memory access. Its potentially invalid address
MUST NOT be dereferenced. A masked load returns the corresponding passthrough
lane. The generated guard branches are real final-LLVM control observations and
are analyzed normally.

The following are never transformed and therefore lead to
`Unknown(ResidualVector)` if present:

- scalable vectors;
- VP intrinsics;
- gather or scatter;
- compress-store or expand-load;
- target vector intrinsics;
- vector reductions;
- vector calls or vector ABI values;
- vector atomics or volatiles;
- vectors of pointers;
- constrained vector floating point;
- a shuffle with undef or poison mask elements; and
- any vector operation not listed above.

## 5.3 Final weakening order

`SPSFinalWeaken_v2` performs the following ordered steps:

1. delete modeled `llvm.assume` calls and their operand bundles;
2. remove the exact poison-generating instruction annotations listed in the
   pinned weakening table;
3. remove the exact whitelisted droppable optimization attributes and metadata;
4. clear every fast-math flag on accepted scalar FP instructions;
5. invalidate and recompute dominance, assumption, and value-tracking analyses;
6. remove an eligible `freeze` only under Section 5.6;
7. expand or reject every residual droppable intrinsic according to the
   intrinsic table;
8. run `SPSFinalDeadCleanup_v2`, the versioned local dead/unreachable cleanup
   defined below; and
9. run the LLVM verifier.

The normalizer MUST NOT use a fact from an `llvm.assume`, removed metadata, or a
removed attribute to justify a later `freeze` deletion.

`SPSFinalDeadCleanup_v2` is a subroutine of `SPSFinalWeaken_v2`, not an
additional post-freeze pass. It deterministically iterates the following two
rules to a fixed point and performs no other deletion:

1. delete every basic block with no CFG path from the function entry, while
   repairing its successor PHIs by the pinned rewrite rule; and
2. delete a zero-use instruction exactly when the LLVM-22.1.8 side-effect
   classifier and the versioned SPS table both classify it as removable.

The cleanup MUST NOT use a solver, policy classification, admission
precondition, future release, or product invariant to declare a CFG-reachable
block dead. Consequently, an `undef`, poison, or unsupported `freeze` remaining
on a CFG-reachable but semantically infeasible path is still rejected
conservatively. The audit record distinguishes removed syntactically
unreachable material from residual material that caused refusal.

## 5.4 Poison-generating flags and fast math

The final artifact MUST contain none of the following:

```text
nsw
nuw
exact
inbounds
GEP nusw/nuw flags
disjoint
nneg
samesign
trunc nsw/nuw
any fast-math flag:
  reassoc nnan ninf nsz arcp contract afn fast
```

The pinned normalizer clears these only where LLVM 22.1.8 defines removal as a
semantics weakening or the profile has a tested per-op rewrite rule.

The residual audit is opcode-aware, not a token-substring scan. For every
instruction, it first requires LLVM 22.1.8's poison-generating-flag query to
report false and then independently checks the displayed closed spelling
allowlist, including `zext nneg` and `icmp samesign`. An accepted instruction
matcher succeeds only when its opcode-specific optional poison-flag set is
empty. A parser/API disagreement is `Unknown(NormalizerMismatch)`; neither the
dispatcher nor PONF may erase or interpret an unrecognized optional flag.

Any residual listed flag or fast-math flag makes `NFConforms(T,I)` false and
produces `Unknown(UnclassifiedAnnotation)` or
`Unknown(NormalizerMismatch)`. Frozen $T$ has no semantics for a residual
poison-generating flag.

Earlier optimization effects are not undone. SPS analyzes the exact transformed
instruction graph after weakening.

## 5.5 Attributes and metadata

Attributes are divided into four exhaustive classes.

### Class A — preserved ABI attributes

The normalizer MUST NOT delete or alter:

```text
signext
zeroext
inreg
byval
byref
sret
inalloca
preallocated
nest
swiftself
swifterror
immarg
elementtype
calling convention
```

The accepted ABI permits only `ccc` and non-vararg signatures. Parameters
may be accepted scalars or declared pointer roots; a claimed top-level entry
result is void or a non-pointer accepted scalar. Expanded internal helpers may
return structural pointers, but pointer results never cross the top-level ABI.
Only integer parameters and results may use optional `signext` or `zeroext`.
The presence of any other Class A attribute makes the module out of profile;
it is not repaired by stripping.

### Class B — release-preservation attributes

The following are retained on manifest release wrappers:

```text
noinline
"nooutline"
noduplicate
nomerge
nobuiltin
```

LLVM 22.1.8 does not define `noipa` in its LangRef; the profile does not use it.
These attributes assist preservation but do not replace the final P1
occurrence/cardinality check.

### Class C — whitelisted droppable facts and hints

The versioned weakener MAY remove only entries explicitly encoded in its
LLVM-22.1.8 table, including the following families where well-formed:

```text
nonnull
dereferenceable
dereferenceable_or_null
noundef
nofpclass
range
noalias
nocapture
returned
align when it is not ABI-coupled
readnone / readonly / writeonly / memory effects
argmemonly / inaccessiblememonly
nofree / nosync / nocallback
nounwind / willreturn / mustprogress / norecurse
speculatable
inline hints, hot/cold, optsize/minsize
branch weight and optimization-only loop metadata
alias.scope / noalias metadata
TBAA and invariant optimization metadata
poison-generating load/call metadata
```

The MemorySanitizer mode is forbidden, because it can make `noundef`
ABI-relevant. A future profile may define an MSan-specific treatment.

### Class D — rejected semantic or code-generation controls

The following are rejected unless a future profile names an exact rule:

```text
non-ccc calling conventions
null_pointer_is_valid
strictfp or constrained FP environment controls
convergent
returns_twice
naked or interrupt functions
coroutine, statepoint, deoptimization, or patchpoint controls
GC strategy or personality functions
sanitizer instrumentation modes
ssp / sspstrong / sspreq
target-specific unclassified attributes
unknown string attributes
unknown metadata
```

Target CPU/features, stack/frame controls, unwind-table controls, and every
other code-generation attribute outside the exact Class A/B and reserved-
marker rules above are rejected; target/code-model choices live only in
the typed `TargetConfigurationEvidenceV2` (with pipeline position separately
bound by `FreezeCoordinateV2`), never in an LLVM string attribute.
`codegenAttributePolicy` is the literal
`ClosedAttributeClassesOnlyV2`, not an author-controlled allowlist.

Only debug metadata may remain without a semantics rule. The module-flag
table is exactly empty and `moduleFlagPolicy` is the literal
`RejectAllModuleFlagsV2`; a residual flag of any name, behavior, or value is
rejected. Every other residual metadata kind is out of profile.

## 5.6 `freeze`

LLVM `freeze` is not an identity operation in general. If its operand is undef
or poison, it chooses an arbitrary but fixed value; multiple uses observe that
same choice.

The only accepted rewrite is:

$$
\operatorname{freeze}(x)\longrightarrow x
$$

when a checked, context-sensitive fact proves:

$$
\operatorname{NoUndefOrPoison}(x,\text{program point}).
$$

The implementation MAY use the pinned LLVM
`isGuaranteedNotToBeUndefOrPoison` analysis as a conservative producer, but the
result MUST be recomputed after assumption and annotation removal and MUST be
recorded in a `FreezeRewriteRecord` containing:

```text
function
basic block
instruction ordinal
operand structural hash
dominance context hash
analysis result
normalizer version
```

The record is an audit locator, not an independently checkable proof. The
consumer MUST recompute the non-undef/non-poison fact from $T$.

If the proof is absent, stale, unsupported, or false, normalization stops with
`Unknown(FreezeMayChoose)`. Residual `freeze` is forbidden by the normal form.

## 5.7 Relationship to the pre-normalized module

For any admitted execution on which the pre-normalized module is defined, every
normalizer rewrite MUST preserve its functional result and declared externally
visible effects. No claim is made for an execution on which the pre-normalized
module already has poison-triggered undefined behavior.

Removing annotations after `-O2` does not reverse transformations that used
those annotations. This is intentional: SPS checks confidentiality of $T$.

Alive2 MAY be used as per-rewrite and regression evidence. It is not a blanket
proof for this profile, particularly for interprocedural, memory, masked
CFG, or ABI transformations. The normalizer and its proof obligations remain
in the TCB unless separately verified.

---

# 6. Exhaustive LLVM normal form

This section is closed-world. “Not listed” means out of profile.

Frozen $T$ is scalar/pointer-only: fixed vectors are solely a
pre-normalization source envelope, and every fixed or scalable vector must be
absent here. First-class aggregate SSA is likewise absent. Every accepted
instruction is free of the poison-generating and fast-math flags prohibited by
Section 5.4; the semantics never interprets a residual prohibited flag.

## 6.1 Accepted types

The default accepted set is:

```text
void                       # only as a function result
i1, i8, i16, i32, i64
float, double
opaque ptr addrspace(0)
label                      # CFG only
metadata                   # debug intrinsic operands only
```

The integer-width set is explicit in the manifest and MUST be a subset of
`{1,8,16,32,64}` for this profile.

`i1` is supported as an SSA, argument, return, PHI, select, comparison, and
branch-condition type. It is not supported as the value type of `load` or
`store`. Every accepted integer memory access has width in `{8,16,32,64}`;
equivalently its scalar bit width is positive and divisible by eight. This
This restriction avoids importing LLVM's separate non-byte-width load padding
and poison rule into the byte-memory model.

Arrays and literal or identified structs MAY occur only as:

- pointee layout descriptions used by `getelementptr`;
- global or constant aggregate storage; or
- ABI schema layout descriptions.

Aggregate values MUST NOT occur as first-class SSA operands or results. The
normalizer must eliminate them or return `Unknown(UnsupportedType)`.

Rejected types include:

```text
all fixed and scalable vectors
half, bfloat, x86_fp80, fp128, ppc_fp128
x86_mmx and target extension types
token
nonzero-address-space pointers
first-class arrays or structs
function values except a direct call target
```

## 6.2 Accepted constants

Accepted constants are:

- integer constants of accepted width;
- finite, infinity, NaN, and signed-zero constants of accepted FP type;
- `null` in address space zero;
- addresses of allowed globals, plus a direct function symbol only as the
  syntactic callee operand of a direct `call`;
- `zeroinitializer` for an allowed global layout; and
- aggregate global initializers recursively composed only of accepted constants.

Rejected constants are:

```text
undef
poison
blockaddress
dso_local_equivalent
no_cfi
ptr auth constants
constant expressions of any kind
```

Constant expressions MUST be expanded to ordinary accepted instructions before
the final audit.

## 6.3 Module and global surface

The module MUST have exactly the triple and `DataLayout` in $I$.

Allowed definitions are:

- manifest entry functions;
- closed internal/private helper functions;
- manifest release wrappers;
- contract-backed external declarations;
- one derived reserved release-marker declaration per release row, used only
  at its bound marker instruction;
- internal/private immutable globals with accepted initializers.

Rejected module features include:

```text
module-level inline assembly
global aliases
ifuncs
COMDAT selection
thread-local storage
appending/common/weak/interposable definitions
global ctors or dtors
JIT-only materialization
post-freeze LTO summaries
any module flag
mutable or externally visible globals
```

Externally visible definitions MUST be non-interposable under the deployment
linkage plan. Symbol resolution is a P4 obligation bound into $I$.

## 6.4 Functions and CFG

An accepted function:

- uses `ccc`;
- is not variadic;
- has only accepted scalar/pointer parameters; an internal helper may have an
  accepted scalar/pointer result, while a claimed top-level entry has only a
  void or non-pointer scalar result;
- has no personality, GC strategy, prefix/prologue data, or operand bundles;
- belongs to an acyclic direct-call graph;
- has a single CFG entry;
- has only the `CanonicalSingleBlockLoopV2` form of Section 9.3;
- contains no indirect control transfer; and
- satisfies LLVM verifier dominance and PHI rules.

Unreachable blocks MAY remain, but the semantics implementation must not use
them unless reached. Exact execution of a reachable `unreachable` instruction
takes the `UBRisk` transition in Section 11.4; inability to decide reachability
is `Unknown(PossibleUB)`.

## 6.5 Instruction surface

| Family | Accepted instructions | Additional obligation |
|---|---|---|
| Terminators | `ret`, unconditional/conditional `br`, integer `switch`, `unreachable` | branch/switch condition defined; `unreachable` unreachable |
| SSA | scalar/pointer `phi`, scalar/pointer `select` | selected value and condition rules below |
| Integer | `add`, `sub`, `mul`, `udiv`, `sdiv`, `urem`, `srem`, `shl`, `lshr`, `ashr`, `and`, `or`, `xor` | no flags; division/shift definedness |
| FP bit operations | `fneg`, `fcmp` | `float`/`double`; no fast math; exact normative bitvector rules |
| Comparison | flag-free integer `icmp`; restricted pointer `icmp eq/ne` under Section 10.1.1 | no `samesign`; pointer operands have byte-identical canonical `AllocationKey` terms; result is exact `OffsetKey` equality; ordered pointer comparison rejected |
| Cast | flag-free `trunc`, `zext`, `sext`, same-width scalar `bitcast` | no `nneg`, `nsw`, or `nuw`; accepted source/result types and exact bitvector rule |
| Pointer | flag-free `getelementptr` | address space zero; checked object/offset model |
| Memory | `alloca`, non-volatile non-atomic non-pointer-scalar `load`, non-volatile non-atomic non-pointer-scalar `store` | Section 10; integer load/store width is one of 8, 16, 32, or 64 bits |
| Call | direct `call` | Section 8 |

Every other LLVM instruction is rejected, including:

```text
indirectbr
invoke, callbr, resume
landingpad, catch*, cleanup*
va_arg
extractvalue, insertvalue
extractelement, insertelement, shufflevector
fence, cmpxchg, atomicrmw
ptrtoint, inttoptr, addrspacecast
freeze
fadd, fsub, fmul, fdiv, frem
fptrunc, fpext, fptoui, fptosi, uitofp, sitofp
all vector instructions
```

The rejected FP arithmetic and numeric-conversion opcodes use
`Unknown(PONFFPArithmeticUnsupported)`. This is a profile refusal, not an
accepted `NFConforms` operation later approximated by PONF.

`select` follows LLVM poison semantics: poison in the unselected data operand
does not contaminate the selected result, while an undefined/poison condition
is not accepted as defined. `phi` selects only the value on the executed
incoming edge.

### 6.5.1 Target-bound timing-risk diagnostics

The normal form does not claim that an accepted LLVM opcode lowers to
constant-latency or branch-free machine code. After each required
coalition-indexed `Low/High` diagnostic run, the implementation MUST emit a
non-authoritative record with this minimum schema:

```text
TimingRiskLintRecord {
  canonical_bitcode_sha256;
  entry_id;
  coalition_id;
  site_id;
  opcode;
  risk_class: HighOperandVariableLatency
            | HighConditionSelectLowering
            | SpectrePHTCandidate
            | PublicDynamicAllocaStackProbe;
  high_operand_positions;
  llvm_commit, llvm_compiler_binary_sha256, ordered_ir_pass_trace_sha256;
  target_triple, target_cpu, target_features, tune_cpu;
  codegen_optimization_level, code_model, relocation_model;
  instruction_selector, fast_isel_enabled;
  global_isel_enabled, global_isel_fallback_enabled;
  observation_semantics_sha256;
  latency_class_table_sha256;
  timing_environment_contract_sha256;
  diagnostic_basis;
  p4_disposition: EvidenceRequired | CoveredByBoundEvidence | NotEvaluated;
}
```

At minimum, accepted `udiv`, `sdiv`, `urem`, and `srem` with a diagnostically
`High` operand produce `HighOperandVariableLatency`. Residual `fdiv` and
`frem` are rejected before this conformant-artifact diagnostic rather than
linted as accepted operations. A scalar `select` with a diagnostically `High`
condition produces
`HighConditionSelectLowering`. The versioned target table MAY conservatively
name additional opcodes. A completed whole-entry diagnostic whose labels are
imprecise uses a `RelationalRequired(reason)` basis. A timeout, incomplete
traversal, or malformed result in that mandatory diagnostic is instead
`Unknown(DiagnosticHealthFailure)` under the normative rule. A timeout while
looking up optional P4 evidence after a healthy diagnostic records
`NotEvaluated`; it does not become `CoveredByBoundEvidence` or change the LLVM
model result.

These records neither establish nor refute `NFConforms`, `ProductSafe_A`, or
`ModelStatus`. They do not add events, alter labels, or remove product
obligations. `CoveredByBoundEvidence` is available only by reference to a P4
evidence item bound to the same artifact, target, selector, latency table, and
timing-environment contract. In particular, the configured ideal
`Latency(site,configuredClass)` is not evidence that operand-dependent real
timing, a select lowered to a branch, or environmental jitter is concealed.

The generic record is supplemented for every `SpectrePHTCandidate` by a
multi-site path record:

```text
SpectrePHTLintRecord {
  canonical_bitcode_sha256, entry_id, coalition_id;
  index_source_sites;
  conditional_bounds_check_sites;
  speculative_cfg_path;
  transient_address_dependency_sites;
  transient_load_sites;
  transient_sink_sites, sink_observation_classes;
  high_region_roles;
  spectre_lint_model_id, speculative_window_bound;
  target_triple, target_cpu, target_features, instruction_selector;
  observation_semantics_sha256;
  pht_mitigation: Open
                | SLHBound(P4EvidenceId)
                | FenceBound(P4EvidenceId)
                | MicroarchitectureBound(P4EvidenceId);
  bti_mitigation: NotEvaluated
                | None
                | Retpoline(P4EvidenceId)
                | IBRS(P4EvidenceId)
                | OtherBTI(P4EvidenceId);
  diagnostic_basis;
}
```

The conservative candidate pattern is a public/adversary-influenced index, one
or more conditional bounds checks, and a data/address-dependence path to a load
from a role containing coalition-`High` bytes and then to a candidate
coalition-observable transmitter/sink within the pinned speculative window
model. All contributing sites are recorded; reducing the record to only the
branch, load, or sink is incomplete. The lint neither asserts that the machine
speculates nor supplies speculative semantics to `Product_A`.

PHT and BTI are separate dispositions. Retpolines, IBRS, and other indirect-
branch-target controls do not discharge a PHT candidate. A PHT disposition may
close only through artifact-, target-, runtime-, and observation-bound evidence
for an applicable PHT mitigation such as proved SLH insertion, an applicable
fence, or an explicit microarchitectural contract. Conversely, a PHT
mitigation does not establish BTI protection. `Open` leaves deployment P4 open
without changing the LLVM `ModelStatus`.

### 6.5.2 Final-machine control-delta evidence

After final assembly and linking, the implementation MUST generate one record
for every conditional control transfer in every claimed entry region:

```text
BackendControlDeltaRecord {
  final_binary_sha256, linked_region_digest;
  target_triple, target_cpu, target_features;
  instruction_selector, linker_identity, post_isel_pass_trace_sha256;
  ordered_link_and_postlink_trace_sha256;
  machine_site, opcode_and_encoding, successor_machine_sites;
  origin_site_set;
  origin_class: FrozenBranchOrSwitch
              | FrozenSelect
              | ContractBoundary
              | BackendRuntimeOrProbe
              | Unmatched;
  introducing_stage_or_pass;
  predicate_correspondence: Open | Bound(P4EvidenceId);
  event_correspondence: Open | Bound(P4EvidenceId);
  observation_mapping_id_or_none;
  p4_disposition: EvidenceRequired | CoveredByBoundEvidence | NotEvaluated;
}
```

The claimed linked region is the complete transitive code closure exercised by
the invocation claim, including runtime/probe helpers, contract stubs, veneers,
and instrumentation; a symbol-range-only inventory that omits those transfers
is incomplete.

Origin mapping is set-valued: lowering may split one frozen site into several
machine transfers or combine several sites. The audit covers the final linked
bytes, not only MIR, because late pseudo expansion, instrumentation, stack
probing, veneers, and the linker can introduce control. An unmatched or
backend-introduced transfer is reported and leaves the corresponding P4
obligation open. A perfect origin count still does not prove predicate,
successor, event, latency, fault, or observation correspondence.

These records are P4 evidence generators. They never prove `NFConforms`,
`ProductSafe_A`, or `ModelStatus`, and an open record is not an LLVM-model
counterexample. Statistical timing, branch-counter, fuzzing, or differential
tests may find a falsifier and add assurance, but cannot establish a universal
paired-refinement or real-observation-containment premise. A bounded binary
relational analyzer contributes deductive P4 evidence only when its result is
bound to the exact final binary and ISA semantics, covers the declared initial
relation and bounds, and supplies an explicit mapping from every concrete
observation to the fixed coalition projection $h_A$. Without that observation
mapping, the record remains `EvidenceRequired` regardless of solver success.

## 6.6 Intrinsic surface

The only accepted residual intrinsics are:

| Intrinsic | Profile semantics |
|---|---|
| `llvm.dbg.*` | semantically ignored, hash retained |

The pinned normalizer may erase well-formed `llvm.lifetime.start/end` markers
before freeze; the same marker-free bytes are analyzed and passed to core
instruction selection. A residual lifetime marker, `llvm.memcpy`,
`llvm.memmove`, or `llvm.memset`, including volatile variants, is
`Unknown(PONFIntrinsicUnsupported)`. Memory intrinsics otherwise MUST be
lowered before freeze to the accepted scalar load/store/branch surface. The profile
deliberately chooses these refusals over an unencoded subobject-lifetime state
or ambiguous event granularity.

All other residual intrinsics, including `llvm.trap`, `llvm.ubsantrap`,
`llvm.assume`, masked memory, VP,
vector reductions, overflow-result aggregates, object-size, stacksave/restore,
coroutines, guards, deoptimization, statepoints, patchpoints, constrained FP,
target intrinsics, stack-protector/stack-guard intrinsics, and
`llvm.sideeffect`, are out of profile. A stack-protector-family intrinsic or
ordinary IR attributed by the pass trace to `StackProtector` uses the more
specific `Unknown(UnsupportedStackProtector)` reason from Section 3.3.
Other residual intrinsics use `Unknown(PONFIntrinsicUnsupported)`.

## 6.7 Concurrency and environment

The execution model is single-threaded within an entry scope. The following
are rejected:

- atomic operations;
- volatile memory;
- fences;
- thread-local storage;
- synchronization intrinsics;
- signals or asynchronous callbacks not represented by a contract;
- inline assembly; and
- self-modifying or JIT-generated code.

External concurrency assumptions belong in P4 and do not relax the LLVM audit.

---

# 7. Conformance predicate and audit

## 7.1 Meaning of `NFConforms(T,I)`

`NFConforms(T,I)` holds only if all of the following are true:

1. $T$ is the successful LLVM 22.1.8 parse of the bitcode named by $I$;
2. its canonical serialization hash equals `I.canonicalBitcodeHash`;
3. every identity, target, pipeline, normalizer, auditor, policy, ABI,
   contract, release, placement, public-alias-topology, alloca-size,
   public-bound, precondition, FP-NaN-semantics, proof-configuration, and
   entry-scope binding equals $I$ under Section 2.2;
4. the recorded pass trace reaches the exact freeze coordinate;
5. replay codegen starts with the recorded first IR-to-MIR translator and has no
   intervening IR mutation;
6. the complete module passes Sections 4–6, selects
   `StableAllocationExactByteOffsetV2`, contains no residual vector or
   first-class aggregate SSA, and contains no prohibited poison or fast-math
   flag; every instruction is assigned exactly one row of the normative
   `TransitionRuleTableV2` dispatcher;
7. every reachable call is closed under Section 8;
8. every analyzed step has the definedness and supported-`undef` treatment in
   Sections 10.3 and 11;
9. every loop is bound to one normative public `BoundId`, every engine cap is
   kept separate, every exact exhaustion transition follows Section 9, and an
   independent `ExpandV2` recomputation reproduces the stable-ID table, expanded
   CFG, terminal/output units, horizon, and all three bound digests;
10. every accepted `alloca` has exactly one typed world-structural byte-size
    binding and an exact equality obligation, every public alias-topology
    binding is uniquely resolved, exact byte memory remains authoritative, and
    every entry/allowed application-return class and contract event has a complete disjoint
    exactly-once output schedule over the full fixed ABI-root surface;
11. the canonical FP-NaN rule table is empty, no FP arithmetic or numeric
    conversion survives the audit, and no Section 10 diagnostic ghost fact is
    used by `Step_{T,K,TE}` or `Product_A`; and
12. no audit result has been suppressed, downgraded, or treated as a warning.

`NFConforms` is a predicate imported by the sole rev-4 normative specification.
The implementation emits an `NFConformanceAuditRecord`. It is a diagnostic
record of the recomputation, not an independently checkable proof artifact, and
it never replaces recomputation.

## 7.2 Exhaustive residual inventory

The auditor MUST inventory, at minimum:

```text
type IDs and widths
constant kinds
global/linkage kinds
function signatures and calling conventions
instruction opcodes
intrinsic IDs
instruction flags
function/return/parameter/call-site attributes
pointer-comparison sites and modular address-expression classes
alloca sites, element-count expressions, and exact public-size bindings
ABI-root alias pairs and public/variable topology classifications
memory-event allocation-class/offset/width encoding modes
forbidden FP-arithmetic and numeric-conversion sites
normative transition-rule ID and exact event-order row for every instruction
metadata kind IDs
address spaces
atomic orderings and volatility
operand bundle tags
inline assembly
CFG reducibility and call-graph SCCs
module flags
```

Each inventory item is classified by one exact profile rule. An empty or
fall-through classification is an auditor bug and causes
`Unknown(UnclassifiedIR)`.
The independently generated transition inventory MUST be a bijection with the
normative `TransitionRuleTableV2` dispatcher: every instruction has one row,
each row's matcher is satisfied, and no accepted instruction uses an
implementation-defined state update, event list, or PONF macro.

For pointer `icmp eq/ne`, `SPSNormalFormAudit_v2` independently lowers both
operands and byte-compares their canonical `AllocationKey` term trees for
every residual site. Merely inventorying the opcode, recognizing two
provenance objects, or proving semantic equality by another analysis does not
establish the accepted classification.

## 7.3 Audit reproducibility

The conformance audit record records:

```text
artifact hash
auditor hash
semantics-table hash
inventory counts by category
normalizer rewrite counts by rule
freeze rewrite records
pointer-comparison layout records
alloca-size equality and overflow-freedom records
public-alias-topology binding records
FP NaN-semantics records
late-IR refusal telemetry
timing-risk lint record digest and counts by target/risk/disposition
Spectre-PHT multi-site record digest and PHT/BTI dispositions
backend-control-delta digest and final conditional-transfer coverage
proof-domain coverage-record digest and counts by query/result/disposition
preflight-task-schedule digest and fixed task count
falsifier implementation/configuration digest (no candidate/result digest or count)
release-wrapper occurrences
call-graph digest
loop-to-`BoundId` table, public-bound digest, and separate engine caps
alloca-site-to-world-structural-expression table and public-alias-topology digest
global/ABI-region and function-placement-table digests
definedness-to-`UBRisk` event mapping version
accepted codegen attribute table
all warnings, which must be empty
```

The Spectre and backend-control fields are a separately typed P4 annex. When no
deployment binary is supplied they contain the explicit value
`NoDeploymentCandidate`; when one is supplied their coverage is mandatory for
the deployment evidence bundle. Neither `NoDeploymentCandidate` nor an open P4
disposition is an audit warning or changes `NFConforms`/`ModelStatus`; it keeps
`DeploymentStatus` open. The alloca, alias, address-mode, and FP records above
are not part of that P4 exception: their site/type/vocabulary/table coverage is
a normal-form gate. Universal alloca equality remains a separately typed
post-audit model gate; FP arithmetic/conversion has no separate reachability or
result-disposition gate because its residual inventory must be syntactically
empty before relational construction.
The proof-domain fields are a separately typed post-audit model annex:
domain/activation dispositions gate aggregate `Proved` under Section 12.4.
Candidate-level falsifier/replay rows are restricted rather than audit-report
fields; only a replay accepted under Section 12.5 can produce the single
public final counterexample receipt. Neither annex is imported as an
`NFConforms` premise.

Optional noncanonical restricted `late-IR refusal telemetry` may have the
following minimum content, with stable site digests as well as counts; it is
not an identity preimage or public-report annex:

```text
CanonicalizeFreezeInLoops: before, after, relocated_or_new_sites
SPSFinalWeaken freeze: candidates, removed, refused
SPSFinalDeadCleanup: unreachable_blocks_removed, dead_instructions_removed
residual literals: undef_sites, poison_sites, unsupported_freeze_sites
stack-protector preflight: ssp_sites, sspstrong_sites, sspreq_sites
StackProtector pass: the canonical PassTraceRowV2.mutatesIR Boolean
residual stack protection: intrinsic_sites, guard_sites, failure_edge_or_call_sites
```

The telemetry measures conservative refusal and is not a proof certificate.
Zero stack-protector fields and complete pointer-comparison records are required
for conformance under their respective rules; freeze/dead-material counts do
not weaken the final residual audit. Missing instrumentation or an incomplete
telemetry record is `Unknown(NormalizerMismatch)`.

---

# 8. Calls and analysis-time inlining

## 8.1 Direct internal calls

Only a direct `call` to:

- a defined function inside $T$; or
- a declaration with an exact manifest contract; or
- the exact reserved release-marker declaration at its bound marker
  instruction

is accepted.

For a defined callee, the implementation of the normative `Step_{T,K,TE}` performs
analysis-time inlining, implemented as semantic expansion:

1. bind actual scalar values to formal scalar values;
2. bind pointer arguments to the same object/offset identities;
3. create a fresh namespace for SSA values and local allocation objects;
4. preserve the caller memory and event trace;
5. execute the callee CFG;
6. return the result and updated memory/events; and
7. preserve an explicit release or contract event at its original call
   boundary.

This expansion does not mutate $T$ and does not erase occurrence identity.

## 8.2 Call bounds and closure

The direct call graph MUST be acyclic. Each analysis path has:

```text
call depth <= K_call
expanded instruction count <= K_expanded_instructions
path count <= K_paths
```

A recursive SCC, indirect call, unresolved function pointer, vararg call,
unclassified operand bundle, inline assembly callee, or exceeded budget causes
`Unknown(IndirectCall)`, `Unknown(Recursion)`, or
`Unknown(ResourceLimit)` as appropriate.

## 8.3 External contracts

Except for the separately validated reserved release marker, an external
declaration is accepted only if its symbol, resolved implementation identity,
and LLVM declaration exactly match one closed normative
`MechanismContract`: `ContractSignatureV2`, singleton `UnitChoiceV2`,
`MechanismOccurrenceSpecV2`, `ContractMemoryEffectV2`,
`ContractFailureV2`, `ContractMetadataBindingV2`, visibility bases, state
fields exactly `None`, `NoContractReleaseV2`, and
`NoFreshContractAllocationV2`. It resolves through the canonical
`ContractTableArtifactV2`; the table digest, contract ID, boundary occurrence,
policy binding, stable call site, and reachable-boundary inventory must all
agree. The ordered
effect/event schemas are the complete trace and observation effect; no parallel
profile field list supplies defaults.

LLVM attributes are not a substitute for a contract. If the contract is ideal,
the corresponding open deployment assumption is carried to P4.
Rev4.1 contracts are deterministic and consume only the singleton
`UnitChoiceV2`. A nondeterministic external, a contract-emitted release, a
pointer result/write, or any fresh allocation, deallocation, reallocation, or
lifetime effect is rejected with the corresponding normative
`MechanismNondeterminismUnsupported`, `ContractReleaseUnsupported`, or
`ContractAllocationUnsupported` reason. Pointer arguments may address only
objects already present in the canonical PONF allocation table and are
accepted only for same-host contract calls. A cross-host signature containing
a pointer argument is rejected because the profile has no raw-address or remote-handle
wire encoding.
Before a call rule can be emitted, an independent structural validator
reconstructs the exact input/output tuple types and verifies one correctly
typed `ContractOutputExpressionV2` per output field; a relation table, callback,
partial expression vector, or duplicate/missing field is rejected. The
dispatcher then applies the exact normative
contract-call event sequence: callee choice, optional request transfer with
the complete `ContractRequestWireTupleV2` bytes; for same-host calls, all
`Read`/`Write` pre-access `Memory` events in effect order; each potential event
slot in order, with metadata slots emitting `ContractMeta` plus bound outputs
and the active failure slot emitting exact `Failure`/`Error` plus bound
outputs; for same-host calls, all `Write`/`Initialize` post-access `Memory`
events in effect order; optional response transfer with the complete
result/outcome/state/effect/metadata/failure
`ContractResponseWireTupleV2` bytes; and latency. Cross-host contracts have no
memory effects. Their request is owner/source to the unique destination and
their response reverses those endpoints. Both
transfers use `"SPS-ContractWire-v2"`. A prose claim of determinism or a host
callback cannot replace this closed typing/coverage check.

## 8.4 Tail calls and exceptional calls

`tail`, `musttail`, `notail`, `invoke`, and `callbr` are rejected. The
normalizer MUST NOT delete `musttail` as if it were an optimization-only fact.

---

# 9. Loops and bounded execution

## 9.1 Normative public bound and engine cap

For every natural loop $L$, the profile manifest supplies exactly one
`loop_bound_ids[L] = b_L`, where $b_L$ resolves to the normative
`PolicyManifest.publicBounds` map. On an admitted state, define

$$
B_L(\sigma,\nu)=\operatorname{EvalPublicBound}(b_L,\sigma,\nu).
$$

The normative well-formedness rules make $B_L$ finite, nonnegative, and a
function only of admitted public values. This is the semantic loop bound.
For `CanonicalSingleBlockLoopV2`, it counts permitted executions of the sole
loop block: copy indices are exactly `0 <= k < B_L`. It does not count
backedges. Consequently `B_L=0` permits no loop-block execution and the
preheader's attempted copy zero takes the retained remainder; an ordinary
exit from any permitted copy does not.
`K_loop[L]` is a separate finite implementation resource cap. Before analysis,
the implementation MUST establish that `K_loop[L]` is large enough to encode
the boundary transition for the maximum value of $B_L$ over all admitted
states. Failure to establish this relationship is
`Unknown(ResourceLimit)`; increasing `K_loop` never changes $B_L$.

The engine runs the normative `ExpandV2(T,e)`, not an alternate unroller. It
first computes `boundMaximum` as the exact maximum of $B_L$ over the finite
admitted public-configuration domain, expands exactly the copies
`0..boundMaximum-1` of the sole canonical loop block, and retains one
canonical remainder unit. Entry to copy zero and continuation to copy `k`
use the exact original preheader/backedge guard conjoined with `k < B_L`.
The complementary edge, with that same original guard conjoined with
`not(k < B_L)`, reaches the remainder. The original exit edge from every
reachable copy bypasses the remainder. At the semantic boundary, the
remainder unit encodes:

```text
emit BoundExhausted(loopSite(L), b_L)
emit Latency(loopSite(L), configuredClass)
terminate with BoundFailure
```

`K_loop[L]` must be at least `boundMaximum` plus capacity for the retained
remainder unit; it never determines the number of semantic copies. The
independent expander reconstructs stable call/loop paths, all output/terminal
edges, the complete canonical `ExpandedCFGTableV2`, and its exact longest-path
horizon from the reparsed bitcode, serializing the result as the normative
`HorizonDerivationV2`. A cap shortfall is `Unknown(ResourceLimit)`; inability to
derive the maximum or any disagreement in IDs, edges, units, or horizon is
`Unknown(HorizonDerivationUnsupported)` or
`Unknown(HorizonDerivationMismatch)`. No truncated graph is solver input.

## 9.2 When a proof may proceed

A `Proved` result requires the solver to establish, under the normative
`Admitted(M,ABI,K,TE,T,e,σ,ν)` predicate, that the original backedge is infeasible
whenever its next copy index is not less than $B_L$, and that loop entry is
infeasible when $B_L=0$, in every relevant run. Equivalently, the semantic
`BoundExhausted` transition is unreachable for every admitted state. The
ordinary exit from any admitted copy remains an ordinary exit and never
passes through the boundary unit.

If a runtime bound guard is also present, that guard and its failure path MUST
appear in $T$. Its control, fault, termination, and timing effects are ordinary
observations, but it does not replace `loop_bound_ids[L]` or the exact
public-bound transition above.

A replayed lane mismatch involving `BoundExhausted`, `BoundFailure`, or their
site/bound identity reaches normative `Bad_A` and is a
`Counterexample(receiptId)`. Any reachable exhaustion, including a
symmetrically reached exhaustion that does not itself make the two-lane product
bad, violates universal bound adequacy and therefore prevents `Proved`; absent
a replayed bad execution, its result is `Unknown(LoopRemainder)`. Solver
timeout or path explosion is `Unknown(ResourceLimit)`.

## 9.3 Loop form

The profile accepts exactly `CanonicalSingleBlockLoopV2`. A loop has one block `H`,
which is both header and sole latch; one outside preheader `P` whose sole
successor is `H`; one backedge `H->H`; and one outside dedicated exit `X`
whose sole predecessor is `H`. `H` has exactly the predecessors `P,H`, ends
in one conditional `br` whose two successors are exactly `H,X`, and every
header PHI has exactly one incoming value from each predecessor. The loop has
no nested loop and `H` contains no non-debug direct/internal/external call,
contract boundary, or release boundary. A debug intrinsic already classified
as `DebugNoOpV2` is allowed and is not a semantic call.

The form is also syntactically loop-closed SSA. Every result defined in `H`
that is used outside `H` may occur there only as the `H` incoming operand of a
PHI in the maximal leading PHI list of `X`; a direct live-out use by an
ordinary instruction, branch, return, or any other PHI is forbidden. The
`CanonicalSingleBlockLoopV2` descriptor lists the complete leading PHIs of
both `H` and `X` in frozen order. This restriction gives every retained
outside use one definition after `H` is cloned: the `X` PHI, rather than an
implementation-selected loop copy.

The residual audit derives this form directly from the reparsed LLVM 22.1.8
CFG, def-use graph, and stable edge/loop table. It checks the loop-closed
condition directly; LoopInfo, LoopSimplify, or LLVM's LCSSA analysis may be
used only as cross-checks. Multiple-block, nested, multiple-entry,
multiple-latch/backedge, multiple-exit, non-dedicated-exit, switch-latch,
call-containing, non-loop-closed, irreducible, or unclassified loops,
recursion used as iteration, and control transfer into a loop body are out of
profile and yield `Unknown(HorizonDerivationUnsupported)` before PONF
construction.

For the accepted form, `ExpandV2` applies the normative preheader, copy,
backedge, exit, remainder, and PHI rewrite literally. Header PHIs on the
preheader edge use their `P` operands; those on copy `k` to `k+1` select their
`H` operands; exit PHIs select their `H` operands from the exiting copy.
Every selected SSA operand and every ordinary cloned operand/branch guard is
then passed through the normative definition-site-aware
`ResolveExpandedSSARefV2`: an argument or outside-loop invariant retains the
enclosing path, while an `H` definition receives the exact current
`LoopFrameV2`. The resolved definition must exist uniquely and dominate the
use or exact PHI source edge. Remainder edges own no PHI assignments. Golden
expanded-CFG fixtures byte-bind every node, edge, guard, resolved operand, PHI
row, remainder, and horizon. A multi-latch, multi-exit, nested,
call-containing, or direct-live-out negative fixture must be refused rather
than normalized by an implementation-selected unroller or SSA repair.

The profile does not rely on `mustprogress`, `willreturn`, ScalarEvolution, or a
compiler trip-count claim as an axiom. Such analyses MAY help establish the
public-bound adequacy obligation or size an engine cap, but the exact boundary
transition and its unreachability are independently checked.

---

# 10. Byte memory and whole-region initialization

## 10.1 Pointer representation

An accepted runtime pointer is modeled as:

$$
\operatorname{Ptr}(o,\delta),
$$

where $o$ is an origin identity—a distinguished null origin, an
allocation/ABI/global provenance object—and $\delta$ is a canonical pointer-index-width
modular byte-offset expression constructed under the pinned flag-free GEP and
`DataLayout` rules. Object liveness is tracked separately. A
pointer may remain a representable value outside an object's live interval;
only an operation whose LLVM semantics requires a live object, such as a
dereference, imposes that condition.

Pointer origins arise only from:

- the address-space-zero null constant;
- a declared ABI root;
- an accepted global;
- an accepted `alloca`;
- flag-free `getelementptr` from an existing pointer.

A direct function symbol is accepted only in the callee position of a direct
`call`; it is not a first-class runtime pointer origin. A contract-produced
pointer or allocation is out of profile.

`ptrtoint`, `inttoptr`, nonzero address spaces, unstable/external-state pointer
representations, and pointer authentication are rejected.

### 10.1.1 Layout-independent pointer equality

LLVM pointer `icmp eq/ne` compares address bits, so distinct allocation IDs do
not prove inequality. The profile accepts only the normative closed syntactic case:
after exact pointer/GEP lowering, the two canonical `AllocationKey` PONF term
trees must be byte-identical. The result is the one canonical equality of
their modular `OffsetKey` terms (`Not` of it for `ne`). This is exact because
the same base is added to both sides; it needs no synthesized predicate or
layout solver.

A same-root pair of GEP chains can satisfy this rule. A selected/different
allocation-key expression, distinct object, or nonidentical term is rejected
even if a stronger theorem might prove it equal in one program. The
audit records only the static site plus the two world-public canonical term
digests and literal disposition `SameCanonicalAllocationKeyV2`; these are
non-authoritative locators, and conformance reconstructs and byte-compares the
terms. Any other disposition is
`Unknown(LayoutDependentPointerComparison)`. It is never `UBRisk` and never by
itself a confidentiality counterexample, because the LLVM comparison is a
defined operation when its operands are usable. Poison or other unusable
operands remain a separate Section 11 obligation.

## 10.2 Objects and bytes

The authoritative memory component of the normative exact state is precisely a
finite map from live allocation object and byte offset to:

```text
ExactByteCell {
  initialized: bool;
  bits: i8;
}
```

Object records contain size, alignment, lifetime, mutability, region identity,
and allowed aliases. Endianness and layout come only from
`ABI.targetDataLayout`.

For every accepted load, store, or memory intrinsic, the fixed memory event
uses:

```text
MemoryAddressV2 {
  stable_allocation_class;
  exact_first_byte_offset;
  exact_width_bytes;
}
```

The allocation class is derived from the hash-bound ABI role, global identity,
or local `alloca` site plus dynamic call/allocation occurrence. It
does not expose a process base address, but it never merges two classes that the
fixed observation model distinguishes. The byte offset is the exact
allocation-relative modular offset after the access's in-bounds obligation has
been checked. Implementations MUST NOT round, mask, bucket, hash, or project the
offset or width before comparison in `Product_A`.

An implementation MAY maintain a separate diagnostic ghost table containing
facts such as:

```text
DiagnosticByteFact {
  dependency;
  last_writer;
}
```

These facts serve only the Section 10 diagnostic analysis of the sole
normative specification. They are not part of an exact lane state, are not read
by `Step_{T,K,TE}` or `Product_A`, and cannot alter a byte, initialization bit,
load result, store effect, event, path condition, definedness obligation, or
result classification. In particular, the profile has no static
program-counter security label. An ordinary inability or conservative
imprecision that merely fails to derive a ghost fact is recorded as
`RelationalRequired(reason)`; exact byte semantics and the whole-entry product
continue, and that record does not by itself prevent `Proved`. A malformed or
stale record, incomplete mandatory diagnostic traversal/coverage, or other
diagnostic-engine health failure is instead
`Unknown(DiagnosticHealthFailure)`. A claimed fact that disagrees with exact
recomputation is `Unknown(ToolInconsistency)`. Neither outcome may justify
`Proved` or suppress an exact product obligation.

Pointer-typed loads and stores are rejected. Accepted memory contains
ordinary bytes interpreted as accepted integer or FP values.

## 10.3 Load

An accepted load satisfies the following LLVM memory preconditions:

1. its pointer resolves to one live object;
2. every accessed byte is within that object;
3. the address satisfies the load alignment;
4. the operation is non-atomic and non-volatile; and
5. reconstructing the requested scalar type is valid under `DataLayout`.

If an exact admitted execution violates one of these conditions, it takes the
`UBRisk` transition in Section 11.4. If the verifier cannot decide whether such
an execution is reachable, it produces `Unknown(PossibleUB)`. The
implementation MUST NOT invent an arbitrary value or filter the execution.

Initialization is a separate semantic-support condition. Under LLVM 22.1.8,
a non-volatile load of an otherwise valid byte that has never been written
produces `undef`; the load is not immediate LLVM UB. The exact SPS byte state
therefore checks:

$$
\forall b\in\operatorname{LoadFootprint}.\ \operatorname{initialized}(b)=1.
$$

If that predicate is reachable and false, or its universal truth cannot be
established, analysis stops with
`Unknown(UninitializedLoadProducesUndef)`. It MUST NOT emit `UBRisk`, construct
a replayable counterexample from the load alone, invent fixed or per-use bits,
or filter the execution. A separately reachable poison or UB condition remains
governed by Sections 11.3--11.4; this unsupported-`undef` refusal does not
reclassify it.

The exact load result is reconstructed solely from the selected exact bytes.
Separately, the Low/High diagnostic MAY join ghost dependencies of those bytes
and the explicit address selector, but that join has no semantic authority.

## 10.4 Store

An accepted store is defined only if:

1. its pointer resolves to one live writable object;
2. every written byte is in bounds;
3. alignment is satisfied; and
4. the operation is non-atomic and non-volatile.

The exact store updates only the affected bytes' `bits` and `initialized`
fields. If an exact admitted execution violates a condition, it takes the
`UBRisk` transition in Section 11.4; undecidable reachability is
`Unknown(PossibleUB)`.

The diagnostic ghost table MAY record a writer locator and join value,
address-selector, and explicit executed-guard dependencies. That update is not
a normative state update and supplies no static program-counter label.

Unwritten bytes retain their former cells.

## 10.5 Exact whole-region initialization and diagnostic facts

For a logical region $R$ at program point $p$, exact initialization means the
finite per-byte predicate:

$$
\operatorname{ExactInitialized}(R,p,\sigma)
\iff
\forall b\in R.\ \sigma.Mem[b].initialized=1.
$$

`Step_{T,K,TE}` and `Product_A` retain the exact bytes and initialization bits.
They MUST NOT replace this state with a region summary, discard prior bytes, or
install `ExactInitialized` as an unproved axiom. An implementation may prove
the finite predicate by a logically equivalent formula, but every exact store,
guard, path, alias possibility, lifetime transition, and loop-bound transition
remains represented in that proof.

For early diagnostics only, the ghost table MAY record
`DiagnosticInitialized(R,p)` when it has established:

1. $p$ postdominates every certified write path that reaches the relevant
   normal exit;
2. for every admitted normal path to $p$ and every byte $b$ in $R$, a
   must-executed in-bounds write covers $b$;
3. the object is not freed, ended, escaped to an invalidating contract, or
   reused before $p$;
4. an inactive masked/conditional write is not counted unless another write
   covers the byte on that path; and
5. every semantic `BoundExhausted` transition involved in the coverage proof is
   unreachable and every engine cap is sufficient.

Diagnostic old-content dependencies may be replaced only in the ghost table
under the stronger last-writer condition:

$$
\forall b\in R.\ \operatorname{LastWriterBefore}(b,p)
\text{ is one of the certified writes.}
$$

The diagnostic region dependency may join final-writer value,
address-selector, explicit guard, and loop-bound dependencies. Neither this
join nor the last-writer record changes exact memory or discharges a product or
definedness obligation. Any implementation that uses either as an
authoritative semantic shortcut fails conformance with
`Unknown(InvalidDiagnosticShortcut)`.

Reads inside an initialization loop require a separate prefix property: every
read byte has a preceding write on that execution. Exit coverage alone does not
justify an earlier read.

## 10.6 Allocation and lifetime

`alloca` creates a fresh object. For a site $s$ reached in exact state $\sigma$,
let `LLVMAllocaBytes_I(s,i,sigma,nu)` be the checked product of the exact runtime
element count and the `DataLayout` allocation size of the allocated type. Before
using that object, the verifier recomputes and proves:

$$
\forall e,\sigma,\nu,s,i.\
\operatorname{Admitted}(M,ABI,K,TE,T,e,\sigma,\nu)
\land \text{execution reaches alloca }s\text{ at occurrence }i
\Longrightarrow
\operatorname{EvalWorldStructuralBytes}
  (M.\operatorname{allocaSizeBindings}
    [\operatorname{alloca\_size\_ids}[s]],
   \operatorname{PublicStructuralState}_{s,i})
=\operatorname{LLVMAllocaBytes}_I(s,i,\sigma,\nu),
$$

together with totality, nonnegativity, and no overflow at every conversion,
multiplication, and target pointer-index-width boundary. The equality is an
exact byte equality, not a maximum-size inequality. The same world-structural
expression is therefore equal in two `LowEq` lanes; that fact follows from the
policy binding rather than an added pair constraint.

A fixed-size `alloca` still requires a literal expression and proof record. A
public-variable size is accepted only with the universal equality proof. A
size controlled by a `High` value, a coalition-relative value, or an unbound
environment value is rejected. If overflow freedom or equality cannot be
proved, the result is `Unknown(AllocaSizeNotWorldStructural)` before object
creation; the verifier does not wrap, cap, or nondeterministically choose a
size. The normative `AllocaExtentRepresentableV2` row has
`failureDisposition=UnsupportedAllocaExtent`: it emits no `UBRisk`, failure,
error, termination, allocation update, or counterexample. A different
reachable immediate-UB operand-definedness failure at an otherwise conformant
`alloca` takes the Section 11.4 `UBRisk` transition.

`K_bytes` is an engine resource cap, not an LLVM semantic limit. Once the exact
world-structural byte size has been proved, exceeding `K_bytes` stops analysis
with `Unknown(ResourceLimit)` and never truncates the object.

A variable or sufficiently large public `alloca` can cause target-dependent
stack adjustment, probing, or helper control after the frozen IR boundary. The
implementation emits `PublicDynamicAllocaStackProbe` timing-risk records for
every site whose final lowering may cross a pinned target probe threshold. This
does not make the IR size `High`, does not change `ModelStatus`, and does not
prove the absence or alignment of probe observations. The concrete final
binary's probe addresses, conditional transfers, failure behavior, and helper
calls remain paired P4 obligations under the exact observation mapping.

The profile has allocation liveness but no subobject/interval lifetime state. Residual
`llvm.lifetime.start/end` is therefore rejected as above. Each dynamic
`alloca` becomes live at its exact expanded allocation transition and remains
live until return from that exact expanded function frame; `HelperReturnV2`
clears all dynamic allocation rows owned by that frame. A later dereference
through an escaped pointer takes the ordinary dead-allocation `UBRisk`
transition.

Heap allocation, deallocation, reallocation, library-owned memory, and fresh
contract-produced pointer origins are unsupported. They require a future
profile with canonical allocation rows, lifetime transitions, and alias rules;
an external contract does not make them representable in the current PONF.

## 10.7 Memory intrinsics

There is no residual memory-intrinsic semantic rule. The deterministic
normalizer must lower `memcpy`, `memmove`, and `memset` into the accepted
load/store/control instructions before freeze, preserving LLVM overlap,
initialization, zero-length, and definedness behavior. The frozen module is
audited after that lowering. A residual memory intrinsic cannot enter
`Step_{T,K,TE}` or PONF and yields `Unknown(PONFIntrinsicUnsupported)`.

---

# 11. Definedness

## 11.1 Universal definedness obligation

The semantics implementation MUST track definedness for every reachable
instruction under the normative admitted-state predicate. Stripping flags does
not make LLVM total. A violated definedness condition is totalized only by the
fixed `UBRisk` transition in Section 11.4; it is never removed as a pair filter.

A `Proved` model result requires every relevant admitted execution of $T$ to be
defined, or requires the sole normative specification to exclude the execution
through its explicit admission predicate.

This universal LLVM-definedness obligation is distinct from exact support for
all LLVM-defined values. In particular, Section 10.3 conservatively returns
`Unknown(UninitializedLoadProducesUndef)` for an uninitialized load rather than
misclassifying LLVM's non-UB `undef` result as `UBRisk`.

## 11.2 Required scalar checks

At minimum, the following are checked:

| Operation | Definedness condition |
|---|---|
| `udiv`, `urem` | divisor is nonzero |
| `sdiv`, `srem` | divisor nonzero; forbidden signed overflow case handled per LangRef |
| shifts | shift amount is less than bit width; failure is unsupported poison, not immediate UB |
| branch/switch | condition is a defined scalar |
| `select` | condition defined; only selected data value must be usable |
| GEP | index arithmetic follows flag-free LLVM semantics; later dereference in bounds |
| pointer `icmp eq/ne` | operands usable; both canonical `AllocationKey` term trees are byte-identical under Section 10.1.1 |
| load/store | Section 10 |
| call | callee and contract precondition defined |
| `unreachable` | instruction is unreachable |

Modulo integer `add`, `sub`, and `mul` are defined after wrap flags are removed.
The only accepted scalar FP operations are the bit-exact `fneg` and `fcmp`
rules; no accepted instruction performs FP arithmetic or numeric conversion.

### 11.2.1 Exact FP bit operations and prohibited-opcode closure

The exact value domain for accepted `float` and `double` values is their full
IEEE bit pattern, including NaN sign and payload. Under the pinned LangRef:

- `fneg` flips only the sign bit;
- scalar `bitcast`, `phi`, `select`, `load`, and `store` preserve the selected
  bit pattern exactly; and
- `fcmp` produces the deterministic predicate result for the exact operands,
  including the ordered/unordered behavior in the presence of NaNs.

Those operations do not authorize canonicalizing, quieting, equating, or
otherwise choosing a NaN payload. `fadd`, `fsub`, `fmul`, `fdiv`, `frem`,
`fptrunc`, `fpext`, and every FP/integer numeric conversion are rejected by the
residual audit with `Unknown(PONFFPArithmeticUnsupported)`, irrespective of
reachability or a proof that one particular result is non-NaN. Therefore
`NoAmbiguousNaNResult_e(T)` is the direct syntactic fact that no such opcode
occurs in an `NFConforms` module, and
`fpNaNPayloadSemanticsDigest` binds the canonical empty rule table. There is
no target-specific unique-result escape hatch.

## 11.3 Undef and poison

Literal undef and poison remaining after `SPSFinalDeadCleanup_v2` fail the
normal-form audit before execution, including when they occur on a
CFG-reachable path that later analysis might prove infeasible. An uninitialized
load that would produce LLVM `undef` is handled by the explicit unsupported
case in Section 10.3, not by `UBRisk`. An out-of-range accepted shift produces
LLVM poison and is handled by the normative
`failureDisposition=UnsupportedPoison` and
`Unknown(PoisonSemanticsUnsupported)` gate: replay stops before the shift,
emits no event/status, and poison production itself is never a
counterexample. Other exact immediate LLVM-UB definedness failures use
Section 11.4. The implementation MUST NOT continue either unsupported value
with an unconstrained solver value and later report `Proved`.

## 11.4 `UBRisk` event and result handling

When an exact admitted execution reaches instruction site $s$ with a false
immediate-LLVM-UB precondition (not an unsupported poison/undef result), the
lane does not produce an arbitrary ordinary result. It instead:

1. emits `UBRisk(s,reasonClass)` with a stable reason class;
2. also emits `Failure(s,UBRisk(reasonClass))` and
   `Error(s,ABI.ubRiskErrorFieldId,UBRisk,reasonClass)` in the fixed `Theta_ct`
   alphabet, where the reserved ID has a declared ABI binding and policy
   visibility basis; and
3. terminates with the normative `UBFailure(reasonClass)` status.

The event site and observation location are derived from the exact instruction
identity and normative `FunctionPlacementTable`. `UBRisk` is an event, not a
diagnostic-only record and never a reason to discard an execution pair.

While the product obligation is `Active`, if only one lane emits the event, or
the event site, reason class, error payload, or terminal status differs, the
fixed normative product reaches `Bad_A`; an exact replay yields
`Counterexample(receiptId)`. After retirement such a mismatch is not a
new `Bad_A`, but unary reachability still prevents `Proved`. If both lanes
reach an aligned risk without making the product bad, universal
definedness still fails, so the result is `Unknown(PossibleUB)`, never
`Proved`. If reachability cannot be decided, the result is
`Unknown(PossibleUB)`. Only a universal proof that every such transition is
unreachable permits `Proved`.

---

# 12. Mechanical prerequisites for relational checking

This section constrains use of the sole normative specification’s
`Product_A`, `Bad_A`, and related judgments. It does not redefine them.

For every proof query `Q`, the implementation uses the normative pipeline

```text
B = BoundInputsV2(M,ABI,R,K,TE,FPT,I,identityPreimages,
                  RelationBindingTableV2)
S = None | ConcreteCoalition(A)
P = BuildPONF_v2(T,B,e,S,Q)
ponf_digest = CanonicalPONFDigest(P)
            = SHA256(CanonPONF_v2(P))
F = LowerPONFToSMT_v2(P, smt_lowering_version)
exact_formula_digest = SHA256(canonical SMT-LIB bytes of F)
```

Here `P` is a canonical `SPS-PONF-v2` object, not an implementation-private
symbolic graph. `S` is chosen from the normative query-arity table.
`SharedSignature` is noncanonical; every relational object and result is
built independently for one concrete coalition.
`BuildPONF_v2` fixes state sorts, allocation identity, exact
memory and initialization, guarded SSA/call/loop expansion, choice coupling,
the prefix-causal ledger recurrence, query templates, and every applicable
bad disjunct. `LowerPONFToSMT_v2` is deterministic for the bound lowering
version. The solver MUST receive exactly the canonical SMT-LIB bytes whose
digest is recorded. Internal solver preprocessing does not change that input
identity. A different or optimized lowering requires a separately bound
lowering version and the validation required by the normative PONF rules; an
asserted claim of logical equivalence is not itself a proof result.
The solver answer and validation state are serialized separately as the
normative public `PONFResultArtifactV2`; its `CanonicalPONFResultDigest` binds
the PONF/formula/configuration identities, content-independent protected-
evidence receipt, replay/evidence validation, and query disposition. Raw
solver transcripts, models, decoded states, and replay traces are confined to
`RestrictedEvidenceBundleV2` and are neither embedded nor content-hashed in the
public result. A solver log or filename is not that result envelope.

## 12.1 Lockstep control checks

The normative product is mandatory for every supported entry and coalition.
Its encoding MUST represent each of the following equalities as a checked
condition whose violation reaches `Bad_A`:

- branch and switch choice;
- loop header, latch, and exit choice;
- direct callee identity;
- return versus fault behavior;
- termination behavior; and
- every other control choice required by the normative observation model.

The encoder may simplify one of these checks only after a sound local proof
that the equality follows from the exact current relational assumptions. A
“public” label is sufficient only where the normative `LowEq` definition
guarantees value equality for the coalition and current release ledger. An
equality is never installed as an assumption that removes unequal pairs.

## 12.2 Divergence

If unequal control is satisfiable, the fixed rev-4 product reaches `Bad_A`.
After exact replay, the result is `Counterexample(receiptId)`. This
remains true even if a later coalition projection would conceal the branch
payload: rev-4 makes active control-location equality an explicit security
condition. The implementation MUST NOT constrain the two runs to take the same
branch merely to reduce solver cost.

## 12.3 Paired loops and calls

Both sides use the call and loop rules in Sections 8–9. A `Proved` result
requires every semantic `BoundExhausted` transition unreachable, every engine
cap sufficient, and all paired calls within bounds. One side exhausting,
emitting `UBRisk`, faulting, terminating, or returning while the other does not
is presented to the normative observation rules rather than suppressed.

## 12.4 Required domain and activation queries

The reference implementation runs every row as a separately scheduled query;
coverage is not inferred as a side effect of the `AuditAll` row. It uses the normative
`PublicQueryScheduleV2`, `QueryDescriptorV2`, `PublicQueryResultRowV2`, and
closed `PONFResultArtifactV2` directly; there is no second
`ProofDomainCoverageRecord` or `ResultValidationV2` wire type. A constructed
row is well formed only if recomputation from the identity-bound inputs
reproduces its PONF and exact-formula digests. In particular, an `UNSAT`
answer applies only to that exact PONF object and lowering.

The required query matrix is exactly the normative section-19
`PublicQueryScheduleV2` derivation:

1. `AuditAll` for every closed entry and concrete derived coalition;
2. `ReleaseActivation` for every `(entry,release)` activation-claim row,
   including Dormant and NotApplicable, and `ReleaseConformance` for every
   non-NotApplicable row;
3. `AdmissionNonempty`, `LLVMDefinedness`, `Initialization`,
   `BoundAdequacy`, `StructuralAlloca`, and `OutputClosure` for every closed
   entry;
4. `HighVariation(c)` for every entry-applicable component classified `High`
   for each coalition, with no coupling constraint; and
5. `CouplingTotality`, `CouplingFiberTotal`, `CouplingSymmetry`, and
   `CouplingSchedulePreservation` for every entry, coalition, and
   syntactically applicable mechanism/timing relation. Fiber checks enumerate
   every reachable active occurrence after construction; construction failure
   leaves the scheduled `NotConstructedV2` row rather than deleting it.

`OutputClosure` covers every manifest-allowed actual top-level program-return
class and every byte in the full fixed ABI-root and contract-event surface;
verifier-only `UBFailure`/`BoundFailure` sentinel stops are not ABI returns and
are excluded.

A SAT result is only a candidate. An admission witness is decoded and rechecked
against one complete `Admitted` predicate. The verifier then mechanically
duplicates it and checks the reflexive `LowEq^0` diagonal for every coalition;
failure is `Unknown(ToolInconsistency)`, not a separate pair-domain result.
Variation witnesses
recheck both individual `Admitted` predicates, the exact ABI/public alias
topologies, and `LowEq^0`; they deliberately recheck no current or future
coupling. A variation witness additionally rechecks unequal carrier values.
A release-activation witness is replayed to the exact bound occurrence. An
invalid SAT witness is `Unknown(ToolInconsistency)`, not coverage.
Each accepted admission/high-variation or RequiredReachable-activation SAT
row uses the parameterless public disposition
`ValidatedExistentialWitness`; its one reserved query receipt becomes the
mandatory `PONFResultArtifactV2.protectedEvidence` field. An accepted
`UNSAT` row uses `Discharged`, except that a `HighVariation` UNSAT row without
a matching expected-variable assertion uses
`ConstrainedOrUnexercised`. Every constructed query has exactly one receipt
and empty fixed-size store slot reserved before solving regardless of
`SAT`/`UNSAT`/`UNKNOWN`; `NotConstructedV2` has the analogous protected
receipt and binding without dummy PONF fields. After all outcomes exist, one
immutable padded authenticated bundle per row is finalized in public schedule
order. No result-dependent receipt, bundle count/length/write order, mutation,
or public replay-validation constructor exists.

`OutputClosure` and `CouplingFiberTotal` have counterexample polarity. Accepted
`UNSAT` discharges them. Their public `SAT` row remains `CandidateOnly`
regardless of restricted replay. Internally, an output candidate either lifts
to a covered `Bad_A` replay or yields the exact output-closure `Unknown`
reason; a coupling-fiber candidate yields
`Unknown(CouplingFiberCoverageFailure)`. Only the separately bound final
`Counterexample(receiptId)` may publish replay acceptance. A public row never
contains a witness-selected site/rule/occurrence, model, choice value, output
byte, replay outcome, or content-derived evidence digest.

Proved UNSAT for `AdmissionNonempty` yields `Unknown(VacuousAdmission)`. Every High
row is reported. Its UNSAT `QueryDispositionV2` is
`ConstrainedOrUnexercised` and ordinarily does
not change `ModelStatus`, but if the exact triple is named by a hash-bound
`expectedVariableAssertion`, any result other than a validated SAT witness is
`Unknown(ExpectedHighVariationAbsent)`. A `RequiredReachable` release requires
a validated SAT activation witness. `Dormant(reason)` requires accepted exact
UNSAT reachability, and `NotApplicable` requires both syntactic and semantic
non-applicability. A contradicted or unresolved activation claim is
`Unknown(ReleaseActivationMismatch)`. Solver/resource UNKNOWN remains its
specific `SolverTimeout` or `ResourceLimit` reason and never becomes a vacuity
proof or dormancy proof.

These existential and intent checks are aggregation gates and review evidence;
they do not replace the universal product or universal definedness/bound
proofs. In particular, one varying High witness does not establish
confidentiality and one dormant release does not establish release conformance.

## 12.5 Preflight triage, conformant falsification, and replay coverage

Best-effort scanners MAY run before full conformance closes. Their selected
origin, locator, and evidence bytes exist only as the normative
`PreflightTriageFindingV2` inside
`PreflightEvidencePlaintextV2`. The only public form is:

```text
PreflightTriageSummaryV2 {
  artifactIdentityDigest: Digest,
  taskId: stable identifier,
  disposition: "NonAuthoritativePreflightOnly",
  protectedEvidence: ProtectedEvidenceReferenceV2
}
```

Such a finding is useful triage but cannot be `Proved`, a normative
`Counterexample`, or evidence that no other bug exists. Unsupported IR,
incomplete event coverage, or an approximate observation profile is never
given invented rev-4 semantics merely to promote the finding. Its authenticated
binding is the `PreflightEvidenceBindingV2` variant and binds this summary,
artifact identity, profile configuration, and exact
`PreflightTaskScheduleV2` directly; it never fabricates a PONF, SMT formula,
solver result, or PONF-result digest. Exactly one summary/bundle pair is
represented for every predeclared task. Its receipt and empty fixed-size store
slot are reserved before scanning; after all findings exist, one immutable
padded bundle is finalized per task in public task order, including
`finding=None`. Public cardinality, scope, task, ciphertext length, write
order, and tag therefore cannot depend on what the scanner selected.

Once `NFConforms(T,I)` closes and exact semantic/event/observation coverage is
available for a candidate prefix, every bug-finding engine stores the candidate
only inside the normative `RestrictedEvidenceBundleV2`. There is no public
candidate record. Candidate count, order, source, per-candidate receipt, and
`ReplayCoveredBad`/rejected/failed disposition all remain restricted. If at
least one candidate exact-replays to `Bad_A`, aggregation publishes exactly
one fresh random final-result receipt with `Counterexample(receiptId)`; it is
independent of candidate contents and resolves internally to one accepted
replay. Otherwise no falsifier-candidate receipt or outcome is public. The
restricted bundle contains initial states, ledgers, aliases, choices, the
candidate prefix, raw/content-derived digests, replay trace, witness source,
and first-bad site/occurrence.

`ReplayCovered_A(T,e,w)` holds only when all of the following are recomputed:

1. `w` binds the exact conformant $T$, $I$, entry, and one actually derived
   coalition, with every referenced schema, digest, ABI, policy, and placement
   identifier uniquely validated;
2. both decoded initial states and choices satisfy the complete `Admitted`
   judgments and `LowEq^0_{A,e}`; each consumed contract/timing choice pair
   satisfies `CurrentCoupled_A` at its occurrence, while no unconsumed future
   choice is retained in the prefix witness or used as an admission filter;
   persistent sequence state is validated as part of the applicable admission
   and invocation-invariant checks;
3. every step of both witness prefixes is replayed by `Step_{T,K,TE}` with exact
   byte memory, definedness, bounds, ledger, stable placement, and fixed
   `StableAllocationExactByteOffsetV2` event production;
4. every operation and value consumed by the prefix has supported exact
   semantics; every local contract, activation, release-expression, footprint,
   audience, and ledger rule strictly before the claimed first-bad transition
   is recomputed and satisfied; at that transition the selected supported
   normative bad clause is recomputed and shown false rather than assumed,
   including a selected `ReleaseConformanceViolation`; this profile adds no
   stronger all-traversed release-conformance premise than the normative
   `ReplayCovered_A(T,e,w)` predicate; and
5. the replay recomputes coalition projection and reaches the normative `Bad_A`
   predicate at the recorded first bad
   site.

The witness source is deliberately absent from this predicate. A sampled,
directed, differential, human, or SMT candidate has identical force after
`ReplayCovered`; before that validation it has none. Replay failure or an
encoder/replayer disagreement is `Unknown(ToolInconsistency)`. Failure to find
a candidate proves nothing.

---

# 13. Result taxonomy

## 13.1 Profile audit classes

The implementation may internally report:

```text
NF-Conformant
NF-OutOfProfile(reason, location)
NF-InvalidConfiguration(reason)
```

Only `NF-Conformant` establishes `NFConforms(T,I)`.

## 13.2 Mapping to `ModelStatus`

This profile imports the sole `ModelStatus` type from normative section 0.1;
it does not redefine it. The exact closed, canonically sorted inventory is
`PublicReasonClassesV2` from the Rev4.1 interface registry and must byte-equal
`ProofConfigurationV2.publicReasonClasses`. There is no local extension table.

This profile constrains the mapping:

| Condition | Permitted `ModelStatus` |
|---|---|
| `NFConforms(T,I)` and the normative proof succeeds | `Proved` |
| `ReplayCovered_A(T,e,w)` reaches `Bad_A`, including a bound or definedness mismatch | `Counterexample(receiptId)` |
| Out of profile | `Unknown(reason)` |
| Parse/canonicalization/identity failure before complete identity and proof-configuration binding | `ConfigurationRejectedV2`; no `ModelStatus` |
| Artifact/pipeline/normalizer mismatch detected after complete identity binding | `Unknown(invalid-configuration reason)` |
| Definedness reachability is undecidable | `Unknown(PossibleUB)` |
| Reachable or unresolved out-of-range shift poison | `Unknown(PoisonSemanticsUnsupported)`; no event/counterexample |
| Aligned reachable `UBRisk` without a replayed bad execution | `Unknown(PossibleUB)` |
| Reachable or unresolved load from an uninitialized byte | `Unknown(UninitializedLoadProducesUndef)` |
| Pointer equality has nonidentical canonical `AllocationKey` terms | `Unknown(LayoutDependentPointerComparison)` |
| An `alloca` lacks an exact world-structural actual-byte equality proof | `Unknown(AllocaSizeNotWorldStructural)` |
| The address observer is not exact stable allocation class plus byte offset/width | `Unknown(UnsupportedAddressObservationProfile)` |
| Any residual FP arithmetic or FP/integer numeric conversion | `Unknown(PONFFPArithmeticUnsupported)` before relational construction |
| Any residual memory, trap, ubsantrap, or other unsupported intrinsic | `Unknown(PONFIntrinsicUnsupported)` |
| `AdaptiveSequence(id)` is requested without the required finite PONF encoding | `Unknown(PersistentInvariantEncodingUnsupported)` |
| Stack-protector preflight, mutation, or residual check is nonempty | `Unknown(UnsupportedStackProtector)` |
| Ordinary diagnostic imprecision recorded as `RelationalRequired` | no `ModelStatus` result by itself; exact product continues |
| Malformed/stale diagnostic record or incomplete mandatory diagnostic coverage | `Unknown(DiagnosticHealthFailure)` |
| Diagnostic claim disagrees with exact recomputation | `Unknown(ToolInconsistency)` |
| Complete entry admission is proved empty | `Unknown(VacuousAdmission)` |
| A validated admission witness fails its duplicated reflexive `LowEq^0` diagonal check | `Unknown(ToolInconsistency)` |
| A hash-bound expected-variable High component lacks a validated variation witness | `Unknown(ExpectedHighVariationAbsent)` |
| A coupling can filter any allowed current choice at a reachable active prefix | `Unknown(CouplingFiberCoverageFailure)` |
| A contract output-expression vector is missing, duplicated, ill typed, or contains an unlisted operation | `Unknown(MechanismNondeterminismUnsupported)` |
| Return/root/event output cover is missing or overlaps | `Unknown(OutputBindingIncomplete)` or `Unknown(OutputBindingOverlap)` |
| A terminal output byte may be uninitialized | `Unknown(UninitializedOutputByte)` |
| Exact terminal output events/order cannot be established | `Unknown(OutputClosureMismatch)` |
| An application, contract, or verifier error count/order/field/class/encoding/initialization/payload cannot be established from `ErrorFieldBindingV2` | `Unknown(OutputClosureMismatch)` or `Unknown(UninitializedOutputByte)` |
| Stable IDs, expanded CFG transition nodes, owned output event rules, or longest-path horizon disagree on recomputation | `Unknown(StableIdentityMismatch)` or the exact horizon-derivation reason |
| A release activation claim is contradicted or unresolved | `Unknown(ReleaseActivationMismatch)` |
| Release intrinsic or flattened intrinsic-operand ABI is absent, duplicate, ambiguous, stale, or ill typed | `Unknown(ReleaseCarrierMismatch)` |
| Supported and bound release guard/value/footprint/order mismatch replays to the normative release bad state | `Counterexample(receiptId)` |
| Restricted `PreflightTriageFindingV2` without conformant exact replay | no counterexample; retain the applicable `Unknown` blocker and only the fixed scheduled public summary |
| Open Spectre-PHT lint or backend-control-delta record | no `ModelStatus` result by itself; corresponding `DeploymentStatus` obligation remains open |
| Aligned reachable `BoundExhausted` without a replayed bad execution | `Unknown(LoopRemainder)` |
| Engine cap cannot encode the normative public-bound transition | `Unknown(ResourceLimit)` |
| Other resource limit or solver timeout | `Unknown(ResourceLimit)` or `Unknown(SolverTimeout)` |

An out-of-profile construct is not itself a confidentiality counterexample.
Conversely, `Unknown` MUST NOT be presented as evidence of security.

### 13.2.1 Aggregation priority

Aggregation consumes exactly one `AggregationInputV2`. Its accepted replay is
an optional `AcceptedBadReplayV2`, and its blockers are an ordered unique list
of `BlockerRecordV2` values whose scopes are `ReplayInvalidating`,
`ProofCompletion`, or `RunFinalization`. `AggregationDecisionV2` binds that
input and its output report to the same `ArtifactIdentityEvidenceV2` closure.

The order is deterministic and source-independent:

1. any `RunFinalization` blocker produces `ReportingFailedV2` and no
   `ModelStatus`;
2. otherwise, a valid `AcceptedBadReplayV2` produces
   `Counterexample(receiptId)`;
3. without an accepted replay, one blocker produces its exact V2 `Unknown`
   reason and two or more blockers produce
   `Unknown(OpenModelObligations)`; and
4. with no blockers, `Proved` is available exactly when
   `allRequiredGatesClosed=true` and the complete required query schedule and
   diagnostic/report/policy-review gates are closed.

An accepted replay together with a `ReplayInvalidating` blocker is rejected as
an inconsistent aggregation input. A proof-completion timeout outside the
accepted bad prefix may coexist with a counterexample because it is not a
premise of that concrete replay. A failed `NFConforms` audit is
replay-invalidating: a finding on nonconformant or semantically uncovered IR
cannot become `AcceptedBadReplayV2` and remains preflight triage.

Public reason selection is a total deterministic map, not a reporting choice:

1. A malformed solver result or query-evidence consistency failure uses
   the normative adapter normalization
   `rawSolverResult=UNKNOWN, queryDisposition:
   Unknown({"reasonClassId":"ToolInconsistency"})` and
   contributes `ToolInconsistency` if aggregation remains possible. Failure to finalize
   mandatory authenticated evidence uses the normative payload-free
   `ReportingFailedV2` envelope and issues no `ModelStatus`. Protected detail
   never selects a finer public tag.
2. A solver timeout carries `SolverTimeout`; an independently detected path,
   byte, memory, or other engine cap carries `ResourceLimit`; every other gate
   carries the one literal reason assigned by its normative rule.
3. If exactly one blocker remains, `ModelStatus.Unknown` carries that class.
   If two or more remain, it carries `OpenModelObligations`; the complete
   canonical blocker set remains restricted. Empty blockers yield `Proved`.

No source location, candidate origin, witness property, first-failing row, or
free-form diagnostic participates in this map.

## 13.3 Stable reason codes

The stable Rev4.1 reason-code inventory is exactly `PublicReasonClassesV2` in
the interface registry. There is no local or extension registry.

`LoopRemainder` is retained as the stable wire reason for an exactly modeled,
reachable `BoundExhausted` transition that does not yield a replayed bad
execution. It never denotes an engine-cap remainder; insufficient engine caps
use `ResourceLimit`.

Public reports are exactly the closed normative `SPSRunReportV2` envelope.
A completed report contains only `SPSPublicReportV2`: identity/configuration
digests, fixed query schedule/results, fixed preflight summaries,
`ModelStatusV2`, open-only `DeploymentStatusV2`, the exact release-policy
review, its one run-evidence receipt, and the literal status-noninterference
field. The bitcode hash and static manifest/PHT/backend-control objects remain
separate world-public identity/P4 artifacts and are not copied into the
report. Reports include neither the ordered blocker set nor any candidate-
level replay row. A report MUST preserve the distinction among `ModelStatusV2`,
`DeploymentStatusV2`, and diagnostic or review findings. A basic block,
instruction ordinal, rule/site/occurrence, witness source, or first-failure
location selected by a secret-bearing witness is restricted even when the
identifier itself is structural. Witness/model/transcript/state/choice/memory/
trace contents and every content-derived digest of them are likewise
forbidden. A secret-bearing artifact appears only in
`RestrictedEvidenceBundleV2`; the public report carries only fixed query rows,
the fixed scheduled preflight summaries, its mandatory random `runEvidence`
receipt, and the single additional random final-counterexample receipt iff
`ModelStatusV2` is `Counterexample`.

A noncanonical internal result candidate is discarded before it becomes a
report; after rebuilding the closed result it may contribute
`Unknown(ToolInconsistency)`. If a prohibited raw/content-derived evidence
field is detected in a would-be `CompletedV2` serialization, issuance stops
and the run returns `ReportingFailedV2` with no `ModelStatus`. The writer never
“sanitizes” an already-issued report or publishes `Unknown` alongside the
prohibited field.

---

# 14. Implementation blueprint

## 14.1 Compiler components

The reference implementation consists of:

1. **Pinned compiler driver** — rejects wrong LLVM/build/target configuration.
2. **Pass-trace recorder** — records stable pass IDs, ordinals, and options.
3. **`SPSPreCGPNormalize_v2`** — performs the limited structural lowering.
4. **`SPSFinalWeaken_v2`** — performs only the last-stage weakening rules.
5. **LLVM verifier adapter** — treats every verifier diagnostic as fatal.
6. **`SPSNormalFormAudit_v2`** — exhaustively inventories and classifies IR.
7. **`SPSFreezeCapture_v2`** — serializes and hashes without mutation.
8. **Frozen-byte replay driver** — parses $B$ and starts at core ISel.
9. **Conformance audit-record writer** — records Section 7 diagnostics; it is
   not a proof checker.
10. **Final-machine control mapper** — inventories every conditional transfer
    in the final linked entry regions and emits `BackendControlDeltaRecord` P4
    evidence locators; it is not a model-proof checker.

## 14.2 Analysis components

The LLVM semantics implementation provides:

1. exact normative `StableIRBindingTableV2` reconstruction, `ExpandV2`,
   expanded-CFG serialization, and longest-path horizon recomputation;
2. closed `TransitionRuleTableV2` dispatch with no fallback callback;
3. exact scalar operations, syntactically empty ambiguous-NaN surface, and
   the byte-identical canonical-allocation-key pointer-equality restriction;
4. exact object-and-byte memory, exact world-structural `alloca` sizes, public
   alias-topology checks, and strictly non-authoritative diagnostic
   ghost facts;
5. direct-call expansion and contract application, including function
   totality/uniqueness checks;
6. public-`BoundId` loop expansion with exact `BoundExhausted`/`BoundFailure`
   and a separate engine cap;
7. universal definedness obligations, the separate uninitialized-load
   `undef` refusal, and fixed `UBRisk` event production;
8. release carrier occurrence reconstruction;
9. exact full-root terminal and contract-event output scheduler with independent
   closure validation;
10. fixed stable-allocation/exact-byte-offset observation-event production
   required by the normative spec;
11. lockstep-eligibility and prefix-fiber-totality queries for the normative
    product;
12. admission, diagonal-consistency, High-variation, and release-activation checks with
    exact witness validation;
13. canonical `SPS-PONF-v2` construction by `BuildPONF_v2`, canonical PONF
    serialization/digesting, and deterministic `LowerPONFToSMT_v2` lowering
    with exact canonical SMT-LIB digesting;
14. access-controlled restricted-evidence storage and content-independent
    public receipt/report generation;
15. preflight triage and source-independent conformant falsifier replay;
16. target-bound, non-authoritative timing-risk and multi-site Spectre-PHT lint
    production; and
17. priority-ordered, reason-preserving result aggregation.

## 14.3 Required defensive checks

The implementation MUST:

- compare the complete inventory against the generated LLVM-22.1.8 table;
- fail if an LLVM enum value has no classification;
- fail if an accepted instruction has zero or multiple
  `TransitionRuleTableV2` rows, or if an opcode-specific event order differs;
- reject FP arithmetic/conversions, trap intrinsics, and residual memory
  intrinsics before PONF construction;
- fail if a target pass is unrecorded;
- fail if a pass mutates after capture;
- rehash before analysis and before codegen;
- validate every normative identity-field mapping and bound structure digest;
- reject a missing placement, loop-to-`BoundId`, or alloca-to-world-structural-
  expression binding;
- prove every accepted `alloca`'s actual total bytes equal its exact
  world-structural expression, including overflow freedom;
- validate every public alias-topology expression against each lane's exact
  realized entry topology without equating `Variable` topology;
- reject any observation configuration other than stable allocation class plus
  exact byte offset and width;
- verify syntactically that the ambiguous-NaN opcode inventory is empty and
  that the bound FP-NaN rule table is the canonical empty object;
- fail if diagnostic ghost state is read by exact semantics or the product;
- preserve ordinary diagnostic imprecision as `RelationalRequired` while the
  whole-entry product continues;
- fail closed with `DiagnosticHealthFailure` for malformed/stale diagnostic
  records or incomplete mandatory diagnostic traversal/coverage;
- fail closed with `ToolInconsistency` when a diagnostic claim disagrees with
  exact recomputation;
- fail if a pointer comparison's two canonical `AllocationKey` term trees are
  not byte-identical;
- fail if a reachable immediate LLVM-UB violation is not mapped to `UBRisk`;
- fail if reachable or unresolved out-of-range shift poison is not mapped to
  `Unknown(PoisonSemanticsUnsupported)`, or is mapped to an event,
  counterexample, or unconstrained suffix;
- fail if an uninitialized load is mapped to `UBRisk`, an ordinary value, or a
  counterexample rather than `Unknown(UninitializedLoadProducesUndef)`;
- fail if stack-protector preflight is nonempty, its pass-trace
  `mutatesIR` is true, or the residual protection inventory is nonempty;
- bind every timing-risk lint to the exact target, selector, latency table, and
  timing-environment contract;
- emit complete multi-site Spectre-PHT records and keep PHT and BTI mitigation
  dispositions separate;
- inventory every final linked conditional control transfer in a
  `BackendControlDeltaRecord` without treating the record as a model proof;
- emit and validate every required admission, High-variation, and
  release-activation query row;
- independently validate the full ABI-root/output schedules and discharge
  `OutputClosure` for every entry;
- validate the by-construction total single-valued contract output-expression
  vector and discharge coupling fiber totality without inserting coupling
  into High-variation queries;
- independently recompute stable IDs, `ExpandV2`, every cloned/remainder/
  terminal transition node, every output event rule owned by such a
  transition, and the exact longest-path horizon;
- rebuild every proof query through `BuildPONF_v2`, verify its canonical PONF
  digest, reproduce the deterministic PONF-to-SMT lowering, and verify that
  the bytes passed to the solver have the recorded `exact_formula_digest`;
- distinguish scheduled nonconformant preflight evidence from a conformant
  restricted falsifier candidate, publish no candidate-level row, and require
  `ReplayCovered` before reporting the one final counterexample receipt;
- prevent public reports/results from containing raw or content-hashed models,
  states, choices, memory, traces, witnesses, paths, lengths, or capabilities;
  store them only in `RestrictedEvidenceBundleV2` and expose only a random
  `ProtectedEvidenceReferenceV2`;
- aggregate a replay-covered counterexample before independent `Unknown`
  blockers, and `Unknown` blockers before `Proved`;
- verify release wrapper count and ABI before analysis-time inlining;
- preserve source locations only as diagnostics, never as identity;
- retain every `Unknown` reason through report aggregation; and
- isolate every single-invocation entry/product query in fresh verifier state.
  A request for an adaptive-sequence harness returns
  `Unknown(PersistentInvariantEncodingUnsupported)`; a future
  incorporated profile must reset transient query state while carrying exactly
  the declared persistent state and release ledger under its checked
  invariant.

## 14.4 TCB statement

Unless separately verified, the profile TCB includes:

- pinned LLVM parser, verifier, bitcode reader/writer, and target pipeline;
- the SPS patch and pass-trace hook;
- both normalizer passes;
- the normal-form auditor and generated semantics table;
- the frozen-byte replay driver;
- ABI, contract, and canonical `SPS-ReleaseTable-v2` decoders, including
  `SPS-PolicyExpr-NF-v2` typing/evaluation and release-carrier binding;
- stable-ID construction, `ExpandV2`/horizon, closed scalar/call/loop/memory/
  output/definedness transition dispatch, deterministic contract checking, and
  prefix-fiber coupling;
- structural-allocation, alias-topology, observation-production, and
  coverage-query encodings;
- `BuildPONF_v2`, the `SPS-PONF-v2` canonicalizer, deterministic
  `LowerPONFToSMT_v2`, canonical SMT-LIB serialization, and the solver; and
- witness replay, restricted evidence storage/access enforcement,
  content-independent receipt generation, conformance audit-record, and report
  aggregation.

Testing or Alive2 evidence reduces risk but does not remove a component from the
TCB without an explicit normative validation argument.

---

# 15. Acceptance cases

These cases are normative conformance tests. Each fixture records $I$, $B$, the
pass trace, normalizer trace, audit inventory, and expected result.

## `NF-A01` — Exact byte replay to core ISel

A scalar module is normalized, serialized, reparsed, audited, and passed
directly to the selected core ISel. Both parses reserialize to the same hash and
the pass trace has no post-capture IR mutator.

**Expected:** `NFConforms(T,I)` may hold.

## `NF-A02` — Closed scalar arithmetic surface

The module contains flag-free modulo integer arithmetic, checked division and
shift operands. Floating-point values occur only in bit-preserving movement,
same-width bitcasts, `fneg`, and `fcmp`; the frozen closure contains no FP
arithmetic, width conversion, or FP/integer numeric conversion.

**Expected:** accepted when all admitted executions satisfy definedness and
the exhaustive transition-rule audit, including the syntactic
`NoAmbiguousNaNResult_e(T)` gate, succeeds for every claimed entry.

## `NF-A03` — Safe annotation weakening

An optimized module contains `add nsw`, `getelementptr inbounds`, range
metadata, and an optimization-only `nonnull` fact. The actual final module has
the permitted annotations removed, passes the verifier, and is the module
hashed and selected.

**Expected:** accepted; earlier optimizer effects remain part of $T$.

## `NF-A04` — Proven-safe `freeze` erasure

`freeze` consumes a dominating scalar value proved non-undef and non-poison
after all assumptions and annotations are removed.

**Expected:** the normalizer records the rewrite, erases `freeze`, and the
residual audit accepts the module.

## `NF-A05` — Complete fixed-vector scalarization

A private `<4 x i32>` lane-wise computation has no ABI/global escape. Every
lane, PHI, select, and constant shuffle is converted to scalar SSA and no vector
type remains.

**Expected:** accepted if the residual inventory contains zero vector items.

## `NF-A06` — Masked memory to guarded lanes

A fixed contiguous masked load and store are lowered to per-lane CFG. Inactive
load lanes take passthrough values and perform no access. Lane alignments use
`commonAlignment`.

**Expected:** accepted; introduced branch/address events remain visible to
analysis and may still lead to `Counterexample` or `Unknown`.

## `NF-A07` — Closed direct-call analysis inlining

An acyclic internal helper with scalar/pointer ABI is called directly. The
analysis expands it without mutating $T$, preserves memory and events, and stays
within `K_call` and `K_paths`.

**Expected:** accepted.

## `NF-A08` — Outlined release wrapper equivalence

A manifest release wrapper is a direct, occurrence-preserved call with
`noinline`, `"nooutline"`, `noduplicate`, `nomerge`, and `nobuiltin`. P1 finds
the exact count and ABI-role schema. Its body is expanded like an internal
helper, so every ordinary branch/memory/call/latency effect remains in the
product. Exactly one side-effect-free marker call is named by
`emitMarkerInstructionId`; expansion replaces only that marker, at its exact
incoming/outgoing CFG position, with `ReleaseBoundaryV2`. The sole normative
specification discharges the local expression/guard equivalence without
summarizing the wrapper body.

**Expected:** carrier accepted; final `ModelStatus` remains owned by the
normative release rules.

## `NF-A09` — Exhausted bounded loop

A natural loop is mapped by `loop_bound_ids[L]` to public `BoundId b`, whose
maximum admitted value is 16. `K_loop[L]` is independently set large enough to
encode the boundary transition. The original guards appear in every expansion
copy, and the backedge at the exact public bound is proved infeasible for every
admitted input.

**Expected:** `BoundExhausted(loopSite(L),b)` is encoded but proved unreachable;
the loop may contribute to `Proved`. The value of `K_loop[L]` supplies no
semantic premise.

## `NF-A10` — Whole-region initialization at exit

A bounded loop writes every byte of an output region once. The exit
postdominates all writes, no early exit or trap bypasses a byte, and the finite
exact per-byte initialization predicate is proved. Any optional diagnostic
last-writer record agrees with the exact trace.

**Expected:** the universal all-byte initialization and definedness obligations
may be discharged at the exit. Exact byte memory remains authoritative; no
abstract initialization fact or dependency replacement substitutes for it.

## `NF-A11` — Eligible lockstep product

For a paired branch and bounded loop, the audit-all product encodes branch,
latch, exit, definedness, and termination/fault equality as bad-state checks;
all are proved unreachable under the exact relational assumptions.

**Expected:** `ProductSafe_A` may hold. The product is not optional.

## `NF-A12` — Contracted external call

A direct external call has a hash-bound contract covering ABI, reads, writes,
initialization, events, termination, faults, and deployment identity.

**Expected:** accepted with any ideal-mechanism assumption propagated to P4.

## `NF-A13` — Layout-independent pointer equality

Two flag-free GEP expressions from the same live ABI root are compared with
`icmp eq`. Exact lowering produces byte-identical canonical `AllocationKey`
term trees and two canonical modular `OffsetKey` terms.

**Expected:** the auditor records the two world-public term digests and
`SameCanonicalAllocationKeyV2`; conformance independently reproduces
byte-identical allocation-key trees, and the result is the literal equality
of the two offset terms. A semantically proved-but-nonidentical allocation-key
pair is rejected.

## `NF-A14` — Versioned unreachable cleanup

A CFG-unreachable block contains a literal poison and an unsupported `freeze`.
`SPSFinalDeadCleanup_v2` removes the block by its pinned entry-reachability and
PHI-repair rule before the final audit.

**Expected:** the removal and original sites appear in refusal telemetry and
the residual audit may accept. A companion CFG-reachable block remains and
causes the applicable `Unknown` result even if a later semantic query could
show its guard infeasible.

## `NF-A15` — Target-bound timing-risk lint

For one derived coalition, an accepted division has a diagnostically `High`
operand and a scalar `select` has a diagnostically `High` condition.

**Expected:** both target-bound `TimingRiskLintRecord` variants are emitted.
They do not change `NFConforms` or `ModelStatus`; deployment remains
`Open(P4EvidenceProfileUnavailable)` until the required paired P4 evidence
profile is implemented and validated.

## 15.1 Required issue-closure fixture matrix

These fixtures supplement, and do not renumber, `NF-A01`–`NF-A15`:

| Fixture | Construction | Required disposition |
|---|---|---|
| `NF-FX-ALLOCA-FIXED` | A fixed `alloca` maps to a literal expression equal to its exact `DataLayout` byte size. | Continue; emit a validated alloca-size record. |
| `NF-FX-ALLOCA-PUBLIC` | A runtime count is world-visible, its checked actual byte product equals the bound expression on every admitted state, and `K_bytes` is sufficient. | Continue; both `LowEq` lanes have equal exact object sizes. |
| `NF-FX-ALLOCA-HIGH` | A coalition-`High` count selects the actual size, even though both sizes are below one public cap. | `Unknown(AllocaSizeNotWorldStructural)`. |
| `NF-FX-ALLOCA-OVERFLOW` | The element-count product can overflow or its exact fit/equality proof is unresolved. | `Unknown(AllocaSizeNotWorldStructural)`; never wrap or cap the object. |
| `NF-FX-ALLOCA-PROBE` | An otherwise accepted public size crosses a target stack-probe threshold and the final binary gains probe control. | LLVM `ModelStatus` unchanged; emit timing and control-delta records; deployment remains `Open(P4EvidenceProfileUnavailable)` until the required evidence profile validates closure. |
| `NF-FX-ADDR-EXACT` | Two memory sites use stable allocation classes and distinct exact byte offsets. | Continue and keep the offsets distinct in every product event. |
| `NF-FX-ADDR-COARSE` | Configuration requests cache-line, page, or arbitrary bucketed address classes. | `Unknown(UnsupportedAddressObservationProfile)`. |
| `NF-FX-FP-PRESERVE` | Existing NaN bit patterns flow only through `fneg`, scalar bitcast, `phi`/`select`, load/store, and deterministic `fcmp`. | Continue with exact bits; no canonicalization. |
| `NF-FX-FP-NONNAN` | A residual FP-arithmetic/conversion result is proved non-NaN. | `Unknown(PONFFPArithmeticUnsupported)` at residual audit; no reachability escape hatch. |
| `NF-FX-FP-UNIQUE` | A target rule purports to select exact FP-arithmetic result bits. | `Unknown(PONFFPArithmeticUnsupported)`; the bound FP rule table remains canonical empty. |
| `NF-FX-FP-AMBIGUOUS` | Residual `fadd`, `fsub`, `fmul`, `fdiv`, `frem`, `fptrunc`, or `fpext`. | `Unknown(PONFFPArithmeticUnsupported)` before relational construction. |
| `NF-FX-ALIAS-PUBLIC` | The singleton topology partitions roots into exact full-object base-zero alias classes with identical metadata; other classes are disjoint. | Continue; both lanes must equal that one fixed partition and PONF emits one object row per class. |
| `NF-FX-ALIAS-VARIABLE` | A second topology, partial overlap, nonzero relative base, or lane-varying `MayAlias` realization is requested. | `Unknown(AliasBindingMismatch)` before PONF construction. |
| `NF-FX-COVER-ADMISSION` | Complete authored entry constraints are contradictory. | `Unknown(VacuousAdmission)`. |
| `NF-FX-COVER-PAIR` | A validated admitted state is duplicated, but the implementation's `LowEq^0` encoding rejects its reflexive diagonal. | `Unknown(ToolInconsistency)`; there is no separate pair-domain query or vacuity reason. |
| `NF-FX-COVER-HIGH` | A High component is constrained constant, first without and then with a hash-bound expected-variable assertion. | First report `ConstrainedOrUnexercised` and continue; second return `Unknown(ExpectedHighVariationAbsent)`. |
| `NF-FX-COVER-RELEASE` | Exercise `RequiredReachable`, proved `Dormant`, and contradicted/unresolved activation claims at one exact bound site. | Respectively validated activation and continue, dormant report and continue, and `Unknown(ReleaseActivationMismatch)`. |
| `NF-FX-FALSIFIER-PRIORITY` | Audit-all times out, but a directed or sampled admitted pair exactly replays to `Bad_A`. | `Counterexample(receiptId)` regardless of discovery source. |
| `NF-FX-PREFLIGHT-ONLY` | Nonconformant IR produces an apparent best-effort leak without complete exact semantics. | Retain the profile `Unknown`, store the finding only in the fixed scheduled restricted bundle, and publish the same task-static summary shape as a no-finding run; never promote it to a normative counterexample. |
| `NF-FX-SPECTRE-PHT` | An attacker-influenced index crosses a conditional bounds-check path to a transient address-dependent High-region load. | Emit the full multi-site record; `ModelStatus` unchanged and paired P4 open absent applicable mitigation evidence. |
| `NF-FX-SPECTRE-BTI-ONLY` | Only retpoline or IBRS evidence is offered for the conditional-branch PHT fixture. | PHT disposition remains `Open`; BTI evidence cannot close it. |
| `NF-FX-BACKEND-CONTROL` | The final binary has an unmatched conditional transfer, then a companion has a mapped public stack-probe transfer. | Both receive control-delta records; the first leaves P4 open, and the second closes only through ordinary paired predicate/event/observation evidence. |
| `NF-FX-OUTPUT-RETURN` | An entry returns one High bit through its ABI result. | The mandatory terminal `Output` differs and exact replay is `Counterexample(receiptId)`. |
| `NF-FX-OUTPUT-WRITEBACK` | An entry writes one High byte through an ABI pointer and returns normally. | The mandatory full-root terminal `Output` differs and exact replay is a counterexample. |
| `NF-FX-OUTPUT-OMIT` | A return bit or ABI-root byte is omitted or covered twice. | `Unknown(OutputBindingIncomplete)` or `Unknown(OutputBindingOverlap)` before audit-all. |
| `NF-FX-OUTPUT-UNINIT` | A terminal full-root output byte can be uninitialized. | `Unknown(UninitializedOutputByte)`; never invent a byte. |
| `NF-FX-BITENC-NONBYTE` | Scalar values `i1 1` and `i12 0xabc` are encoded as terminal/error payloads in both declared byte orders; a raw root slice contains bytes `12 34`. | Golden `EncodeBitsV2` bytes are respectively `01`, little-endian `bc 0a`, and big-endian `0a bc`; the root remains `12 34`. Decoding reproduces the exact LSB-numbered source bits. |
| `NF-FX-BITENC-PADDING` | An `i12` encoding has a nonzero high nibble in its most-significant significance byte, or puts the partial byte at the wrong serialized end. | Binding/canonical decoding fails closed with `Unknown(OutputBindingIncomplete)` or `Unknown(ManifestMismatch)`; padding is never observed as a source bit. |
| `NF-FX-EVENT-SUCCESSOR-DOMAIN` | A cloned branch selects two loop/call-expanded destinations that originate from the same source block ID. | Golden event fields use the distinct destination `ExpandedProgramLocationDomainV2` tags; a raw block ID or unrefined BV is `Unknown(ToolInconsistency)`. |
| `NF-FX-EVENT-FIELD-SCHEMA` | The complete positive event corpus exercises every `EventFieldKindV2`; mutations remove a field, add an inapplicable field, change its sort/domain, leave an inactive value unconstrained, or use an out-of-range byte/path. | Only the exact `EventFieldSchemaV2` table reproduces; every mutation is `Unknown(ToolInconsistency)`. |
| `NF-FX-BAD-CIRCUIT` | A High bit selects two branch successors and, independently, one High return bit reaches a terminal `Output`. A third case executes an authorized-equal release and then a visible High output. Controls reproduce all counterexamples. Mutations replace `CurrentControlV2` or `NextControlV2` with pre-PC equality/false, replace the output-byte comparison with false, omit/reorder one `BadViolationSourceRowV2`, change a visibility guard, use location visibility to retire, omit `AuditAll` marker-Seen state, conflate `potentialSlotOrdinal` with emitted `WithinStepOrdinal`, or emit overlapping `NonReleasePreserve` and append ledger equations. | The correct construction and exact replay reach the applicable first bad row, including the post-equal-release output. Every circuit/source/slot/ledger mutation disagrees with the independent byte-for-byte reconstruction and is `Unknown(ToolInconsistency)` before solving; it can never prune the release path or yield `Discharged`. |
| `NF-FX-REPLAY-WIRE` | Start from one valid safety witness, one unary violation witness, and one static existential witness. Mutations omit/add/duplicate/widen a model value, request an array/intermediate symbol, insert an unconsumed future choice into `ReplayWitnessV2.consumedChoices`, select the wrong trace-body variant/unit/bad row, alter an intermediate event/state, append a suffix, or mismatch witness/trace digests. | Only the exact `ModelExtractionPlanV2`, typed query-specific `ReplayWitnessV2`, and recomputed `ReplayTraceV2` validate. Every mutation is `Unknown(ToolInconsistency)` and no malformed safety candidate becomes a counterexample or proof result. |
| `NF-FX-OUTPUT-CONTRACT-CONTEXT` | One contract has two metadata event ordinals and failure-slot outputs for outcomes `Success`, `f1`, and `f2`; all executions are compared with golden source rows and event bytes. | There is one transition count/no-unexpected pair. Each metadata family has a distinct boundary/event-ordinal/slot context; `Success` activates no failure-output family, and `f1` or `f2` activates only its matching failure-slot family. |
| `NF-FX-OUTPUT-CONTEXT-DUPLICATE` | A source table repeats a canonical transition-output row or one context-specific row. | `Unknown(ToolInconsistency)`; byte-identical source rows are forbidden rather than folded. |
| `NF-FX-ERROR-OMIT`, `NF-FX-ERROR-ID`, `NF-FX-ERROR-PAYLOAD` | An application, contract, or verifier error is respectively omitted/reordered, given the wrong field/class, or sampled with the wrong encoding/initialization/payload. | `Unknown(OutputClosureMismatch)` or `Unknown(UninitializedOutputByte)` from independent, context-guarded `ErrorSourceV2` rows; an output schedule cannot cover the error. |
| `NF-FX-ERROR-CONTRACT-CONTEXT` | One contract has outcomes `Success`, `f1`, and `f2`; all three executions are checked against golden source rows and event bytes. | There is one transition count/no-unexpected pair. `Success` selects the empty expected sequence, while `f1` and `f2` activate only their distinct `ContractFailureErrorContextV2(boundaryId,failureId)` row families and exact bound error. |
| `NF-FX-ERROR-VERIFIER-CONTEXT` | One partial instruction has several possible verifier-UB predicate/reason rows. | Only the section-21.3 first-false `VerifierUBErrorContextV2(predicate,reasonClass)` family is active; all later and successful contexts are inactive, and the transition-level sequence still forbids extra errors. |
| `NF-FX-ERROR-CONTEXT-DUPLICATE` | A source table repeats a canonical transition row or one context-specific row. | `Unknown(ToolInconsistency)`; byte-identical source rows are forbidden rather than folded. |
| `NF-FX-COUPLING-HIGH-FILTER` | A coupling attempts `highLeft == highRight` or references input/state/result/effect data. | Schema rejection or `Unknown(CouplingFiberCoverageFailure)`; admission/diagonal and High-variation checks remain unfiltered. |
| `NF-FX-COUPLING-PREFIX` | A timing relation has a partner at the first occurrence but none at a reachable second occurrence. | `Unknown(CouplingFiberCoverageFailure)`. |
| `NF-FX-CONTRACT-PARTIAL` | One typed contract input has no functional row, or one input has two unequal result/effect rows. | `Unknown(MechanismNondeterminismUnsupported)`. |
| `NF-FX-CONTRACT-POINTER` | An external returns/writes a pointer or creates/frees an allocation. | `Unknown(ContractAllocationUnsupported)`. |
| `NF-FX-MEM-I1-LOAD` | Frozen IR contains `load i1`. | `Unknown(UnsupportedType)` before PONF; no byte is truncated. |
| `NF-FX-MEM-I1-STORE` | Frozen IR contains `store i1`. | `Unknown(UnsupportedType)` before PONF; no padding convention is invented. |
| `NF-FX-ZEXT-NNEG` | Frozen IR contains `zext nneg`. | `Unknown(UnclassifiedAnnotation)` or `Unknown(NormalizerMismatch)` before transition dispatch. |
| `NF-FX-ICMP-SAMESIGN` | Frozen IR contains `icmp samesign`. | `Unknown(UnclassifiedAnnotation)` or `Unknown(NormalizerMismatch)` before transition dispatch. |
| `NF-FX-INTRINSIC-RESIDUAL` | A frozen module contains a memory, trap, or ubsantrap intrinsic. | `Unknown(PONFIntrinsicUnsupported)`. |
| `NF-FX-LOOP-CANONICAL` | A one-block loop with one preheader, self-backedge, dedicated exit, and two-input header PHIs is expanded at public bounds zero and positive. | Golden `ExpandedCFGTableV2` bytes contain the exact complementary entry/copy/remainder guards, cloned exits, PHIs, remainder, and horizon. |
| `NF-FX-LOOP-SSA-MIXED` | One ordinary `H` instruction and one backedge/exit PHI mix an entry argument, a `P`-defined invariant, and `H`-defined local values. | Golden bytes keep both invariant references at the enclosing path and give only the local definitions the exact copy's `LoopFrameV2`; every resolved definition uniquely dominates its use or source edge. |
| `NF-FX-LOOP-LCSSA-LIVEOUT` | An `H`-defined value leaves the loop solely through a leading PHI in `X`, whose result is then returned; golden expansions cover positive and zero `boundMaximum`. | At positive bounds every cloned `H^k->X` edge writes the one declared `X` field from copy `k`. At zero there are no such assignments, but the unreachable retained PHI field still exists with its canonical zero initial value. |
| `NF-FX-LOOP-DIRECT-LIVEOUT` | An ordinary instruction or return in `X` directly uses an `H`-defined value rather than the leading `X` PHI result. | `Unknown(HorizonDerivationUnsupported)` before expansion; no loop-copy definition is guessed. |
| `NF-FX-LOOP-MULTILATCH`, `NF-FX-LOOP-MULTIEXIT`, `NF-FX-LOOP-NESTED`, `NF-FX-LOOP-CALL` | Frozen IR contains respectively multiple latches, multiple exits, nesting, or a call in the loop block. | `Unknown(HorizonDerivationUnsupported)` before expansion. |
| `NF-FX-HORIZON-OMIT` | A cloned call, final loop copy, remainder, output, or terminal unit is missing from expansion. | `Unknown(HorizonDerivationMismatch)`; never solve the truncated graph. |
| `NF-FX-HOST-TRANSFER` | Different secret bytes cross a transfer observed at a coalition-visible endpoint. | Project `Transfer.valueBytes`; exact replay is a counterexample. |
| `NF-FX-HOST-RELEASE` | A release is visible at a coalition host but that coalition is not its audience. | Project and compare the value; inequality is a counterexample and never retires the ledger. |
| `NF-FX-PUBLIC-EVIDENCE` | A `CompletedV2` result would embed or hash a raw model/witness, expose its path, length, or capability, or use candidate size to select a resource result. A companion proof configuration sets `maxEvidenceBytesPerBundle-8` below `MaxCanonicalRequiredEvidenceBytesV2`. | Public secret-bearing evidence causes `ReportingFailedV2` with no `ModelStatus`; only a random protected-evidence receipt is public. The underprovisioned companion is exactly `ConfigurationRejectedV2(InsufficientEvidenceCapacity)` before candidate work. Optional raw transcript/model diagnostics may become `None` without changing a verdict; mandatory witness/trace size never selects a public resource reason. |

## 15.2 Executable reference subset

`SPS/reference/fixture-catalog.json` is the exact machine-checked catalog for
the namespaced executable reference subset. At this revision it contains 19
cases spanning 10 of the 61 `NF-FX-*` families. The runner

```text
python3 SPS/reference/run_reference_checks.py
```

rejects fixture deletion/addition/header drift, malformed identity fields,
post-compilation program mutation, incomplete model-input extraction,
Low-inequal or wrong-domain replay, missing termination, unsupported partial
release footprints, bad-circuit mutation, and symbolic/concrete trace
disagreement. The reference PONF binds canonical program, coalition,
expanded-CFG, and exact-SMT digests and is strictly reparsed into SMT; that
lowering must byte-equal the independently constructed product lowering.
Every noninterference case compares deterministic Z3 lowering and symbolic
finite-domain evaluation with a separately interpreted exhaustive product;
SAT witnesses from each backend undergo exact replay. CVC5 is checked when
installed and otherwise remains explicitly open.

All artifacts use `SPS-Reference-*` identifiers. This subset is regression
evidence only: it neither implements `SPS-LLVM-NF-v2` nor emits normative
`SPS-PONF-v2`, cannot report `ModelStatus: Proved`, and does not close any
unimplemented family, LLVM-semantics differential obligation, second-solver
obligation, proof mechanization, or P4 deployment premise.

---

# 16. Required countermodels

Each countermodel prevents a tempting but unsound implementation.

## `NF-CM01` — Post-freeze IR mutation

The module is hashed before StackProtector or another late IR pass, while the
mutated output proceeds to ISel.

**Required result:** `Unknown(PipelineMismatch)`; never `Proved`.

## `NF-CM02` — Residual target-legal masked/vector operation

The stock masked-memory scalarizer leaves an intrinsic because the target
supports it, or the stock scalarizer leaves a vector operation it cannot split.

**Required result:** `Unknown(ResidualVector)`. Running a scalarizer pass is not
evidence of closure.

## `NF-CM03` — ABI attribute stripped

The normalizer deletes `sret`, `byval`, `inreg`, `signext`, or another ABI
attribute to make the audit pass.

**Required result:** normalizer failure and
`Unknown(NormalizerMismatch)` or `Unknown(UnsupportedType)`.

## `NF-CM04` — `freeze` of undef unsafely erased

`freeze undef` feeds two uses whose equality depends on the fixed choice. The
implementation treats `freeze` as identity or replaces it with unconstrained
per-use values.

**Required result:** `Unknown(FreezeMayChoose)`.

## `NF-CM05` — Public-bound exhaustion discarded

A loop mapped to public bound `b` can take another backedge at $B_L$, but the
implementation drops that transition, treats `K_loop[L]` as the semantic
bound, or proves only a truncated program.

**Required result:** execute the exact `BoundExhausted(loopSite(L),b)` then
`BoundFailure` transition. A replayed lane mismatch is
`Counterexample(receiptId)`; an
aligned reachable exhaustion without a bad execution is
`Unknown(LoopRemainder)`. Never `Proved`.

## `NF-CM06` — Divergent controls forced into lockstep

Two admitted runs can choose different branches, but the implementation asserts
equal guards so that a lockstep product has one path.

**Required result:** after replay, `Counterexample(receiptId)`. Never
`Proved` and never a forced-alignment assumption.

## `NF-CM07` — `UBRisk` pair filtered away

Two admitted runs, before any retiring release, reach the same `udiv` site,
but only one has a zero divisor. The implementation discards that active pair
as immediate LLVM UB or replaces the invalid result with an unconstrained
value.

**Required result:** the invalid lane emits `UBRisk`, `Failure`, and the
applicable `Error`, then terminates with `UBFailure(reasonClass)`. Exact replay
reaches `Bad_A` and yields `Counterexample(receiptId)`.

A companion fixture in which both lanes reach the same aligned `UBRisk` must
return `Unknown(PossibleUB)`, never `Proved`, because universal definedness
fails even though the paired event is equal.

A separate out-of-range-shift fixture MUST return
`Unknown(PoisonSemanticsUnsupported)` in both asymmetric and aligned cases,
emit no `UBRisk`/failure/termination event for the shift, and never use poison
production itself as a counterexample.

## `NF-CM08` — Diagnostic initialization summary used as semantics

A diagnostic whole-region fact says an output is initialized, but one feasible
exact path skips a byte. The implementation discards exact byte state or uses
the diagnostic fact to suppress the uninitialized read.

**Required result:** `Unknown(InvalidDiagnosticShortcut)` for the
nonconforming implementation. With exact semantics, a reachable otherwise
valid read of the unwritten byte produces
`Unknown(UninitializedLoadProducesUndef)`. It emits no `UBRisk` and is not a
replayable counterexample merely because LLVM returns `undef`.

## `NF-CM09` — ABI separation inferred from LLVM

Two distinct pointer arguments have different SSA names or residual optimizer
facts and their normative ABI clause is `MayAlias`, but the required singleton
topology is missing or does not place them in distinct classes. The
implementation nevertheless assigns them distinct allocation identities.

**Required result:** `Unknown(AliasBindingMismatch)`; no proof may use the
inferred separation.

## `NF-CM10` — Adjacent-allocation pointer equality guessed false

The program compares the one-past pointer of object $a$ with the base pointer
of distinct object $b$. The ABI and target constraints permit both an adjacent
placement, where the address bits are equal, and a nonadjacent placement, where
they differ. An implementation reduces the comparison to $a\ne b$.

**Required result:** `Unknown(LayoutDependentPointerComparison)`; never
`UBRisk`, `Counterexample`, or a guessed false result.

## `NF-CM11` — Null compared with a wrapping GEP

A flag-free GEP from a non-null root is compared with null. Exact modular
`DataLayout` arithmetic permits the derived address to wrap to the null address
for some admissible base placements but not others. An implementation assumes
that a non-null root makes the comparison false.

**Required result:** `Unknown(LayoutDependentPointerComparison)`. Comparison
with null is not a layout-independence shortcut.

## `NF-CM12` — Stack-protector semantics enter the frozen artifact

One fixture carries `sspstrong` before the pinned code-generation pipeline. A
companion fault-injection fixture starts with zero stack-protector attributes
but records a `StackProtector` mutation or leaves a pass-attributed guard,
volatile access, failure edge/call, or residual intrinsic.

**Required result:** `Unknown(UnsupportedStackProtector)` at preflight or the
post-pass residual check. The pass remains present in the recorded pipeline,
and its effects are never accepted as unclassified ordinary IR.

---

# 17. Conformance test suite

The implementation MUST provide:

1. one positive and one negative fixture for every accepted/rejected type,
   opcode, intrinsic, flag, attribute class, metadata class, and module feature;
2. every `NF-A01`–`NF-A15` acceptance case;
3. every `NF-CM01`–`NF-CM12` countermodel;
4. target matrices for every enabled target triple/CPU/feature set;
5. SelectionDAG and GlobalISel tests only when that selector is independently
   declared in $I$;
6. mutation-after-capture fault injection;
7. bitcode hash/reparse reproducibility tests;
8. fuzzed residual-IR inventory tests that require total enum classification;
9. differential normalizer tests, including Alive2 where applicable;
10. loop tests with public bounds at 0, 1, and the admitted maximum, engine caps
    below/equal/above that maximum, and a feasible backedge at $B_L$;
11. memory tests for zero length, one-past pointers, alignment, overlap,
    uninitialized-byte propagation through `memcpy`/`memmove`, early exits, and
    last writers, including proof that an uninitialized scalar load never
    becomes `UBRisk` or a counterexample by itself;
12. asymmetric and symmetric `UBRisk` event/replay tests;
13. normative/profile identity mapping, placement-digest, and loop-bound-binding
    mismatch tests;
14. same-object, adjacent-allocation, distinct-allocation, null, and wrapping-GEP
    pointer-comparison matrices, including comparisons outside an object's live
    interval, at every supported pointer/index-width pair;
15. zero/nonzero stack-protector preflight and pass-mutation fault injection;
16. freeze relocation, dead/unreachable cleanup, residual undef/poison, and
    stack-protector refusal telemetry checks;
17. per-target High-operand division/remainder and High-condition `select`
    timing-lint matrices;
18. diagnostic tests distinguishing ordinary `RelationalRequired` imprecision,
    `DiagnosticHealthFailure`, and exact/diagnostic `ToolInconsistency`; and
19. report tests proving that no `Unknown` reason is lost;
20. every `NF-FX-*` issue-closure fixture in Section 15.1;
21. fixed/public/High/overflowing alloca-size matrices at every supported
    pointer-index width, plus target stack-probe-threshold companions;
22. exact-address tests proving that adjacent byte offsets remain distinct and
    that every attempted line/page/bucket configuration fails closed;
23. per-FP-op matrices for existing quiet/signaling NaN bit preservation and
    unconditional rejection of every residual FP arithmetic/numeric-conversion
    opcode;
24. singleton fixed alias-partition matrices covering valid disjoint and
    full-object same-allocation classes, plus rejection of multiple, variable,
    nonzero-base, and partial-overlap topologies;
25. admission, diagonal-consistency, every-High-component, and every-release activation
    query/report matrices, including invalid SAT witnesses and solver UNKNOWN;
26. witness-source metamorphic tests showing that identical replay-covered SMT,
    directed, random, differential, and manual candidates receive the same
    result, while nonconformant preflight findings do not;
27. multi-site Spectre-PHT tests separating PHT from BTI disposition, and
    final-linked conditional-transfer inventories covering selector,
    legalization, stack-probe, instrumentation, veneer, and linker additions;
28. canonical `SPS-PolicyExpr-NF-v2` release-table parsing, typing,
    serialization, and carrier-binding fixtures, including noncanonical,
    ill-typed, wrong-`SemanticsVersion`, and LLVM-metadata-only cases;
29. repeated and cross-process `BuildPONF_v2`/`LowerPONFToSMT_v2`
    determinism fixtures, plus one-field mutation tests showing that the PONF
    and exact-formula digests bind allocation, coupling, ledger, query, and
    lowering-version changes; and
30. P4 evidence tests showing that statistical testing alone cannot mark a
    backend record covered and that a bounded binary relational result without
    the exact coalition observation mapping remains `EvidenceRequired`.

Release of a new compiler binary requires the complete suite, regeneration of
the semantics-table hash, and a per-target aggregate telemetry report for
`CanonicalizeFreezeInLoops`, freeze refusal, removed/residual dead
undef/poison, stack-protector preflight/pass effects, pointer-layout refusal,
alloca-size/alias/FP refusal, exact-address-mode validation, coverage-query
dispositions, Spectre-PHT lints, and final-machine control deltas. The report
measures availability; it supplies no
security premise and creates no acceptance threshold implicitly.

---

# 18. Normative and authoritative dependencies

## 18.1 Sole SPS normative dependency

This profile is incorporated by:

- `SPS/SPS_Rev4_Normative_Specification.md`

through the predicate:

$$
\operatorname{NFConforms}(T,I).
$$

If terminology conflicts, the sole rev-4 normative specification controls
policy and theorem meaning, while this document controls the LLVM
`SPS-LLVM-NF-v2` conformance surface and exact artifact coordinate.

Other P0–P4 architecture, workflow, dataflow, and type-system documents are
explanatory only. They MUST NOT override the exact `FreezeCoordinate` in this
document.

## 18.2 LLVM 22.1.8 authoritative sources

- LLVM 22.1 Language Reference:  
  <https://releases.llvm.org/22.1.0/docs/LangRef.html>
- LLVM 22.1.8 pinned `LangRef.rst`:  
  <https://github.com/llvm/llvm-project/blob/llvmorg-22.1.8/llvm/docs/LangRef.rst>
- LLVM 22.1.8 `TargetPassConfig.cpp`:  
  <https://github.com/llvm/llvm-project/blob/llvmorg-22.1.8/llvm/lib/CodeGen/TargetPassConfig.cpp>
- LLVM 22.1.8 `StackProtector.cpp`:  
  <https://github.com/llvm/llvm-project/blob/llvmorg-22.1.8/llvm/lib/CodeGen/StackProtector.cpp>
- LLVM 22.1.8 `CanonicalizeFreezeInLoops.cpp`:  
  <https://github.com/llvm/llvm-project/blob/llvmorg-22.1.8/llvm/lib/Transforms/Utils/CanonicalizeFreezeInLoops.cpp>
- LLVM new pass-manager documentation, including the legacy codegen boundary:  
  <https://llvm.org/docs/NewPassManager.html>
- LLVM code generator documentation:  
  <https://llvm.org/docs/CodeGenerator.html>
- LLVM Scalarizer interface and its documented partial behavior:  
  <https://llvm.org/docs/doxygen/Scalarizer_8h_source.html>
- LLVM masked-memory scalarizer implementation:  
  <https://llvm.org/doxygen/ScalarizeMaskedMemIntrin_8cpp.html>
- LLVM value-tracking API, including
  `isGuaranteedNotToBeUndefOrPoison`:  
  <https://llvm.org/doxygen/ValueTracking_8h.html>
- LLVM 22.1.8 release announcement:  
  <https://discourse.llvm.org/t/llvm-22-1-8-released/91084>

## 18.3 Validation and product-program background

These are supporting research references, not replacements for the normative
profile:

- Alive2: <https://github.com/AliveToolkit/alive2>
- Alive2 PLDI 2021 publication page:  
  <https://web.ist.utl.pt/nuno.lopes/pubs.php?id=alive2-pldi21>
- ct-verif product-program paper:  
  <https://www.usenix.org/system/files/conference/usenixsecurity16/sec16_paper_almeida.pdf>

---

# 19. Profile summary

An implementation establishes `NFConforms(T,I)` only when:

```text
the toolchain and target are exact
the entire late-IR pass trace is exact
the last mutation is SPSFinalWeaken_v2
the verifier and exhaustive audit pass
the captured bytes replay directly into core ISel
every normative identity field, digest, placement, and proof setting is bound
the residual IR is entirely within the scalar closed world and has no prohibited flags
ABI attributes and carrier identities are preserved
freeze removal is justified after assumption removal
only versioned syntactic dead/unreachable cleanup precedes the final residual audit
stack-protector preflight is empty, PassTraceRowV2.mutatesIR is false, and residual checks are empty
all calls are direct/closed or exactly contracted
each loop is bound to a public BoundId and K_loop remains only an engine cap
each alloca maps uniquely to a typed world-structural byte expression and an exact equality obligation
the singleton fixed full-object alias partition is exactly bound; variable or partial topology is rejected
exact BoundExhausted/BoundFailure transitions are encoded; ModelStatus Proved separately requires BoundAdequate
exact byte memory remains authoritative and diagnostic ghost facts remain non-authoritative
memory observations use stable allocation class plus exact byte offset and width with no coarsening knob
ordinary diagnostic imprecision defers to the exact product while diagnostic health failures gate
every pointer equality has byte-identical canonical AllocationKey terms and uses exact OffsetKey equality
the residual prohibited-FP opcode inventory is empty and its bound rule table is the canonical empty object
uninitialized-load refusal and UBRisk transitions are exactly classified, not folded into NFConforms reachability
target-bound timing-risk lints remain non-authoritative and P4 evidence remains explicit
multi-site Spectre-PHT and final-machine control-delta records remain P4 evidence generators, not model proofs
control divergence reaches Bad_A and is never assumed away
ModelStatus Proved separately requires universal initialization, LLVM-definedness, bound adequacy, WorldStructuralAlloca, and NoAmbiguousNaNResult
admission, diagonal-consistency, High-variation, and release-activation reports are complete
only a conformant ReplayCovered witness is a counterexample, independent of discovery source
aggregation prioritizes replay-covered counterexamples, then Unknown blockers, then Proved
every unsupported, undecidable, or resource-exhausted case remains `Unknown`
```

That predicate is one premise of the sole SPS rev-4 normative security
specification. It is not, by itself, a confidentiality proof or a deployment
closure claim.

---

# 20. Release-intrinsic preservation and machine boundary

This section states the compiler-specific preservation and lowering
obligations for the release carrier defined in Section 4.4. The pinned LLVM
baseline is `llvmorg-22.1.8` plus the exactly identity-bound SPS patch tree
implementing these capabilities.

## 20.1 Intrinsic conformance

The sole release carrier is `llvm.sps.release`. It is a target-independent,
zero-result, variadic integer intrinsic with `IntrHasSideEffects`, `IntrNoMem`,
`IntrNoDuplicate`, and `IntrNoMerge`; it is non-speculatable. Its operands are
exactly the flattened release payload leaves. A release ID or any other
locator operand is forbidden. The `ReleaseImplementationBindingV2` sidecar
resolves `emitMarkerInstructionId` uniquely after canonical reparse.

The NFv2 auditor verifies that each occurrence survives every permitted
optimization, `SPSFinalWeaken_v2`, dead cleanup, bitcode write/read, and fresh
parse without deletion, merging, duplication, motion across an observable
program point, operand reordering, or binding drift. The normalizer cannot
infer the intrinsic's absence from `memory(none)` because compiler-side
retention is carried by `IntrHasSideEffects`.

## 20.2 MIR boundary

Core instruction selection lowers one conforming intrinsic to one
identity-bound `SPS_RELEASE` MIR pseudo with the same payload uses.
`ReleaseMarkerMachineMapV2` records the stable IR instruction, pseudo, and P4
capture boundary. The pseudo remains until that capture and is then erased.
MC emission must contain no marker bytes, call, external symbol, or relocation.
These facts establish carrier preservation and machine evidence provenance;
they do not establish paired P4 refinement.

## 20.3 Freeze and audit

`SPSFinalWeaken_v2` performs the weakening in Section 5 while preserving the
invariant that no operation may delete, merge, duplicate, speculate, or
reorder `llvm.sps.release`. The last
residual audit checks the intrinsic signature, payload leaves, unique stable
binding, and exact occurrence inventory. `SPSLLVMNFManifestV2` and
`ArtifactIdentityV2` bind the V2 weakener, intrinsic-definition patch,
release-table format, stable binding table, and machine-map format.

The binding is by exact named preimage, not by a version string or generic
digest bag. `ArtifactIdentityEvidenceV2` contains the canonical frozen bitcode
and one required, closed, named canonical envelope for every identity input.
In particular it contains policy, ABI, `SPS-ReleaseTable-v2`, contracts,
placement, timing, stable IR bindings, `ReleaseMarkerBindingArtifactV2`,
`ReleaseMarkerMachineMapV2`, `LLVMReleaseIntrinsicDefinitionV2`, the interface
manifest, `AggregationSemanticsV2`, and `ReplayAcceptanceSemanticsV2`. Every
digest is recomputed from its exact bytes; the evidence record contains neither
an open map nor a `(fieldId,bytes,digest)` extension list. The marker-binding
and machine-map instruction domains are equal and one-to-one.

`SPSLLVMNFManifestV2` carries the complete identity evidence closure and repeats
only fixed format identifiers and digests that are byte-equal to the nested
identity. `ProofConfigurationV2` binds both the exact
`SPS-Model-Aggregation-v2` and `SPS-Replay-Acceptance-v2` canonical semantics
digests. An obsolete release-table format, an omitted required preimage, or a
changed preimage paired with a stale digest is `XF-IDENTITY-001` failure and
cannot establish `NFConforms`.

The verifier derives `RequiredQueryScheduleV2` from the decoded typed policy,
ABI, V2 release table, contract table, entry-scope, and timing preimages.
`QueryScheduleDerivationV2`, `ArtifactIdentityV2`, and
`ProofConfigurationV2.requiredQuerySchedule` bind the same recomputed result;
matching authored schedule bytes and digests do not substitute for derivation.
Every named envelope also passes its closed artifact-specific payload validator;
arbitrary JSON or an unknown nested constructor is `XF-PAYLOAD-001` even when
canonical and self-hashed.

An absent, duplicate, malformed, ill-typed, stale, or wrongly bound intrinsic
maps to `ReleaseCarrierMismatch`. Only a structurally conforming occurrence can
reach `ReleaseConformanceUnknown` or the semantic release-bad replay rule.

## 20.4 Capability probes

Toolchain support is established by direct capability probes named
`sps-nfv2-intrinsic` and `sps-nfv2-codegen`, not by an LLVM version string.
Without the first, an implementation cannot claim NFv2. Without the second,
it cannot claim the NFv2 machine-boundary obligations. A test suite must report
such tests as unsupported rather than fabricating support through another
carrier.

## 20.5 Result binding

The profile's Rev4.1 adapter uses `SPSRunReportV2`, `AcceptedBadReplayV2`, the
ordered unique `BlockerRecordV2` list, and `AggregationDecisionV2`. The decision
carries `ArtifactIdentityEvidenceV2`; its selected replay query and completed
report's policy, release, and review-configuration digests MUST equal that
closure and its bound schedule. A
`RunFinalization` blocker is handled before an accepted replay; an accepted
replay plus a `ReplayInvalidating` blocker is rejected as inconsistent. Carrier
classification uses `ReleaseCarrierMismatch`,
`ReleaseConformanceUnknown` (or the applicable closed solver/resource reason),
or a replay-backed counterexample according to the closed taxonomy.
