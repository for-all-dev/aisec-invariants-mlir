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

`SPS-Harness-Reference-Reduction-Binding-v1` binds the reduction to exact
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
  `argumentIndex`, string `argumentName`, null `allocationSite`, and a program
  root with `terminalOutput: true`;
- `storageKind: InternalAlloca` requires null `abiRoot`, `argumentIndex`, and
  `argumentName`, a
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
binding=binding)`. The contextual form additionally reconstructs the exact
query inventory from the declared High inputs, rebuilds and audits each
reference PONF and deterministic SMT input, checks their digests, checks all
top-level fixture/reduction/program/coalition bindings, and checks outcomes and
the AuditAll first difference against the fixture oracle. Projection is safe
only after that contextual validation; it does not independently load sidecars.
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
