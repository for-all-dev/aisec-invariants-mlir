# Relational Security for Tensor MLIR
## A Thirteen-Module Course for Compiler Students — Actor-Aware Edition

These notes introduce the theory and implementation of a compiler that checks confidentiality properties of tensor programs and verifies that compiler lowering preserves those properties.

The intended reader has taken an undergraduate programming-languages course and is comfortable with:

- operational semantics;
- type systems;
- control-flow graphs and SSA;
- basic dataflow analysis;
- common compiler optimizations;
- elementary propositional logic.

No prior low-level-security, distributed-systems security, or cryptography background is assumed.

---

## What changed in this edition

This edition inserts a new module immediately after the introductory IFC type-system module:

> **Actors, Principals, ACLs, Hosts, and Authority**

The module distinguishes principal identity from execution placement, explains ACLs versus IFC, introduces reader/influencer sets, Viaduct-style acts-for formulas, confidentiality/integrity authority, coalitions, host labels, and actor-relative low-equivalence.

Every later module has been revised to use that model:

- tensor facets now carry principal-indexed policies;
- memory is divided into actor-controlled host address spaces;
- SMT queries are generated per observer coalition;
- translation validation preserves each actor's indistinguishability relation;
- release changes named audiences under named owner authority;
- mechanism contracts include participants and corruption coalitions;
- proofs quantify over the actor environment;
- the MLIR implementation contains principal, host, ACL, and threat declarations;
- every case study begins with an actor and observer matrix.

---

## Course thesis

A security-aware semantics records what an observer can learn:

$$
\langle P,\sigma\rangle\Downarrow(v,\tau).
$$

For observer coalition $A$, confidentiality is

$$
\sigma_0\approx_A^\Delta\sigma_1
\Longrightarrow
Trace_{A,\Theta}(P,\sigma_0)
\sim
Trace_{A,\Theta}(P,\sigma_1).
$$

A compiler must preserve that relation for every coalition in the threat model:

$$
\forall A\in\mathcal A.\quad
Trace_A(S,\sigma_0)\sim Trace_A(S,\sigma_1)
\Longrightarrow
Trace_A(T,\sigma_0)\sim Trace_A(T,\sigma_1).
$$

---

## Reading order

1. [Operational Semantics with Security Traces](01_Operational_Semantics_with_Security_Traces.md)
2. [Hyperproperties and Relational Reasoning](02_Hyperproperties_and_Relational_Reasoning.md)
3. [Information-Flow Type Systems](03_Information_Flow_Type_Systems.md)
4. [Actors, Principals, ACLs, Hosts, and Authority](04_Actors_Principals_ACLs_Hosts_and_Authority.md)
5. [Tensor-Aware Information Flow](05_Tensor_Aware_Information_Flow.md)
6. [Memory, Pointers, Aliasing, and Bufferization](06_Memory_Pointers_Aliasing_and_Bufferization.md)
7. [Self-Composition and SMT](07_Self_Composition_and_SMT.md)
8. [Security Translation Validation](08_Security_Translation_Validation.md)
9. [Sanctioned Release and Robust Declassification](09_Sanctioned_Release_and_Robust_Declassification.md)
10. [Mechanism Contracts and Obligations](10_Mechanism_Contracts_and_Obligations.md)
11. [Proof Architecture](11_Proof_Architecture.md)
12. [Implementation in MLIR](12_Implementation_in_MLIR.md)
13. [Case Studies](13_Case_Studies.md)

Module 6 remains intentionally longer. Memory, aliasing, host address spaces, and bufferization are where an SSA-level security argument most easily becomes unsound.

---

## Terminology rule

These notes use **actor** informally. Formal statements use:

- **principal/party** for policy identity and authority;
- **host** for an execution or storage location;
- **controller** for a principal that can inspect or modify a host;
- **observer coalition** for the attacker view being verified.

This avoids confusing principal-based IFC with the actor concurrency model.

---

## Running examples

### Private tensor lookup

```mlir
func.func @lookup(
    %table: tensor<1024xi32>,
    %secret_index: index
) -> i32 {
  %x = tensor.extract %table[%secret_index]
  return %x : i32
}
```

Actor interpretation:

```text
client: owns the secret index
server: executes the lookup and observes memory behavior
```

### Two-owner private inference

```text
client input:      readable only by client
provider weights:  readable only by provider
server placement:  protected representations only
final prediction:  sanctioned release to client
```

This forces us to separate principal policy, host placement, runtime representation, mechanism contract, release audience, and observer coalition.

---

## Core notation

| Notation | Meaning |
|---|---|
| $\mathcal P$ | Base principals or parties |
| $\mathcal H$ | Hosts or address spaces |
| $A$ | Observer principal or coalition |
| $\mathcal A$ | Threat-model set of observer coalitions |
| $L(h)$ | Authority assigned to host $h$ |
| $p\Rightarrow q$ | Principal $p$ acts for $q$ |
| $\ell=\langle C,I\rangle$ | Confidentiality/integrity label |
| $ACL=\langle R,I\rangle$ | Reader/influencer presentation of a policy |
| $P,S,T$ | Program, source program, target program |
| $\sigma$ | Concrete state |
| $\tau$ | Security trace |
| $\Theta$ | Target leakage profile |
| $\Delta$ | Sanctioned-release policy environment |
| $pc$ | Program-counter label |
| $D(v)$ | Security descriptor for SSA value $v$ |
| $\rho$ | Runtime representation |
| $h$ | Actual host or device placement |
| $\Omega$ | Outstanding obligations |
| $\sqsubseteq$ | Permitted information-flow relation |
| $\sqcup$ | Join of dependencies |
| $\approx_A$ | Low-equivalence for observer $A$ |
| $\sim_{A,\Theta}$ | Observational equivalence |

---

## Suggested laboratory sequence

1. Add branch events to a tiny interpreter.
2. Implement a two-point IFC lattice and `pc` labels.
3. Add principals, host declarations, ACL syntax, and one observer coalition.
4. Solve reader-set or principal-formula flow constraints.
5. Add tensor facets and an MLIR security descriptor.
6. Implement per-host memory effects and a conservative `tensor.extract` address check.
7. Encode an actor-indexed bounded branch example in SMT.
8. Detect a `select`-to-branch security regression for a server observer.
9. Add an authorized release to a named audience.
10. Add an ideal FHE mechanism contract and a two-owner example.
11. Produce a localized two-input, actor-named counterexample.

---

## Primary references

- C. Acay et al., *Viaduct: An Extensible, Optimizing Compiler for Secure Distributed Programs*, PLDI 2021.
- O. Arden, J. Liu, and A. Myers, *Flow-Limited Authorization*, CSF 2015.
- E. Cecchetti, A. Myers, and O. Arden, *Nonmalleable Information Flow Control*, CCS 2017.
- MLIR, *Writing DataFlow Analyses*.
- MLIR, *Bufferization*.
- MLIR, *SMT Dialect*.
- S. Bang et al., *SMT-Based Translation Validation for Machine Learning Compiler*, CAV 2022.
- HEIR, `secret` dialect documentation.
