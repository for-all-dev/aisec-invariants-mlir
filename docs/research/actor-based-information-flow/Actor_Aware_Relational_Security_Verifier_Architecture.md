# Architecture of an Actor-Aware Relational Security Verifier for Tensor MLIR

**Status:** research architecture specification  
**Intended audience:** compiler and programming-languages researchers with basic familiarity with SSA, dataflow analysis, and MLIR  
**Primary goal:** check actor-specific confidentiality properties of tensor programs and verify that MLIR lowering preserves those properties

---

## 1. Executive summary

This document specifies an MLIR verification extension that combines:

1. **principal- and host-aware information-flow analysis**;
2. **tensor-facet security descriptors**;
3. **observable-effect extraction** for control flow, memory, timing, placement, and release;
4. **relational SMT verification** using self-composition;
5. **security translation validation** across MLIR lowerings; and
6. **an explicit obligations ledger** for behavior below the verified IR.

The central security statement is not merely that a value is labeled secret. It is that, for every observer coalition named by the threat model, changing information hidden from that coalition does not change anything the coalition is modeled as observing:

$$
\sigma_0 \approx_A^{\Delta} \sigma_1
\Longrightarrow
\operatorname{Trace}_{A,\Theta}(P,\sigma_0)
\sim
\operatorname{Trace}_{A,\Theta}(P,\sigma_1).
$$

Here:

- $A$ is an observer principal or coalition;
- $\Delta$ is the sanctioned-release policy;
- $\Theta$ is the target leakage profile;
- $\approx_A^{\Delta}$ is release-relative low-equivalence; and
- $\sim$ is observer-specific trace equivalence.

The compiler also checks that lowering does not introduce a new distinction:

$$
\operatorname{Trace}_{A,\Theta}(S,\sigma_0)
\sim
\operatorname{Trace}_{A,\Theta}(S,\sigma_1)
\Longrightarrow
\operatorname{Trace}_{A,\Theta}(T,\sigma_0)
\sim
\operatorname{Trace}_{A,\Theta}(T,\sigma_1).
$$

The architecture is organized into five logical layers:

```text
L0  Policy, principals, hosts, ACLs, coalitions, contracts
L1  Actor-aware information-flow and abstract-memory analysis
L2  Relational SMT verification of unresolved security effects
L3  Security translation validation across lowering passes
L4  Structured obligations for backends, libraries, and hardware
```

Viaduct motivates the L0 policy model and minimum-authority inference structure. This architecture adds tensor facets, target-sensitive traces, relational verification of the emitted artifact, and security-preservation checking across MLIR lowering.

---

## 2. Design goals and non-goals

### 2.1 Goals

The verifier should detect or conditionally verify confidentiality violations expressible through:

- unauthorized public outputs;
- plaintext or metadata placed on an unauthorized host;
- secret-dependent branch outcomes and call targets;
- secret-dependent finite operation counts;
- secret-dependent memory addresses or address classes;
- secret-dependent tensor shape, layout, sparsity, or schedule;
- target-variable-latency operations;
- distinguishable error behavior;
- unauthorized or overly broad release events; and
- compiler transformations that introduce any of the above.

The system should return one of four results:

```text
verified     — proved in the modeled fragment under listed assumptions
unsafe       — concrete policy violation or relational counterexample
unknown      — unsupported semantics, solver timeout, or missing summary
conditional  — verified only if listed obligations are discharged
```

### 2.2 Non-goals for version 1

The first implementation does not claim to verify:

- power, electromagnetic, acoustic, or fault channels;
- speculative-execution leakage;
- data-memory-dependent prefetch behavior such as GoFetch;
- arbitrary network timing and contention;
- arbitrary C or LLVM pointer behavior;
- cryptographic hardness assumptions;
- correctness of opaque FHE, MPC, runtime, or hardware implementations;
- availability or termination-sensitive noninterference;
- automatic selection of all cryptographic mechanisms; or
- wisdom of the programmer's release policy.

These boundaries are explicit. Behavior outside the semantic model becomes an obligation rather than a silent assumption.

---

## 3. Terminology and system entities

The formal architecture uses **principal** or **party**. The term **actor** is informal.

### 3.1 Principals

A principal is an identity named by security policy:

$$
p \in \mathcal P.
$$

Examples include:

```text
client
provider
server
security_officer
GPU_runtime
```

### 3.2 Hosts

A host is an execution or storage location:

$$
h \in \mathcal H.
$$

Examples include:

```text
client_host
provider_host
server_cpu
server_gpu
trusted_enclave
```

A host is not a principal. A principal controls one or more hosts.

### 3.3 Controllers

The controller map records which principals can inspect or modify a host:

$$
\operatorname{controllers}:\mathcal H\rightarrow 2^{\mathcal P}.
$$

For example:

$$
\operatorname{controllers}(\mathsf{server\_gpu})
=
\{\mathsf{server},\mathsf{GPU\_runtime}\}.
$$

### 3.4 Observer coalitions

An observer coalition is a set of principals that may collude:

$$
A\subseteq\mathcal P.
$$

The threat model declares a finite set of coalitions to verify:

$$
\mathcal A\subseteq 2^{\mathcal P}.
$$

The verifier need not enumerate every subset of principals. It verifies the coalitions explicitly declared relevant.

### 3.5 Policy, representation, and placement

These must remain separate:

```text
policy          who may learn or influence the information
representation  plaintext, FHE ciphertext, share, commitment, opaque value
placement       which host currently stores or computes on that representation
```

An FHE ciphertext may be placed on a server while its underlying semantic value remains client-confidential.

### 3.6 Owner, reader, influencer, and observer

These terms have different roles:

- **Owner:** authority whose approval is needed to weaken a policy.
- **Reader:** principal permitted to learn protected information.
- **Influencer:** principal permitted to affect trusted information or a release decision.
- **Observer:** principal or coalition against which the relational property is checked.

---

## 4. Principal formulas, ACLs, and information-flow labels

### 4.1 Principal formulas

The internal policy language uses principal formulas:

$$
\phi ::=
\mathbf 0
\mid
\mathbf 1
\mid
p
\mid
\phi_1\land\phi_2
\mid
\phi_1\lor\phi_2.
$$

The acts-for relation

$$
\phi_1\Rightarrow\phi_2
$$

means that $\phi_1$ has at least the authority of $\phi_2$. It coincides with logical implication over principal formulas. For example:

$$
A\land B\Rightarrow A,
\qquad
A\Rightarrow A\lor B.
$$

### 4.2 Confidentiality and integrity labels

A security label is a pair:

$$
\ell=\langle C(\ell),I(\ell)\rangle,
$$

