# SPS Rev-4 executable reference slice

This directory contains a deliberately small, executable reference slice for
the highest-risk SPS Rev-4 confidentiality rules. It is not a conforming SPS
implementation and cannot emit `ModelStatus: Proved`.

The reference slice exists to make specification drift observable while the
full LLVM normalizer, `ExpandV2`, PONF builder, replay engine, proof
mechanization, and deployment-evidence profile are implemented. Its artifact
identifiers contain `Reference` so that no output can be confused with a
normative `SPS-PONF-v2` artifact.

## The tests-to-theory bridge

One relation fixture represents one local confidentiality claim. Read it in
three layers:

1. the fixture identifies the reduced High/Low inputs, admission predicate,
   observable event fields, and expected relational outcome;
2. `profiles/reference-relation-v1.json` defines the repeated reference
   construction and evaluation requirements once;
3. `SPS-Reference-Evidence-Result-v1` records witness-free evidence that those
   requirements ran.

These layers cite SPS theory but do not schedule normative SPS queries:

| Reference query | SPS concept cited | Exact reference meaning |
| --- | --- | --- |
| `ReferenceAdmissionNonempty` | `AdmissionNonempty` | Some finite one-lane input satisfies the authored admission predicate. |
| `ReferenceHighVariation(c)` | `HighVariation(c)` | Two admitted, Low-equal finite inputs differ in High input `c`. |
| `ReferenceTerminalOutputSurface` | `OutputClosure` | No admitted run violates the reduced return/terminal-ABI-root/termination schedule. This is a strict subset of normative `OutputClosure`. |
| `ReferenceAuditAll` | `AuditAll` | The reduced two-lane product has a public event difference. |

`analogueOf` and `requirementRefs` are citations, not
`PublicQueryScheduleV2` rows. Lowercase `sat`/`unsat` and runner `PASS`/`FAIL`
never imply `Discharged`, `ProductSafe`, `Counterexample`, or a `ModelStatus`.

The profile separates three kinds of evidence:

- query analogues establish non-vacuity, High variation, the reduced terminal
  surface, and the reduced relational outcome;
- artifact-integrity checks audit the reference PONF, compare direct and
  serialized lowering, repeat lowering, and bind the exact SMT input digest;
- evaluation backends require symbolic exhaustive, independent concrete
  exhaustive, and Z3 agreement. Available or explicitly configured CVC5 is
  also required to agree. Every SAT assignment is independently validated,
  and every `ReferenceAuditAll` SAT assignment is concretely replayed.

Implemented:

- canonical JSON and SHA-256 identity for reference artifacts;
- strict duplicate-free schemas and canonical program snapshots that reject
  post-compilation mutation;
- a typed finite bitvector expression language;
- a structured, bounded `SPS-Reference-Program-v3` IR with Low and High inputs,
  a required Boolean admission predicate, explicit branch-successor IDs,
  fixed-offset byte-aligned loads, exact terminal-output order, and
  initialized-byte tracking;
- an independently constructed symbolic terminal surface, independently
  interpreted concrete exhaustive validation, terminal return/explicit
  bound-exhaustion behavior, and ABI-root `Output` events;
- `Transfer.valueBytes` and location-visible `Release.valueBytes`;
- audience-authorized release retirement without location-based retirement;
- fixed-bound structured expansion with explicit remainder events;
- a query-parameterized canonical `SPS-Reference-PONF-v3` object bound to canonical program,
  coalition descriptor, expanded-CFG, and exact-SMT digests;
- deterministic QF_BV SMT-LIB lowering and complete extraction of every
  declared lane input, including formula-irrelevant High inputs;
- strict reparsing and lowering of the serialized PONF, checked byte-for-byte
  against lowering from the independently built product;
- field-by-field PONF auditing that does not call the PONF serializer under
  test;
- Z3 execution plus an independent exhaustive finite-domain backend;
- an independently interpreted exhaustive product for both SAT and UNSAT
  cases, plus concrete replay of every reported confidentiality witness;
- exact replay checks for same-program identity, complete witness domain,
  widths, Low equality, and the shared product support profile;
- an exact fixture catalog that makes deletion, addition, or header drift a
  test failure;
- explicit fail-closed status for unsupported profiles and unavailable tools.
- normalized solver timeout/launch/model-retrieval failures that cannot become
  a successful proof result.
- reproducibility, canonical-byte, schema, raw-negative, semantic-negative,
  and aggregation checks for the Rev4.1 machine interface package.

## Relation fixture v3

An external harness reduction uses this closed shape:

