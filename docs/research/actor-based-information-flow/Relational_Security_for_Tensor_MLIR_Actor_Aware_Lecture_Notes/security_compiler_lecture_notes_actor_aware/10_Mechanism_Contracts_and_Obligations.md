# Module 10 — Mechanism Contracts and Obligations

## Learning objectives

After this module, you should be able to:

1. distinguish policy from the mechanism used to enforce policy;
2. define an ideal security-mechanism contract;
3. model FHE, MPC, local execution, and opaque calls;
4. explain why cryptographic correctness is an assumption boundary;
5. use obligations as conditional premises of a sound theorem;
6. understand how Viaduct-style protocol assignment can be extended for tensor MLIR;
7. relate Viaduct-style protocol authority labels to actor, host, coalition, and facet-exposure contracts.

---

## 1. Policy does not choose an implementation by itself

A policy might say:

```text
client input must remain hidden from server
provider weights must remain hidden from client
final class ID may be released to client
```

Several mechanisms might implement this:

- fully homomorphic encryption;
- multiparty computation;
- trusted hardware;
- local execution;
- a hybrid protocol.

The information-flow policy says **what must be protected**.

A mechanism contract says **what an implementation reveals and assumes**.

---

## 2. From protocol labels to richer contracts

Viaduct characterizes protocols using authority labels and selects protocols whose authority is sufficient for the inferred security requirement.

For tensor MLIR, use a richer contract:

$$
\mathcal K(M)=
\left\langle
\begin{array}{l}
Authority(M),\\
Hosts(M),\\
InputReprs(M),\\
OutputReprs(M),\\
SupportedOps(M),\\
VisibleFacets(M),\\
TraceContract_\Theta(M),\\
ReleaseContract(M),\\
Assumptions(M),\\
Cost_\Theta(M)
\end{array}
\right\rangle.
$$

This contract states both who must be trusted and what observations remain visible.

---

## 3. Viaduct-style authority labels for mechanisms

Viaduct associates every protocol $M$ with an authority label $L(M)$. A protocol may realize a component requiring label $\ell$ only when

$$
L(M)\Rightarrow\ell.
$$

This gives a uniform way to compare local execution, replication, commitments, zero-knowledge proofs, and MPC.

### Local execution

For `Local(h)`, the protocol authority is the authority of host $h$:

$$
L(Local(h))=L(h).
$$

Plaintext storage and computation are exposed to principals controlling that host.

### Commitments and zero-knowledge proofs

A commitment can preserve the committer's confidentiality while increasing confidence that a value is not changed. A zero-knowledge proof lets a verifier trust a result without learning the prover's witness beyond the declared output.

The actor roles must be explicit:

```text
prover
verifier
plaintext holder
commitment holder
output recipient
```

### MPC

An MPC contract names participating hosts and a corruption model. Its confidentiality guarantee may fail only for coalitions exceeding a threshold; its integrity guarantee differs between semi-honest and malicious security.

Thus a contract contains a predicate

$$
AllowedCoalition_M(A)
$$

rather than a vague statement that “MPC is secure.”

### Why our contract is richer than one authority label

An authority label is necessary but insufficient for tensor and side-channel verification. Our mechanism contract also records

$$
\langle
hosts,
representations,
visibleFacets,
traceContract,
coalitionModel,
assumptions
\rangle.
$$

For example, FHE may satisfy the element-value confidentiality requirement for the server while exposing shape, ciphertext count, and operation schedule. The label says who is protected; the visibility contract says exactly what the protected mechanism still reveals.

---

## 4. Ideal versus concrete mechanisms

An **ideal mechanism** has a simple semantic contract.

Example ideal FHE:

```text
server learns ciphertext metadata but not plaintext payload
designated key holder can decrypt
evaluation computes the declared plaintext function
```

A concrete library such as OpenFHE or another backend is assumed or separately verified to implement that ideal contract.

Write

$$
B\preceq^{contract}M
$$