where:

- $C(\ell)$ is the confidentiality authority required to read the information;
- $I(\ell)$ is the integrity authority associated with influencing or trusting it.

The information-flow ordering follows the Viaduct/FLAM style:

$$
\ell_1\sqsubseteq\ell_2
\quad\Longleftrightarrow\quad
C(\ell_2)\Rightarrow C(\ell_1)
\;\land\;
I(\ell_1)\Rightarrow I(\ell_2).
$$

Intuitively, information may flow into a destination that is at least as restrictive in confidentiality and no more trusted in integrity than the source permits.

The join combines dependencies:

$$
\ell_1\sqcup\ell_2
=
(\ell_1\land\ell_2)^{\rightarrow}
\land
(\ell_1\lor\ell_2)^{\leftarrow}.
$$

An implementation may initially use a simpler reader/influencer set domain, provided it has a sound embedding into this authority model.

### 4.3 ACL syntax as a presentation layer

Programmers may prefer ACL-like annotations:

```mlir
#ifc.acl<
  owners = [@client],
  readers = [@client],
  influencers = [@client]
>
```

ACLs are normalized during L0 into canonical principal formulas. They are not the internal analysis representation.

This separation matters because ACL checks answer:

> May this principal access this object now?

IFC answers:

> Where may information derived from this object flow after copying, arithmetic, control flow, indexing, buffering, and lowering?

### 4.4 Actor authorization predicates

The verifier exposes abstract predicates:

$$
\operatorname{CanRead}(A,\ell),
\qquad
\operatorname{CanInfluence}(A,\ell),
$$

which are derived from coalition authority and the acts-for relation. Keeping these predicates abstract in most rules avoids coupling later components to one concrete label representation.

---

## 5. Security semantics

### 5.1 Event-emitting execution

Ordinary semantics produces a result:

$$
\langle P,\sigma\rangle\Downarrow v.
$$

Security semantics also produces a trace:

$$
\langle P,\sigma\rangle
\Downarrow
(v,\tau).
$$

A trace is an ordered sequence:

$$
\tau=e_0e_1\cdots e_{n-1}.
$$

### 5.2 Event alphabet

The core event model is:

$$
\begin{aligned}
e ::= {}&
\mathsf{exec}(site,opcode)\\
&\mid \mathsf{branch}(site,outcome)\\
&\mid \mathsf{call}(site,target)\\
&\mid \mathsf{memory}(site,addressClass,width,mode)\\
&\mid \mathsf{variableLatency}(site,opcode,class)\\
&\mid \mathsf{allocation}(site,size,host)\\
&\mid \mathsf{shape}(site,dimensions)\\
&\mid \mathsf{kernelLaunch}(site,kernel,device)\\
&\mid \mathsf{transfer}(site,source,destination,size)\\
&\mid \mathsf{expose}(site,host,facet,representation,view)\\
&\mid \mathsf{error}(site,errorClass)\\
&\mid \mathsf{release}(site,policy,audience,value).
\end{aligned}
$$

`exec` events make finite operation-count differences explicit.

### 5.3 Target leakage profile

The target profile $\Theta$ defines what is observable:

$$
\Theta=
\langle
\mu_\Theta,
\operatorname{lat}_\Theta,
\operatorname{callContract}_\Theta,
\operatorname{hardwareAssumptions}_\Theta
\rangle.
$$

Examples:

- $\mu_\Theta(a)$ may return an exact address, cache line, page, or bank.
- $\operatorname{lat}_\Theta(op,\bar v)$ returns an observable latency class.
- a call contract specifies which arguments affect outputs, memory, and timing.

### 5.4 Actor-relative trace projection

The full trace is projected for coalition $A$:

$$
\operatorname{Trace}_{A,\Theta}(P,\sigma)
=
\pi_{A,\Theta}
\left(
\operatorname{Trace}(P,\sigma)
\right).
$$

Projection depends on:

- hosts controlled by $A$;
- the representation of each value;
- mechanism contracts;
- target-profile observability; and
- release audiences.

### 5.5 Release-relative low-equivalence

Two states are low-equivalent for $A$ when they agree on everything $A$ is initially allowed to know and on all authorized release functions visible to $A$:

$$
\begin{aligned}
\sigma_0\approx_A^{\Delta}\sigma_1
\quad\Longleftrightarrow\quad{}&
\operatorname{PublicView}_A(\sigma_0)
=
\operatorname{PublicView}_A(\sigma_1)\\
&\land
\bigwedge_{k:\,A\in\operatorname{audience}(k)}
R_k(\sigma_0)=R_k(\sigma_1).
\end{aligned}
$$

### 5.6 Program security

The source-level security property is:

$$
\boxed{
\operatorname{Secure}_{A,\Theta,\Delta}(P)
\triangleq
\forall\sigma_0,\sigma_1.
\;
\sigma_0\approx_A^{\Delta}\sigma_1
\Longrightarrow
\operatorname{Trace}_{A,\Theta}(P,\sigma_0)
\sim
\operatorname{Trace}_{A,\Theta}(P,\sigma_1)
}
$$

The complete claim quantifies over declared coalitions:

$$
\forall A\in\mathcal A.
\;
\operatorname{Secure}_{A,\Theta,\Delta}(P).
$$

---

## 6. Architectural overview

```text
┌──────────────────────────────────────────────────────────────┐
│ Inputs                                                       │
│ MLIR + principal/host declarations + ACLs + release policy   │
│ + mechanism contracts + threat coalitions + target profile  │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ L0 — Policy normalization and environment construction       │
│ ACLs → principal formulas; acts-for relation; host map;      │
│ coalition set; release and mechanism environments            │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ L1 — Actor-aware abstract interpretation                     │
│ SSA descriptors; pc labels; abstract memory; alias state;    │
│ placement; representations; provenance; obligations          │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Observable-effect extraction and actor projection            │
│ branches, addresses, counts, latency, transfers, releases    │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Static triage per observer coalition                         │
│ safe | definite violation | relational proof | obligation    │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ L2 — Self-composed SMT verification                          │
│ backward slice; two executions; low-equivalence; trace diff  │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ L3 — Security translation validation                         │
│ source pair indistinguishable ⇒ target pair indistinguishable│
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ L4 — Obligation ledger and diagnostic report                 │
│ backend, runtime, FHE, target, DIT/DOIT, opaque calls         │
└──────────────────────────────────────────────────────────────┘
```

---

## 7. Persistent MLIR policy layer

Only semantically meaningful policy facts should persist through transformations.

### 7.1 Principal and host declarations

A proposed surface syntax is:

```mlir
ifc.principal @client
ifc.principal @provider
ifc.principal @server

ifc.host @client_host {
  controllers = [@client],
  authority = #ifc.label<conf = @client, integ = @client>,
  address_space = 0,
  target = #ifc.target<client_cpu>
}

ifc.host @server_host {
  controllers = [@server],
  authority = #ifc.label<conf = @server, integ = @server>,
  address_space = 1,
  target = #ifc.target<server_cpu>
}
```

### 7.2 Threat model

```mlir
ifc.threat_model @deployment {
  observer_coalitions = [
    #ifc.coalition<[@server]>,
    #ifc.coalition<[@client]>,
    #ifc.coalition<[@provider]>,
    #ifc.coalition<[@server, @provider]>
  ]
}
```

### 7.3 Value and tensor-facet policies

```mlir
func.func @inference(
  %input: tensor<1x128xi16> {
    ifc.value_policy = #ifc.acl<owners=[@client], readers=[@client]>,
    ifc.shape_policy = #ifc.public,
    ifc.layout_policy = #ifc.public,
    ifc.host = @client_host,
    ifc.representation = #ifc.plain
  },
  %weights: tensor<128x128xi16> {
    ifc.value_policy = #ifc.acl<owners=[@provider], readers=[@provider]>,
    ifc.shape_policy = #ifc.public,
    ifc.layout_policy = #ifc.public,
    ifc.host = @provider_host,
    ifc.representation = #ifc.plain
  })
```

### 7.4 Explicit policy-changing operations

Representation and release boundaries should be explicit:

```mlir
%cx = ifc.conceal %input {
  mechanism = @client_fhe,
  destination = @server_host
}

%plain = ifc.decrypt %cipher {
  at = @client_host,
  key = @client_secret_key
}

%released = ifc.release %plain {
  policy = @prediction_to_client
}
```

### 7.5 Persistent versus inferred information

Persist:

- principal and host declarations;
- controller relationships;
- input, global, and release policies;
- representation-changing operations;
- mechanism contract identifiers;
- target-profile identifiers;
- trusted call summaries; and
- threat coalitions.

Recompute after transformations:

- intermediate labels;
- `pc` labels;
- points-to sets;
- memory-content labels;
- event dependencies;
- provenance slices; and
- proof status.

A compiler pass must not make a leak disappear by dropping an inferred attribute.

---

## 8. Core analysis state

### 8.1 Security descriptor

For each SSA value $v$, compute:

$$
D(v)=
\left\langle
\tau,
\ell_{\mathrm{value}},
\ell_{\mathrm{index}},
\ell_{\mathrm{shape}},
\ell_{\mathrm{layout}},
\rho,
H,
\nu,
\Omega
\right\rangle.
$$

Where:

- $\tau$: ordinary MLIR type;
- $\ell_{\mathrm{value}}$: scalar value or tensor-element policy;
- $\ell_{\mathrm{index}}$: selector, token, or logical-index policy;
- $\ell_{\mathrm{shape}}$: dimension and length policy;
- $\ell_{\mathrm{layout}}$: sparsity, stride, routing, and layout policy;
- $\rho$: representation;
- $H\subseteq\mathcal H$: actual placement set;
- $\nu$: provenance and symbolic dependency information;
- $\Omega$: outstanding obligations.

A scalar usually uses only $\ell_{\mathrm{value}}$. Unused facets take neutral values.

### 8.2 Program-point state

Some facts are not properties of one SSA definition:

$$
S_p=\langle pc_p,\widehat M_p,\operatorname{pathSummary}_p\rangle.
$$

- $pc_p$ records implicit control dependence.
- $\widehat M_p$ is abstract memory.
- `pathSummary` optionally stores lightweight feasibility information.

### 8.3 Abstract memory

Memory is host-indexed:

$$
\widehat M:
\mathcal H
\rightarrow
(\mathsf{Allocation}\times\mathsf{AccessPath}
\rightarrow D).
$$

This makes it possible to distinguish:

- client plaintext memory;
- server ciphertext memory;
- provider model memory;
- GPU scratch memory; and
- aliases spanning address spaces.

### 8.4 Security effects

Each operation may produce zero or more effects:

$$
E(op)=
\left\{
\langle
kind,
payload,
\ell_{dep},
execHost,
representation,
visibleFacets,
\Omega
\rangle
\right\}.
$$

Effects are required even for operations with no SSA result, such as branches, stores, transfers, and releases.

### 8.5 Provenance graph

The analysis records dependency edges:

$$
v_1\leadsto v_2,
\qquad
v\leadsto e.
$$

This graph is used to construct a backward SMT slice from a suspicious effect to relevant inputs and memory state.

---

## 9. L0: policy normalization and validation

L0 constructs the policy environment:

$$
\mathcal E=
\langle
\mathcal P,
\mathcal H,
\operatorname{controllers},
\operatorname{actsFor},
\mathcal A,
\Delta,
\mathcal K,
\Theta
\rangle.
$$

### 9.1 L0 tasks

1. Resolve all principal and host symbols.
2. Normalize ACL syntax to principal formulas.
3. Canonicalize principal formulas.
4. Build and validate the acts-for relation.
5. Check host-controller consistency.
6. Validate threat coalitions.
7. Load mechanism and external-call contracts.
8. Validate release-policy declarations.
9. Select the active target leakage profile.

### 9.2 Early errors

L0 rejects malformed policy before dataflow begins:

```text
unknown principal
host with no controller
cyclic or inconsistent authority declaration
release audience not declared
mechanism references nonexistent key holder
unsupported coalition under a mechanism contract
```

### 9.3 Minimum-authority inference

The analysis generates flows-to constraints over label variables:

$$
L_x\sqsubseteq L_z,
\qquad
L_y\sqsubseteq L_z,
\qquad
pc\sqsubseteq L_z.
$$

These are reduced to acts-for constraints over confidentiality and integrity components. A fixed-point solver computes a minimum-authority solution:

$$
\operatorname{Infer}(P)=\Gamma^*.
$$

The intended property is:

$$
\Gamma\vdash P
\Longrightarrow
\Gamma^*\preceq\Gamma.
$$

Relational SMT is not used for ordinary label inference.

---

## 10. L1: actor-aware information-flow analysis

### 10.1 Analysis sensitivity

The recommended design is:

| Dimension | Version-1 behavior |
|---|---|
| SSA definitions | flow-sensitive by construction |
| control context | flow-sensitive `pc` state |
| CFG merges | path-insensitive joins |
| immutable tensors | flow-sensitive through SSA |
| memrefs | flow-sensitive with conservative aliasing |
| calls | summary-based, initially context-insensitive |
| SMT | path-sensitive within bounded slices |

