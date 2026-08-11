# Module 4 — Actors, Principals, ACLs, Hosts, and Authority

## Learning objectives

After this module, you should be able to:

1. distinguish an actor, principal, host, owner, controller, observer, and coalition;
2. explain the difference between access-control lists and information-flow labels;
3. use reader/influencer sets as a first multi-principal security lattice;
4. understand Viaduct-style principal formulas and the acts-for relation;
5. form confidentiality-and-integrity labels and their flows-to relation;
6. state actor-relative low-equivalence and trace projection;
7. check whether a value may be exposed at a host under a given representation;
8. generate principal-aware information-flow constraints for an MLIR program.

> **Viaduct reading map.** The architecture diagram is on PDF page 2; principal formulas and confidentiality/integrity labels are introduced on pages 3–4; label inference appears on pages 7–8; protocol-assignment validity and optimization appear on pages 9–10; and protocol composition appears on page 11.

---

## 1. Why `High` and `Low` are not enough

A two-point lattice is an excellent way to learn information flow:

$$
\mathsf{Low}\sqsubseteq\mathsf{High}.
$$

It is insufficient for the distributed programs we want to compile.

Consider private inference with three parties:

```text
client:    owns the private query
provider:  owns the private model
server:    performs outsourced computation
```

The following values have different policies:

```text
query:          client may read
model weights:  provider may read
ciphertexts:    server may store, but not decrypt
prediction:     eventually released to client
```

Calling both the query and weights simply `High` loses the main policy distinction. It cannot express that the client must not learn the model and the provider must not learn the query.

The security architecture therefore needs named participants and explicit trust relationships.

---

## 2. Vocabulary: one word is not enough

Security papers often use several nearby terms. We will use them carefully.

### Principal

A **principal** is an identity or authority named by the policy.

Examples:

```text
client
provider
server-operator
hospital
researcher
GPU-runtime
```

The set of base principals is written

$$
\mathcal P=\{C,P,S,\ldots\}.
$$

A principal is not necessarily a process or machine. It is the entity whose permission or trust matters.

### Actor

In these notes, **actor** is an informal umbrella term for an active participant in the system. An actor may submit data, run code, receive output, or control a host.

For formal writing, prefer **principal** or **party**. The word *actor* can be confused with the actor concurrency model.

### Host

A **host** is an execution or storage location:

$$
\mathcal H=\{h_C,h_P,h_S,h_{GPU},\ldots\}.
$$

Examples include:

- a client's laptop;
- an inference server;
- a GPU address space;
- an enclave;
- an MPC participant process.

A host has a trust or authority description. We write

$$
L(h)
$$

for the authority assigned to host $h$.

### Controller

A **controller** is a principal or coalition that can inspect or modify a host.

A simple environment might contain

$$
\operatorname{controllers}(h_S)=\{S\}.
$$

A more realistic environment may say that both the cloud operator and a system administrator can inspect a host.

### Owner

An **owner** is a principal whose authority is required to weaken a policy. Ownership is about policy authority, not necessarily current possession.

The client may own the confidentiality policy of a query even after an encrypted representation is transferred to the server.

### Observer

An **observer** is the principal or coalition for which we are proving confidentiality.

We write the observer as

$$
A.
$$

The same program must often be checked for several observers:

```text
server observer
client observer
provider observer
client + server coalition
provider + server coalition
```

### Coalition

A **coalition** is a set or formula of principals that may collude.

A value hidden from the server alone might become visible to the coalition

$$
\{\mathsf{server},\mathsf{keyHolder}\}.
$$

A threat model must say which coalitions are considered.

---

## 3. ACLs and IFC solve different problems

An access-control list for object $o$ might be

$$
ACL(o)=\langle R(o),W(o)\rangle,
$$

where:

- $R(o)$ is the set of principals allowed to read the object;
- $W(o)$ is the set of principals allowed to write the object.