when concrete backend $B$ refines ideal mechanism $M$.

Then a substitution theorem can state

$$
Secure(P[M])
\land
B\preceq^{contract}M
\Longrightarrow
Secure(P[B]).
$$

The compiler does not prove lattice hardness. It proves that the program uses the mechanism within its declared interface.

---

## 5. Local plaintext execution

Contract:

$$
M=Local(h).
$$

Possible fields:

```text
hosts:
  h

input representations:
  plaintext

visible facets:
  all plaintext facets to controllers of h

trace:
  ordinary branch, address, count, call, and latency events

assumptions:
  target profile Theta
```

A computation requiring client-only confidentiality cannot run in plaintext on a server controlled by the server.

---

## 6. FHE contract

A simplified FHE mechanism:

$$
M=FHE(pk,evaluator,decryptors).
$$

### Payload confidentiality

Unauthorized evaluator does not observe abstract plaintext payload, under the cryptographic assumption.

### Metadata visibility

The evaluator may observe:

- ciphertext bytes;
- ciphertext count;
- parameter set;
- tensor dimensions;
- packing layout;
- transfer size;
- operation schedule.

Those facets require independent policies.

### Decryption authority

Only declared decryptors may convert ciphertext to plaintext.

### Supported operations

Depends on scheme and backend:

- additions;
- multiplications;
- rotations;
- comparisons only through special constructions;
- bootstrapping;
- approximate arithmetic.

### Cost

May depend on:

$$
\#mult,
\quad
\#rotate,
\quad
depth,
\quad
\#bootstrap,
\quad
ciphertextBytes.
$$

### Missing properties

Ordinary FHE does not automatically provide:

- evaluator result integrity;
- circuit privacy;
- hidden shape;
- hidden communication pattern;
- constant-time client decryption.

Those become separate mechanisms or obligations.

---

## 7. MPC contract

A simplified MPC mechanism:

$$
M=MPC(H,t,model).
$$

Fields:

```text
participants:
  H

corruption threshold:
  t

security model:
  semi-honest or malicious

representation:
  secret shares

visible behavior:
  message endpoints, counts, sizes, rounds
  according to observer profile

supported operations:
  protocol-specific
```

Security depends on coalition assumptions.

A single share may reveal nothing, but a threshold coalition can reconstruct the secret.

MPC does not automatically hide:

- message sizes;
- number of rounds;
- control-dependent protocol selection;
- participant dropout;
- timing, unless modeled.

---

## 8. Oblivious memory contract

A mechanism for secret gather:

$$
M=ObliviousGather(h).
$$

Contract:

```text
logical result:
  table[index]

address trace:
  independent of index

operation count:
  fixed public bound

supported layout:
  declared dense or ORAM representation

assumptions:
  backend preserves the oblivious primitive
```

Possible implementations:

- full scan with masked selection;
- ORAM;
- approved hardware primitive;
- MPC or FHE subprotocol.

The compiler can reason against the abstract contract and separately validate the lowering.

---

## 9. Opaque calls

An external call is a trust boundary.

```mlir
%r = func.call @crypto_helper(%x)
```

A call contract should specify:

$$
\begin{aligned}
&ValueDeps,\\
&MemoryReads,\\
&MemoryWrites,\\
&AddressDeps,\\
&ControlDeps,\\
&LatencyDeps,\\
&HostExposure,\\
&RepresentationEffects,\\
&ReleaseEffects.
\end{aligned}
$$

Example:

```text
@ct_compare:
  reads buffers a and b
  writes no memory
  output = equality(a,b)
  address trace = sequential over public length
  operation count = public length
  latency class = fixed
  retains no pointers
```

Without a contract, the sound result is

```text
unknown or obligation outstanding
```

not safe.

---

## 10. Obligations are premises, not apologies

A compiler theorem is always relative to a model.

Suppose the compiler proves

$$
Secure_\Theta(P).
$$

This means $P$ is secure under target profile $\Theta$.

To transfer the claim to a real platform, require