```json
{
  "formatId": "SPS-Executable-Reference-Fixture-v3",
  "familyId": "NF-FX-OUTPUT-RETURN",
  "caseId": "example",
  "kind": "relation",
  "requirementRefs": ["Normative 21.4"],
  "input": {
    "program": {
      "formatId": "SPS-Reference-Program-v3",
      "entryId": "entry",
      "entryHost": "entry",
      "observerProfile": "EventInterfaceOnly",
      "inputs": [],
      "abi": {
        "return": null,
        "roots": [],
        "terminalOutputOrder": []
      },
      "admission": {"bool": true},
      "statements": [
        {"op": "return", "site": "return", "value": null}
      ]
    },
    "coalition": {"id": "observer", "principals": [], "controlledHosts": []}
  },
  "expected": {
    "admissionNonempty": "sat",
    "highVariation": [],
    "terminalOutputSurface": "unsat",
    "auditAll": {"status": "unsat", "firstDifference": null}
  }
}
```

An `if` statement names both `thenSuccessor` and `elseSuccessor`. A load is
`{"load":{"root":"buffer","offset":4,"width":8,"byteOrder":"LittleEndian"}}`.
Widths are in bits and reference loads are currently byte aligned.

Program roots have exact fields `id`, `byteLength`, `host`, `terminalOutput`,
`outputId`, `initialBytes`, and `initialized`. A true `terminalOutput` root has
a non-null `outputId` and is emitted at its declared terminal-order position.
An internal allocation uses `terminalOutput: false` and `outputId: null`; it
supports stores and loads but never manufactures a terminal root output.
Initially uninitialized roots are allowed only when every byte consumed by or
emitted from every admitted terminal path becomes initialized.

`abi.terminalOutputOrder` is a required, duplicate-free exact cover of the
return output (when present) and every root with `terminalOutput: true`. Its
authored order is semantic: the reference emits those `Output` events in that
order and then emits `Termination`. A harness binding must preserve the full
ABI order rather than infer return-before-root or root-before-return.

## Harness reduction binding

`SPS-Harness-Reference-Reduction-Binding-v2` binds the reduction to exact
snapshot, C, MLIR, policy, ABI, and relation-fixture byte digests. Paths are
canonical POSIX paths relative to the containing harness case and may not
escape that directory. `harnessCase` has the exact form
`precision-control/<case>`.

The required `coalition` mapping binds the reference coalition ID, principals,
controlled hosts, and the selected policy adversary row. For the precision
fixtures, reference host `observer` maps to
`policyHost: null, boundaryClass: PublicObservationEndpoint`. This explicitly
means “the policy-public observation boundary”; it is not host identity with
the full program's `compute` host. Every controlled reference host must have
exactly one sorted mapping.

Argument mappings use an unambiguous numeric `argumentIndex` plus source-level
`argumentName`. Components, scalar argument indices, and scalar argument names
are unique. Root ABI identities, indices, and names are also unique, and root
and scalar ABI positions may not overlap. Root mappings have two
disjoint alternatives:

- `storageKind: ABIArgument` requires string `abiRoot`, numeric
  `argumentIndex`, string `argumentName`, a string policy `component`, null
  `allocationSite`, and a program root with `terminalOutput: true`;
- `storageKind: InternalAlloca` requires null `abiRoot`, `argumentIndex`, and
  `argumentName`, and `component`, plus a
  stable `allocationSite`, `initialClassification: Uninitialized`,
  `terminalVisibility: NotTerminalOutput`, and a program root with
  `terminalOutput: false`.

The reference validator checks the binding against the reduced fixture itself:
reduced widths and classifications agree, every root has the same byte length,
`offsets` exactly list the load/store start offsets used by the reduced program,
classified ABI inputs start fully initialized, and an `Uninitialized` internal
allocation starts wholly uninitialized. These are structural reduction checks.
The harness remains responsible for the cross-layer claims: that component and
root IDs really name the stated policy/ABI entities, that indices and signatures
match MLIR, that classifications and terminal visibility match the sidecars, and
that `abi.terminalOutputOrder` matches the full ABI. Supplying file paths lets
the reference validator verify bytes and hashes; digest strings alone do not
establish those cross-layer facts.

The closed observation vocabulary is `BranchSuccessor/successor` and
`Output/valueBytes`. Required limitations are
`ExecutableReferenceOnly`, `HandAuthoredReduction`, `NotFrozenLLVM`, and
`ReducedBitWidth`.

Binding v2 also has the required `counterexamplePair` field. An expected-safe
relation uses `null`. An expected-bad relation uses exactly
`{"path":"counterexample-pair.yaml","sha256":"..."}` and binds the raw bytes
of that fixed sibling. A selected pair cannot be supplied by digest alone:
generation and contextual endpoint validation both load, hash, materialize,
and independently replay it.