An ACL answers a local question:

> May principal $p$ perform this read or write now?

Information-flow control answers a global question:

> After information has been read and transformed, where may the derived information flow?

### ACL-only failure

Suppose a file has

```text
readers = {client}
```

and the client process is allowed to read it:

```c
secret = read(file);
public_socket.send(secret);
```

The file ACL did its job: only the client read the file. But the information was copied to a public socket.

IFC attaches a policy to the information itself:

$$
\ell(secret)=\mathsf{clientOnly}.
$$

The derived output keeps that dependency and the send is rejected.

### Practical relationship

Our compiler may offer ACL-like syntax because it is intuitive:

```mlir
{ifc.readers = [@client], ifc.writers = [@client]}
```

But its semantics is information-flow semantics. The policy propagates through SSA operations, control dependence, memory, and lowering.

A useful rule of thumb is:

$$
\boxed{
\text{ACLs protect objects at access points; IFC protects information after it moves.}
}
$$

---

## 4. A first principal model: reader and influencer sets

Before introducing principal formulas, use a concrete set model.

For a value $v$, define

$$
\ell(v)=\langle R(v),I(v)\rangle,
$$

where:

- $R(v)\subseteq\mathcal P$ lists principals allowed to learn the information;
- $I(v)\subseteq\mathcal P$ lists principals that may have influenced the information.

The second component is intentionally called an **influencer set**, not merely a writer ACL. It records provenance after computation.

### Permitted flow

Information with label $\ell_1=\langle R_1,I_1\rangle$ may flow to $\ell_2=\langle R_2,I_2\rangle$ when

$$
\ell_1\sqsubseteq\ell_2
\quad\Longleftrightarrow\quad
R_2\subseteq R_1
\;\land\;
I_1\subseteq I_2.
$$

Why?

- The destination may not add new readers.
- The destination must acknowledge every principal that may already have influenced the value.

### Join

When two values influence one result,

$$
\ell_1\sqcup\ell_2
=
\langle R_1\cap R_2,\; I_1\cup I_2\rangle.
$$

The result is readable only by principals allowed to read both sources, and it may have been influenced by anyone who influenced either source.

### Example

Client query:

$$
\ell_q=\langle\{C\},\{C\}\rangle.
$$

Provider weights:

$$
\ell_w=\langle\{P\},\{P\}\rangle.
$$

A result depending on both has

$$
\ell_r
=
\ell_q\sqcup\ell_w
=
\langle\varnothing,\{C,P\}\rangle.
$$

No principal is initially authorized to read the joint plaintext result. A protected mechanism can compute it, and a later release may authorize a particular output.

---

## 5. Why sets are sometimes too weak

Reader sets work well for many policies, but they do not naturally express threshold and combined authority.

Examples:

```text
Alice and Bob together may authorize release.
Any two of three key holders may decrypt.
Either the hospital or the patient may read.
The server may influence a result only if a verifier approves it.
```

For this, Viaduct follows the FLAM tradition and uses formulas over principals.

---

## 6. Principal formulas and the acts-for relation

Let principal expressions be

$$
p,q ::= A\mid B\mid 0\mid 1\mid p\land q\mid p\lor q.
$$

The relation

$$
p\Rightarrow q
$$

is read as:

> $p$ acts for $q$, or $p$ has at least the authority of $q$.

It behaves like logical implication. For example,

$$
A\land B\Rightarrow A
$$

and

$$
A\Rightarrow A\lor B.
$$

Intuitively:

- $A\land B$ represents combined authority;
- $A\lor B$ represents authority common to either principal;
- $0$ is maximal authority;
- $1$ is minimal authority.

The names $0$ and $1$ can feel reversed if you are thinking of Boolean false and true. Treat them as lattice extrema rather than truth values.

### Example

If a release requires both client and provider approval, its authority requirement can contain

$$
C\land P.
$$

A principal possessing only $C$ does not act for $C\land P$.

