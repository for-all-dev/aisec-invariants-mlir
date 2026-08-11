# Module 12 — Implementation in MLIR

## Learning objectives

After this module, you should be able to:

1. separate persistent MLIR policy annotations from inferred analysis facts;
2. design an MLIR dataflow lattice for security descriptors;
3. propagate `pc`, tensor facets, and abstract memory;
4. define operation interfaces for security semantics;
5. construct a relational SMT-lowering pipeline;
6. rerun analysis and validation across compiler passes;
7. design actionable diagnostics and tests;
8. design persistent MLIR declarations and analysis environments for principals, hosts, ACLs, and observer coalitions.

---

## 1. End-to-end compiler architecture

A practical pipeline is:

```text
partially annotated MLIR
        │
        ▼
policy and trust-boundary parsing
        │
        ▼
security dataflow fixed point
        │
        ├── SSA descriptors
        ├── program-point pc labels
        ├── abstract memory state
        ├── observable effect summaries
        └── obligations
        │
        ▼
static classification
        ├── safe by type/effect rule
        ├── definite violation
        ├── requires SMT
        └── unknown/obligation
        │
        ▼
backward slice and self-composition
        │
        ▼
MLIR SMT dialect / SMT-LIB
        │
        ▼
SAT / UNSAT / UNKNOWN
        │
        ▼
repeat after compiler lowerings
```

This architecture keeps cheap inference separate from expensive relational proof.

---

## 2. Persistent versus inferred information

### Persistent policy facts

These belong in the IR or compiler configuration because they are part of program meaning:

- principal declarations;
- host declarations;
- input and global policies;
- representation boundaries;
- `conceal`, `decrypt`, and `release`;
- mechanism contracts;
- target profile identifier;
- external-call summaries.

Example:

```mlir
func.func @f(
  %x: tensor<128xi16>
    {ifc.value_policy = #ifc.readers<[client]>,
     ifc.shape_policy = #ifc.public,
     ifc.host = #ifc.host<client>}
)
```

### Inferred analysis facts

These should usually live in analysis state:

- result labels;
- `pc` labels;
- points-to sets;
- memory content summaries;
- dependency graph;
- effect labels;
- proof status.

Do not trust inferred attributes copied through arbitrary passes. Recompute them from persistent boundaries.

---

## 3. Persistent principal, host, ACL, and threat declarations

The MLIR module needs a small persistent policy layer.

### Principal declarations

```mlir
ifc.principal @client
ifc.principal @provider
ifc.principal @server
```

Internally, assign each base principal a stable symbol identity. Principal formulas should be interned and canonicalized so equivalent conjunction/disjunction expressions compare cheaply.

### Host declarations

```mlir
ifc.host @server_host {
  controllers = [@server],
  authority = #ifc.label<conf = @server, integ = @server>,
  address_space = 1
}
```

The host environment records

$$
HostEnv(h)=\langle authority,controllers,addressSpace,targetProfile\rangle.
$$

### Policy declarations and ACL shorthand

Users may write an ACL-oriented policy:

```mlir
#ifc.acl<readers = [@client], influencers = [@client]>
```

or a principal formula:

```mlir
#ifc.label<conf = and<@client,@provider>,
           integ = or<@client,@provider>>
```

A normalization pass converts both into the internal `PrincipalPolicy` domain.

### Threat-model declarations

```mlir
ifc.observers [
  #ifc.coalition<[@server]>,
  #ifc.coalition<[@client, @server]>
]
```

Only declared coalitions receive proof obligations. The artifact should record which coalitions were checked.

### Analysis environments

The pass maintains at least:

```cpp
PrincipalEnvironment principalEnv;
HostEnvironment hostEnv;
PolicyEnvironment policyEnv;
MechanismEnvironment mechanismEnv;
ThreatEnvironment threatEnv;
```

The SSA descriptor stores policy formulas, not human-readable ACL lists. Diagnostics can render them back to actor names.

### Effect observers

Every security effect should carry or compute an observer predicate:

```cpp
bool isVisibleTo(SecurityEffect effect,
                 Coalition observer,
                 TargetProfile target,
                 MechanismContract contract);
```

This makes the actor dimension explicit when constructing traces and SMT queries.

---

## 4. Why not put everything in the MLIR type?

A first-class type such as

```mlir
!ifc.labeled<tensor<128xi16>, policy>
```

has advantages:

- explicit IR invariants;
- verifier hooks;
- transformations must handle the type.

But it also increases integration cost:

- every dialect conversion must understand the wrapper;
- canonicalization may become difficult;
- tensor, memref, and secret types interact;
- inferred facts clutter IR.

A practical v1 uses attributes plus analysis side tables, with optional materialization for debugging.

---

## 5. Security descriptor lattice

Define a C++ structure conceptually like:

```cpp
struct SecurityDescriptor {
  Label value;
  Label index;
  Label shape;
  Label layout;
  Representation repr;
  HostSet placement;
  ObligationSet obligations;
  Provenance provenance;
};
```

The join is componentwise:

```cpp
SecurityDescriptor join(
    const SecurityDescriptor &a,
    const SecurityDescriptor &b);
```

For labels:

$$
D_1\sqcup D_2
=
\langle
\ell^1_{val}\sqcup\ell^2_{val},
\ell^1_{idx}\sqcup\ell^2_{idx},
\ell^1_{shape}\sqcup\ell^2_{shape},
\ell^1_{layout}\sqcup\ell^2_{layout},
\ldots
\rangle.
$$

Representation and placement joins need careful design.

For example:

```text
same representation:
  preserve

different compatible representations:
  unknown representation or explicit union

incompatible representations:
  analysis error or top
```

---

## 6. Using MLIR's dataflow framework

MLIR provides utilities for writing fixed-point dataflow analyses. The exact API evolves, so pin an LLVM revision.

The conceptual pieces are:

- a lattice state attached to SSA values or program points;
- transfer functions for operations;
- dependency registration;
- a solver/worklist that propagates changes to a fixed point.

A sparse analysis is natural for SSA values because information flows through explicit use-def edges.

A dense or program-point analysis is useful for:

- `pc` labels;
- abstract memory;
- host execution context;
- region-level obligations.

A hybrid analysis is likely necessary.

Official MLIR documentation emphasizes that extensible dialects need interfaces or conservative fallbacks so analyses do not become giant operation-type switches.

---

## 7. Flow policy

Recommended v1 behavior:

| Dimension | Policy |
|---|---|
| SSA values | flow-sensitive |
| control context | flow-sensitive |
| CFG merge | path-insensitive join |
| immutable tensors | SSA-sensitive |
| memrefs | flow-sensitive abstract memory |
| alias uncertainty | conservative weak updates |
| calls | summary-based, initially context-insensitive |
| SMT | bounded path-sensitive |

This matches MLIR's strengths while keeping the analysis implementable.

---

## 8. Program-counter state

Associate each block or program point with

$$
pc_p.
$$

At function entry:

$$
pc=\bot.
$$

For a region entered under condition `%c`:

$$
pc_{region}
=
pc_{parent}
\sqcup
\ell_{\mathrm{val}}(\%c).
$$

For `scf.if`, analyze both regions under the joined `pc`.

For `cf.cond_br`, propagate edge-specific control labels.

At a merge, join incoming control labels.

A high `pc` also labels observable effects, not only result values.

---

## 9. Operation transfer interface

Avoid hard-coding every dialect operation into one pass.

A conceptual interface:

```cpp
class SecurityTransferInterface {
public:
  virtual TransferResult transfer(
      Operation *op,
      ArrayRef<SecurityDescriptor> operands,
      const ProgramPointState &state,
      const TargetProfile &target) const = 0;
};
```

`TransferResult` contains:

```cpp
struct TransferResult {
  SmallVector<SecurityDescriptor> results;
  SmallVector<SecurityEffect> effects;
  MemoryState memory;
  ObligationSet obligations;
};
```

Unknown operations use a conservative fallback or require a contract.

---