### 10.2 Worklist algorithm

For operation $op$, define a monotone transfer function:

$$
F_{op}
\left(
D(v_1),\ldots,D(v_n),
S_p,
\mathcal E
\right)
=
\left(
D(r_1),\ldots,D(r_m),
S_{p'},
E(op),
\Omega
\right).
$$

The analysis iterates to a fixed point:

```text
seed arguments, globals, constants, and policy operations
place entry operations on a worklist

while the worklist is not empty:
    read operand descriptors and program-point state
    apply the operation transfer function
    join result descriptors and successor states
    record effects, provenance, and obligations
    enqueue affected users and CFG successors
```

Joins are monotone:

$$
D_{new}=D_{old}\sqcup D_{incoming}.
$$

### 10.3 Arithmetic

For:

```mlir
%z = arith.addi %x, %y : i32
```

$$
\ell_{value}(z)
=
pc
\sqcup
\ell_{value}(x)
\sqcup
\ell_{value}(y).
$$

If operation counts are observed, the operation also emits:

$$
\mathsf{exec}(site,\mathsf{addi})@pc.
$$

### 10.4 `arith.select`

For:

```mlir
%r = arith.select %c, %a, %b : i32
```

$$
\ell_{value}(r)
=
pc
\sqcup
\ell_{value}(c)
\sqcup
\ell_{value}(a)
\sqcup
\ell_{value}(b).
$$

The source profile may treat the operation as branchless and fixed-latency. It then carries a lowering obligation:

$$
\Omega\ni
\operatorname{PreserveConstantTimeSelect}(site,\Theta).
$$

### 10.5 Conditional control flow

For:

```mlir
scf.if %c {
  ...
} else {
  ...
}
```

compute:

$$
pc'=pc\sqcup\ell_{value}(c).
$$

Emit:

$$
e=\mathsf{branch}(site,c)
\quad\text{with dependency}\quad
\ell(e)=pc'.
$$

Analyze both regions under $pc'$. At the merge, join yielded descriptors.

### 10.6 Loops

For a loop with lower bound $l$, upper bound $u$, step $s$, and guard $g$:

$$
\ell_{count}
=
pc
\sqcup
\ell(l)
\sqcup
\ell(u)
\sqcup
\ell(s)
\sqcup
\ell(g).
$$

A secret-dependent finite iteration count is observable even when both executions terminate. The checker may:

- reject;
- require a public fixed upper bound with masked iterations; or
- emit a relational SMT obligation.

### 10.7 Tensor extraction and gather

For:

```mlir
%x = tensor.extract %table[%i]
```

result value dependency:

$$
\ell_{value}(x)
=
pc
\sqcup
\ell_{value}(table)
\sqcup
\ell_{index}(i).
$$

address dependency:

$$
\ell_{addr}
=
pc
\sqcup
\ell_{index}(i)
\sqcup
\ell_{shape}(table)
\sqcup
\ell_{layout}(table).
$$

The effect payload is:

$$
\mu_\Theta
\left(
\operatorname{address}(table,i)
\right).
$$

### 10.8 Variable-latency operations

For target profile $\Theta$, let $\operatorname{rel}_\Theta(op)$ identify latency-relevant operands:

$$
\ell_{lat}
=
pc
\sqcup
\bigsqcup_{j\in\operatorname{rel}_\Theta(op)}
\ell_{value}(v_j).
$$

Emit:

$$
e=
\mathsf{variableLatency}
\left(
site,op,
\operatorname{lat}_\Theta(op,\bar v)
\right).
$$

The conservative default may expose the relevant operands themselves when no precise latency model is available.

### 10.9 Concealment, transfer, decryption, and release

Concealment changes representation, not policy:

$$
\ell_f(\operatorname{conceal}(v))=\ell_f(v),
\qquad
\rho'=\mathsf{FHE}(k).
$$

Transfer changes placement:

$$
H'=\{h_{destination}\}.
$$

Decryption changes representation back to plaintext but still does not declassify:

$$
\ell_f(\operatorname{decrypt}(v))=\ell_f(v).
$$

Only `ifc.release` may weaken a confidentiality policy, subject to $\Delta$.

### 10.10 External calls

Every external call requires a summary describing:

- output dependence;
- memory reads and writes;
- address dependence;
- timing-relevant operands;
- host execution;
- representation preservation;
- release behavior; and
- remaining assumptions.

No summary means `unknown` or an explicit obligation.

---

## 11. Memory, pointers, aliases, and bufferization

Memory is the main point where a purely SSA-based security argument can become unsound.

### 11.1 Points-to information

For a memref-like value $p$:

$$
\operatorname{PointsTo}(p)
\subseteq
\mathsf{Allocation}\times\mathsf{OffsetRegion}.
$$

A pointer or memref descriptor must separate:

```text
policy of the handle
policy of the address choice
policy of the stored contents
host containing the allocation
representation stored in the allocation
```

### 11.2 Address computation

For a strided memref:

$$
addr
=
base
+
offset
+
\sum_{j=0}^{n-1}i_j\cdot stride_j.
$$

The address dependency is:

$$
\ell_{addr}
=
pc
\sqcup
\ell(baseChoice)
\sqcup
\ell(offset)
\sqcup
\bigsqcup_j\ell(i_j)
\sqcup
\ell(strides)
\sqcup
\ell(layout).
$$

### 11.3 Strong and weak updates

If an exact unique location is known, use a strong update:

$$
\widehat M'[a]=D(v).
$$

If the target may alias several locations, use a weak update:

$$
\widehat M'[a]
=
\widehat M[a]\sqcup D(v).
$$

### 11.4 Host exposure

A store is safe only if every facet exposed by representation $\rho$ on host $h$ is authorized:

$$
\forall A,f.
\;
\operatorname{Exposed}_{\mathcal K,\Theta}(A,h,\rho,f)
\Longrightarrow
\operatorname{CanRead}(A,\ell_f).
$$

### 11.5 Bufferization

Tensor-to-memref lowering changes immutable value semantics into mutable memory semantics. Security translation validation therefore requires a source-target representation relation:

$$
\operatorname{RepRel}(T,M,b).
$$

For every valid index $i$:

$$
T[i]=\operatorname{load}(M,b+i\cdot width).
$$

The relation must also record:

- which host owns the allocation;
- which aliases are introduced;
- whether initialization is complete;
- what metadata becomes visible;
- whether allocation size is observable; and
- whether an encrypted wrapper was preserved.

A functionally correct bufferization may still be insecure if it creates a plaintext server-readable memref or changes address behavior.

---

## 12. Observable-effect extraction and static triage

For each declared observer coalition $A$, the checker classifies each effect.

### 12.1 Safe by authority

If $A$ can observe $e$ and is authorized for every dependency:

$$
\operatorname{Visible}(A,e)
\Longrightarrow
\operatorname{CanRead}(A,\ell(e)),
$$

then the effect is statically safe.

### 12.2 Definite violation

Some violations need no SMT query:

```text
client-confidential plaintext copied to server memory
release audience differs from declared audience
server performs decryption without authority
opaque call explicitly exposes its argument
```

### 12.3 Relational proof required

A secret may syntactically influence an event while the event is semantically constant. For example:

```mlir
%x = arith.xori %secret, %secret
%c = arith.cmpi ne, %x, %c0
cf.cond_br %c, ^a, ^b
```

The static analysis is conservative. SMT can prove that the branch outcome never differs.

### 12.4 Obligation or unknown

Unsupported or externally defined behavior creates an obligation:

```text
runtime helper timing contract missing
backend behavior below last verified IR
opaque FHE call has no metadata-exposure contract
unbounded loop has no invariant or bound
```

---

## 13. L2: relational SMT verification

### 13.1 Role of metadata

Security labels are usually not encoded as arbitrary SMT integers. They guide query construction:

- which inputs and facets must be equal;
- which secrets may differ;
- which observer-visible effects are compared;
- which representation projection is visible;
- which release functions must be held equal; and
- which backward slice must be encoded.

### 13.2 Self-composition

Create two renamed copies:

$$
P^0,
\qquad
P^1.
$$

For every input or initial memory facet visible to $A$, assert equality:

$$
\operatorname{CanRead}(A,\ell_f(v))
\Longrightarrow
f(v^0)=f(v^1).
$$

Hidden facets remain independent.

### 13.3 Leak query

The basic query is:

$$
\begin{aligned}
\Phi_{leak}(P,A)={} &
\operatorname{Sem}(P^0,\sigma_0,\tau_0)\\
&\land
\operatorname{Sem}(P^1,\sigma_1,\tau_1)\\
&\land
\operatorname{LowEq}_{A,\Delta}(\sigma_0,\sigma_1)\\
&\land
\neg\operatorname{TraceEq}_{A,\Theta}(\tau_0,\tau_1).
\end{aligned}
$$

Interpretation:

- `SAT`: a modeled leak exists;
- `UNSAT`: no leak exists in the exact encoded fragment;
- `UNKNOWN`: no certification.

### 13.4 Arithmetic encoding

```mlir
%z = arith.addi %x, %y : i32
```

becomes:

$$
z^j=\operatorname{bvadd}(x^j,y^j),
\qquad j\in\{0,1\}.
$$

### 13.5 Conditionals

For pure values:

$$
r^j=\operatorname{ite}(c^j,a^j,b^j).
$$

Branch observation:

$$
e_{branch}^j=c^j.
$$

For side effects, use path predicates:

$$
path_{then}^j=path^j\land c^j,
\qquad
path_{else}^j=path^j\land\neg c^j.
$$

### 13.6 Loops

Version 1 should use bounded unrolling. For maximum bound $B$:

$$
valid_k^j=(k<tripCount^j).
$$

A loop-carried state is encoded as:

$$
x_{k+1}^j
=
\operatorname{ite}
\left(
valid_k^j,
body(x_k^j,k),
x_k^j
\right).
$$

Operation count:

$$
count^j
=
\sum_{k=0}^{B-1}
\operatorname{ite}(valid_k^j,1,0).
$$

The query may assert:

$$
count^0\neq count^1.
$$

Unbounded loops require a relational invariant or produce `unknown`.

### 13.7 Memory

Memory is represented as an SMT array:

$$
M:\operatorname{Array}(\mathsf{Address},\mathsf{Byte}).
$$

Load:

$$
v=\operatorname{select}(M,addr).
$$

Store:

$$
M'=\operatorname{store}(M,addr,v).
$$

The memory observation is separate:

$$
e_{mem}=\mu_\Theta(addr).
$$

### 13.8 Aliases

If pointer $p$ may refer to $a_1$ or $a_2$:

$$
base(p)
=
\operatorname{ite}(choice=0,base(a_1),base(a_2)).
$$

The solver explores feasible alias choices subject to static points-to constraints.

### 13.9 Trace representation

A simple bounded representation is:

$$
\tau=
\langle
(e_0,valid_0),\ldots,(e_{N-1},valid_{N-1}),length
\rangle.
$$

Trace difference is:

$$
length_0\neq length_1
\;\lor\;
\bigvee_{i=0}^{N-1}
\left(
valid_i^0\neq valid_i^1
\lor
(valid_i^0\land e_i^0\neq e_i^1)
\right).
$$

### 13.10 Backward slicing

For unresolved effect $e$:

1. start at the effect payload;
2. follow SSA and memory dependencies backward;
3. include reaching stores and path conditions;
4. stop at constants, inputs, and verified summaries;
5. clone only the resulting slice twice.

This keeps SMT queries manageable.

### 13.11 Counterexample lifting

A satisfying model is converted into:

```text
observer coalition
public input assignment
secret input 0
secret input 1
first divergent event
source locations
relevant target profile
runnable test harness
```

Raw solver models are not acceptable user diagnostics.

---

## 14. L3: security translation validation

Functional correctness does not imply confidentiality preservation.

### 14.1 Actor-indexed security refinement

Define the indistinguishability kernel:

$$
\mathcal K_{A,\Theta,\Delta}(P)
=
\left\{
(\sigma_0,\sigma_1)
\mid
\sigma_0\approx_A^\Delta\sigma_1
\land
\operatorname{Trace}_{A,\Theta}(P,\sigma_0)
\sim
\operatorname{Trace}_{A,\Theta}(P,\sigma_1)
\right\}.
$$

Source $S$ security-refines target $T$ when:

$$
S\preceq^{sec}_{A,\Theta,\Delta}T
\quad\Longleftrightarrow\quad
\mathcal K_{A,\Theta,\Delta}(S)
\subseteq
\mathcal K_{A,\Theta,\Delta}(T).
$$

The target may not split a source indistinguishability class.

### 14.2 Regression query

The four-run query is:

$$
\begin{aligned}
\Phi_{regress}(S,T,A)={} &
\operatorname{LowEq}_{A,\Delta}(\sigma_0,\sigma_1)\\
&\land
\operatorname{Sem}(S,\sigma_0,\tau_0^S)\\
&\land
\operatorname{Sem}(S,\sigma_1,\tau_1^S)\\
&\land
\operatorname{TraceEq}_{A,\Theta}(\tau_0^S,\tau_1^S)\\
&\land
\operatorname{Sem}(T,\sigma_0,\tau_0^T)\\
&\land
\operatorname{Sem}(T,\sigma_1,\tau_1^T)\\
&\land
\neg\operatorname{TraceEq}_{A,\Theta}(\tau_0^T,\tau_1^T).
\end{aligned}
$$

`SAT` means compilation introduced a channel.

### 14.3 Functional refinement remains separate

The pipeline must establish both:

$$
S\preceq^{fun}T
\qquad\text{and}\qquad
S\preceq^{sec}_{A,\Theta,\Delta}T.
$$

A target can be constant-time and wrong, or functionally correct and leaky.

### 14.4 Per-pass localization

The pass manager records checkpoints:

```text
P0 → pass1 → P1 → pass2 → P2 → ... → Pn
```

Security refinement is checked incrementally or by bisection. The diagnostic reports the first pass for which:

$$
P_i\not\preceq^{sec}_A P_{i+1}.
$$

### 14.5 Observation-transparent rewrite subset

A rewrite $L\rightsquigarrow R$ is observation-transparent if:

$$
\forall\sigma_0,\sigma_1.
\;
\operatorname{Obs}(L,\sigma_0)
\sim
\operatorname{Obs}(L,\sigma_1)
\Longrightarrow
\operatorname{Obs}(R,\sigma_0)
\sim
\operatorname{Obs}(R,\sigma_1).
$$

A syntactic linter can certify simple rules that introduce no new secret-dependent:

- branch;
- loop count;
- address;
- allocation or transfer size;
- variable-latency operand;
- host exposure;
- release; or
- opaque call.

General cases fall back to SMT.

---

## 15. Sanctioned release and robust declassification

### 15.1 Release policy

Each release policy is:

$$
\Delta(k)=
\left\langle
owners_k,
audience_k,
R_k,
trustedInfluencers_k,
requiredIntegrity_k,
requirements_k
\right\rangle.
$$

It answers:

1. whose authority permits release;
2. who may receive it;
3. which exact semantic function may be revealed;
4. who may influence the released value or release occurrence;
5. what integrity is required; and
6. which authentication, proof, or sanitization steps are mandatory.

### 15.2 Static checks

For:

```mlir
%r = ifc.release %v {policy = @k}
```

check:

- $k\in\Delta$;
- the audience matches;
- owners authorize the downgrade;
- the current `pc` has sufficient integrity;
- the decrypting host is authorized;
- prerequisites have been discharged;
- the release is not duplicated or reordered illegally.

### 15.3 Relational check

Hold the authorized function equal:

$$
R_k(\sigma_0)=R_k(\sigma_1),
$$

then ask whether any other visible event differs. This catches protocol oracles where both runs release `invalid` but differ in mismatch position, operation count, or error class.

### 15.4 Decryption is not release

$$
\operatorname{decrypt}\neq\operatorname{release}.
$$

Decryption changes representation. Release expands an audience. They require separate operations and proof rules.

---

## 16. Mechanism contracts

Version 1 validates a programmer- or frontend-supplied mechanism assignment. Automatic mechanism synthesis is future work.

### 16.1 Contract schema

$$
\mathcal K(M)=
\left\langle
participants,
hosts,
controllers,
corruptionModel,
inputRepresentations,
outputRepresentations,
supportedOps,
visibleFacets,
traceContract,
integrityGuarantee,
assumptions
\right\rangle.
$$

### 16.2 FHE example

An ideal FHE evaluator contract may state:

```text
participants:
  client key holder, server evaluator

server can observe:
  ciphertext bytes, ciphertext count, public dimensions,
  parameter set, operation schedule, transfer size

server cannot observe:
  abstract plaintext payload

decryptors:
  client only

integrity:
  not guaranteed unless an additional proof mechanism is used

assumptions:
  cryptographic security, key secrecy, backend conformance
```

The verifier proves correct use of this contract; it does not prove lattice hardness.

### 16.3 Opaque call example

```mlir
%r = func.call @openfhe_eval(%ct)
  {ifc.contract = @openfhe_eval_contract}
```

The contract must specify payload exposure, shape exposure, timing, memory behavior, host, and output representation.

### 16.4 Contract substitution

For ideal mechanism $M$ and concrete backend $B$:

$$
B\preceq^{contract}M
$$

means the backend produces no observation beyond the ideal contract and computes the required function. The desired substitution theorem is:

$$
\operatorname{Secure}(P[M])
\land
B\preceq^{contract}M
\Longrightarrow
\operatorname{Secure}(P[B]).
$$

---

## 17. L4: obligations ledger

### 17.1 Purpose

An obligation records a condition required to lift an IR-level proof to the intended deployment.

The conditional soundness statement is:

$$
\operatorname{Secure}_\Theta(P)
\land
\operatorname{Adequate}(\Theta,platform)
\Longrightarrow
\operatorname{Secure}_{real}(P).
$$

If adequacy is not established, the correct result is conditional.

### 17.2 Obligation categories

```text
backend constant-time lowering
register-allocation preservation
runtime helper latency
opaque library information-flow contract
FHE cryptographic assumption
circuit-privacy sanitization
DIT/DOIT requirement
GPU isolation and scratch initialization
speculation exclusion
key-placement assumption
```

### 17.3 Structured obligation record

```text
id: O-17
kind: runtime-latency-contract
host: server_cpu
observer: [server]
protected_principals: [client]
source_ops: [%42, %43]
target_symbol: __muldi3
required_property: operand-independent latency
status: outstanding
```

An outstanding load-bearing obligation prevents an unconditional `verified` result.

---

## 18. Proposed MLIR extension interfaces

The names below are architectural proposals rather than fixed upstream APIs.

### 18.1 `PolicyPropagationInterface`

An operation declares how result facets depend on operand facets and `pc`:

```cpp
SecurityTransferResult inferSecurity(
    Operation *op,
    ArrayRef<SecurityDescriptor> operands,
    const ProgramPointState &state,
    const PolicyEnvironment &env);
```

### 18.2 `SecurityEffectInterface`

An operation declares observable effects:

```cpp
SmallVector<SecurityEffect> getSecurityEffects(
    Operation *op,
    const SecurityAnalysisState &state,
    const TargetProfile &target);
```

### 18.3 `MechanismContractInterface`

Provides representation and visibility semantics.

### 18.4 `TargetLeakageInterface`

Defines:

- address abstraction;
- latency classes;
- constant-time operation contracts;
- helper-call behavior; and
- hardware obligations.

### 18.5 `CallSecuritySummaryInterface`

Describes external function output, memory, timing, placement, and release effects.

### 18.6 `LoweringRepresentationInterface`

Provides source-target state relations for transformations such as bufferization and outlining.

---

## 19. Proposed pass pipeline

A possible command-line decomposition is:

```text
--ifc-normalize-policy
--ifc-infer
--ifc-extract-effects
--ifc-static-check
--ifc-relational-verify
--ifc-security-tv
--ifc-emit-obligations
--ifc-report
```

### 19.1 Pass responsibilities

#### `ifc-normalize-policy`

- resolve symbols;
- normalize ACLs;
- validate hosts, coalitions, contracts, and releases.

#### `ifc-infer`

- solve label constraints;
- compute descriptors, `pc`, abstract memory, and provenance.

#### `ifc-extract-effects`

- instantiate event semantics under $\Theta$;
- calculate actor visibility.

#### `ifc-static-check`

- discharge obvious effects;
- identify definite violations;
- queue relational obligations.

#### `ifc-relational-verify`

- slice;
- self-compose;
- lower to the MLIR SMT dialect or SMT-LIB;
- solve and lift witnesses.

#### `ifc-security-tv`

- compare before/after IR snapshots;
- check actor-indexed security refinement;
- localize the first bad pass.

#### `ifc-emit-obligations`

- serialize unresolved backend, mechanism, and hardware assumptions.

#### `ifc-report`

- emit human-readable diagnostics, JSON, and CI status.

### 19.2 Analysis invalidation

After every security-relevant transformation:

```text
invalidate inferred descriptors
recompute actor-aware dataflow
recompute effects
run or reuse security-TV result
```

Only persistent policy facts may be trusted across arbitrary passes.

---

## 20. Diagnostics and proof artifacts

A good diagnostic is actor-specific and relational:

```text
security result: unsafe
observer coalition: [server]
protected owner: client
executing host: server_host
property: exact-address trace noninterference

secret input 0:
  token_index = 4
secret input 1:
  token_index = 81

first divergence:
  operation: tensor.extract at model.mlir:82
  run 0: memory(cache-line 17)
  run 1: memory(cache-line 21)

lowering pass:
  lower-tensor-gather

target profile:
  server-x86-exact-address

suggested actions:
  use an oblivious gather mechanism
  make the index public under an authorized release
  move the operation to a host allowed to observe the index
```

The verifier should emit:

- source locations;
- actor and host names;
- policy path and provenance;
- concrete paired inputs;
- first divergent event;
- first security-breaking pass;
- target profile;
- obligations; and
- machine-readable proof status.

---

## 21. Trusted computing base

The result depends on the correctness of:

1. the semantics of supported MLIR operations;
2. policy normalization and authority solving;
3. the abstract interpretation;
4. self-composition;
5. SMT encoding;
6. the solver result;
7. target profiles;
8. mechanism and call contracts;
9. source-target representation relations; and
10. everything below the final verified IR, unless separately discharged.

The architecture should make this TCB visible in every proof report.

---

## 22. Principal theorem statements

### 22.1 Label-inference soundness and principality

$$
\operatorname{Infer}(P)=\Gamma^*
\Longrightarrow
\Gamma^*\models\mathcal C(P).
$$

For every valid assignment $\Gamma$:

$$
\Gamma\vdash P
\Longrightarrow
\Gamma^*\preceq\Gamma.
$$

### 22.2 Abstract-analysis soundness

If concrete state $\sigma$ is represented by abstract state $\widehat\sigma$, then one concrete step is covered by the abstract transfer function:

$$
\sigma\in\gamma(\widehat\sigma)
\land
\sigma\xrightarrow{op/e}\sigma'
\Longrightarrow
\sigma'\in\gamma(F_{op}(\widehat\sigma)).
$$

The abstract event dependency must overapproximate concrete dependence.

### 22.3 Source IFC soundness

$$
\mathcal E;\Delta;\Theta
\vdash
P\triangleright\Omega
\land
\operatorname{Discharged}(\Omega)
\Longrightarrow
\forall A\in\mathcal A.
\operatorname{Secure}_{A,\Theta,\Delta}(P).
$$

### 22.4 SMT encoding correctness

For the exact bounded fragment:

$$
\operatorname{SAT}(\Phi_{leak})
\Longleftrightarrow
\text{a modeled violating execution pair exists}.
$$

`UNKNOWN` yields no theorem.

### 22.5 Security translation validation

$$
\operatorname{UNSAT}(\Phi_{regress}(S,T,A))
\Longrightarrow
S\preceq^{sec}_{A,\Theta,\Delta}T.
$$

### 22.6 End-to-end preservation

$$
\operatorname{Secure}_{A,\Theta,\Delta}(S)
\land
S\preceq^{sec}_{A,\Theta,\Delta}T
\Longrightarrow
\operatorname{Secure}_{A,\Theta,\Delta}(T).
$$

### 22.7 Pass composition

$$
P_0\preceq_A^{sec}P_1
\land
P_1\preceq_A^{sec}P_2
\Longrightarrow
P_0\preceq_A^{sec}P_2.
$$

### 22.8 Platform adequacy

$$
\operatorname{Secure}_{A,\Theta}(P)
\land
\operatorname{Adequate}(\Theta,platform)
\Longrightarrow
\operatorname{Secure}_{A,real}(P).
$$

---

## 23. Worked flow: secret tensor index on a server

Consider:

```mlir
func.func @lookup(
  %table: tensor<1024xi32> {
    ifc.value_policy = #ifc.public,
    ifc.shape_policy = #ifc.public,
    ifc.host = @server_host
  },
  %index: index {
    ifc.value_policy = #ifc.acl<owners=[@client], readers=[@client]>,
    ifc.host = @client_host
  }) -> i32 {
  %x = tensor.extract %table[%index]
  return %x : i32
}
```

### 23.1 L0

The threat model contains coalition:

$$
A=\{\mathsf{server}\}.
$$

The server controls `server_host` and can observe its exact addresses.

### 23.2 L1

The result label is:

$$
\ell_{value}(x)
=
\ell_{value}(table)
\sqcup
\ell_{index}(index).
$$

The memory event dependency is:

$$
\ell_{addr}
=
\ell_{index}(index)
\sqcup
\ell_{shape}(table)
\sqcup
\ell_{layout}(table).
$$

The server is not authorized to learn the index, so the event requires relational proof or rejection.

### 23.3 L2

Create $index^0,index^1$ with:

$$
0\le index^0,index^1<1024.
$$

Because the index is hidden from the server, do not constrain them equal.

$$
addr^j=base+4\cdot index^j.
$$

Ask:

$$
addr^0\neq addr^1.
$$

The solver returns, for example:

$$
index^0=0,
\qquad
index^1=1.
$$

The program is unsafe for the server observer under exact-address observation.

### 23.4 Repair options

- oblivious full scan;
- ORAM or an approved oblivious-gather mechanism;
- a trusted hardware primitive with a contract;
- moving the access to an authorized host; or
- an explicit policy release if learning the index is intended.

### 23.5 L3

If the source uses an oblivious scan but lowering replaces it with direct indexing, the regression query finds a target-only address difference.

---

## 24. Worked flow: two-owner FHE inference

Suppose:

```text
client input      readable only by client
provider weights  readable only by provider
server            may see protected representations only
final class ID    released to client
```

### 24.1 Combined policy

An intermediate depending on both inputs receives combined authority:

$$
\ell_{joint}
=
\ell_{client}
\sqcup
\ell_{provider}.
$$

No single party may read the joint plaintext unless the release policy explicitly allows it.

### 24.2 Representation transitions

$$
\begin{aligned}
input_{plain}
&\xrightarrow{conceal}
input_{FHE},\\
weights_{plain}
&\xrightarrow{conceal}
weights_{FHE},\\
result_{FHE}
&\xrightarrow{decrypt\;at\;client}
result_{plain},\\
result_{plain}
&\xrightarrow{release\;@prediction}
classID_{client}.
\end{aligned}
$$

The semantic policies survive concealment and decryption. Only release changes the audience.

### 24.3 Server projection

The FHE contract may expose:

$$
\langle
shape,
ciphertextCount,
transferSize,
operationSchedule
\rangle
$$

while abstracting the plaintext payload.

The relational query checks whether two client/provider secret assignments with the same authorized final class create different server-visible metadata or traces.

### 24.4 Negative mutations

The verifier should reject:

- removing a `conceal`;
- decrypting on the server;
- exposing a secret shape through transfer size;
- passing ciphertext to an opaque helper without a contract;
- returning logits when only `argmax` is authorized;
- bufferizing into a server-readable plaintext memref.

---

## 25. Minimum viable implementation

### 25.1 Supported policy features

- named principals and hosts;
- controller declarations;
- simple principal formulas or reader/influencer ACLs;
- declared observer coalitions;
- explicit release policies;
- explicit mechanism contracts.

### 25.2 Supported dialects

- `arith`;
- bounded `scf`;
- selected `cf`;
- static-shape `tensor`;
- structured `linalg`;
- a restricted `memref` subset;
- HEIR `secret` boundaries;
- project-specific `ifc` operations.

### 25.3 Supported leakage model

- public outputs and placement;
- branch outcomes;
- exact memory addresses;
- finite operation counts;
- selected target-variable-latency operations;
- transfer endpoints and sizes;
- errors and releases.

### 25.4 Solver fragment

- fixed-width bitvectors;
- bounded loops;
- finite static tensors;
- SMT arrays for restricted memory;
- bounded traces;
- no unrestricted recursion.

### 25.5 Mechanisms

- local plaintext execution;
- ideal FHE placement;
- one oblivious-gather contract;
- opaque-call contracts.

Automatic FHE/MPC/ZKP selection is deferred.

---

## 26. Future extension: verified mechanism synthesis

A later phase may insert a Viaduct-style synthesis layer:

```text
minimum-authority inference
        ↓
candidate host/representation/mechanism assignments
        ↓
security-hard constraints + cost optimization
        ↓
generated MLIR plan
        ↓
relational verification
        ↓
counterexample-guided resynthesis
```

Let $\Pi$ be a mechanism assignment. Synthesis solves:

$$
\Pi^*
=
\arg\min_{\Pi}
\operatorname{Cost}(\Pi)
\quad\text{subject to}\quad
\operatorname{StaticValid}(\Pi,P).
$$

Security remains a hard constraint. The relational verifier independently certifies the selected plan:

$$
\operatorname{Optimizer\;proposes},
\qquad
\operatorname{Verifier\;certifies}.
$$

Counterexample-guided synthesis can block an insecure plan and select padding, oblivious access, FHE, MPC, or a different placement.

---

## 27. Evaluation architecture

The implementation should be tested across four corpora:

1. **source-level vulnerable/fixed pairs**;
2. **compiler-preservation cases**;
3. **tensor- and party-native cases**; and
4. **negative-control obligations** that the tool must refuse to certify.

Measurements should include:

- detection rate;
- false positives;
- annotation burden;
- dataflow time;
- SMT time and timeout rate;
- fraction discharged statically;
- first-bad-pass localization quality;
- counterexample reproducibility;
- target-profile sensitivity; and
- number and type of outstanding obligations.

---

## 28. Final architectural invariant

Every component should preserve the separation:

$$
\boxed{
\text{policy}
\neq
\text{representation}
\neq
\text{placement}
\neq
\text{observation}
}
$$

The complete reasoning chain is:

$$
\boxed{
\begin{array}{c}
\text{principal and host policies}\\
\Downarrow\\
\text{actor-aware dataflow dependencies}\\
\Downarrow\\
\text{observable-effect summaries}\\
\Downarrow\\
\text{two-run SMT noninterference}\\
\Downarrow\\
\text{security-preserving translation validation}\\
\Downarrow\\
\text{conditional deployment theorem + obligations}
\end{array}
}
$$

The verifier does not prove a vague statement that “the program contains secrets.” It proves, for every declared principal or coalition:

- which facets it may observe;
- which hosts it controls;
- which representations protect hidden values;
- which releases are authorized;
- which target effects are modeled;
- whether compilation introduced a new distinction; and
- which backend or hardware assumptions remain outstanding.

---

## References and design lineage

- Coşku Acay, Rolph Recto, Joshua Gancher, Andrew C. Myers, and Elaine Shi. *Viaduct: An Extensible, Optimizing Compiler for Secure Distributed Programs*. PLDI 2021.
- Andrew C. Myers and related work on decentralized information-flow control.
- Owen Arden, Jed Liu, and Andrew C. Myers. *Flow-Limited Authorization*. CSF 2015.
- Ethan Cecchetti, Andrew C. Myers, and Owen Arden. *Nonmalleable Information Flow Control*. CCS 2017.
- MLIR dataflow analysis, bufferization, and SMT dialect documentation.
- Bang et al. *SMT-Based Translation Validation for Machine Learning Compiler*. CAV 2022.
- HEIR secret-dialect documentation.
- Project research plan, competitive landscape, threat model, and actor-aware lecture notes.