---

## 7. Confidentiality and integrity labels

A Viaduct-style label is a pair

$$
\ell=\langle C(\ell),I(\ell)\rangle.
$$

Here:

- $C(\ell)$ is the authority required to read the information;
- $I(\ell)$ is the authority required to influence or vouch for the information.

For shorthand, a principal $A$ may denote

$$
\langle A,A\rangle.
$$

We can also project the components:

$$
\ell^{\mathsf C}=\langle C(\ell),1\rangle,
\qquad
\ell^{\mathsf I}=\langle 1,I(\ell)\rangle.
$$

### Reading and influencing

An authority $a$ may read data labeled $\ell$ when

$$
a\Rightarrow C(\ell).
$$

It has enough integrity authority for the data when

$$
a\Rightarrow I(\ell).
$$

These equations are an abstract policy relation. The actual runtime visibility also depends on host placement and representation.

---

## 8. The flows-to relation

The information-flow order is

$$
\ell_1\sqsubseteq\ell_2
\quad\Longleftrightarrow\quad
C(\ell_2)\Rightarrow C(\ell_1)
\;\land\;
I(\ell_1)\Rightarrow I(\ell_2).
$$

The confidentiality direction is reversed because moving to a destination with a stronger reading requirement is safe.

The integrity direction is forward because the destination must not claim more trust than the source justifies.

### Join and meet

Viaduct defines

$$
\ell_1\sqcup\ell_2
=
\langle
C(\ell_1)\land C(\ell_2),
I(\ell_1)\lor I(\ell_2)
\rangle,
$$

and

$$
\ell_1\sqcap\ell_2
=
\langle
C(\ell_1)\lor C(\ell_2),
I(\ell_1)\land I(\ell_2)
\rangle.
$$

The join combines dependencies just as the set model did:

- confidentiality becomes more restrictive;
- integrity records that either source may have influenced the result.

### Two-owner result

Let

$$
\ell_q=\langle C,C\rangle,
\qquad
\ell_w=\langle P,P\rangle.
$$

Then

$$
\ell_q\sqcup\ell_w
=
\langle C\land P, C\lor P\rangle.
$$

Reading requires combined confidentiality authority. The integrity component says the value may depend on either input principal.

---

## 9. Hosts carry authority too

A host declaration associates a host with authority:

$$
L:\mathcal H\rightarrow\mathcal L.
$$

A simplified MLIR declaration might look like:

```mlir
ifc.host @client_host {
  controllers = [@client],
  authority = #ifc.label<conf = @client, integ = @client>
}

ifc.host @server_host {
  controllers = [@server],
  authority = #ifc.label<conf = @server, integ = @server>
}
```

The host label does not mean every value on the host automatically has that label. It describes what the host can safely see or be trusted to compute.

### Plaintext placement

If a plaintext facet labeled $\ell_f$ is exposed on host $h$, a basic requirement is

$$
C(L(h))\Rightarrow C(\ell_f).
$$

If the server does not act for client confidentiality, client plaintext cannot be placed there.

### Protected placement

A ciphertext may be placed on the server even though the underlying information remains client-confidential. The representation contract says which facets are exposed.

This is why the complete rule is not merely

$$
C(L(h))\Rightarrow C(\ell_f).
$$

It is

$$
\operatorname{Exposed}_{\Pi,\Theta}(A,h,\rho,f)
\Longrightarrow
\operatorname{CanRead}(A,\ell_f).
$$

The representation $\rho$ may hide element values while revealing shape and transfer size.

---

## 10. Actor-relative observations

There is no single universal trace. Each observer sees a projection.

Let

$$
\pi_{A,\Theta}(\tau)
$$

retain exactly the events visible to observer coalition $A$ under target profile $\Theta$.

Then

$$
\operatorname{Trace}_{A,\Theta}(P,\sigma)
=
\pi_{A,\Theta}(\operatorname{Trace}(P,\sigma)).
$$