## `UnimplementedDraft`: pointer-rebinding interface successors

The interfaces in this section are design reservations, not executable
formats. They have status **`UnimplementedDraft`** and no normative claim
effect. Current closed validators accept only the versions documented above
and MUST reject every identifier below. No file may claim one of these
versions until its parser, canonicalizer, independent auditor, backends,
negative tests, and replay path are implemented together.

| Reserved interface | Status | Intended addition |
|---|---|---|
| `SPS-Executable-Reference-Fixture-v4` | `UnimplementedDraft` | pointer-rebinding relation expectations |
| `SPS-Reference-Program-v4` | `UnimplementedDraft` | exact alias partition, pointer-select address, and `Memory` events |
| `SPS-Harness-Reference-Reduction-Binding-v3` | `UnimplementedDraft` | exact full-ABI topology and artifact-shape binding |
| `SPS-Reference-Relation-v2` | `UnimplementedDraft` | `Memory/allocationClass` observation and agreement requirements |
| `SPS-Reference-PONF-v4` | `UnimplementedDraft` | finite pointer tuple and memory-event comparison terms |
| `SPS-Reference-Replay-v3` | `UnimplementedDraft` | independent selected-class replay |
| `SPS-Reference-Evidence-Result-v2` | `UnimplementedDraft` | witness-free memory first-difference result |

Version 3 fixtures, programs, PONF, version 2 bindings/replay, and version 1
profiles/results remain byte-for-byte legacy formats. There is no implicit
upgrade, mixed-version pairing, fallback parser, or alias for a reserved ID.

### Draft program and fixture shape

`SPS-Reference-Program-v4` retains the finite scalar expression and structured
statement vocabulary, but replaces root-only load expressions with one
event-producing scalar load statement:

```text
RootAddressV4 =
    StaticRootAddressV4 {
      tag: "StaticRoot", root: RootId, offset: natural
    }
  | SelectRootAddressV4 {
      tag: "SelectRoot",
      condition: BooleanExpressionV4,
      trueAddress:  {root: RootId, offset: natural},
      falseAddress: {root: RootId, offset: natural}
    }

LoadStatementV4 {
  op: "load",
  site: SiteId,
  target: fresh ScalarLocalId,
  address: RootAddressV4,
  width: positive byte-aligned bit width,
  byteOrder: "LittleEndian" | "BigEndian"
}
```

The statement produces a scalar local and exactly one `Memory(...,Read)`
event. A V4 scalar `store` likewise emits `Memory(...,Write)`. The draft adds
no pointer-valued local, pointer return, pointer load, or pointer store. Such
an operation remains outside the program grammar and maps to the harness
expectation `Unknown(UnsupportedType)` without a relation fixture or PONF.

The V4 ABI root fields are exactly the V3 root fields plus `permission` and
`addressSpace`. Its additional required topology member is:

```json
{
  "equivalenceClasses": [
    ["left"],
    ["private_result"],
    ["right"]
  ],
  "overlaps": []
}
```

Each class is a nonempty sorted unique root-ID list; classes are sorted by
their first ID. Their union is exactly the program root set. A root occurs
once, and `overlaps` is the literal empty list. Members of one class must have
identical byte length, host, permission, address space, initial bytes, and
initialized-bit vector. They denote one memory object initialized once, not
separate arrays constrained equal. Distinct classes denote disjoint objects.
Terminal-output identifiers remain subject to the existing exact output-order
rules and do not create another alias relation.

The supported pointer fixture body is represented without a control-flow
`if`:

```json
[
  {
    "op": "load",
    "site": "load.selected",
    "target": "loaded",
    "address": {
      "tag": "SelectRoot",
      "condition": {"var": "secret_selector"},
      "trueAddress": {"root": "right", "offset": 0},
      "falseAddress": {"root": "left", "offset": 0}
    },
    "width": 8,
    "byteOrder": "LittleEndian"
  },
  {
    "op": "store",
    "site": "store.result",
    "root": "private_result",
    "offset": 0,
    "value": {"var": "loaded"},
    "byteOrder": "LittleEndian"
  },
  {"op": "return", "site": "return", "value": null}
]
```

Both selected addresses must type-check to the load width and be in range.
The condition must be Boolean, both roots must exist, and the target must be
fresh. The selected pointer lowers fieldwise to one allocation-key `ite` and
one offset-key `ite`; no branch event is emitted. V4 event shape includes the
load and store `Memory` rows before the unchanged terminal schedule.

`SPS-Executable-Reference-Fixture-v4.expected.auditAll.firstDifference` admits
the new exact locator