## 10. Security effect interface

An operation can expose information without producing a result.

```cpp
struct SecurityEffect {
  EventKind kind;
  SymbolicExpr payload;
  Label dependency;
  ObserverSet observers;
  Location sourceLoc;
};
```

Possible kinds:

```text
Branch
CallTarget
Exec
Memory
Allocation
Shape
KernelLaunch
Transfer
VariableLatency
Error
Expose
Release
```

An interface can report effect templates, while the analysis instantiates their dependency labels from operand descriptors and `pc`.

---

## 11. Example transfer: arithmetic

```mlir
%z = arith.addi %x, %y : i32
```

Transfer:

$$
\ell_{val}(z)
=
pc
\sqcup
\ell_{val}(x)
\sqcup
\ell_{val}(y).
$$

Optional event:

$$
\mathsf{exec}(site,\mathsf{addi})
$$

with dependency $pc$ if operation occurrence depends only on control.

If target marks `addi` fixed-latency, no operand-derived latency effect is needed.

---

## 12. Example transfer: conditional branch

```mlir
cf.cond_br %c, ^then, ^else
```

Effect:

$$
e=
\mathsf{branch}(site,c).
$$

Dependency:

$$
\ell(e)
=
pc\sqcup\ell_{val}(c).
$$

Successor control states:

$$
pc_{then}
=
pc\sqcup\ell_{val}(c),
$$

$$
pc_{else}
=
pc\sqcup\ell_{val}(c).
$$

The static checker compares event observers to the dependency label.

---

## 13. Example transfer: tensor extract

```mlir
%x = tensor.extract %t[%i]
```

Result:

$$
\ell_{val}(x)
=
pc
\sqcup
\ell_{val}(t)
\sqcup
\ell_{idx}(i).
$$

Effect:

$$
e=
\mathsf{memory}
(
site,
Address(t,i),
width,
read
).
$$

Dependency:

$$
pc
\sqcup
\ell_{idx}(i)
\sqcup
\ell_{shape}(t)
\sqcup
\ell_{layout}(t).
$$

At high-level tensor IR, decide whether ordinary `tensor.extract` denotes a logical observation or only a potential lowering effect. A dedicated oblivious operation can carry a stronger contract.

---

## 14. Example transfer: conceal and reveal

HEIR provides:

```mlir
secret.conceal
secret.generic
secret.reveal
```

For conceal:

$$
Policy(output)=Policy(input),
$$

$$
Representation(output)=Secret/FHEAbstract.
$$

For reveal:

$$
Policy(output)=Policy(input),
$$

$$
Representation(output)=Plain.
$$

Then check whether the current host may hold the plaintext. Do not automatically declassify.

`secret.generic` propagates policies through the lifted region and retains protected representation on results.

---

## 15. Abstract memory implementation

State:

```cpp
DenseMap<AbstractLocation, MemorySecurityState>
```

where:

```cpp
struct MemorySecurityState {
  SecurityDescriptor contents;
  InitializationState init;
  HostSet placement;
  AliasClass aliases;
};
```

Pointer analysis provides:

```cpp
PointsToSet getPointsTo(Value memref);
```

For `memref.store`:

- emit address effect;
- compute candidate locations;
- strong update if unique exact region;
- otherwise weak join;
- propagate aliases.

For `memref.load`:

- emit address effect;
- join candidate contents;
- check initialization;
- build result descriptor.

---

## 16. Bufferization integration

MLIR One-Shot Bufferize already computes alias and equivalence sets and asks operations about memory reads, writes, and aliasing through `BufferizableOpInterface`.

Security integration options:

### Reuse analysis results

Consume in-place decisions, alias sets, and buffer relations to construct source-target representation relations.

### Add a security-aware external model

For each bufferizable operation, describe how policy facets map from tensors to buffers.

### Validate before and after

Snapshot tensor IR and bufferized memref IR, then run security translation validation.

The safest design uses all three.

---

## 17. Persistent policy through lowering

When a tensor becomes a memref, policy must survive semantically.

Possible implementation approaches:

1. side table keyed by source-target mapping;
2. explicit policy attributes on bufferization boundary operations;
3. a shadow `ifc.handle` value;
4. reconstruction from translation-validation correspondence.

Do not rely on arbitrary attributes being copied automatically.

Boundary operations such as `bufferization.to_buffer` and `to_tensor` are natural places to assert correspondence.

---

## 18. Target leakage interface

A target profile should answer:

```cpp
class TargetLeakageInterface {
public:
  AddressClass classifyAddress(SymbolicAddress a) const;
  LatencyExpr latency(Operation *op,
                      ArrayRef<SymbolicExpr> operands) const;
  bool observesBranch(Operation *op) const;
  CallContract lookupCall(SymbolRefAttr callee) const;
};
```

The profile is part of the certification artifact.

Examples:

```text
generic-exact-address
x86-64-software-trace
riscv32-with-helper-contracts
apple-dit-obligation
```

Target behavior should not be hard-coded into the information-flow lattice.

---

## 19. Static classification

For each effect:

### Statically safe

Observer is authorized for every dependency.

### Definite violation

Example: plaintext client secret explicitly exposed on server.

### Requires relational proof

Secret dependency exists, but effect may be semantically constant.

### Unknown or conditional

Missing semantics, target contract, or mechanism contract.

This classification controls solver workload and diagnostic wording.

---

## 20. Dependency graph and slicing

Record provenance edges:

```text
operand -> result facet
operand -> effect
pc -> result/effect
memory location -> load
store -> memory location
```

For unresolved effect $e$, compute a backward slice.

A slice should include:

- value definitions;
- path conditions;
- relevant memory stores;
- shape/layout computations;
- external summaries;
- release functions.

Exclude unrelated kernels.

This can be represented as a subgraph or cloned MLIR region.

---

## 21. Self-composed verification IR

One implementation strategy:

1. clone the relevant function twice;
2. rename symbols and SSA values;
3. create paired arguments;
4. insert public-equality assumptions;
5. insert release-equality assumptions;
6. instrument symbolic event expressions;
7. assert divergence;
8. lower operations to SMT dialect.

Conceptual wrapper:

```mlir
func.func @verify_pair(%public0, %public1, %secret0, %secret1) {
  smt.assume %public0 == %public1

  %trace0 = call @program_0(...)
  %trace1 = call @program_1(...)

  %different = ifc.trace_diff %trace0, %trace1
  smt.assert %different
  smt.check_sat
}
```

The real SMT dialect API uses logical operations and solver regions rather than this illustrative syntax.

---

## 22. Direct SMT generation versus verification dialect

Options:

### Direct solver AST

Translate MLIR to Z3 or cvc5 APIs.

Pros: mature APIs and performance.

Cons: formulas are less inspectable in MLIR.

### MLIR SMT dialect

Construct `smt` operations and export SMT-LIB.

Pros:

- formulas remain IR;
- standard MLIR tooling applies;
- easier debugging and rewriting;
- upstream infrastructure.

Cons:

- some custom encodings still needed;
- solver integration and model lifting remain work.

A hybrid approach can use SMT dialect as canonical formula IR and a direct API backend.

---

## 23. Pass pipeline integration

After each security-critical pass:

```text
snapshot pre-pass IR
run pass
snapshot post-pass IR
recompute security analysis
run functional TV
run security TV
record obligations
```

Not every pass needs SMT.

A pass can be:

- certified by an observation-transparent rewrite subset;
- checked by static re-analysis;
- checked relationally only when it touches protected regions;
- excluded with an explicit obligation.

---

## 24. Diagnostic design

A security diagnostic should report:

```text
observer
policy source
secret owner
source operation
target operation
first bad pass
event kind
two concrete inputs
target profile
obligations
```

Example:

```text
observer: server
property: address-trace noninterference

secret input 0:
  token = 3

secret input 1:
  token = 71

first divergence:
  pass: lower-tensor-to-memref
  operation: memref.load
  address class 0: 192
  address class 1: 4544
```