For a server observer, the projection may include:

- server branch outcomes;
- server memory addresses;
- transfer sizes entering the server;
- plaintext values exposed in server memory;
- ciphertext metadata allowed by the cryptographic contract.

For a client observer, it may instead include:

- client-side decryption;
- final released prediction;
- messages delivered to the client;
- client-side timing.

A single event can therefore be security-relevant for one actor and invisible to another.

---

## 11. Actor-relative low-equivalence

Two states are low-equivalent for observer $A$ when they agree on everything $A$ is initially authorized to observe:

$$
\sigma_0\approx_A\sigma_1.
$$

With facet policies, this means equality is imposed separately.

For every input facet $f$:

$$
\operatorname{CanRead}(A,\ell_f)
\Longrightarrow
f(\sigma_0)=f(\sigma_1).
$$

Hidden facets may differ.

### Example

Suppose the client can read the query and final result, while the server can see only public shape.

For the server query:

$$
shape_0=shape_1,
$$

but

$$
query_0\text{ and }query_1
$$

are independent.

For the client query, the input query is already visible to the client, so the two runs constrain it equal. The hidden model weights may differ.

Security is therefore always indexed by an observer:

$$
\operatorname{Secure}_A(P).
$$

---

## 12. Coalitions and collusion

Checking only singleton observers can be unsound.

Suppose an FHE server sees ciphertexts and a separate key service holds the decryption key. Neither actor alone sees plaintext, but the coalition does.

Let the relevant threat set be

$$
\mathcal A
\subseteq
2^{\mathcal P}.
$$

The compiler proves

$$
\forall A\in\mathcal A.\;\operatorname{Secure}_A(P).
$$

The threat model may exclude some coalitions. Threshold MPC, for example, is secure only below a corruption threshold.

### Monotonicity warning

Security against a larger coalition is usually stronger, but observations and authority need not be represented by simple set inclusion when integrity and cryptographic thresholds are involved. State the coalition model explicitly rather than assuming it.

---

## 13. Program-counter labels become actor-aware

Consider code running on the server:

```mlir
scf.if %client_secret_condition {
  ...
}
```

The branch context becomes

$$
pc'=pc\sqcup\ell(%client\_secret\_condition).
$$

If the server can observe the branch, the branch effect requires the server to be authorized for that combined label, or the computation must use an oblivious/protected mechanism.

A conceptual rule is