$$
Adequate(\Theta,platform).
$$

Then:

$$
Secure_\Theta(P)
\land
Adequate(\Theta,platform)
\Longrightarrow
Secure_{real}(P).
$$

If adequacy is not proved, emit it as an obligation.

Example result:

```text
verified:
  no secret-dependent branches or software addresses

outstanding:
  __muldi3 must have operand-independent timing
  backend must preserve oblivious select
  DIT must be enabled for this region
```

The result is conditional but meaningful.

---

## 11. Why "safe" is wrong at an unmodeled boundary

Suppose MLIR lowers a secret multiplication to:

```text
call __muldi3
```

The IR-level verifier cannot see inside the helper.

Reporting SAFE assumes the helper is constant-time without evidence.

Correct outcomes:

- discharge the obligation with a verified helper contract;
- continue validation into the helper;
- mark the result conditional;
- return UNKNOWN.

---

## 12. Why "the project is useless" is also wrong

No compiler proof covers every physical effect.

A useful theorem can still prove:

- output confidentiality;
- host placement;
- software path equality;
- exact address equality;
- operation-count equality;
- target-declared latency classes;
- correct release discipline.

It should state where the proof stops.

This is standard modular verification: prove components relative to interfaces, then compose when interfaces are discharged.

---

## 13. Hardware obligations

Examples:

### Backend constant-time select

```text
obligation:
  ifc.oblivious_select lowers without secret-dependent branch
```

### Runtime helper

```text
obligation:
  __muldi3 timing class is independent of secret operands
```

### Data-independent timing mode

```text
obligation:
  DIT/DOIT is enabled and covers relevant instructions
```

### Speculation

If speculation is outside the model:

```text
out of scope:
  transient execution observations
```

Do not encode an unsupported hardware guarantee as a Boolean attribute that anyone can set without evidence. Obligations should name evidence or a verifier expected to discharge them.

---

## 14. Cryptographic obligations

### Semantic security

Ciphertext payload confidentiality relies on a scheme assumption and parameter choice.

### Key management

Correct keys must be generated, stored, and assigned to the declared principals.

### Circuit privacy

If server function privacy is required, ordinary FHE may be insufficient.

### Approximate decryption

Approximate schemes may require sanitization or a proof that released ciphertext/noise behavior is safe.

### MPC assumptions

Corruption threshold and adversary model must match deployment.

The compiler records and checks use of these assumptions; it does not invent the cryptographic theorem.

---

## 15. Structured obligation record

A useful artifact is:

```yaml
id: obligation-17
kind: target-latency
subject: __muldi3
region: client_decrypt
property: operand-independent-latency
observer: local-server
target: riscv32
status: outstanding
evidence_required:
  - verified implementation
  - target manual contract
introduced_by_pass: convert-arith-to-llvm
```

This is more useful than a warning string because CI and downstream tools can consume it.

---

## 16. Valid mechanism assignment

Let

$$
\Pi:Ops\to Mechanisms.
$$

An assignment is valid when every operation's inferred requirement is satisfied.

A conceptual judgment is

$$
\Sigma;\Delta;\Theta;\Pi
\models
op@M
:
D
\triangleright\Omega.
$$

Premises include:

$$
M\in Viable(op),
$$

$$
Authority(M)\Rightarrow Requirement(op),
$$

$$
RepresentationsCompatible,
$$

$$
FacetExposureSafe,
$$

$$
TraceSafe_\Theta,
$$

$$
ReleaseSafe_\Delta.
$$

A v1 verifier can check a programmer-provided assignment.

A later synthesizer can search for an optimal assignment.

---

## 17. Mechanism selection as constrained optimization

Security constraints are hard constraints:

$$
Valid(\Pi,P).
$$

Then optimize:

$$
\Pi^*
=
\arg\min_{\Pi:Valid(\Pi,P)}
Cost_\Theta(\Pi).
$$

A useful lexicographic objective is