```json
{
  "eventOrdinal": 0,
  "kind": "Memory",
  "field": "allocationClass",
  "site": "load.selected"
}
```

only when `auditAll.status` is `sat`. `unsat` requires `firstDifference:null`.
The full V4 observation vocabulary adds `Memory/allocationClass`,
`Memory/byteOffset`, `Memory/width`, and `Memory/addressSpace`; access kind,
site, occurrence, and event presence remain structural. Projection-gated
fields are present only under the coalition's derived location visibility.

### Draft binding and topology audit

`SPS-Harness-Reference-Reduction-Binding-v3` retains every V2 byte-digest and
component/root mapping and adds:

- the complete reference equivalence-class partition and the corresponding
  complete full-ABI partition, both derived from their bound files;
- one selector mapping from the reduced Boolean input to its policy component,
  ABI argument index/name, and frozen-artifact scalar argument;
- one pointer-selection mapping naming the reduced load site, true/false
  roots, frozen pointer `select`, consuming scalar load, and result store; and
- the instruction-owner and possible allocation hosts needed to rederive
  `LocVisible` for the selected coalition.

Validation compares equivalence relations, not class spelling: it must reject
any split, merge, omitted root, duplicate root, partial overlap, or topology
alternative. It also reparses the bound MLIR/LLVM artifact and requires the
mapped scalar condition to feed a pointer `select`, that exact result to feed
the scalar load, the loaded scalar to feed the result store, and no conditional
branch to precede and encode the same selection. Visibility is recomputed from
policy, placement, instruction owner, and both possible allocation hosts; a
binding cannot assert `hostVisible` as an independent Boolean.

The bad fixture binds distinct `left` and `right` classes and a synthetic pair
whose two selector values differ while all Low inputs, including the two
selected bytes, are equal. The control binds `left` and `right` to one class
and has no pair. A V4 fixture with a V2 binding, a V3 fixture with a V3
binding, or a pair whose replayed first difference disagrees with the fixture
is rejected.

### Draft PONF, backend, replay, and result contracts

`SPS-Reference-PONF-v4` binds the exact V4 program, coalition, alias table,
expanded statements, query descriptor, and deterministic SMT digest. It uses
the finite QF_BV pointer profile in section 10.1 of the candidate-directed SMT
framework: allocation key zero is null, class keys follow sorted topology
order, roots have offset zero, and conditional addresses use fieldwise `Ite`.
Memory event rows carry structural access kind plus projection-gated allocation
class, exact byte offset, width, and address space. A field auditor reconstructs
the topology, key widths, selected-byte mux, visibility term, aligned event
rows, every earlier-false bad row, and the claimed first-difference coordinate
without calling the PONF serializer.

`SPS-Reference-Relation-v2` requires symbolic exhaustive, concrete exhaustive,
canonical SMT-LIB, Z3, and replay agreement. Its finite concrete backend must
enumerate both selector values even when one is formula-irrelevant. A future
Z3 adapter is informative only: canonical SMT-LIB bytes and the PONF digest
remain solver-independent identities.

`SPS-Reference-Replay-v3` receives a complete primitive assignment or the
bound synthetic pair. It independently reconstructs class ordinals, evaluates
the select and load, applies the store, emits and projects events, and confirms
the least differing ordinal and field. A solver-supplied selected class,
projected event, or first-difference label is a claim to check, never replay
input.

`SPS-Reference-Evidence-Result-v2` remains witness-free. It may report the
query result, canonical PONF/SMT digests, backend agreement, replay acceptance,
and `Memory/allocationClass` first-difference locator, but no selector value,
root byte, allocation key assignment, model, or trace. Lowercase `sat` is still
`ExecutableReferenceOnly`; lowercase `unsat` still cannot issue
`ModelStatus: Proved`.

Required negative coverage includes incomplete/duplicate topology,
nonempty `overlaps`, same-class metadata or byte disagreement, an unknown or
out-of-range selected arm, a non-Boolean selector, partition split/merge in
the binding, missing load-site visibility evidence, an illegal
`Memory/valueBytes` or `Output/allocationClass` locator, a pair/replay
first-difference mismatch, mixed interface generations, backend disagreement,
and either pointer-valued spill operation being absent from an artifact that
expects `UnsupportedType`.

## Synthetic counterexample pair

`counterexample-pair.yaml` is public, human-authored test data with no
normative claim effect. Its closed shape is:

```yaml
format_id: SPS-Harness-Synthetic-Counterexample-Pair-v1
claim_boundary: NonClaimableFixtureOracle
source_class: SyntheticTestData
entry: xor_secret_output_bad
coalition:
  - observer
inputs:
  low_equal: {}
  high_left:
    secret:
      bitvector:
        width: 32
        hex: "00000000"
  high_right:
    secret:
      bitvector:
        width: 32
        hex: "00000001"
expected:
  bad_state: public-output-mismatch
  first_difference:
    kind: Output
    field: valueBytes
    id: return
```

The three input partitions are exact maps over entry-state policy components
and initialized ABI roots. Scalars use full-ABI-width, fixed-width lowercase
hex bitvectors. Roots use a block `bytes` mapping containing `length` and
`hex`, with two lowercase hexadecimal digits per byte.
Low inputs occur once under `low_equal`; High inputs occur in both lane maps,
and at least one High component must differ. Write-only or initially
uninitialized output roots are replay state and are not pair inputs.

For a reference-supported reduction, every scalar value must materialize into
the reduced width without truncation, and every authored root must equal the
reduced program's exact initialized entry bytes. Independent replay then
checks both lane admissions, Low equality, an actual bad state, its earliest
semantic `kind`/`field`, and the optional event `id`. The YAML reader accepts
only two-space block mappings, scalar sequences, JSON-like scalars, and the
exact `{}` empty-map literal; aliases, anchors, tags, merges, duplicate keys,
comments, nulls, floats, and general flow collections are rejected.

The pair is deliberately not an SPS solver model, external primitive
assignment, restricted replay artifact, or public counterexample receipt. No
pair value, replay flag, model, or trace is copied into
`SPS-Reference-Evidence-Result-v1`; the binding digest transitively binds the
raw pair and successful replay acts only as a fail-closed generation and
validation gate.

## Witness-free result API

Harness code imports:

```python
from sps_ref.evidence import project_relation_result, validate_relation_result
```

`validate_relation_result(value, profile_path_or_value)` validates the exact
profile binding, the closed result shape and backend/check vocabularies,
backend agreement, SAT-validation summaries, digest syntax, and the canonical
self digest. That two-argument form is deliberately structural.

Before consuming a stored endpoint as evidence, the harness calls
`validate_relation_result(value, profile_path_or_value, fixture=fixture,
binding=binding, fixture_path=fixture_path, binding_path=binding_path)`. The
paths are mandatory when the binding selects a counterexample pair. The
contextual form additionally reconstructs the exact
query inventory from the declared High inputs, rebuilds and audits each
reference PONF and deterministic SMT input, checks their digests, checks all
top-level fixture/reduction/program/coalition bindings, and checks outcomes and
the AuditAll first difference against the fixture oracle. It also rehashes,
materializes, and independently replays the selected pair. Projection is safe
only after that contextual validation; it does not independently load other
sidecars.
`project_relation_result(value)` returns only:

- `query.admission-nonempty`;
- `query.high-variation`;
- `query.terminal-output-surface`;
- `query.audit-all`;
- optional `query.audit-all-first-difference`;
- `backend.agreement`.

The canonical endpoint contains no solver assignments, input values, traces,
models, normative dispositions, or normative status fields.

Not implemented and never implied by a passing reference run:

- parsing or normalizing LLVM bitcode;
- the patched `llvm.sps.release` intrinsic or its `SPS_RELEASE` MIR lowering;
- the complete normative `ExpandedCFGTableV2` or `SPS-PONF-v2` schemas;
- the full LLVM instruction, memory, contract, error, timing, and query
  surfaces;
- an inductive proof of the complete written metatheory;
- a concrete deployment/P4 refinement proof;
- arbitrary physical, microarchitectural, debugger, kernel, or DMA compromise.

Run all executable checks from the workspace root:

```sh
python3 SPS/reference/run_reference_checks.py
```

The command exits nonzero on a fixture failure, a disagreement between the
SMT, symbolic exhaustive, and independently interpreted concrete backends, a
rejected replay, specification/fixture drift, or a falsely closed unsupported
assurance claim. Z3 is required for this slice; CVC5 is cross-checked when
installed and otherwise remains explicitly open in the run output and
assurance manifest.

Set `Z3=/absolute/path/to/solver` to select an exact Z3 executable. The
reference runner honors that path directly; it does not silently substitute a
different ambient `z3` binary.

Run one external reduction and emit canonical JSON with:

```sh
python3 SPS/reference/run_reference_checks.py \
  --relation-fixture path/to/relation-reference/fixture.json \
  --binding path/to/relation-reference/binding.json \
  --output path/to/result.json
```

Use `--output -` for stdout. Set `CVC5=/absolute/path/to/cvc5` to require an
exact CVC5 executable; a configured but unavailable executable fails closed.