$$
\frac{
\Gamma\vdash c:\ell_c
\qquad
pc'=pc\sqcup\ell_c
\qquad
\operatorname{ObserverAllowed}(h,pc')
}{
\Gamma;pc;h\vdash \texttt{if }c\texttt{ then }s_1\texttt{ else }s_2
}.
$$

In our stronger trace model, merely hiding the final assigned values is not enough. The host must also be unable to distinguish branch outcomes, operation counts, addresses, and other events.

---

## 14. ACL changes versus declassification

A normal flow must not silently expand the reader set.

In the set model, this is forbidden:

$$
R_{dest}\not\subseteq R_{source}.
$$

An explicit sanctioned release may intentionally expand readers:

$$
\{C\}
\longrightarrow
\{C,P\}.
$$

But that transition requires policy authority, an exact release function, and integrity checks. It is not an ordinary assignment.

The original SSA value remains protected. A release produces a new SSA value with a new policy.

---

## 15. Constraint generation and minimum-authority inference

The compiler need not require a label annotation on every SSA value.

For

```mlir
%z = arith.addi %x, %y
```

generate constraints

$$
\ell_x\sqsubseteq\ell_z,
\qquad
\ell_y\sqsubseteq\ell_z,
\qquad
pc\sqsubseteq\ell_z.
$$

For an output to host $h$, generate a host-authority constraint. In a simplified form:

$$
\ell_{output}\sqsubseteq L(h).
$$

For a branch involving hosts $H$, require every participating host to be allowed to know the guard, unless the branch is converted into a protected oblivious computation.

Viaduct translates flows-to constraints into acts-for constraints and solves them to obtain a minimum-authority assignment. The important architecture lesson is:

$$
\boxed{
\text{infer principal labels with a fast lattice solver; use SMT later for semantic noninterference.}
}
$$

The label solver answers *what authority is required*. The relational SMT solver answers *whether two secret-varying executions can actually be distinguished*.

---

## 16. Worked example: two-owner tensor computation

Assume:

```text
principal C: client
principal P: provider
principal S: server
```

Inputs:

$$
\ell(x)=\langle C,C\rangle,
\qquad
\ell(w)=\langle P,P\rangle.
$$

Hosts:

$$
L(h_C)=C,
\qquad
L(h_P)=P,
\qquad
L(h_S)=S.
$$

The plaintext multiplication result has

$$
\ell(y)=\ell(x)\sqcup\ell(w)
=
\langle C\land P,C\lor P\rangle.
$$

Neither $C$, $P$, nor $S$ alone acts for $C\land P$. Therefore no one may receive the joint intermediate in plaintext.

A valid implementation can instead use a mechanism:

```text
representation: threshold-FHE ciphertext or MPC share
placement:      server/MPC hosts
visible facets: public shape and protocol metadata
plaintext:      hidden
```

A release policy may later reveal

$$
R(x,w)=\operatorname{argmax}(model(w,x))
$$

to the client.

The release does not authorize the client to see $w$, logits, or arbitrary intermediates.

---

## 17. Viaduct's architecture and our extension

Viaduct's architecture is:

```text
partially labeled source
        ↓
label inference
        ↓
protocol selection with a cost model
        ↓
distributed program and runtime backends
```

Its central insight is that the authority requirements of program components and the guarantees of protocols can be described using the same principal-label language.

A protocol $M$ with authority label $L(M)$ may implement a component requiring $\ell$ when

$$
L(M)\Rightarrow\ell.
$$

Our compiler keeps that idea and adds three requirements:

1. tensor facets have separate principal-indexed policies;
2. mechanism contracts state exactly which facets and trace events are visible;
3. relational translation validation checks the actual emitted MLIR and its lowerings.

So authority labels guide placement and mechanism choice, while relational verification checks artifact-level behavior.

---

## 18. How this appears in MLIR

A possible surface representation is:

```mlir
ifc.principal @client
ifc.principal @provider
ifc.principal @server

ifc.host @server_host {
  controllers = [@server],
  authority = #ifc.label<conf = @server, integ = @server>
}

func.func @infer(
  %x: tensor<1x128xi16>
    {ifc.value_policy = #ifc.acl<readers = [@client],
                                 influencers = [@client]>,
     ifc.shape_policy = #ifc.public,
     ifc.host = @client_host},
  %w: tensor<128x128xi16>
    {ifc.value_policy = #ifc.acl<readers = [@provider],
                                 influencers = [@provider]>,
     ifc.shape_policy = #ifc.public,
     ifc.host = @provider_host})
```

The ACL syntax is only a front-end convenience. Internally, it can be normalized to principal formulas and placed in the security descriptor.

Most intermediate labels should remain analysis facts rather than permanent IR annotations.

---

## 19. Design rules for the research compiler

1. **Do not equate actor with host.** A principal may control several hosts, and a protocol may span several hosts.
2. **Do not equate ownership with readability.** Owners authorize policy changes; readers receive information.
3. **Do not equate ACLs with IFC.** ACLs are boundary checks; IFC propagates dependencies.
4. **Do not equate placement with policy.** A ciphertext can be on a server while its plaintext policy remains client-only.
5. **Do not check only singleton attackers.** State the permitted coalition model.
6. **Do not omit integrity around release.** An unauthorized actor controlling the release guard can turn declassification into an oracle.
7. **Do not ask SMT to infer the principal lattice.** Use a monotone label solver first.
8. **Do not call the public research abstraction “actor-based” without defining it.** Prefer principal-based or party-labeled IFC in papers.

---

## 20. Common mistakes

### Mistake 1: “The server stores it, so the server may read it”

False for ciphertexts, shares, opaque handles, and enclave-protected values. Representation determines exposure.

### Mistake 2: “The client owns it, so only the client may ever receive a result derived from it”

A sanctioned release can authorize a specific derived function for another audience.

### Mistake 3: “A write ACL is the same as integrity”

An integrity policy records who may have influenced derived information and who is trusted to vouch for it. It is not merely a list checked at one store operation.

### Mistake 4: “Public” is global

Public often means public to a specified observer or coalition. In a multi-party system, always name the observer.

### Mistake 5: “MPC means no party learns anything”

MPC reveals its declared outputs and may expose protocol metadata. Its security also depends on the allowed corruption coalition.

---

## 21. Exercises

### Exercise 1 — vocabulary

For a client/server FHE application, identify:

- principals;
- hosts;
- controllers;
- observer coalitions;
- policy owners.

### Exercise 2 — ACL flow

Let

$$
\ell_1=\langle\{A,B\},\{A\}\rangle,
\qquad
\ell_2=\langle\{A\},\{A,B\}\rangle.
$$

Determine whether $\ell_1\sqsubseteq\ell_2$.

### Exercise 3 — join

Compute the set-model join of

$$
\langle\{C\},\{C\}\rangle
\quad\text{and}\quad
\langle\{P\},\{P\}\rangle.
$$

Explain the confidentiality and integrity results.

### Exercise 4 — acts-for

Which of the following hold?

$$
A\land B\Rightarrow A,
\qquad
A\Rightarrow A\land B,
\qquad
A\Rightarrow A\lor B.
$$

### Exercise 5 — actor-relative equivalence

A tensor has client-secret elements and public shape. Write the equalities imposed between two executions for:

1. a server observer;
2. a client observer.

### Exercise 6 — ACL versus IFC

Construct a program that passes every file ACL check but leaks information through a derived public output. Explain how IFC rejects it.

### Exercise 7 — host placement

A client-confidential FHE ciphertext with public shape is placed on a server. List which facets may be visible to the server under a reasonable ideal-FHE contract.

### Exercise 8 — coalition

Give a system that is secure against each of two principals separately but insecure against their coalition.

---

## 22. Summary

The distributed security model has four distinct layers:

$$
\boxed{
\text{principals express authority}
}
$$

$$
\boxed{
\text{hosts express where execution and storage occur}
}
$$

$$
\boxed{
\text{labels/ACL views express who may learn or influence information}
}
$$

$$
\boxed{
\text{observer coalitions determine which relational property is checked}
}
$$

The central policy relation is

$$
\ell_1\sqsubseteq\ell_2,
$$

and the central actor-relative security property is

$$
\sigma_0\approx_A\sigma_1
\Longrightarrow
\operatorname{Trace}_{A,\Theta}(P,\sigma_0)
\sim
\operatorname{Trace}_{A,\Theta}(P,\sigma_1).
$$

The following modules apply this model to tensor facets, memory, SMT, lowering, release, and cryptographic mechanisms.

---

## Further reading

- Coşku Acay et al., *Viaduct: An Extensible, Optimizing Compiler for Secure Distributed Programs*, PLDI 2021, especially Sections 2–4.
- Owen Arden, Jed Liu, and Andrew C. Myers, *Flow-Limited Authorization*, CSF 2015.
- Andrew C. Myers and Barbara Liskov, decentralized information-flow control.
- Steve Zdancewic and Andrew C. Myers, robust declassification.
- Ethan Cecchetti, Andrew C. Myers, and Owen Arden, nonmalleable information flow control.