$$
\left\langle
|\Omega_\Pi|,
TCBWeight(\Pi),
Latency(\Pi),
Bandwidth(\Pi),
Memory(\Pi)
\right\rangle.
$$

This first minimizes outstanding assumptions and trusted code, then performance.

Do not allow a weighted objective to trade confidentiality for speed.

---

## 18. Counterexample-guided mechanism synthesis

A future system can run:

$$
Synthesize
\to
Verify
\to
Block
\to
Resynthesize.
$$

Example:

1. optimizer chooses FHE with unpadded secret shape;
2. relational verifier finds different transfer sizes;
3. add constraint requiring public padding or shape-hiding mechanism;
4. optimizer selects padded FHE or MPC.

The validator becomes an independent certification layer for synthesized plans.

---

## 19. Two-owner example

Policy:

$$
Readers(x)=\{client\},
$$

$$
Readers(W)=\{provider\}.
$$

Candidate mechanisms:

### Plain server execution

Rejected: server sees both.

### Plain client execution

Rejected: client sees provider weights.

### FHE under client key

May protect client input from server, but can expose provider function or weights depending on protocol and output structure.

### Threshold or multi-key FHE

Potentially valid under an appropriate key and release contract.

### MPC

Potentially valid under a declared collusion and integrity model.

### Hybrid

Potentially lowest cost.

The contract framework forces every hidden assumption into the plan.

---

## 20. Contract composition

Suppose:

```text
client local encryption
→ server FHE evaluation
→ client local decryption
→ sanctioned release
```

Each boundary must compose.

If $M_1$ outputs representation $\rho$, then $M_2$ must accept $\rho$.

If $M_1$ exposes shape, the policy must authorize it.

If $M_2$ returns a ciphertext lacking circuit privacy, the release policy may require a sanitizer before decryption.

Compositional checking is a type-and-effect system over mechanism interfaces.

---

## 21. Common mistakes

### Mistake 1: the mechanism label is the data label

Mechanisms implement policy; they are not the policy.

### Mistake 2: FHE hides every facet

Metadata and schedules may remain visible.

### Mistake 3: external crypto call is automatically safe

It needs a contract.

### Mistake 4: an obligation is equivalent to verification failure

It is a conditional premise, provided it is explicit and auditable.

### Mistake 5: a user-set `trusted=true` attribute discharges an obligation

Evidence must be meaningful.

### Mistake 6: protocol optimization may trade security for cost

Security belongs in constraints, not a soft objective.

---

## 22. Exercises

### Exercise 1

Write a contract for a local constant-time comparison helper.

### Exercise 2

List the visible facets of a typical FHE ciphertext tensor on the evaluator.

### Exercise 3

Why does ordinary FHE not automatically prove evaluator integrity?

### Exercise 4

Give an obligation generated when a protected tensor crosses into an opaque GPU runtime.

### Exercise 5

Design a valid mechanism assignment for two-party private set intersection using only abstract mechanism contracts.

### Exercise 6

Explain how a counterexample about transfer size could change mechanism synthesis.

---

## 23. Summary

A mechanism is selected for actors, not just for data types. Its contract names the participating hosts, the coalitions against which it is secure, the authority it supplies, and the facet and trace observations it exposes.


A mechanism contract states:

$$
\boxed{
\text{what it computes}
+
\text{what it reveals}
+
\text{who participates}
+
\text{what it assumes}.
}
$$

An obligation is a missing premise in the end-to-end theorem, not a silent guess.

The next module assembles the individual definitions into a proof architecture.

---

## Further reading

- C. Acay et al., [Viaduct](https://www.cs.cornell.edu/andru/papers/viaduct/viaduct.pdf).
- C. Acay et al., [formal Viaduct security report](https://www.cs.cornell.edu/andru/papers/viaduct-formal/viaduct-formal-tr.pdf).
- HEIR [`secret` dialect](https://heir.dev/docs/dialects/secret/).
- Universal composability and ideal functionality as advanced follow-up topics.