A raw solver model is not enough.

---

## 25. Suggested command-line interface

Illustrative:

```text
--ifc-infer
--ifc-check
--ifc-observer=server
--ifc-target-profile=riscv32
--ifc-smt
--ifc-security-tv=before.mlir
--ifc-print-descriptors
--ifc-print-obligations
--ifc-counterexample-out=witness.yaml
```

For CI:

```text
exit 0: safe under stated profile
exit 1: concrete violation
exit 2: unknown or outstanding required obligation
```

Whether conditional results fail CI should be configurable.

---

## 26. Testing strategy

### Unit tests

One transfer function per operation.

### Lattice tests

Join, order, convergence.

### Lit tests

Expected accept/reject diagnostics.

### Differential tests

Compare static and SMT results on small exhaustive domains.

### Witness replay

Run generated inputs through an interpreter and confirm divergence.

### Pass regression tests

Store vulnerable/fixed source-target pairs.

### Negative-control tests

Ensure unsupported hardware claims return UNKNOWN.

---

## 27. Staged implementation plan

### Stage 1

- two-point or reader-set labels;
- function-argument annotations;
- `pc`;
- branch, loop, division, tensor-index effects;
- direct placement checks.

### Stage 2

- tensor facets;
- conceal/reveal semantics;
- release policies;
- target profiles;
- abstract memory.

### Stage 3

- self-composition;
- bitvector and bounded tensor SMT;
- witness generation.

### Stage 4

- per-pass security translation validation;
- bufferization relations;
- observation-transparent rewrite checker.

### Stage 5

- mechanism contracts;
- synthesis;
- distributed choreography.

This ordering preserves a publishable core even if later stages take longer.

---

## 28. Common mistakes

### Mistake 1: trusting inferred attributes after lowering

Recompute analysis.

### Mistake 2: one analysis state for both SSA and memory

They have different flow structure.

### Mistake 3: hard-coding operation names

Use interfaces and conservative fallbacks.

### Mistake 4: sending every program to SMT

Use static triage and slicing.

### Mistake 5: ignoring the target profile in diagnostics

Variable latency and memory visibility are target-relative.

### Mistake 6: reporting UNKNOWN as a warning but continuing to certify

Certification status must reflect it.

---

## 29. Exercises

### Exercise 1

Design a C++ lattice join for a descriptor with value and shape labels.

### Exercise 2

Write pseudocode for the transfer function of `scf.if`.

### Exercise 3

What persistent annotation should survive a `secret.conceal` lowering?

### Exercise 4

Design a `SecurityEffectInterface` result for `memref.load`.

### Exercise 5

Explain how One-Shot Bufferize alias sets could help build `RepRel`.

### Exercise 6

Write a test matrix for select-to-branch preservation across three target profiles.

### Exercise 7

Design a diagnostic for a missing opaque-call contract.

---

## 30. Summary

The compiler implementation needs first-class environments for principals, hosts, policies, mechanisms, and threat coalitions. Inferred SSA metadata is evaluated relative to those environments, and every relational query names the observer for which it is proving security.


The MLIR implementation separates:

$$
\boxed{
\text{persistent policy boundaries}
}
$$

from

$$
\boxed{
\text{recomputed abstract security facts}.
}
$$

Dataflow finds possible dependencies. Operation interfaces define security effects. SMT decides unresolved relational obligations. Per-pass validation ensures that lowering does not introduce new distinctions.

---

## Further reading

- MLIR, [Writing DataFlow Analyses](https://mlir.llvm.org/docs/Tutorials/DataFlowAnalysis/).
- MLIR, [Interfaces](https://mlir.llvm.org/docs/Interfaces/).
- MLIR, [Bufferization](https://mlir.llvm.org/docs/Bufferization/).
- MLIR, [SMT Dialect](https://mlir.llvm.org/docs/Dialects/SMT/).
- HEIR, [`secret` dialect](https://heir.dev/docs/dialects/secret/).
- S. Bang et al., [MLIR-TV](https://github.com/aqjune/mlir-tv).
