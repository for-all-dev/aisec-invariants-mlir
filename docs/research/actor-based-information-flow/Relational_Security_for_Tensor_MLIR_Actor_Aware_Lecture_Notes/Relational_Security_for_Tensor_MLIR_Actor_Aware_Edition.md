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

\[
\langle P,\sigma\rangle\Downarrow(v,\tau).
\]

For observer coalition \(A\), confidentiality is

\[
\sigma_0\approx_A^\Delta\sigma_1
\Longrightarrow
Trace_{A,\Theta}(P,\sigma_0)
\sim
Trace_{A,\Theta}(P,\sigma_1).
\]

A compiler must preserve that relation for every coalition in the threat model:

\[
\forall A\in\mathcal A.\quad
Trace_A(S,\sigma_0)\sim Trace_A(S,\sigma_1)
\Longrightarrow
Trace_A(T,\sigma_0)\sim Trace_A(T,\sigma_1).
\]

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
| \(\mathcal P\) | Base principals or parties |
| \(\mathcal H\) | Hosts or address spaces |
| \(A\) | Observer principal or coalition |
| \(\mathcal A\) | Threat-model set of observer coalitions |
| \(L(h)\) | Authority assigned to host \(h\) |
| \(p\Rightarrow q\) | Principal \(p\) acts for \(q\) |
| \(\ell=\langle C,I\rangle\) | Confidentiality/integrity label |
| \(ACL=\langle R,I\rangle\) | Reader/influencer presentation of a policy |
| \(P,S,T\) | Program, source program, target program |
| \(\sigma\) | Concrete state |
| \(\tau\) | Security trace |
| \(\Theta\) | Target leakage profile |
| \(\Delta\) | Sanctioned-release policy environment |
| \(pc\) | Program-counter label |
| \(D(v)\) | Security descriptor for SSA value \(v\) |
| \(\rho\) | Runtime representation |
| \(h\) | Actual host or device placement |
| \(\Omega\) | Outstanding obligations |
| \(\sqsubseteq\) | Permitted information-flow relation |
| \(\sqcup\) | Join of dependencies |
| \(\approx_A\) | Low-equivalence for observer \(A\) |
| \(\sim_{A,\Theta}\) | Observational equivalence |

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

---

# Module 1 — Operational Semantics with Security Traces

## Learning objectives

After this module, you should be able to:

1. extend an ordinary operational semantics with observable events;
2. distinguish internal computation from attacker-visible behavior;
3. define traces and observer projections;
4. explain why equal functional outputs do not imply equal security behavior;
5. design an event alphabet for a compiler security model.

---

## 1. From values to observable behavior

An ordinary big-step semantics has the form

\[
\langle c,\sigma\rangle \Downarrow \sigma',
\]

meaning that command \(c\), starting from state \(\sigma\), terminates in state \(\sigma'\).

For an expression, we might write

\[
\langle e,\sigma\rangle \Downarrow v.
\]

This is enough for many compiler-correctness questions. If two programs produce the same result for every input, they may be functionally equivalent.

Security needs more information. Two executions can return the same result while taking different branches, touching different addresses, or placing plaintext on different hosts.

We therefore enrich the semantics:

\[
\langle c,\sigma\rangle \Downarrow (\sigma',\tau),
\]

where \(\tau\) is a sequence of security-relevant events.

The trace is a **ghost object** in the semantics. A deployed program does not have to write it to a log. It is a mathematical record of what the threat model says an observer can distinguish.

---

## 2. A small language

Consider this toy language.

### Expressions

\[
e ::= n \mid x \mid e_1 \oplus e_2
\]

### Commands

\[
\begin{aligned}
c ::= {}&
\mathbf{skip}
\mid x := e
\mid c_1;c_2\\
&\mid \mathbf{if}\ e\ \mathbf{then}\ c_t\ \mathbf{else}\ c_f\\
&\mid \mathbf{while}\ e\ \mathbf{do}\ c\\
&\mid x := \mathbf{load}(e)\\
&\mid \mathbf{store}(e_a,e_v)\\
&\mid \mathbf{output}_h(e).
\end{aligned}
\]

A concrete state is

\[
\sigma = \langle \rho,\mu\rangle,
\]

where:

- \(\rho : \mathrm{Var}\to\mathrm{Val}\) maps variables to values;
- \(\mu : \mathrm{Addr}\to\mathrm{Val}\) maps memory addresses to values.

---

## 3. Events

A useful event alphabet for the toy language is

\[
\begin{aligned}
\alpha ::= {}&
\epsilon\\
&\mid \mathsf{branch}(s,b)\\
&\mid \mathsf{exec}(s,op)\\
&\mid \mathsf{memory}(s,a,w,k)\\
&\mid \mathsf{output}(s,h,v)\\
&\mid \mathsf{error}(s,k).
\end{aligned}
\]

Here:

- \(s\) is a static program site;
- \(b\) is a branch outcome;
- \(a\) is an address or an abstract address class;
- \(w\) is an access width;
- \(k\) distinguishes read and write, or identifies an error class;
- \(\epsilon\) is an unobservable internal step.

For tensor MLIR, we will later add events such as

\[
\mathsf{shape},\quad
\mathsf{allocation},\quad
\mathsf{kernelLaunch},\quad
\mathsf{transfer},\quad
\mathsf{variableLatency},\quad
\mathsf{release}.
\]

The event alphabet defines the **security envelope**. A theorem cannot protect observations omitted from the model.

---

## 4. Labeled small-step semantics

A labeled transition has the form

\[
\langle c,\sigma\rangle
\xrightarrow{\alpha}
\langle c',\sigma'\rangle.
\]

The trace of a complete execution is the concatenation of all nonempty labels.

### Assignment

Assignment is usually not directly observable:

\[
\frac{
\langle e,\sigma\rangle \Downarrow v
}{
\langle x:=e,\sigma\rangle
\xrightarrow{\epsilon}
\langle \mathbf{skip},\sigma[x\mapsto v]\rangle
}.
\]

We may optionally emit an `exec` event if operation counts are observable.

### Conditional

Let site \(s\) identify this conditional.

\[
\frac{
\langle e,\sigma\rangle\Downarrow \mathbf{true}
}{
\langle
\mathbf{if}^{s}\ e\ \mathbf{then}\ c_t\ \mathbf{else}\ c_f,
\sigma
\rangle
\xrightarrow{\mathsf{branch}(s,\mathbf{true})}
\langle c_t,\sigma\rangle
}
\]

and similarly for false.

The branch result is in the trace even when both branches compute the same final value.

### Load

\[
\frac{
\langle e,\sigma\rangle\Downarrow a
\qquad
\mu(a)=v
}{
\langle x:=\mathbf{load}^{s}(e),\langle\rho,\mu\rangle\rangle
\xrightarrow{\mathsf{memory}(s,a,w,\mathsf{read})}
\langle
\mathbf{skip},
\langle\rho[x\mapsto v],\mu\rangle
\rangle
}.
\]

### Store

\[
\frac{
\langle e_a,\sigma\rangle\Downarrow a
\qquad
\langle e_v,\sigma\rangle\Downarrow v
}{
\langle
\mathbf{store}^{s}(e_a,e_v),
\langle\rho,\mu\rangle
\rangle
\xrightarrow{\mathsf{memory}(s,a,w,\mathsf{write})}
\langle
\mathbf{skip},
\langle\rho,\mu[a\mapsto v]\rangle
\rangle
}.
\]

### Output

\[
\frac{
\langle e,\sigma\rangle\Downarrow v
}{
\langle \mathbf{output}^{s}_h(e),\sigma\rangle
\xrightarrow{\mathsf{output}(s,h,v)}
\langle\mathbf{skip},\sigma\rangle
}.
\]

---

## 5. Traces

A finite trace is a sequence

\[
\tau = \alpha_0\alpha_1\cdots\alpha_{n-1}.
\]

The empty trace is \(\varepsilon\). Concatenation is written \(\tau_1\cdot\tau_2\).

A big-step judgment with traces can be defined by taking the reflexive transitive closure of the small-step relation:

\[
\langle c,\sigma\rangle
\xRightarrow{\tau}
\langle \mathbf{skip},\sigma'\rangle.
\]

We may then abbreviate this as

\[
\langle c,\sigma\rangle\Downarrow(\sigma',\tau).
\]

### Why order matters

These traces are different:

```text
memory(A), memory(B)
```

```text
memory(B), memory(A)
```

Even if the same two addresses are eventually touched, an observer may distinguish the order.

### Why multiplicity matters

These traces are different:

```text
exec(add), exec(add)
```

```text
exec(add), exec(add), exec(add)
```

This is how finite secret-dependent operation counts enter the model.

---

## 6. Observer projection

The complete semantic trace may contain more information than a particular principal can observe.

Let

\[
\pi_{A,\Theta}(\tau)
\]

project trace \(\tau\) to events observable by principal or coalition \(A\), under target profile \(\Theta\).

The observer trace is

\[
\operatorname{Trace}_{A,\Theta}(P,\sigma)
=
\pi_{A,\Theta}
\left(
\operatorname{Trace}(P,\sigma)
\right).
\]

Examples:

- A server sees operations and memory accesses executed on the server.
- The server may see a ciphertext's size but not its idealized plaintext payload.
- A cache-line observer sees \(\lfloor a/64\rfloor\), not the exact byte address.
- A client may see the final released result but not server-local intermediate buffers.

A target profile can define

\[
\mu_\Theta(a)=
\begin{cases}
a & \text{exact-address model}\\
\left\lfloor a/64\right\rfloor & \text{cache-line model}\\
\left\lfloor a/4096\right\rfloor & \text{page model}.
\end{cases}
\]

The memory event exposed to the observer is then

\[
\mathsf{memory}(s,\mu_\Theta(a),w,k).
\]

---

## 7. Worked example: same result, different trace

Consider:

```c
if (secret)
    result = 5;
else
    result = 5;
```

Both executions return \(5\). Functionally,

\[
\operatorname{Result}(P,\mathsf{false})
=
\operatorname{Result}(P,\mathsf{true})
=
5.
\]

But the traces are

\[
\tau_0=
[\mathsf{branch}(s,\mathsf{false})]
\]

and

\[
\tau_1=
[\mathsf{branch}(s,\mathsf{true})].
\]

If branch outcomes are observable,

\[
\tau_0\not\sim\tau_1.
\]

This is the smallest example showing why functional equivalence does not imply confidentiality.

---

## 8. Worked example: same control path, different address

Consider:

```c
x = table[secret_index];
```

Both executions perform one load and follow the same control-flow graph. If array elements have width \(4\),

\[
a = base + 4\cdot secretIndex.
\]

Two executions may generate

\[
\mathsf{memory}(s,base,\;4,\mathsf{read})
\]

and

\[
\mathsf{memory}(s,base+400,\;4,\mathsf{read}).
\]

The control-flow path is identical, but the security traces differ.

This is why a trace is broader than a path.

---

## 9. Variable-latency events

Suppose the target has operand-dependent division timing. We can emit

\[
\mathsf{variableLatency}
\left(
s,\mathsf{div},
\operatorname{lat}_\Theta(x,y)
\right).
\]

The function \(\operatorname{lat}_\Theta\) need not be an exact cycle count. It can return an abstract equivalence class.

For a conservative model,

\[
\operatorname{lat}_\Theta(\mathsf{div},x,y)
=
\langle x,y\rangle.
\]

That means different latency-relevant operands are treated as potentially distinguishable.

For a trusted constant-time helper,

\[
\operatorname{lat}_\Theta(\mathsf{ctDiv},x,y)
=
\mathsf{fixed}.
\]

The target profile is part of the theorem. If the hardware leaks more than the profile models, the theorem becomes conditional on a profile-adequacy obligation.

---

## 10. Determinism and nondeterminism

So far, a program and state determine one trace. Real systems may have nondeterminism from:

- thread scheduling;
- allocator choices;
- random coins;
- external calls;
- asynchronous communication.

Then a program denotes a **set** of traces:

\[
\llbracket P\rrbracket(\sigma)
\subseteq \mathrm{Trace}.
\]

Security must specify how nondeterminism is coupled across the two executions.

Typical options are:

1. compare executions under the same public nondeterministic choices;
2. quantify over all schedulers;
3. model random coins as secret or public inputs;
4. use a simulation-based definition for distributed protocols.

The first compiler prototype should use a sequential, deterministic core and make other effects explicit obligations.

---

## 11. Designing an event alphabet

A good event model is:

- strong enough to express the bugs you claim to catch;
- simple enough to encode and reason about;
- explicit about what it omits.

A reasonable tensor-compiler alphabet is

\[
\begin{aligned}
e ::= {}&
\mathsf{output}(h,v)
\mid \mathsf{expose}(h,f,\rho,v)\\
&\mid \mathsf{branch}(s,b)
\mid \mathsf{call}(s,t)\\
&\mid \mathsf{exec}(s,op)
\mid \mathsf{memory}(s,a,w,k)\\
&\mid \mathsf{allocation}(s,n)
\mid \mathsf{shape}(s,\bar d)\\
&\mid \mathsf{kernelLaunch}(s,k)
\mid \mathsf{transfer}(s,h_1,h_2,n)\\
&\mid \mathsf{variableLatency}(s,op,c)
\mid \mathsf{error}(s,k)\\
&\mid \mathsf{release}(s,p,k,v).
\end{aligned}
\]

Do not silently treat speculation, physical power, or data-memory-dependent prefetch behavior as covered unless the semantics includes them.

---

## 12. Common mistakes

### Mistake 1: treating the trace as a debug log

A semantic trace is defined by the threat model. It need not correspond to existing logging code.

### Mistake 2: putting only outputs in the trace

This misses timing, address, count, and placement channels.

### Mistake 3: modeling exact cycle counts too early

Abstract timing classes are usually easier to state and less brittle.

### Mistake 4: adding every physical effect

An unusably detailed model is not automatically more sound. It is better to define a precise software model and list hardware assumptions explicitly.

### Mistake 5: forgetting event occurrence

Even if a release payload is constant, whether the event occurs can reveal a secret.

---

## 13. Exercises

### Exercise 1

Give the traces for both executions of:

```c
if (secret)
    output(0);
else
    output(0);
```

under:

1. output-only observations;
2. output-plus-branch observations.

### Exercise 2

Define an event rule for an allocation

```c
p = alloc(n);
```

when the observer sees allocation size but not the returned address.

### Exercise 3

A target observer sees only cache-line numbers. Let the cache line size be \(64\). Are addresses \(128\) and \(160\) distinguishable? What about \(128\) and \(192\)?

### Exercise 4

Add a `call(target)` event for indirect calls. Explain why a secret-dependent call target can leak even when every callee returns the same value.

### Exercise 5

Write trace semantics for a bounded `for` loop. Make operation-count leakage explicit.

---

## 14. Summary

The central move is

\[
\text{ordinary semantics}
\quad\longrightarrow\quad
\text{ordinary result plus observer trace}.
\]

Once traces exist, we can define confidentiality by comparing traces from two executions. The next module explains why that comparison is a hyperproperty.

---

## Further reading

- A. Sabelfeld and A. Myers, surveys on language-based information-flow security.
- D. Clark et al., work on observational determinism and trace-based confidentiality.
- The project threat model for the proposed tensor-MLIR event alphabet.

---

# Module 2 — Hyperproperties and Relational Reasoning

## Learning objectives

After this module, you should be able to:

1. distinguish trace properties from hyperproperties;
2. define low-equivalence for an observer;
3. state termination-insensitive noninterference;
4. explain why constant-time behavior is a two-execution property;
5. understand why self-composition is possible for many confidentiality properties.

---

## 1. A property of one execution is not enough

A safety property typically classifies one trace at a time.

Examples:

- "No division by zero occurs."
- "No invalid memory address is accessed."
- "Every opened file is eventually closed."

If a single trace contains a bad event, that trace witnesses failure.

Confidentiality is different. One execution rarely tells us whether information leaked. We need to know whether changing a secret changes something visible.

Consider:

```c
output(secret);
```

A trace containing `output(7)` is not inherently insecure. It is insecure only relative to a policy saying the observer should not learn `secret`, and relative to another possible run where the secret differs.

The property compares multiple traces. Such a property is called a **hyperproperty**.

---

## 2. Trace properties and hyperproperties

Let \(\mathrm{Traces}\) be the set of all traces.

A trace property is a set

\[
P \subseteq \mathrm{Traces}.
\]

A program satisfies \(P\) when each of its traces belongs to \(P\).

A hyperproperty is a set of sets of traces:

\[
H \subseteq \mathcal P(\mathrm{Traces}).
\]

A program denotes a trace set \(T\), and satisfies \(H\) when

\[
T\in H.
\]

You do not need category theory to use this distinction. The practical lesson is:

> Confidentiality is about relationships among possible executions, not merely whether one execution contains a locally forbidden event.

---

## 3. Public and secret components

Suppose an input state is

\[
\sigma =
\langle
\mathsf{publicInput},
\mathsf{clientSecret},
\mathsf{providerSecret}
\rangle.
\]

An observer \(A\) is allowed to know only some components.

Define an observation of the initial state:

\[
\operatorname{low}_A(\sigma).
\]

Two states are **low-equivalent** for \(A\) when

\[
\sigma_0\approx_A\sigma_1
\quad\Longleftrightarrow\quad
\operatorname{low}_A(\sigma_0)
=
\operatorname{low}_A(\sigma_1).
\]

For a server observer, we might require equality of public dimensions and public configuration, while allowing client input and provider weights to differ.

Example:

```text
sigma_0:
  batch_size = 8
  client_secret = 42

sigma_1:
  batch_size = 8
  client_secret = 99
```

If the server may know `batch_size` but not `client_secret`, then

\[
\sigma_0\approx_{\mathsf{server}}\sigma_1.
\]

---

## 4. Noninterference

A deterministic program is termination-insensitively noninterfering for observer \(A\) when

\[
\forall \sigma_0,\sigma_1.\quad
\sigma_0\approx_A\sigma_1
\land
P(\sigma_0)\Downarrow
\land
P(\sigma_1)\Downarrow
\Longrightarrow
\operatorname{Obs}_A(P,\sigma_0)
\sim_A
\operatorname{Obs}_A(P,\sigma_1).
\]

Read this as:

> If two initial states look the same to the observer, then their executions must continue to look the same to that observer.

The hidden information is not allowed to interfere with observable behavior.

The observer may be:

- one party;
- a coalition of parties;
- a host plus a local timing attacker;
- an abstract cache-line observer.

---

## 5. Why this is a 2-safety property

A \(k\)-safety property can be refuted by \(k\) finite traces.

For basic deterministic noninterference, two traces suffice:

1. one execution with secret \(s_0\);
2. one execution with secret \(s_1\);
3. equal public inputs;
4. different visible observations.

The pair is a counterexample.

This makes noninterference a form of **2-safety** for the relevant finite semantics.

That observation is important because it suggests self-composition:

\[
P\times P
\]

runs two renamed copies of \(P\) and checks an ordinary safety assertion comparing their observations.

Not every security hyperproperty is reducible this simply, but the core property in this course is.

---

## 6. Output noninterference

Suppose observations include only final public output:

\[
\operatorname{Obs}^{\mathrm{out}}_A(P,\sigma)
=
\operatorname{PublicOutput}_A(P,\sigma).
\]

Then noninterference says changing secrets cannot change unauthorized outputs.

Example:

```c
public_result = secret & 1;
```

Choose \(secret_0=0\) and \(secret_1=1\). The public outputs differ, so the program violates output noninterference.

This is useful but incomplete for low-level security.

---

## 7. Trace noninterference and constant time

Let the observer see branch outcomes, memory addresses, operation counts, and target latency classes:

\[
\operatorname{Obs}^{\mathrm{ct}}_{A,\Theta}
=
\langle
\mathsf{branches},
\mathsf{addresses},
\mathsf{counts},
\mathsf{latencyClasses}
\rangle.
\]

Then

\[
\sigma_0\approx_A\sigma_1
\Longrightarrow
\operatorname{Obs}^{\mathrm{ct}}_{A,\Theta}(P,\sigma_0)
=
\operatorname{Obs}^{\mathrm{ct}}_{A,\Theta}(P,\sigma_1)
\]

is a constant-time-style noninterference property.

It does not mean physical wall-clock readings are identical. It means the specific software-level leakage observations in \(\Theta\) are identical.

### Example

```c
if (secret)
    x = 0;
else
    x = 0;
```

Output-only noninterference holds.

Trace noninterference fails if branch outcomes are observable.

This shows that "secure" is always relative to an observation model.

---

## 8. Observer-parametric security

The same program can be secure for one observer and insecure for another.

Suppose a ciphertext is sent to the server:

```text
payload: encrypted client data
shape: public
ciphertext count: public
```

For the client:

- plaintext is observable;
- decryption happens locally.

For the server:

- ciphertext representation is observable;
- idealized plaintext is not;
- shape and transfer size may be observable.

We write

\[
\operatorname{Obs}_{A,\Theta}
\]

rather than one global trace because parties have different views.

This is essential for distributed cryptographic compilation.

---

## 9. Coalitions and collusion

A policy should often quantify over coalitions

\[
A\subseteq\mathcal P
\]

rather than only individual principals.

For secret sharing, one server share may reveal nothing, while a threshold coalition can reconstruct the secret.

Low-equivalence and observation projection become coalition-relative:

\[
\sigma_0\approx_A\sigma_1,
\qquad
\pi_{A,\Theta}(\tau).
\]

A mechanism contract must state which coalitions it protects against.

---

## 10. Termination sensitivity

There are two common forms.

### Termination-insensitive noninterference

Compare executions only when both terminate:

\[
P(\sigma_0)\Downarrow
\land
P(\sigma_1)\Downarrow.
\]

This does not treat divergence itself as a leak.

However, finite loop-count differences remain observable if `exec` events are in the trace.

### Termination-sensitive noninterference

Require termination behavior to agree:

\[
P(\sigma_0)\Downarrow
\Longleftrightarrow
P(\sigma_1)\Downarrow.
\]

This is stronger and substantially harder, especially with unbounded loops and distributed systems.

A realistic first compiler can use termination-insensitive security while still checking finite operation-count leakage.

---

## 11. Nondeterministic programs

If a program produces a set of traces, several relational definitions are possible.

A strong possibilistic property may require:

\[
\forall \tau_0\in\llbracket P\rrbracket(\sigma_0).
\ \exists \tau_1\in\llbracket P\rrbracket(\sigma_1).
\ \tau_0\sim_A\tau_1
\]

and symmetrically.

Other settings quantify over schedulers, couple random choices, or use probabilistic indistinguishability.

For the core MLIR validator, the recommended starting point is deterministic sequential semantics with external nondeterminism represented as explicit symbolic inputs or contracts.

---

## 12. Noninterference modulo release

Useful programs intentionally reveal results.

A password checker may reveal

\[
R(s,g)=[s=g].
\]

A private inference service may reveal

\[
R(w,x)=\operatorname{argmax}(\operatorname{model}(w,x)).
\]

Strict noninterference would reject those programs.

We therefore define release-relative low-equivalence:

\[
\sigma_0\approx_A^\Delta\sigma_1
\]

when:

1. initial public information is equal;
2. every sanctioned release function visible to \(A\) has equal value.

Then require

\[
\sigma_0\approx_A^\Delta\sigma_1
\Longrightarrow
\operatorname{Trace}_{A,\Theta}(P,\sigma_0)
\sim
\operatorname{Trace}_{A,\Theta}(P,\sigma_1).
\]

Intuition:

> Hold the allowed release constant, and verify that no additional information becomes distinguishable.

Module 9 develops this carefully.

---

## 13. Worked example: early-exit password comparison

Suppose the only authorized release is whether a guess equals the password.

```c
for (i = 0; i < n; ++i) {
    if (guess[i] != password[i])
        return false;
}
return true;
```

Choose two invalid guesses:

- run 0 mismatches at byte \(1\);
- run 1 mismatches at byte \(12\).

The authorized result is false in both runs:

\[
R(\sigma_0)=R(\sigma_1)=\mathsf{false}.
\]

But operation counts differ:

\[
\operatorname{count}(\tau_0)=1,
\qquad
\operatorname{count}(\tau_1)=12.
\]

Therefore, the program leaks more than the sanctioned Boolean.

---

## 14. Hyperproperties and compiler correctness

Functional compiler correctness commonly states

\[
\forall x.\quad
\operatorname{Result}(S,x)
=
\operatorname{Result}(T,x).
\]

Security preservation must relate four executions:

\[
S(x_0),\quad S(x_1),\quad T(x_0),\quad T(x_1).
\]

The core condition is

\[
\operatorname{Obs}(S,x_0)
\sim
\operatorname{Obs}(S,x_1)
\Longrightarrow
\operatorname{Obs}(T,x_0)
\sim
\operatorname{Obs}(T,x_1).
\]

This is why ordinary translation validation is insufficient for security. Module 8 develops this relation.

---

## 15. Common mistakes

### Mistake 1: "A secret-labeled value exists, so the program leaks"

A label indicates possible dependence. Leakage occurs only if an unauthorized observation changes.

### Mistake 2: comparing one execution to a policy

The core confidentiality question compares executions that vary hidden information.

### Mistake 3: forgetting the observer

There is no observer-independent definition of "public."

### Mistake 4: saying "constant time" without defining observations

Branches, addresses, instruction classes, and wall-clock time are different models.

### Mistake 5: allowing releases by deleting them from the trace

The occurrence, timing, and audience of release are themselves observable.

---

## 16. Exercises

### Exercise 1

Classify each property as a trace property or hyperproperty:

1. no invalid memory access;
2. public output never equals `secret`;
3. changing a key does not change memory addresses;
4. every release has a policy identifier.

### Exercise 2

Define low-equivalence for a state containing:

```text
public batch size
client-secret input tensor
provider-secret model tensor
public model architecture
```

for the server observer.

### Exercise 3

Give two traces that refute constant-time behavior for an early-exit string comparison.

### Exercise 4

Explain why two runs with different ciphertext bytes do not necessarily violate server confidentiality under randomized encryption.

### Exercise 5

State a termination-sensitive version of trace noninterference.

---

## 17. Summary

Confidentiality is relational:

\[
\text{equal authorized knowledge}
\Longrightarrow
\text{equal observable behavior}.
\]

This is a hyperproperty because it compares multiple executions. The next module shows how an information-flow type system proves a conservative approximation of this property.

---

## Further reading

- M. Clarkson and F. Schneider, work introducing hyperproperties.
- A. Sabelfeld and A. Myers, language-based information-flow surveys.
- G. Barthe et al., self-composition for secure information flow.

---

# Module 3 — Information-Flow Type Systems

## Learning objectives

After this module, you should be able to:

1. define a security lattice and permitted-flow relation;
2. distinguish explicit and implicit information flow;
3. use a program-counter label to track control dependence;
4. derive labels for SSA operations;
5. state the soundness theorem for an IFC type system;
6. recognize the two-point lattice as a special case of a principal-indexed policy;
7. explain why a distributed system needs a separate model of principals, hosts, coalitions, and access-control authority.

---

## 1. Why use a type system?

Relational verification is precise but potentially expensive. A type system provides a fast, compositional, conservative check.

The type system answers:

> Which protected information may influence each value and each observable effect?

If an event visible to observer \(A\) is influenced only by information \(A\) may know, the event is safe.

The type system may reject some secure programs. That is acceptable if it is sound. In this module, `Low` and `High` are teaching abbreviations. The next module replaces them with policies indexed by named principals and coalitions:

\[
\text{well typed}
\Longrightarrow
\text{noninterfering}.
\]

SMT can later recover precision for cases the type system cannot decide.

---

## 2. Security labels and lattices

A simple two-point lattice is

\[
\mathsf{Low}\sqsubseteq\mathsf{High}.
\]

Interpretation:

- `Low` information may flow into either `Low` or `High`;
- `High` information may flow only into `High`.

The lattice has:

\[
\bot=\mathsf{Low},
\qquad
\top=\mathsf{High}.
\]

The join is

\[
\begin{aligned}
\mathsf{Low}\sqcup\mathsf{Low}&=\mathsf{Low},\\
\mathsf{Low}\sqcup\mathsf{High}&=\mathsf{High},\\
\mathsf{High}\sqcup\mathsf{High}&=\mathsf{High}.
\end{aligned}
\]

A join combines dependencies.

If

\[
z=x+y,
\]

then

\[
\ell(z)=\ell(x)\sqcup\ell(y).
\]

---

## 3. Reader-set labels

For multiple parties, a useful confidentiality label can be a reader set

\[
R\subseteq\mathcal P.
\]

A smaller reader set is more restrictive.

A flow from \(R_1\) to \(R_2\) is safe when

\[
R_2\subseteq R_1.
\]

For example:

\[
\{\mathsf{client},\mathsf{provider}\}
\sqsubseteq
\{\mathsf{client}\}
\]

under the convention that information may move to a value readable by fewer principals.

The join is set intersection:

\[
R_1\sqcup R_2=R_1\cap R_2.
\]

If client-only input and provider-only weights jointly influence a plaintext value,

\[
\{\mathsf{client}\}
\cap
\{\mathsf{provider}\}
=
\varnothing.
\]

No party is authorized to see that joint value in plaintext unless a release policy says otherwise.

Different papers choose different order conventions. Always define the direction of \(\sqsubseteq\) explicitly.

---

## 4. Explicit flow

Consider:

```c
low = high;
```

The assignment is permitted only when

\[
\ell(high)\sqsubseteq \ell(low).
\]

In the two-point lattice:

\[
\mathsf{High}\not\sqsubseteq\mathsf{Low},
\]

so the assignment is rejected.

For an expression:

\[
\frac{
\Gamma\vdash e_1:\ell_1
\qquad
\Gamma\vdash e_2:\ell_2
}{
\Gamma\vdash e_1\oplus e_2:
\ell_1\sqcup\ell_2
}.
\]

The result records all explicit data dependencies.

---

## 5. Implicit flow

Consider:

```c
if (high)
    low = 1;
else
    low = 0;
```

The assigned constants are low. A data-only rule would miss the leak.

The value of `low` depends on which branch executed. This is an **implicit flow** through control.

The standard solution is a program-counter label \(pc\).

Inside a branch guarded by \(g\),

\[
pc' = pc\sqcup\ell(g).
\]

An assignment to variable \(x\) is allowed only if

\[
pc\sqcup\ell(e)\sqsubseteq\ell(x).
\]

So the branch above requires

\[
\mathsf{High}\sqsubseteq\mathsf{Low},
\]

and is rejected.

---

## 6. Typing judgments

A simple expression judgment is

\[
\Gamma\vdash e:\ell.
\]

A command judgment tracks control context:

\[
\Gamma;pc\vdash c.
\]

### Constants

\[
\frac{}{ \Gamma\vdash n:\bot }.
\]

### Variables

\[
\frac{\Gamma(x)=\ell_x}{\Gamma\vdash x:\ell_x}.
\]

### Binary operations

\[
\frac{
\Gamma\vdash e_1:\ell_1
\qquad
\Gamma\vdash e_2:\ell_2
}{
\Gamma\vdash e_1\oplus e_2:\ell_1\sqcup\ell_2
}.
\]

### Assignment

\[
\frac{
\Gamma\vdash e:\ell_e
\qquad
pc\sqcup\ell_e\sqsubseteq\Gamma(x)
}{
\Gamma;pc\vdash x:=e
}.
\]

### Conditional

\[
\frac{
\Gamma\vdash e:\ell_g
\qquad
\Gamma;pc\sqcup\ell_g\vdash c_t
\qquad
\Gamma;pc\sqcup\ell_g\vdash c_f
}{
\Gamma;pc\vdash
\mathbf{if}\ e\ \mathbf{then}\ c_t\ \mathbf{else}\ c_f
}.
\]

### Output

If host \(h\) has authority label \(L(h)\),

\[
\frac{
\Gamma\vdash e:\ell
\qquad
pc\sqcup\ell\sqsubseteq L(h)
}{
\Gamma;pc\vdash \mathbf{output}_h(e)
}.
\]

For a trace-sensitive system, the branch itself also creates an observable effect whose dependency is

\[
pc\sqcup\ell_g.
\]

This is stronger than checking assignments alone.

---

## 7. Effects as well as values

An MLIR operation may leak even if it produces no result.

Examples:

```mlir
cf.cond_br %secret, ^a, ^b
memref.store %x, %m[%secret_index]
ifc.transfer %x to @server
```

Therefore, use a judgment such as

\[
\Gamma;pc;h
\vdash
op(\bar v)
:
\bar D
\triangleright E.
\]

Here \(E\) is a set of abstract observable effects.

An effect can be represented as

\[
e=
\langle
\mathsf{kind},
\mathsf{symbolicExpression},
\ell_e,
\mathsf{observers}
\rangle.
\]

The static sufficient condition is

\[
A\in\mathsf{observers}(e)
\Longrightarrow
A\text{ is authorized for }\ell_e.
\]

If that condition fails, the compiler may reject or ask SMT whether the event is nevertheless constant across low-equivalent runs.

---

## 8. Flow sensitivity and SSA

In a source language:

```c
x = secret;
x = 0;
output(x);
```

A flow-insensitive analysis assigns one label to `x` and may keep it secret forever.

A flow-sensitive analysis can observe that the later assignment overwrites the secret.

SSA makes this easier:

```mlir
%x0 = ...
%x1 = arith.constant 0
return %x1
```

Each definition is a different value.

For pure SSA values, security descriptors are naturally flow-sensitive. Control-flow joins still require lattice joins, and mutable memory requires a separate analysis.

---

## 9. Path sensitivity

A standard dataflow IFC analysis is usually path-insensitive.

Consider:

```c
if (secret == secret)
    x = 0;
else
    x = secret;
```

The else branch is unreachable, but a simple lattice join labels \(x\) secret.

SMT can prove

\[
secret=secret
\]

and recover precision.

The intended architecture is:

\[
\text{fast path-insensitive IFC}
\quad+\quad
\text{selected path-sensitive SMT}.
\]

---

## 10. Confidentiality and integrity

Confidentiality asks:

> Who may learn this information?

Integrity asks:

> Who is trusted to influence this information?

Viaduct uses labels of the form

\[
\ell=\langle C,I\rangle.
\]

The confidentiality component restricts readers. The integrity component restricts untrusted influence.

Integrity matters for release:

```c
if (attacker_controlled)
    release(secret);
```

Even if the released audience is authorized, an untrusted party may be controlling whether release occurs.

A complete lattice combines both components, often using principal formulas rather than simple sets.

For the first honest-but-curious compiler prototype, confidentiality can be primary, while integrity is retained around release guards, authentication, and endorsement.

---

## 11. Label inference

Users should annotate trust boundaries, not every temporary.

Introduce a label variable \(L_v\) for each SSA value and generate constraints.

For

```mlir
%z = arith.addi %x, %y
```

generate

\[
L_x\sqsubseteq L_z,
\qquad
L_y\sqsubseteq L_z,
\qquad
pc\sqsubseteq L_z.
\]

For a branch result, add the guard:

\[
L_g\sqsubseteq L_r.
\]

For an output to host \(h\),

\[
L_v\sqsubseteq L(h).
\]

Solve for a least or minimum-authority assignment.

A desirable principality theorem is:

\[
\Gamma^*=\operatorname{Infer}(P)
\Longrightarrow
\forall\Gamma.
\ \Gamma\models\mathcal C(P)
\Rightarrow
\Gamma^*\preceq\Gamma.
\]

Viaduct follows this broad approach: infer labels by solving flow constraints, then use the inferred requirements to guide protocol selection.

---

## 12. Soundness statement

A source-level soundness theorem has the form

\[
\Gamma;pc_0\vdash P
\Longrightarrow
\operatorname{Secure}_{A,\Theta}(P)
\]

for observers covered by the policy.

A proof usually needs several lemmas.

### Expression confinement

If two states agree on all values visible at label \(\ell\), then evaluating an expression labeled at most \(\ell\) produces equal low results.

### Low-step preservation

If two low-equivalent states take corresponding steps, their low-equivalence is preserved and their low events agree.

### High-context confinement

Commands executing under a high \(pc\) cannot change low state or produce low-observable events.

### Induction over execution

Combine the local lemmas to show equal observer traces.

The exact proof shape depends on loops, memory, declassification, and nondeterminism.

---

## 13. Static soundness versus completeness

A sound IFC checker may reject a secure program.

Example:

```mlir
%x = arith.xori %secret, %secret
```

Dataflow gives

\[
\ell(x)=\ell(secret).
\]

Semantically,

\[
x=0.
\]

The checker is sound because it overapproximates possible dependence, but incomplete because it cannot prove the cancellation.

SMT can discharge the relational obligation

\[
x_0\ne x_1.
\]

That formula is unsatisfiable.

---

## 14. Common mistakes

### Mistake 1: labels are runtime encryption states

A confidentiality policy is semantic. Encryption is a representation. They must be separate.

### Mistake 2: only label SSA results

Branches, stores, calls, transfers, and errors may leak without producing values.

### Mistake 3: forget `pc`

This misses implicit flow.

### Mistake 4: treat every failed static check as a definite leak

Some are merely possible dependencies requiring semantic proof.

### Mistake 5: declassify by manually changing a label

Release must be an explicit checked operation.

---

## 15. Exercises

### Exercise 1

Derive labels for:

```c
z = (public + secret) * public;
```

### Exercise 2

Why does this leak?

```c
low = 0;
if (high)
    skip;
else
    low = 0;
```

Assume branch outcomes are observable even though `low` is unchanged.

### Exercise 3

Write a typing rule for `while e do c` using \(pc\).

### Exercise 4

For reader-set labels, compute the join of:

\[
\{\mathsf{client},\mathsf{provider}\}
\quad\text{and}\quad
\{\mathsf{client}\}.
\]

### Exercise 5

Explain why integrity is relevant to an attacker-controlled release guard.

---

## 16. Summary

The type system computes a conservative dependency structure:

\[
\text{labels on data}
+
pc
+
\text{labels on observable effects}.
\]

Well-typedness is intended to imply relational noninterference. The next module first explains who the labels are about: principals, actors, hosts, ACLs, authority, and observer coalitions. Tensor facets, representations, and placements then build on that actor-aware policy model.

---

## Further reading

- A. Sabelfeld and A. Myers, language-based information-flow security.
- C. Acay et al., [Viaduct](https://www.cs.cornell.edu/andru/papers/viaduct/viaduct.pdf), especially label checking and inference.
- Jif and the decentralized label model for principal-based policies.

---

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

\[
\mathsf{Low}\sqsubseteq\mathsf{High}.
\]

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

\[
\mathcal P=\{C,P,S,\ldots\}.
\]

A principal is not necessarily a process or machine. It is the entity whose permission or trust matters.

### Actor

In these notes, **actor** is an informal umbrella term for an active participant in the system. An actor may submit data, run code, receive output, or control a host.

For formal writing, prefer **principal** or **party**. The word *actor* can be confused with the actor concurrency model.

### Host

A **host** is an execution or storage location:

\[
\mathcal H=\{h_C,h_P,h_S,h_{GPU},\ldots\}.
\]

Examples include:

- a client's laptop;
- an inference server;
- a GPU address space;
- an enclave;
- an MPC participant process.

A host has a trust or authority description. We write

\[
L(h)
\]

for the authority assigned to host \(h\).

### Controller

A **controller** is a principal or coalition that can inspect or modify a host.

A simple environment might contain

\[
\operatorname{controllers}(h_S)=\{S\}.
\]

A more realistic environment may say that both the cloud operator and a system administrator can inspect a host.

### Owner

An **owner** is a principal whose authority is required to weaken a policy. Ownership is about policy authority, not necessarily current possession.

The client may own the confidentiality policy of a query even after an encrypted representation is transferred to the server.

### Observer

An **observer** is the principal or coalition for which we are proving confidentiality.

We write the observer as

\[
A.
\]

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

\[
\{\mathsf{server},\mathsf{keyHolder}\}.
\]

A threat model must say which coalitions are considered.

---

## 3. ACLs and IFC solve different problems

An access-control list for object \(o\) might be

\[
ACL(o)=\langle R(o),W(o)\rangle,
\]

where:

- \(R(o)\) is the set of principals allowed to read the object;
- \(W(o)\) is the set of principals allowed to write the object.

An ACL answers a local question:

> May principal \(p\) perform this read or write now?

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

\[
\ell(secret)=\mathsf{clientOnly}.
\]

The derived output keeps that dependency and the send is rejected.

### Practical relationship

Our compiler may offer ACL-like syntax because it is intuitive:

```mlir
{ifc.readers = [@client], ifc.writers = [@client]}
```

But its semantics is information-flow semantics. The policy propagates through SSA operations, control dependence, memory, and lowering.

A useful rule of thumb is:

\[
\boxed{
\text{ACLs protect objects at access points; IFC protects information after it moves.}
}
\]

---

## 4. A first principal model: reader and influencer sets

Before introducing principal formulas, use a concrete set model.

For a value \(v\), define

\[
\ell(v)=\langle R(v),I(v)\rangle,
\]

where:

- \(R(v)\subseteq\mathcal P\) lists principals allowed to learn the information;
- \(I(v)\subseteq\mathcal P\) lists principals that may have influenced the information.

The second component is intentionally called an **influencer set**, not merely a writer ACL. It records provenance after computation.

### Permitted flow

Information with label \(\ell_1=\langle R_1,I_1\rangle\) may flow to \(\ell_2=\langle R_2,I_2\rangle\) when

\[
\ell_1\sqsubseteq\ell_2
\quad\Longleftrightarrow\quad
R_2\subseteq R_1
\;\land\;
I_1\subseteq I_2.
\]

Why?

- The destination may not add new readers.
- The destination must acknowledge every principal that may already have influenced the value.

### Join

When two values influence one result,

\[
\ell_1\sqcup\ell_2
=
\langle R_1\cap R_2,\; I_1\cup I_2\rangle.
\]

The result is readable only by principals allowed to read both sources, and it may have been influenced by anyone who influenced either source.

### Example

Client query:

\[
\ell_q=\langle\{C\},\{C\}\rangle.
\]

Provider weights:

\[
\ell_w=\langle\{P\},\{P\}\rangle.
\]

A result depending on both has

\[
\ell_r
=
\ell_q\sqcup\ell_w
=
\langle\varnothing,\{C,P\}\rangle.
\]

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

\[
p,q ::= A\mid B\mid 0\mid 1\mid p\land q\mid p\lor q.
\]

The relation

\[
p\Rightarrow q
\]

is read as:

> \(p\) acts for \(q\), or \(p\) has at least the authority of \(q\).

It behaves like logical implication. For example,

\[
A\land B\Rightarrow A
\]

and

\[
A\Rightarrow A\lor B.
\]

Intuitively:

- \(A\land B\) represents combined authority;
- \(A\lor B\) represents authority common to either principal;
- \(0\) is maximal authority;
- \(1\) is minimal authority.

The names \(0\) and \(1\) can feel reversed if you are thinking of Boolean false and true. Treat them as lattice extrema rather than truth values.

### Example

If a release requires both client and provider approval, its authority requirement can contain

\[
C\land P.
\]

A principal possessing only \(C\) does not act for \(C\land P\).

---

## 7. Confidentiality and integrity labels

A Viaduct-style label is a pair

\[
\ell=\langle C(\ell),I(\ell)\rangle.
\]

Here:

- \(C(\ell)\) is the authority required to read the information;
- \(I(\ell)\) is the authority required to influence or vouch for the information.

For shorthand, a principal \(A\) may denote

\[
\langle A,A\rangle.
\]

We can also project the components:

\[
\ell^{\mathsf C}=\langle C(\ell),1\rangle,
\qquad
\ell^{\mathsf I}=\langle 1,I(\ell)\rangle.
\]

### Reading and influencing

An authority \(a\) may read data labeled \(\ell\) when

\[
a\Rightarrow C(\ell).
\]

It has enough integrity authority for the data when

\[
a\Rightarrow I(\ell).
\]

These equations are an abstract policy relation. The actual runtime visibility also depends on host placement and representation.

---

## 8. The flows-to relation

The information-flow order is

\[
\ell_1\sqsubseteq\ell_2
\quad\Longleftrightarrow\quad
C(\ell_2)\Rightarrow C(\ell_1)
\;\land\;
I(\ell_1)\Rightarrow I(\ell_2).
\]

The confidentiality direction is reversed because moving to a destination with a stronger reading requirement is safe.

The integrity direction is forward because the destination must not claim more trust than the source justifies.

### Join and meet

Viaduct defines

\[
\ell_1\sqcup\ell_2
=
\langle
C(\ell_1)\land C(\ell_2),
I(\ell_1)\lor I(\ell_2)
\rangle,
\]

and

\[
\ell_1\sqcap\ell_2
=
\langle
C(\ell_1)\lor C(\ell_2),
I(\ell_1)\land I(\ell_2)
\rangle.
\]

The join combines dependencies just as the set model did:

- confidentiality becomes more restrictive;
- integrity records that either source may have influenced the result.

### Two-owner result

Let

\[
\ell_q=\langle C,C\rangle,
\qquad
\ell_w=\langle P,P\rangle.
\]

Then

\[
\ell_q\sqcup\ell_w
=
\langle C\land P, C\lor P\rangle.
\]

Reading requires combined confidentiality authority. The integrity component says the value may depend on either input principal.

---

## 9. Hosts carry authority too

A host declaration associates a host with authority:

\[
L:\mathcal H\rightarrow\mathcal L.
\]

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

If a plaintext facet labeled \(\ell_f\) is exposed on host \(h\), a basic requirement is

\[
C(L(h))\Rightarrow C(\ell_f).
\]

If the server does not act for client confidentiality, client plaintext cannot be placed there.

### Protected placement

A ciphertext may be placed on the server even though the underlying information remains client-confidential. The representation contract says which facets are exposed.

This is why the complete rule is not merely

\[
C(L(h))\Rightarrow C(\ell_f).
\]

It is

\[
\operatorname{Exposed}_{\Pi,\Theta}(A,h,\rho,f)
\Longrightarrow
\operatorname{CanRead}(A,\ell_f).
\]

The representation \(\rho\) may hide element values while revealing shape and transfer size.

---

## 10. Actor-relative observations

There is no single universal trace. Each observer sees a projection.

Let

\[
\pi_{A,\Theta}(\tau)
\]

retain exactly the events visible to observer coalition \(A\) under target profile \(\Theta\).

Then

\[
\operatorname{Trace}_{A,\Theta}(P,\sigma)
=
\pi_{A,\Theta}(\operatorname{Trace}(P,\sigma)).
\]

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

Two states are low-equivalent for observer \(A\) when they agree on everything \(A\) is initially authorized to observe:

\[
\sigma_0\approx_A\sigma_1.
\]

With facet policies, this means equality is imposed separately.

For every input facet \(f\):

\[
\operatorname{CanRead}(A,\ell_f)
\Longrightarrow
f(\sigma_0)=f(\sigma_1).
\]

Hidden facets may differ.

### Example

Suppose the client can read the query and final result, while the server can see only public shape.

For the server query:

\[
shape_0=shape_1,
\]

but

\[
query_0\text{ and }query_1
\]

are independent.

For the client query, the input query is already visible to the client, so the two runs constrain it equal. The hidden model weights may differ.

Security is therefore always indexed by an observer:

\[
\operatorname{Secure}_A(P).
\]

---

## 12. Coalitions and collusion

Checking only singleton observers can be unsound.

Suppose an FHE server sees ciphertexts and a separate key service holds the decryption key. Neither actor alone sees plaintext, but the coalition does.

Let the relevant threat set be

\[
\mathcal A
\subseteq
2^{\mathcal P}.
\]

The compiler proves

\[
\forall A\in\mathcal A.\;\operatorname{Secure}_A(P).
\]

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

\[
pc'=pc\sqcup\ell(%client\_secret\_condition).
\]

If the server can observe the branch, the branch effect requires the server to be authorized for that combined label, or the computation must use an oblivious/protected mechanism.

A conceptual rule is

\[
\frac{
\Gamma\vdash c:\ell_c
\qquad
pc'=pc\sqcup\ell_c
\qquad
\operatorname{ObserverAllowed}(h,pc')
}{
\Gamma;pc;h\vdash \texttt{if }c\texttt{ then }s_1\texttt{ else }s_2
}.
\]

In our stronger trace model, merely hiding the final assigned values is not enough. The host must also be unable to distinguish branch outcomes, operation counts, addresses, and other events.

---

## 14. ACL changes versus declassification

A normal flow must not silently expand the reader set.

In the set model, this is forbidden:

\[
R_{dest}\not\subseteq R_{source}.
\]

An explicit sanctioned release may intentionally expand readers:

\[
\{C\}
\longrightarrow
\{C,P\}.
\]

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

\[
\ell_x\sqsubseteq\ell_z,
\qquad
\ell_y\sqsubseteq\ell_z,
\qquad
pc\sqsubseteq\ell_z.
\]

For an output to host \(h\), generate a host-authority constraint. In a simplified form:

\[
\ell_{output}\sqsubseteq L(h).
\]

For a branch involving hosts \(H\), require every participating host to be allowed to know the guard, unless the branch is converted into a protected oblivious computation.

Viaduct translates flows-to constraints into acts-for constraints and solves them to obtain a minimum-authority assignment. The important architecture lesson is:

\[
\boxed{
\text{infer principal labels with a fast lattice solver; use SMT later for semantic noninterference.}
}
\]

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

\[
\ell(x)=\langle C,C\rangle,
\qquad
\ell(w)=\langle P,P\rangle.
\]

Hosts:

\[
L(h_C)=C,
\qquad
L(h_P)=P,
\qquad
L(h_S)=S.
\]

The plaintext multiplication result has

\[
\ell(y)=\ell(x)\sqcup\ell(w)
=
\langle C\land P,C\lor P\rangle.
\]

Neither \(C\), \(P\), nor \(S\) alone acts for \(C\land P\). Therefore no one may receive the joint intermediate in plaintext.

A valid implementation can instead use a mechanism:

```text
representation: threshold-FHE ciphertext or MPC share
placement:      server/MPC hosts
visible facets: public shape and protocol metadata
plaintext:      hidden
```

A release policy may later reveal

\[
R(x,w)=\operatorname{argmax}(model(w,x))
\]

to the client.

The release does not authorize the client to see \(w\), logits, or arbitrary intermediates.

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

A protocol \(M\) with authority label \(L(M)\) may implement a component requiring \(\ell\) when

\[
L(M)\Rightarrow\ell.
\]

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

\[
\ell_1=\langle\{A,B\},\{A\}\rangle,
\qquad
\ell_2=\langle\{A\},\{A,B\}\rangle.
\]

Determine whether \(\ell_1\sqsubseteq\ell_2\).

### Exercise 3 — join

Compute the set-model join of

\[
\langle\{C\},\{C\}\rangle
\quad\text{and}\quad
\langle\{P\},\{P\}\rangle.
\]

Explain the confidentiality and integrity results.

### Exercise 4 — acts-for

Which of the following hold?

\[
A\land B\Rightarrow A,
\qquad
A\Rightarrow A\land B,
\qquad
A\Rightarrow A\lor B.
\]

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

\[
\boxed{
\text{principals express authority}
}
\]

\[
\boxed{
\text{hosts express where execution and storage occur}
}
\]

\[
\boxed{
\text{labels/ACL views express who may learn or influence information}
}
\]

\[
\boxed{
\text{observer coalitions determine which relational property is checked}
}
\]

The central policy relation is

\[
\ell_1\sqsubseteq\ell_2,
\]

and the central actor-relative security property is

\[
\sigma_0\approx_A\sigma_1
\Longrightarrow
\operatorname{Trace}_{A,\Theta}(P,\sigma_0)
\sim
\operatorname{Trace}_{A,\Theta}(P,\sigma_1).
\]

The following modules apply this model to tensor facets, memory, SMT, lowering, release, and cryptographic mechanisms.

---

## Further reading

- Coşku Acay et al., *Viaduct: An Extensible, Optimizing Compiler for Secure Distributed Programs*, PLDI 2021, especially Sections 2–4.
- Owen Arden, Jed Liu, and Andrew C. Myers, *Flow-Limited Authorization*, CSF 2015.
- Andrew C. Myers and Barbara Liskov, decentralized information-flow control.
- Steve Zdancewic and Andrew C. Myers, robust declassification.
- Ethan Cecchetti, Andrew C. Myers, and Owen Arden, nonmalleable information flow control.

---

# Module 5 — Tensor-Aware Information Flow

## Learning objectives

After this module, you should be able to:

1. explain why one `secret` bit is insufficient for tensor programs;
2. distinguish value, index, shape, and layout confidentiality;
3. separate semantic policy from runtime representation and placement;
4. derive security transfer rules for common tensor operations;
5. identify tensor-native side channels before lowering destroys tensor structure;
6. interpret every tensor facet policy relative to named principals, hosts, and observer coalitions.

---

## 1. Why tensors need more than one label

A scalar `i32` has one obvious payload. A tensor carries several kinds of information:

\[
T =
\langle
\text{elements},
\text{indices},
\text{shape},
\text{layout},
\text{placement}
\rangle.
\]

Those components can have different policies.

Example:

```text
element values: client-confidential
shape:          public
layout:         public
representation: FHE ciphertext
placement:      server
```

This is common in outsourced encrypted computation. The server may know that a ciphertext represents a \(128\times 128\) matrix without learning its entries.

The reverse is also possible:

```text
elements:       public
shape:          client-confidential
```

For example, the number of medical records or sequence length may itself be sensitive.

A single `secret<T>` wrapper cannot express all of these distinctions precisely.

---

## 2. The security descriptor

For an MLIR SSA value \(v\), define

\[
D(v)=
\left\langle
\tau,\;
\ell_{\mathrm{val}},
\ell_{\mathrm{idx}},
\ell_{\mathrm{shape}},
\ell_{\mathrm{layout}},\;
\rho,\;
h,\;
\Omega
\right\rangle.
\]

The fields are:

- \(\tau\): ordinary MLIR type;
- \(\ell_{\mathrm{val}}\): policy for scalar or tensor element values;
- \(\ell_{\mathrm{idx}}\): policy for logical indices, selectors, token identifiers, or permutation choices;
- \(\ell_{\mathrm{shape}}\): policy for ranks, dimensions, lengths, and batch sizes;
- \(\ell_{\mathrm{layout}}\): policy for strides, sparsity patterns, nonzero locations, tiling, routing, and storage format;
- \(\rho\): representation, such as plaintext, FHE ciphertext, share, or opaque handle;
- \(h\): actual host or device placement;
- \(\Omega\): outstanding proof or platform obligations.

Each facet label may itself contain confidentiality and integrity:

\[
\ell_f=\langle C_f,I_f\rangle.
\]

For an honest-but-curious first version, confidentiality may dominate, but retaining the full structure makes release and authentication cleaner.

---

## 3. Principal-indexed facet policies

Every facet label is a principal-indexed policy, not an unqualified `secret` bit.

For a tensor facet \(f\), we may use either the ACL view

\[
ACL_f(v)=\langle R_f(v),I_f(v)\rangle
\]

or the authority-formula view

\[
\ell_f(v)=\langle C_f(v),I_f(v)\rangle.
\]

The ACL view is easier to read in examples; the authority-formula view supports combined and threshold-like authority. The implementation should normalize both syntaxes into one internal representation.

### Actor-relative meaning

The statement

```text
shape is public
```

is incomplete. It should mean something like

```text
shape is readable by client, provider, and server
```

or, formally,

\[
\operatorname{CanRead}(A,\ell_{shape})
\]

for the specific observer coalition \(A\).

The same tensor can therefore have this actor matrix:

| Facet | Client | Provider | Server |
|---|---:|---:|---:|
| elements | yes | no | no |
| logical indices | yes | no | no |
| shape | yes | yes | yes |
| layout | no | no | yes |

This matrix is a presentation of four labels. It is not four unrelated runtime ACL checks.

### Host and representation interaction

A facet is actually observable only when the host and representation expose it:

\[
\operatorname{Exposed}(A,h,\rho,f)
\Longrightarrow
\operatorname{CanRead}(A,\ell_f).
\]

For example, an FHE representation may hide element values from the server while exposing rank, dimensions, ciphertext count, and parameter identifiers. A packed representation may also make layout choices observable.

### Two-owner join

If client input elements have policy \(\ell_C\) and provider weight elements have policy \(\ell_P\), then a joint tensor result has

\[
\ell_{val}(r)=pc\sqcup\ell_C\sqcup\ell_P.
\]

In a reader-set presentation, the plaintext reader set becomes

\[
R_C\cap R_P.
\]

This may be empty. That does not prohibit the computation; it prohibits an unprotected plaintext realization. The mechanism and placement layers must choose an FHE, MPC, or otherwise protected representation.

---

## 4. Does every matrix have all four labels?

Conceptually, yes: every tensor value has all four **facets**. That does not mean all four are secret or even operationally interesting.

For a fixed-size dense matrix

```mlir
tensor<32x32xf32>
```

we might have

\[
\ell_{\mathrm{shape}}=\mathsf{Public},
\qquad
\ell_{\mathrm{layout}}=\mathsf{Public}.
\]

If the matrix is not used as an index, then \(\ell_{\mathrm{idx}}\) may be irrelevant or set to bottom.

For a scalar index value

```mlir
%token : index
```

the meaningful facet is often

\[
\ell_{\mathrm{idx}}(\%token).
\]

The descriptor is a uniform analysis structure. Operation-specific transfer functions decide which facets matter.

---

## 5. Element-value confidentiality

\(\ell_{\mathrm{val}}\) protects the logical payload.

Examples:

- pixels in a medical image;
- coefficients of a secret polynomial;
- model weights;
- private inference inputs;
- intermediate activations;
- decrypted FHE results.

For elementwise arithmetic,

```mlir
%z = arith.addi %x, %y : i32
```

or elementwise tensor addition, use

\[
\ell_{\mathrm{val}}(z)
=
pc
\sqcup
\ell_{\mathrm{val}}(x)
\sqcup
\ell_{\mathrm{val}}(y).
\]

For matrix multiplication,

\[
C=A\cdot B,
\]

the result elements depend on both operands:

\[
\ell_{\mathrm{val}}(C)
=
pc
\sqcup
\ell_{\mathrm{val}}(A)
\sqcup
\ell_{\mathrm{val}}(B).
\]

If \(A\) is client-only and \(B\) is provider-only, the joint plaintext result may be readable by neither party.

---

## 6. Index confidentiality

\(\ell_{\mathrm{idx}}\) protects which logical item is selected.

Examples:

- token ID used in an embedding lookup;
- table index in a cryptographic lookup table;
- gather/scatter indices;
- selected expert in a mixture-of-experts model;
- permutation or shuffle indices;
- secret row or column;
- top-\(k\) selected positions.

Consider

```mlir
%x = tensor.extract %table[%i]
```

The returned value depends on both table contents and the selector:

\[
\ell_{\mathrm{val}}(x)
=
pc
\sqcup
\ell_{\mathrm{val}}(table)
\sqcup
\ell_{\mathrm{idx}}(i).
\]

Even if all table elements are public, the chosen value reveals the index.

More importantly, the memory address depends on the index:

\[
\ell_{\mathrm{address}}
=
pc
\sqcup
\ell_{\mathrm{idx}}(i)
\sqcup
\ell_{\mathrm{shape}}(table)
\sqcup
\ell_{\mathrm{layout}}(table).
\]

A direct gather can therefore violate constant-time trace noninterference.

---

## 7. Shape confidentiality

\(\ell_{\mathrm{shape}}\) protects information such as:

- dynamic dimensions;
- sequence length;
- batch size;
- number of records;
- image dimensions;
- beam width;
- number of active tokens;
- early-exit network depth;
- number of ciphertext chunks.

Shape can become observable through:

\[
\mathsf{shape}(\bar d),
\quad
\mathsf{allocation}(n),
\quad
\mathsf{transfer}(n),
\quad
\mathsf{kernelLaunch}(k),
\quad
\mathsf{execCount}(n).
\]

Example:

```mlir
%buffer = memref.alloc(%secret_len) : memref<?xi32>
```

The allocation event exposes

\[
n=4\cdot secretLen.
\]

Even if the allocated contents are encrypted, the length may leak.

### Static versus dynamic shape

A static type

```mlir
tensor<128xi32>
```

makes the dimension public as part of the program.

A dynamic type

```mlir
tensor<?xi32>
```

does not automatically make the runtime dimension secret. The security descriptor determines its policy.

---

## 8. Layout and sparsity confidentiality

\(\ell_{\mathrm{layout}}\) protects how values are arranged or scheduled.

Examples:

- sparse nonzero coordinates;
- compressed sparse row index arrays;
- strides and offsets;
- secret-dependent tile choice;
- zero-skipping;
- data-dependent compaction;
- routing to CPU, GPU, or NPU;
- expert routing;
- dynamic kernel choice;
- packed ciphertext layout;
- permutation induced by a private query.

A sparse tensor may have public nonzero values but a secret sparsity pattern. Iterating only over nonzeros leaks the pattern through addresses and operation counts.

For a sparse operation,

\[
\ell_{\mathrm{schedule}}
=
pc
\sqcup
\ell_{\mathrm{layout}}(T).
\]

A dense oblivious implementation may have a public schedule even when logical sparsity is secret.

---

## 9. Policy, representation, and placement are different

This distinction is central.

### Policy

Who is authorized to learn the underlying information?

\[
\ell_{\mathrm{val}}=\mathsf{ClientOnly}.
\]

### Representation

How is the information currently encoded?

\[
\rho\in
\{
\mathsf{Plain},
\mathsf{FHE}(pk),
\mathsf{Share}(t,n),
\mathsf{Opaque}(K)
\}.
\]

### Placement

Where does the representation exist?

\[
h\in
\{
\mathsf{Client},
\mathsf{Server},
\mathsf{Provider},
\mathsf{GPU}
\}.
\]

Encryption changes representation:

\[
\rho_{\mathsf{plain}}
\rightarrow
\rho_{\mathsf{FHE}}.
\]

Transfer changes placement:

\[
h_{\mathsf{client}}
\rightarrow
h_{\mathsf{server}}.
\]

Neither operation automatically changes semantic policy.

Only a checked release may expand the authorized audience.

---

## 10. Example: FHE ciphertext on the server

Suppose

```mlir
%cipher = secret.conceal %input
%remote = ifc.transfer %cipher to @server
```

The descriptors may be:

\[
\begin{aligned}
D(input) &=
\langle
tensor<128xi16>,
ClientOnly,
\ldots,
Plain,
Client,
\varnothing
\rangle,\\
D(cipher) &=
\langle
!secret.secret<tensor<128xi16>>,
ClientOnly,
\ldots,
FHE(pk),
Client,
\Omega_{\mathrm{crypto}}
\rangle,\\
D(remote) &=
\langle
!secret.secret<tensor<128xi16>>,
ClientOnly,
\ldots,
FHE(pk),
Server,
\Omega_{\mathrm{crypto}}
\rangle.
\end{aligned}
\]

The server is not in the plaintext reader set, but placement is legal because the FHE contract hides the payload.

The server may still observe:

- shape;
- ciphertext count;
- parameter set;
- transfer size;
- kernel schedule.

Those facets require separate policies.

HEIR's `secret` dialect provides scheme-agnostic operations such as `secret.conceal`, `secret.generic`, and `secret.reveal`. A party-aware verifier can treat those as representation boundaries while retaining principal-specific semantic policies.

---

## 11. Facet transfer functions

A transfer function is operation-specific.

### Elementwise map

For

```mlir
%r = linalg.map ins(%x, %y) ...
```

a reasonable rule is

\[
\ell_{\mathrm{val}}(r)
=
pc\sqcup
\ell_{\mathrm{val}}(x)
\sqcup
\ell_{\mathrm{val}}(y),
\]

\[
\ell_{\mathrm{shape}}(r)
=
\ell_{\mathrm{shape}}(x)
\sqcup
\ell_{\mathrm{shape}}(y),
\]

while layout is determined by result construction and target scheduling.

### Reshape

For

```mlir
%r = tensor.reshape %x(%shape)
```

the output payload policy is inherited:

\[
\ell_{\mathrm{val}}(r)
=
\ell_{\mathrm{val}}(x).
\]

The output shape depends on the shape operand:

\[
\ell_{\mathrm{shape}}(r)
=
pc
\sqcup
\ell_{\mathrm{shape}}(x)
\sqcup
\ell_{\mathrm{val}}(\%shape).
\]

### Transpose

Logical values are unchanged, but layout changes:

\[
\ell_{\mathrm{val}}(r)=\ell_{\mathrm{val}}(x),
\]

\[
\ell_{\mathrm{layout}}(r)
=
pc
\sqcup
\ell_{\mathrm{layout}}(x)
\sqcup
\ell_{\mathrm{idx}}(\mathsf{permutation}).
\]

If the permutation is secret, later addresses may leak it.

### Slice

For

```mlir
%r = tensor.extract_slice %x[%offsets][%sizes][%strides]
```

\[
\ell_{\mathrm{val}}(r)
=
\ell_{\mathrm{val}}(x)
\sqcup
\ell_{\mathrm{idx}}(\mathsf{offsets})
\sqcup
\ell_{\mathrm{shape}}(\mathsf{sizes}).
\]

The result shape depends on `sizes`; layout depends on offsets and strides.

### Top-\(k\)

The selected values and indices depend on the input values:

\[
\ell_{\mathrm{val}}(values)
=
\ell_{\mathrm{val}}(x),
\]

\[
\ell_{\mathrm{idx}}(indices)
=
\ell_{\mathrm{val}}(x).
\]

A data-dependent algorithm may also leak through operation counts or memory accesses.

---

## 12. Tensor effects

A tensor operation can produce observable effects independent of its result descriptor.

### Allocation

\[
e_{\mathrm{alloc}}
=
\mathsf{allocation}
\left(
s,
\operatorname{bytes}(\bar d,\tau)
\right).
\]

Dependency:

\[
\ell(e_{\mathrm{alloc}})
=
pc\sqcup\ell_{\mathrm{shape}}.
\]

### Kernel selection

\[
e_{\mathrm{kernel}}
=
\mathsf{kernelLaunch}(s,k).
\]

If \(k\) depends on a secret shape, sparsity pattern, or value, the kernel identity becomes a channel.

### Transfer

\[
e_{\mathrm{transfer}}
=
\mathsf{transfer}(s,h_1,h_2,n).
\]

The size \(n\) may depend on shape, layout, compression, or ciphertext packing.

### Sparse iteration

Repeated `exec` and memory events expose the number and positions of nonzeros.

---

## 13. Worked example: secret token embedding

```mlir
%e = tensor.extract %embedding[%secret_token]
  : tensor<50000x4096xf32>
```

Assume:

```text
embedding values: provider-confidential
token index:      client-confidential
shape:            public
layout:           public dense row-major
host:             server
```

The logical result depends on both parties:

\[
\ell_{\mathrm{val}}(e)
=
ProviderOnly
\sqcup
ClientOnly.
\]

The address is

\[
a=
base
+
secretToken\cdot 4096\cdot 4.
\]

The server-local memory observer sees

\[
\mu_\Theta(a).
\]

The direct lookup therefore leaks the token index unless:

- the server is authorized to know it;
- the access runs under an oblivious mechanism;
- the memory contract hides the address;
- or SMT proves the address class is equal, which is unlikely for unconstrained token values.

A possible repair is an oblivious full scan:

```text
for every row i:
    selected = constant_time_equal(i, secret_token)
    result = select(selected, embedding[i], result)
```

This trades performance for an index-independent address trace.

---

## 14. Two-owner inference

Let:

\[
\ell_{\mathrm{val}}(x)=ClientOnly
\]

and

\[
\ell_{\mathrm{val}}(W)=ProviderOnly.
\]

For

\[
y=W x,
\]

the joint plaintext result is

\[
\ell_{\mathrm{val}}(y)
=
ClientOnly\sqcup ProviderOnly.
\]

In a reader-set lattice, this may yield no plaintext reader.

That does not mean the computation is impossible. It means the representation must remain protected, for example:

\[
\rho(y)=FHE
\quad\text{or}\quad
\rho(y)=MPCShare.
\]

A policy can later sanction release of

\[
R(W,x)=\operatorname{argmax}(Wx)
\]

to the client without releasing \(W\), \(x\), or full logits.

---

## 15. Why tensor altitude matters

At tensor level, the compiler can see:

```text
gather by token ID
dynamic sequence length
sparse iteration
top-k selection
expert routing
tensor transfer
ciphertext packing
```

After lowering to LLVM IR, these concepts become:

```text
pointer arithmetic
loops
loads and stores
runtime calls
```

The security property remains expressible, but analysis requires reconstructing high-level meaning through alias analysis and whole-program reasoning.

Tensor-level checking is not a substitute for lower-level validation. It is an advantageous place to infer policy and identify semantic channels before structure is lost.

---

## 16. Common mistakes

### Mistake 1: every facet inherits the element label

This is safe but unnecessarily imprecise. Public shape with secret elements is common.

### Mistake 2: encrypted means public

Ciphertexts still carry semantic secret policy.

### Mistake 3: placement is a confidentiality label

Placement is a fact. Whether it is safe depends on representation and host authority.

### Mistake 4: only values leak

Shape, layout, routing, and schedule can leak independently.

### Mistake 5: indexing affects only the loaded value

It also affects the address trace.

---

## 17. Exercises

### Exercise 1

Give a descriptor for a sparse medical tensor whose:

- values are patient-confidential;
- shape is public;
- nonzero pattern is patient-confidential;
- representation is plaintext;
- placement is a hospital GPU.

### Exercise 2

Derive facet labels for:

```mlir
%r = tensor.extract_slice %x[%secret_offset][%public_size][1]
```

### Exercise 3

Explain why padding a secret-length sequence to a public maximum can make transfer size public.

### Exercise 4

A top-\(k\) operation returns public values but secret indices. Is that policy coherent? Give a use case or explain why it may be dangerous.

### Exercise 5

For two-owner inference, define a release policy that reveals only the predicted class to the client.

---

## 18. Summary

Every statement in this chapter is actor-relative. A facet label says which principal authority is required to observe or influence that facet; host placement and representation determine whether the facet is actually exposed to a given observer.


Tensor security is facet-sensitive:

\[
\boxed{
\text{elements}
\neq
\text{indices}
\neq
\text{shape}
\neq
\text{layout}
}
\]

and orthogonal to

\[
\boxed{
\text{policy}
\neq
\text{representation}
\neq
\text{placement}.
}
\]

The next module explains what happens when immutable tensor SSA values become mutable buffers, pointers, and aliases.

---

## Further reading

- HEIR [`secret` dialect](https://heir.dev/docs/dialects/secret/).
- MLIR tensor, linalg, sparse tensor, and bufferization documentation.
- The project threat model's tensor metadata event classes.

---

# Module 6 — Memory, Pointers, Aliasing, and Bufferization

## Learning objectives

After this module, you should be able to:

1. explain why memory is harder to analyze than pure SSA values;
2. distinguish pointer confidentiality, address confidentiality, and pointee confidentiality;
3. use points-to sets and abstract locations;
4. explain may-alias versus must-alias;
5. apply strong and weak abstract-memory updates;
6. understand MLIR `memref` addressing and subviews;
7. identify how tensor-to-memref bufferization can introduce security exposure;
8. state the representation relation needed to validate bufferization securely;
9. reason about per-host address spaces, allocation ACLs, and alias exposure to different principals.

---

## 1. Why memory is the difficult chapter

Pure SSA has a useful property:

> Every SSA value has exactly one definition.

If

```mlir
%z = arith.addi %x, %y
```

then the security descriptor of `%z` is derived once from `%x`, `%y`, and the current control context.

Memory does not obey this simple model.

```mlir
memref.store %secret, %m[%i]
...
%x = memref.load %m[%j]
```

To label `%x`, the analysis must answer:

1. Can `%i` and `%j` refer to the same location?
2. What other stores may reach the load?
3. Does another pointer alias `%m`?
4. Did a call mutate the memory?
5. Does the address itself reveal a secret?
6. Did bufferization make two source tensors share one buffer?
7. Is the buffer placed on an unauthorized host?
8. Can stale or uninitialized contents be observed?

This is why memory analysis combines information flow, alias analysis, abstract interpretation, and operational semantics.

---

## 2. Concrete memory semantics

Let the concrete store be

\[
\mu:\mathrm{Addr}\to\mathrm{Val}.
\]

A pointer value is an address:

\[
p\in\mathrm{Addr}.
\]

A load evaluates as

\[
\operatorname{load}(\mu,p)=\mu(p).
\]

A store produces

\[
\operatorname{store}(\mu,p,v)=\mu[p\mapsto v].
\]

For arrays or memrefs, an address is calculated from a base, offset, indices, strides, and element size:

\[
\operatorname{addr}
=
base
+
offset
+
\sum_{k=0}^{r-1} i_k\cdot stride_k.
\]

In bytes, multiply element units by the element size if the stride representation requires it.

Security cares about both:

1. the value read or written;
2. the address used.

---

## 3. Three distinct security questions about a pointer

It is helpful to distinguish three labels.

### Pointer-value label

\[
\ell_{\mathrm{ptr}}(p)
\]

protects the pointer value itself.

If a pointer selects one of two objects based on a secret, the pointer value is secret-dependent.

### Address-observation label

\[
\ell_{\mathrm{addr}}(p)
\]

protects which concrete address or address class is accessed.

An observer may learn the address through cache behavior even if the pointer bits are never output.

### Pointee-content label

\[
\ell_{\mathrm{content}}(\lambda)
\]

protects data stored in abstract location \(\lambda\).

These labels need not be identical.

Example:

```text
pointer value:    server-visible
address pattern:  public fixed scan
pointee contents: client-confidential ciphertext
```

An FHE buffer handle may be public to the server while its idealized payload is confidential.

---

## 4. Actors, host address spaces, and allocation ACLs

In a distributed program, memory is not one global map. A useful concrete model is

\[
M:\mathcal H\rightarrow(\mathsf{Addr}\rightharpoonup\mathsf{Byte}),
\]

so every host has an address space \(M_h\).

An allocation descriptor can contain

\[
D_{alloc}(a)=
\langle
h_a,\ell_{content},\ell_{address},\rho,\operatorname{controllers}(h_a)
\rangle.
\]

This separates five questions:

1. Which host owns the address space?
2. Which principals can inspect that host?
3. Who may learn the stored contents?
4. Who may learn the address or access pattern?
5. Is the stored representation plaintext, ciphertext, shares, or an opaque handle?

### Pointers are local capabilities

A raw pointer or `memref` normally denotes storage in one host address space. Sending the pointer bits to another host does not transfer the referenced memory. Cross-host movement must be an explicit operation such as

```mlir
%remote = ifc.transfer %buffer to @server_host
```

with a representation and transfer contract.

A pointer therefore needs several actor-aware facts:

\[
\langle
\ell_{pointerBits},
\ell_{addressChoice},
\ell_{pointee},
h_{addressSpace},
capabilities
\rangle.
\]

The pointer bits may be public while the pointee is client-confidential. Conversely, a public table may be indexed by a client-secret address choice.

### Allocation ACLs and aliasing

For an allocation \(a\), define a reader set or principal policy for its plaintext contents. A host access is permitted only if the host's controllers are authorized for the exposed representation.

Aliasing can widen exposure without copying data. If bufferization creates an alias to client-confidential plaintext in a server-controlled address space, the policy is violated even if the compiler never inserts an explicit `send`.

This is why allocation placement is a security event:

\[
expose(site,h,facet,representation).
\]

### Memory traces are actor-relative

A load performed on the client may be invisible to the server. The same load performed on the server may reveal an address to the server controller.

For observer \(A\), include the event only when

\[
\operatorname{CanObserveMemory}(A,h,\Theta).
\]

Then compare

\[
\mu_{A,\Theta}(addr_0)
\quad\text{and}\quad
\mu_{A,\Theta}(addr_1).
\]

The target profile can give different observers different granularities, such as exact address for a local host controller and page number for a remote observer.

---

## 5. Abstract locations

A static analysis cannot usually track every concrete address. It groups addresses into **abstract locations**.

Let

\[
\Lambda
\]

be the set of abstract locations.

Examples:

- one allocation site;
- one global variable;
- one stack slot;
- one struct field;
- one array region;
- one memref base plus an index abstraction.

An abstract memory state is

\[
\widehat{\mu}:\Lambda\to D_{\mathrm{mem}},
\]

where \(D_{\mathrm{mem}}\) contains a content security descriptor and perhaps initialization, placement, and representation facts.

A pointer analysis computes

\[
\operatorname{Pt}(p)\subseteq\Lambda,
\]

the set of abstract locations that pointer \(p\) may reference.

---

## 6. May-alias and must-alias

Two pointers may alias when

\[
\operatorname{Pt}(p)\cap\operatorname{Pt}(q)\neq\varnothing.
\]

They must alias when the analysis proves they always denote the same location.

A simple sufficient condition is

\[
\operatorname{Pt}(p)=\operatorname{Pt}(q)=\{\lambda\},
\]

plus a proof that offsets agree.

### Why the distinction matters

A store through a must-alias pointer can overwrite the unique abstract location precisely.

A store through a may-alias pointer may affect several locations, so the analysis must conservatively join the new information into each candidate.

---

## 7. Strong updates

Suppose

\[
\operatorname{Pt}(p)=\{\lambda\}
\]

and \(\lambda\) represents one unique concrete cell.

For

```text
*p = v
```

a strong update replaces the old abstract content:

\[
\widehat{\mu}'(\lambda)=D(v).
\]

This models definite overwrite.

Example:

```c
x = secret;
x = 0;
output(x);
```

If `x` is a unique cell, the final content can be labeled public.

---

## 8. Weak updates

Suppose

\[
\operatorname{Pt}(p)=\{\lambda_1,\lambda_2\}.
\]

The store may affect either location. For each candidate,

\[
\widehat{\mu}'(\lambda_i)
=
\widehat{\mu}(\lambda_i)
\sqcup
D(v).
\]

This is a weak update.

It preserves both possibilities:

- the old value remains;
- the new value is written.

Weak updates are conservative but can cause labels to accumulate.

---

## 9. Worked alias example

```c
int a = public_value;
int b = public_value;
int *p;

if (secret)
    p = &a;
else
    p = &b;

*p = secret_data;
output(a);
```

The pointer points-to set is

\[
\operatorname{Pt}(p)=\{\lambda_a,\lambda_b\}.
\]

A weak update labels both locations secret:

\[
\widehat{\mu}'(\lambda_a)
=
Public\sqcup Secret
=
Secret,
\]

\[
\widehat{\mu}'(\lambda_b)
=
Public\sqcup Secret
=
Secret.
\]

That is conservative. In one run only one cell receives the secret, but the public output of `a` may differ across secret control choices, so rejecting is reasonable.

The address event also leaks which object was selected:

\[
\mathsf{memory}(addr(a))
\quad\text{versus}\quad
\mathsf{memory}(addr(b)).
\]

---

## 10. Flow sensitivity for memory

A flow-sensitive memory analysis computes a different abstract memory state at each program point:

\[
\widehat{\mu}_p.
\]

A flow-insensitive analysis has one global summary:

\[
\widehat{\mu}.
\]

Flow sensitivity is much more precise for stores and overwrites, but requires control-flow fixed points.

At a CFG merge:

\[
\widehat{\mu}_{join}
=
\widehat{\mu}_{left}
\sqcup
\widehat{\mu}_{right},
\]

joining each abstract location.

For loops, the analysis iterates until a fixed point.

---

## 11. Field sensitivity and index sensitivity

An abstract location can be coarse or precise.

### Field-insensitive

One struct object is one location:

\[
\lambda_{\mathsf{object}}.
\]

Writing a secret into one field taints the whole object.

### Field-sensitive

Use separate locations:

\[
\lambda_{\mathsf{object.field1}},
\qquad
\lambda_{\mathsf{object.field2}}.
\]

This is more precise.

### Index-insensitive array abstraction

One location represents all elements:

\[
\lambda_{\mathsf{array[*]}}.
\]

Any secret store can label every future load secret.

### Index-sensitive abstraction

Use exact constant indices or intervals:

\[
\lambda_{\mathsf{array[0]}},
\quad
\lambda_{\mathsf{array[1..15]}}.
\]

Precision improves, but the state space grows.

For tensor MLIR, a useful compromise is:

- exact constant slices;
- affine regions when available;
- one summary for unknown dynamic indices.

---

## 12. Address dependence is different from content dependence

Consider:

```c
x = public_table[secret_index];
```

If all table entries happen to be equal, the loaded value may be constant.

Still, the address is

\[
a=base+width\cdot secretIndex.
\]

A static IFC checker should generate:

\[
\ell_{\mathrm{contentResult}}
=
\ell_{\mathrm{val}}(table)
\sqcup
\ell_{\mathrm{idx}}(secretIndex),
\]

and separately:

\[
\ell_{\mathrm{memoryEvent}}
=
pc
\sqcup
\ell_{\mathrm{idx}}(secretIndex)
\sqcup
\ell_{\mathrm{layout}}(table).
\]

SMT may prove the loaded value equal while the address event still differs.

This is a common source of unsoundness in generic taint analyses that track only loaded values.

---

## 13. Pointer comparisons and pointer arithmetic

These operations can also leak:

```c
if (p == q) ...
r = p + secret_offset;
```

For pointer arithmetic,

\[
\ell_{\mathrm{ptr}}(r)
=
\ell_{\mathrm{ptr}}(p)
\sqcup
\ell_{\mathrm{idx}}(secretOffset).
\]

A later dereference creates an address event with the same dependency.

Pointer equality may expose allocation identity or placement. The target model must decide whether pointer values are observable directly or only through behavior.

---

## 14. Calls and memory summaries

A call

```mlir
%r = func.call @f(%p)
```

may:

- read through `%p`;
- write through `%p`;
- retain an alias;
- free the allocation;
- expose the address;
- produce variable-time behavior;
- transfer memory to another host.

A summary should specify at least:

\[
\mathsf{Reads}(f),
\quad
\mathsf{Writes}(f),
\quad
\mathsf{Escapes}(f),
\quad
\mathsf{Effects}(f),
\quad
\mathsf{Contract}(f).
\]

Without a summary, a sound analysis must be conservative:

- assume relevant memory may be read and written;
- assume pointers may escape;
- emit an opaque-call obligation.

---

## 15. Initialization and residual state

Memory security is not only about flows between initialized values.

### Uninitialized read

A buffer may contain data from a previous principal or kernel.

An abstract location can carry an initialization state:

\[
Init(\lambda)\in
\{
\mathsf{Uninitialized},
\mathsf{Initialized}(D)
\}.
\]

Reading uninitialized memory should be rejected or treated as an obligation.

### Lifetime and deallocation

After `dealloc`, aliases become dangling. A use-after-free is primarily memory safety, but allocator reuse can also reveal residual secrets.

### Zeroization

A security policy may require:

\[
\mathsf{secretBuffer}
\Longrightarrow
\mathsf{clearedBeforeDomainTransition}.
\]

An optimization that removes a clearing store can violate an erasure obligation even if ordinary functional behavior is unchanged.

This is usually a separate property from v1 noninterference, but the memory framework should leave room for it.

---

## 16. MLIR `memref` values

An MLIR `memref` is a typed descriptor of a strided memory region.

A type such as

```mlir
memref<4x8xi32>
```

describes a ranked memory reference.

More general layouts can be written as

```mlir
memref<?x?xi32, strided<[?, ?], offset: ?>>
```

A conceptual memref descriptor contains:

\[
\langle
base,
alignedBase,
offset,
sizes,
strides
\rangle.
\]

The address of element \((i_0,\ldots,i_{r-1})\) is approximately

\[
alignedBase
+
offset
+
\sum_k i_k\cdot stride_k.
\]

Security analysis must account for:

- labels on indices;
- labels on dynamic sizes;
- labels on strides and offsets;
- base-buffer placement;
- aliasing from subviews and casts.

---

## 17. `memref.subview`

A subview creates an aliasing view into another buffer.

```mlir
%sub = memref.subview %base[%off][%size][%stride]
```

The subview does not necessarily allocate new memory.

A points-to model may record

\[
\operatorname{Pt}(\%sub)
=
\{
\langle
\lambda_{\%base},
off,
size,
stride
\rangle
\}.
\]

The subview's layout label depends on:

\[
\ell_{\mathrm{layout}}(\%base)
\sqcup
\ell(\%off)
\sqcup
\ell(\%size)
\sqcup
\ell(\%stride).
\]

A secret offset can leak through every later address.

Because `%sub` aliases `%base`, stores through either view affect the same content abstraction.

---

## 18. Casts and reinterpretation

Operations such as:

```mlir
memref.cast
memref.reinterpret_cast
bufferization.to_buffer
bufferization.to_tensor
```

change type or view information.

A security analysis should not treat them as producing independent storage unless the semantics allocates or copies.

A safe default is:

\[
\operatorname{Pt}(result)
\supseteq
\operatorname{Pt}(operand).
\]

`reinterpret_cast` may introduce new dynamic offsets or strides, so layout and address dependencies must be propagated.

---

## 19. Why tensor semantics are easier

Tensor SSA values are immutable mathematical values.

For:

```mlir
%r = tensor.insert %x into %t[%i]
```

`%t` is not modified. `%r` is a new tensor value.

At tensor level, the semantics can be modeled functionally:

\[
r = store(t,i,x).
\]

No aliasing exists between `%t` and `%r` at the language level.

This gives a clean information-flow rule.

---

## 20. What bufferization does

Bufferization converts tensor semantics into memref semantics.

Conceptually:

```mlir
%r = tensor.insert %x into %t[%i]
```

may become either:

### Out-of-place

```mlir
%new = memref.alloc()
memref.copy %t_buffer, %new
memref.store %x, %new[%i]
```

### In-place

```mlir
memref.store %x, %t_buffer[%i]
```

The in-place version reuses storage.

MLIR's One-Shot Bufferize analyzes tensor SSA use-def chains, builds alias and equivalence information, and decides whether in-place reuse is safe. Operations describe their behavior through `BufferizableOpInterface`.

Functionally correct bufferization must preserve tensor values despite introduced mutation.

Security-preserving bufferization must additionally preserve:

- host exposure;
- address behavior;
- alias boundaries;
- initialization;
- release boundaries;
- representation protection.

---

## 21. Read-after-write conflicts

Consider:

```mlir
%t0 = tensor.from_elements %a, %a, %a
%t1 = tensor.insert %b into %t0[%i]
%x  = tensor.extract %t0[%j]
```

At tensor level, `%t0` remains unchanged. `%t1` is a new tensor.

If bufferization implemented `%t1` by overwriting `%t0`'s buffer, the later extraction from `%t0` could read the wrong value.

One-Shot Bufferize detects this read-after-write conflict and inserts a copy.

From a security perspective, the same decision can affect:

- allocation count;
- copy count;
- memory addresses;
- secret lifetime;
- which buffer is exposed to which host.

Therefore, functional bufferization analysis is necessary but not sufficient for security.

---

## 22. Security regression: unauthorized alias exposure

Suppose a source tensor is semantically protected:

```text
%secret_tensor:
  policy = client-only
  representation = protected
```

A lowering produces a plaintext memref on the server:

```mlir
%buf = memref.alloc() : memref<128xi32>
... write decrypted elements into %buf ...
func.call @debug_dump(%buf)
```

Functional output may remain correct.

But the target introduces

\[
\mathsf{expose}
(
server,
value,
Plain,
\%buf
).
\]

This violates placement confidentiality.

A source-level label attached only to `%secret_tensor` is not enough. The lowering validator must reconstruct or propagate the semantic policy into the target memory representation and inspect aliases and calls.

---

## 23. Security regression: secret-dependent copying

A bufferization or optimization may choose whether to copy based on a secret-dependent condition.

Then the trace differs through:

\[
\mathsf{allocation},
\quad
\mathsf{memory},
\quad
\mathsf{execCount}.
\]

In ordinary MLIR bufferization, compile-time analysis decisions do not depend on runtime secrets. However, generated target control flow or dynamic-shape conditions may.

The principle is:

> Compile-time choice being deterministic does not imply that generated runtime behavior is secret-independent.

---

## 24. Source-target representation relation

Tensor and memref states have different structures.

To validate bufferization, define

\[
\operatorname{RepRel}
(
\sigma_S,
\sigma_T
).
\]

For a tensor value \(t\) and target memref \(m\), the relation may require:

\[
\forall \bar i\in\operatorname{bounds}(t).\quad
t[\bar i]
=
\mu_T(\operatorname{addr}(m,\bar i)).
\]

It may also record:

- which memrefs alias;
- whether an allocation is initialized;
- which host owns the allocation;
- which representation protects the bytes;
- which extra target buffers are semantically invisible;
- which target layouts correspond to source indices.

A source-target validation query begins with related states rather than identical states.

---

## 25. Information-flow relation for memory states

Low-equivalence for memory can be defined by an observer-specific abstraction.

Let

\[
\operatorname{View}_{A,\Theta}(\mu)
\]

include:

- contents of authorized locations;
- allocation metadata visible to \(A\);
- protected projections of ciphertext buffers;
- not the plaintext content of protected representations.

Then

\[
\mu_0\approx_{A,\Theta}\mu_1
\quad\Longleftrightarrow\quad
\operatorname{View}_{A,\Theta}(\mu_0)
=
\operatorname{View}_{A,\Theta}(\mu_1).
\]

For aliased memory, equality must respect the same abstract object graph or a relation between corresponding allocations.

---

## 26. Encoding memory in SMT

A common bounded model represents memory as an SMT array:

\[
M:\mathrm{BitVec}_{w_a}\to\mathrm{BitVec}_{8}.
\]

A load of \(n\) bytes uses array selects; a store uses nested array stores.

Alternatively, tensor-shaped buffers can be represented as mathematical arrays indexed by tuples:

\[
T:
I_0\times\cdots\times I_{r-1}
\to
V.
\]

The choice depends on the IR level.

### Address trace

Even when memory contents are modeled abstractly, emit a symbolic address event:

\[
e_{\mathrm{addr}}
=
\mu_\Theta
(
base+offset+\sum_k i_k stride_k
).
\]

### Aliasing

If two pointer expressions can denote the same address, the SMT model naturally couples them through the same memory array.

Static points-to analysis is still valuable for slicing and for bounding the model.

---

## 27. Strong and weak updates in MLIR analysis

A practical analysis can maintain

```text
AbstractLocation -> MemorySecurityState
```

At a `memref.store`:

1. compute possible target regions;
2. compute the descriptor of the stored value;
3. perform a strong update if the target is unique and exact;
4. otherwise weakly join;
5. emit an address event;
6. update initialization state;
7. propagate through aliases.

At a `memref.load`:

1. compute possible source regions;
2. join their content descriptors;
3. join the address/index dependency into the result when selection itself carries information;
4. emit the memory event;
5. reject or obligate uninitialized reads.

---

## 28. Security-aware alias abstractions

Useful choices, from simplest to more precise:

### Allocation-site abstraction

One abstract location per `memref.alloc`, function argument, and global.

Good first implementation.

### Offset-class abstraction

Track constant offsets or affine intervals within an allocation.

Useful for tensor slices.

### Region abstraction

Track rectangular or strided regions:

\[
R=
\langle
base,
offsets,
sizes,
strides
\rangle.
\]

Two regions may overlap if their index sets intersect.

### Symbolic region constraints

Use Presburger or SMT constraints for dynamic affine indices.

More precise but more expensive.

A v1 compiler can use allocation-site plus exact constants, and send unresolved overlap questions to SMT or mark them unknown.

---

## 29. Bufferization-specific checks

For every tensor-to-buffer mapping, check:

1. **Policy preservation**

   The buffer content carries the tensor's element policy.

2. **Shape preservation**

   Dynamic dimensions retain shape labels.

3. **Layout provenance**

   New strides, offsets, and views carry layout dependencies.

4. **Placement safety**

   The buffer is allocated on an authorized host or under a protecting representation.

5. **Alias safety**

   No unauthorized alias can read or write the buffer.

6. **Address-trace safety**

   Generated indices do not introduce secret-dependent memory observations absent from the source model.

7. **Initialization**

   Every read is initialized under the supported semantics.

8. **Release discipline**

   Decrypted or released buffers do not appear earlier or on broader hosts.

9. **Lifetime obligations**

   Required clearing and deallocation are preserved when modeled.

---

## 30. Worked example: bufferized secret gather

Source:

```mlir
%x = tensor.extract %table[%secret_i]
```

Target:

```mlir
%x = memref.load %table_buf[%secret_i]
```

The source tensor semantics may already include a logical access event if the security model treats `tensor.extract` as observable.

Then the lowering preserves the channel rather than introducing it.

If the source semantics treats the tensor operation as abstract and oblivious, but the target emits a direct indexed load, the lowering introduces an address distinction.

This illustrates a critical design choice:

> The source observation model must state whether high-level tensor operations promise oblivious implementation or merely describe functional behavior.

A special operation such as

```mlir
%r = ifc.oblivious_gather ...
```

can carry a strong source contract that lowering must preserve.

---

## 31. Worked example: subview with secret offset

```mlir
%sub = memref.subview %base[%secret_off][16][1]
%x = memref.load %sub[%i]
```

The target address is

\[
a=
base
+
secretOff\cdot stride
+
i.
\]

Even if `%i` is public,

\[
\ell_{\mathrm{address}}
=
\ell(secretOff)
\sqcup
\ell(layout(base)).
\]

The subview descriptor must retain the secret offset provenance. If an analysis labels only `%i`, it is unsound.

---

## 32. Worked example: public pointer to secret content

Suppose `%p` always points to the same secret buffer.

\[
\ell_{\mathrm{ptr}}(p)=Public,
\qquad
\ell_{\mathrm{content}}(\lambda)=ClientOnly.
\]

The fixed address may be safe to observe.

A load result is still secret:

\[
\ell_{\mathrm{val}}(load(p))
=
ClientOnly.
\]

This example shows why pointer label and pointee label must be distinct.

---

## 33. Common mistakes

### Mistake 1: SSA means the whole program is alias-free

Only SSA values are single-assignment. Memrefs denote mutable storage.

### Mistake 2: pointer labels equal pointee labels

A public handle may point to secret content; a secret pointer may select public cells.

### Mistake 3: loads leak only their values

Addresses and widths can leak.

### Mistake 4: every store can strongly update

Strong updates require uniqueness and exactness.

### Mistake 5: tensor and memref values correspond one-to-one

Bufferization can reuse, copy, alias, split, and merge storage.

### Mistake 6: functional bufferization correctness implies security preservation

It does not rule out new exposures or traces.

### Mistake 7: unknown aliasing means no alias

Unknown must be treated conservatively or reported as an obligation.

---

## 34. Exercises

### Exercise 1

Given:

\[
Pt(p)=\{\lambda_1\},
\qquad
Pt(q)=\{\lambda_1,\lambda_2\},
\]

which stores permit strong updates?

### Exercise 2

Analyze:

```c
*p = secret;
x = *q;
```

under the assumption that \(p\) and \(q\) may alias.

### Exercise 3

For

```mlir
%sub = memref.subview %m[%off][%size][%stride]
```

list which security facets affect:

1. loaded values;
2. memory addresses;
3. allocation or transfer sizes.

### Exercise 4

Construct a source tensor program and a functionally correct in-place bufferization that violates source immutability because an old tensor value is read later.

### Exercise 5

Define a simple \(\operatorname{RepRel}\) between a rank-one tensor and a contiguous memref.

### Exercise 6

Why can a weak update cause false positives? Why is replacing it with a strong update without proof unsound?

### Exercise 7

Design an opaque-call memory summary for a constant-time cryptographic helper that reads one input buffer and writes one output buffer without retaining aliases.

---

## 35. Summary

Memory security is indexed by host and observer. A pointer identifies a location in a host address space; an allocation policy limits which principals may inspect its contents; and an address-event policy limits which principals may learn how it is accessed.


Memory analysis requires two related but distinct models:

\[
\boxed{
\text{abstract contents and aliases}
}
\]

and

\[
\boxed{
\text{observable addresses, sizes, and lifetimes}.
}
\]

For each pointer or memref, track:

\[
\text{where it may point}
+
\text{what those locations contain}
+
\text{how the address was chosen}
+
\text{who can observe the storage}.
\]

Bufferization is a security-critical lowering because it turns immutable tensor values into mutable, aliased physical storage. Secure translation validation must relate source tensor states to target memory states explicitly.

---

## Further reading

- MLIR, [Bufferization](https://mlir.llvm.org/docs/Bufferization/).
- MLIR, [`bufferization` dialect](https://mlir.llvm.org/docs/Dialects/BufferizationOps/).
- MLIR, [Ownership-Based Buffer Deallocation](https://mlir.llvm.org/docs/OwnershipBasedBufferDeallocation/).
- Standard compiler texts on points-to analysis, abstract interpretation, and memory SSA.
- Research on information flow for heap-allocated and object-oriented languages.

---

# Module 7 — Self-Composition and SMT

## Learning objectives

After this module, you should be able to:

1. explain self-composition as a reduction from 2-safety to safety;
2. construct two renamed copies of a program;
3. generate low-equivalence assumptions from security metadata;
4. encode symbolic observations in SMT;
5. interpret SAT, UNSAT, and UNKNOWN correctly;
6. lift a model into a concrete information-flow counterexample;
7. construct a different low-equivalence and observation query for each relevant principal or coalition.

---

## 1. Why the type system is not enough

A type system tracks possible dependence.

For:

```mlir
%x = arith.xori %secret, %secret
```

the label analysis gives

\[
\ell(x)=\ell(secret).
\]

But bitvector semantics gives

\[
x=0.
\]

If `%x` controls a branch, a static IFC checker may report a possible leak even though the branch is constant.

SMT can reason about actual symbolic values and prove the observation equal.

The division of labor is:

\[
\boxed{
\text{dataflow finds where a leak may occur}
}
\]

\[
\boxed{
\text{SMT decides whether an actual distinguishing pair exists}
}
\]

for a bounded, exactly encoded fragment.

---

## 2. Self-composition

Given program \(P\), create two renamed copies:

\[
P^0
\qquad\text{and}\qquad
P^1.
\]

Every variable and SSA value is duplicated:

\[
x^0,\ x^1.
\]

Public inputs are constrained equal:

\[
x^0=x^1.
\]

Secret inputs remain independent:

\[
s^0,\ s^1
\]

with no equality constraint.

Both copies execute symbolically. At the end, assert that an observer-visible event or trace differs.

If the resulting formula is satisfiable, the model is a two-run leak witness.

---

## 3. A first example

Program:

```c
if (secret)
    output(0);
else
    output(0);
```

### Copy 0

\[
b_0=secret_0.
\]

### Copy 1

\[
b_1=secret_1.
\]

Output values are equal:

\[
out_0=0,
\qquad
out_1=0.
\]

If the observer sees only output, the violation formula is

\[
out_0\neq out_1,
\]

which is UNSAT.

If the observer sees branches, the formula is

\[
b_0\neq b_1,
\]

which is SAT with

\[
secret_0=\mathsf{false},
\qquad
secret_1=\mathsf{true}.
\]

The same program is secure under one observation model and insecure under another.

---

## 4. General leak query

Let:

- \(\operatorname{Sem}(P,\sigma,\tau)\) encode program semantics;
- \(\operatorname{LowEq}_{A,\Delta}\) encode equal authorized initial knowledge and equal sanctioned releases;
- \(\operatorname{TraceEq}_{A,\Theta}\) compare visible traces.

The query is

\[
\begin{aligned}
\Phi_{\mathrm{leak}}(P)
={} &
\operatorname{Sem}(P,\sigma_0,\tau_0)\\
&\land
\operatorname{Sem}(P,\sigma_1,\tau_1)\\
&\land
\operatorname{LowEq}_{A,\Delta}(\sigma_0,\sigma_1)\\
&\land
\neg\operatorname{TraceEq}_{A,\Theta}(\tau_0,\tau_1).
\end{aligned}
\]

Interpretation:

- SAT: a modeled leak exists;
- UNSAT: no leak exists in the exact encoded fragment;
- UNKNOWN: no conclusion.

---

## 5. How metadata shapes the query

Security labels usually do not become unknown label variables in this query. Label inference has already run.

The metadata determines:

1. which inputs are constrained equal;
2. which inputs may differ;
3. which party observes each operation;
4. which representation facets are visible;
5. which target leakage function applies;
6. which release functions must be held equal;
7. which backward slice is relevant.

Example:

```text
public size:
  size_0 = size_1

client-secret index:
  index_0 and index_1 independent

FHE payload on server:
  plaintext payload omitted from server view

public ciphertext count:
  count_0 = count_1 required

release policy:
  R(secret_0) = R(secret_1)
```

---

## 6. Principal-indexed query construction and coalitions

The relational formula is indexed by an observer coalition \(A\). Labels and ACLs determine which equalities are inserted.

For each input facet \(f\):

\[
\operatorname{CanRead}(A,\ell_f)
\Longrightarrow
f_0=f_1.
\]

If \(A\) is not authorized to read the facet, the two copies remain independent.

### Example query matrix

Suppose:

```text
query elements:  client-only
model elements:  provider-only
shape:           client, provider, server
server trace:    visible to server
prediction:      released to client
```

For the **server** query:

\[
shape_0=shape_1,
\]

while query and model elements may differ. The solver asks whether server-visible placement, branch, memory, transfer, or latency events differ.

For the **client** query, the query is constrained equal because the client already knows it, while model weights may differ. The solver checks whether the client learns anything about the model beyond the sanctioned prediction.

For a **client-server coalition**, both the client-known query and server-visible metadata are fixed. The coalition query determines whether combining their views reveals additional provider information.

### Visibility projection

Not every symbolic event is compared for every actor. Define

\[
visible_{A,\Theta}(e)
\]

and construct

\[
Trace_{A,\Theta}=filter(visible_{A,\Theta},Trace).
\]

Representation contracts participate in this projection. For an FHE value on the server, the payload expression may be hidden while shape and ciphertext-count expressions are included.

### Query scheduling

A practical compiler should not enumerate all \(2^{|\mathcal P|}\) coalitions blindly. The policy environment declares a finite threat set

\[
\mathcal A=\{A_1,\ldots,A_k\}.
\]

The verifier creates one query per relevant observer, or reuses shared symbolic semantics with different low-equivalence and trace-projection constraints.

### Integrity and active attackers

The confidentiality-only v1 model treats attacker-controlled inputs as independent symbolic inputs. A full nonmalleable IFC model additionally constrains which values and control decisions the attacker may influence according to integrity labels. That extension changes both the paired-state relation and the allowed adversarial contexts; it is more than adding another equality.

---

## 7. Symbolic execution

A symbolic state maps SSA values to SMT terms.

For

```mlir
%z = arith.addi %x, %y : i32
```

encode

\[
z_0=bvadd(x_0,y_0),
\]

\[
z_1=bvadd(x_1,y_1).
\]

Use bitvectors for fixed-width integer semantics. Infinite mathematical integers can be unsound when overflow matters.

For

```mlir
%r = arith.select %c, %a, %b
```

encode

\[
r_j=ite(c_j,a_j,b_j)
\]

for \(j\in\{0,1\}\).

The upstream MLIR SMT dialect includes booleans, bitvectors, integers, arrays, equality, implication, and `ite`, so a verifier can construct formulas inside MLIR before exporting them to a solver.

---

## 8. Path conditions

For a branch:

```c
if (c)
    x = e_t;
else
    x = e_f;
```

symbolic execution can encode

\[
x=ite(c,e_t,e_f).
\]

Observable branch behavior remains separate:

\[
event_{\mathrm{branch}}=c.
\]

For more complicated control flow, maintain path conditions:

\[
PC_t=PC\land c,
\qquad
PC_f=PC\land\neg c.
\]

Events are guarded by their path conditions.

---

## 9. Memory encoding

A byte-addressed memory can be modeled as an SMT array:

\[
M:\mathrm{BV}_{w_a}\to\mathrm{BV}_8.
\]

A byte load is

\[
v=select(M,a).
\]

A byte store is

\[
M'=store(M,a,v).
\]

Multi-byte values require concatenation and endianness rules.

At tensor level, an \(n\)-dimensional tensor may instead be encoded as an array from index tuples to values:

\[
T:
I_0\times\cdots\times I_{n-1}\to V.
\]

The security event for a memory operation is still encoded separately:

\[
e_{\mathrm{addr}}
=
\mu_\Theta(a).
\]

Memory contents being equal does not imply addresses are equal.

---

## 10. Bounded loops

Unbounded loops are difficult for quantifier-free SMT.

A first implementation can:

1. require a static bound \(N\);
2. unroll \(N\) iterations;
3. give each iteration a validity condition.

For loop condition \(c_i\),

\[
valid_0=true,
\]

\[
valid_{i+1}=valid_i\land c_i.
\]

An operation event in iteration \(i\) is guarded by \(valid_i\).

Operation count can be encoded as

\[
count=\sum_{i=0}^{N-1} ite(valid_i,1,0).
\]

A leak query asks

\[
count_0\neq count_1.
\]

If the loop can exceed \(N\), the result is bounded and must be reported as such.

---

## 11. Trace encoding

### Explicit bounded event vector

Represent a trace by

\[
\tau=
\langle
e_0,\ldots,e_{N-1},n
\rangle.
\]

Each event may have fields:

\[
e_i=
\langle
valid_i,
kind_i,
site_i,
payload_i
\rangle.
\]

Trace equality requires:

\[
n_0=n_1
\]

and, for each position,

\[
valid_i^0=valid_i^1
\]

and equal visible fields when valid.

### Event-specific proof obligations

Instead of building one global trace, verify each possible effect:

\[
\exists \sigma_0,\sigma_1.
\ LowEq
\land
event_0\neq event_1.
\]

This is easier to slice and localize but may miss differences in order unless ordering is modeled.

A practical system can begin with event-specific queries and bounded structured trace segments.

---

## 12. Branch example in SMT style

Conceptual SMT-LIB:

```lisp
(declare-fun secret0 () Bool)
(declare-fun secret1 () Bool)

(define-fun branch0 () Bool secret0)
(define-fun branch1 () Bool secret1)

(assert (not (= branch0 branch1)))
(check-sat)
(get-model)
```

A model may return:

```text
secret0 = false
secret1 = true
```

That model becomes a compiler diagnostic.

---

## 13. Proving a syntactic dependency constant

Program:

```mlir
%x = arith.xori %secret, %secret : i32
%c0 = arith.constant 0 : i32
%b = arith.cmpi ne, %x, %c0 : i32
```

Copy 0:

\[
x_0=s_0\oplus s_0=0,
\qquad
b_0=(0\neq0)=false.
\]

Copy 1:

\[
x_1=s_1\oplus s_1=0,
\qquad
b_1=false.
\]

The divergence formula

\[
b_0\neq b_1
\]

is UNSAT.

The static label remains conservative; SMT discharges this particular effect.

---

## 14. Tensor-index example

Source:

```mlir
%x = tensor.extract %table[%secret_i]
```

Assume table and base are equal across runs.

\[
a_0=base+4i_0,
\]

\[
a_1=base+4i_1.
\]

The address leak query is

\[
0\le i_0,i_1<1024
\land
\mu_\Theta(a_0)\neq\mu_\Theta(a_1).
\]

Under exact addresses, SAT is immediate with

\[
i_0=0,\quad i_1=1.
\]

Under cache-line observation, adjacent indices may be equal, so the solver finds indices on different lines.

---

## 15. Variable latency

For operation \(op\), the target profile defines

\[
\operatorname{lat}_\Theta(op,\bar v).
\]

The query is

\[
\operatorname{lat}_\Theta(op,\bar v_0)
\neq
\operatorname{lat}_\Theta(op,\bar v_1).
\]

Three levels of modeling are possible:

1. relevant operands themselves;
2. documented timing buckets;
3. a constant-time contract returning `fixed`.

If no reliable model exists, emit an obligation rather than asserting safety.

---

## 16. Sanctioned release in the query

Suppose policy \(k\) permits release function \(R_k\).

Add

\[
R_k(\sigma_0)=R_k(\sigma_1)
\]

to low-equivalence.

Then ask whether any other observation differs.

For password checking:

\[
[s_0=g_0]=[s_1=g_1].
\]

The solver may choose two invalid guesses with different mismatch positions and expose a count or address difference.

---

## 17. Program slicing

Encoding an entire large module is expensive.

The static analysis constructs a provenance graph:

```text
secret source
    ↓
arithmetic
    ↓
index
    ↓
memory event
```

For an unresolved event:

1. start at the event expression;
2. follow SSA and memory dependencies backward;
3. include relevant path conditions;
4. stop at inputs, constants, or trusted summaries;
5. duplicate only that slice.

Labels and effect metadata are therefore query-planning information.

---

## 18. Counterexample lifting

A raw solver model is not a useful user interface.

Translate it into:

```text
observer: server
secret input 0: index = 0
secret input 1: index = 32

first divergent event:
  operation: tensor.extract
  site: foo.mlir:41
  run 0 address class: 0
  run 1 address class: 2

target profile:
  64-byte cache lines
```

For compiler preservation, also report the pass that first introduces divergence.

A good witness should be reproducible in an interpreter or test harness.

---

## 19. SAT, UNSAT, and UNKNOWN

### SAT

The formula has a model.

For a sound encoding, it corresponds to a real modeled leak.

### UNSAT

No violating pair exists in the exact encoded semantics.

This is a proof only for:

- supported operations;
- modeled target observations;
- stated loop bounds;
- stated memory assumptions;
- declared mechanism contracts.

### UNKNOWN

Causes include:

- solver timeout;
- unsupported dialect;
- unbounded loop;
- opaque call;
- incomplete alias model;
- missing latency contract.

UNKNOWN must never be converted to SAFE.

---

## 20. Soundness and completeness of the encoding

For the supported bounded fragment, aim to prove

\[
SAT(\Phi_{\mathrm{leak}})
\Longleftrightarrow
\exists\text{ modeled violating pair}.
\]

This contains two directions.

### Encoding soundness

Every satisfying assignment corresponds to a valid execution pair.

### Encoding completeness

Every violating execution pair can be represented by a satisfying assignment.

Practical abstractions may weaken completeness. For example, an overapproximated floating-point model can create spurious SAT results requiring refinement.

---

## 21. Common mistakes

### Mistake 1: asserting secret inputs differ

Noninterference allows them to be equal or different. Do not require inequality unless generating a nicer witness.

### Mistake 2: constraining all duplicate inputs equal

That proves only same-input determinism, not confidentiality.

### Mistake 3: comparing only final values

This misses trace channels.

### Mistake 4: using mathematical integers for machine arithmetic

Overflow changes semantics.

### Mistake 5: treating solver timeout as secure

It is UNKNOWN.

### Mistake 6: forgetting representation projections

Randomized ciphertext bytes need not be equal across runs even when server observations are secure under an ideal cryptographic contract.

---

## 22. Exercises

### Exercise 1

Self-compose:

```c
public_out = secret & 1;
```

Write the low-equivalence and divergence formula.

### Exercise 2

Encode a three-iteration bounded early-exit loop with validity bits.

### Exercise 3

Why is

\[
secret_0\neq secret_1
\]

not required in the general query?

### Exercise 4

Give an SMT formula that checks whether a loaded address differs at cache-line granularity.

### Exercise 5

A solver returns SAT because two randomized ciphertext byte strings differ. Explain how the observation model should be corrected.

### Exercise 6

Design a backward slice for a branch condition computed from five arithmetic operations and one unrelated matrix multiplication.

---

## 23. Summary

The same symbolic program can be checked from several actor viewpoints. Principal labels generate the observer-specific input equalities, host and mechanism contracts generate the observer-specific trace projection, and SMT searches for a distinguishing pair for that observer.


Self-composition turns

\[
\text{two-run confidentiality}
\]

into

\[
\text{one safety query over a product program}.
\]

Metadata determines what must be equal and what can be observed. Symbolic semantics determines whether the observations can actually differ.

The next module uses the same idea to compare source and target compiler IRs.

---

## Further reading

- G. Barthe et al., self-composition for secure information flow.
- ct-verif and other product-program constant-time verifiers.
- MLIR, [SMT Dialect](https://mlir.llvm.org/docs/Dialects/SMT/).
- S. Bang et al., [MLIR-TV](https://github.com/aqjune/mlir-tv).

---

# Module 8 — Security Translation Validation

## Learning objectives

After this module, you should be able to:

1. distinguish functional refinement from security refinement;
2. explain why security validation compares four executions;
3. define a program's observer-indistinguishability relation;
4. state the source-to-target security-regression query;
5. understand cross-level representation and observation relations;
6. explain per-pass localization and compositional pass validation;
7. define security refinement separately for each observer coalition and across changes in host placement or protocol representation.

---

## 1. Ordinary translation validation

A compiler transforms source program \(S\) into target program \(T\).

Ordinary translation validation checks the particular compilation result rather than proving the compiler correct once and for all.

A simplified functional property is

\[
\forall x.\quad
\operatorname{Result}(S,x)
=
\operatorname{Result}(T,x).
\]

A more realistic refinement relation accounts for:

- undefined or poison behavior;
- nondeterminism;
- memory effects;
- floating-point approximation;
- target-specific semantics.

MLIR-TV is an important methodological precedent: it uses SMT to validate high-level MLIR transformations involving tensors, loops, and bufferization.

Functional validation is necessary. It is not enough for confidentiality.

---

## 2. A functionally correct security regression

Source:

```mlir
%r = arith.select %secret, %a, %b : i32
```

Assume the source operation promises branchless, fixed-class behavior.

Target:

```mlir
cf.cond_br %secret, ^then, ^else
```

Both programs compute

\[
r=
\begin{cases}
a & secret\\
b & \neg secret.
\end{cases}
\]

So functional equivalence may hold.

The source traces can be equal across secret values:

```text
exec(select), latency(fixed)
```

The target traces differ:

```text
branch(false)
branch(true)
```

The compiler preserved the answer and broke confidentiality.

---

## 3. Do not compare source and target traces directly

A tempting condition is

\[
\operatorname{Trace}(S,x)
=
\operatorname{Trace}(T,x).
\]

This is far too strong.

Lowering necessarily changes:

- operation names;
- number of instructions;
- allocation structure;
- loop form;
- memory representation;
- call boundaries.

A tensor operation and a loop nest should not have identical traces.

The security question is different:

> Did the target make any previously indistinguishable pair of inputs distinguishable?

---

## 4. Indistinguishability kernel

For program \(P\), define

\[
\mathcal K_{A,\Theta,\Delta}(P)
=
\left\{
(x_0,x_1)
\ \middle|\
\begin{array}{l}
x_0\approx_A^\Delta x_1\\
\land\
\operatorname{Obs}_{A,\Theta}(P,x_0)
\sim
\operatorname{Obs}_{A,\Theta}(P,x_1)
\end{array}
\right\}.
\]

This is the set of low-equivalent input pairs that \(P\) keeps indistinguishable.

The target is security-refining when

\[
\mathcal K(S)\subseteq\mathcal K(T).
\]

The target may not split a source indistinguishability class.

We write

\[
S\preceq^{sec}_{A,\Theta,\Delta}T.
\]

---

## 5. Actor-indexed indistinguishability kernels

For every observer coalition \(A\), define an indistinguishability kernel

\[
\mathcal K_A(P)=
\{(x_0,x_1)\mid x_0\approx_A x_1
\land Obs_A(P,x_0)\sim Obs_A(P,x_1)\}.
\]

Security refinement is actor-indexed:

\[
S\preceq^{sec}_A T
\quad\Longleftrightarrow\quad
\mathcal K_A(S)\subseteq\mathcal K_A(T).
\]

The compiler satisfies the declared threat model when

\[
\forall A\in\mathcal A.\;S\preceq^{sec}_A T.
\]

### Why the actor index matters

A lowering can preserve security for one party and break it for another.

Example:

```text
source: encrypted tensor remains opaque on server
lowering: debug plaintext copy is created on client host
```

This might not add a server observation, but it may leak provider-owned information to the client.

### Host and principal mappings

Source and target may use different execution locations. Let

\[
\eta_H:\mathcal H_T\rightarrow\mathcal H_S\cup\{\mathsf{new}\}
\]

relate target hosts or devices to source-level locations, while principal identities remain stable through the compilation.

A CPU-to-GPU lowering, for instance, must state which principals control the GPU, runtime, and shared memory. A new target allocation cannot be treated as unobservable merely because the source had no corresponding allocation.

### Protocol-changing lowerings

A lowering may convert

```text
FHE tensor -> library call
MPC value  -> message exchange
oblivious gather -> target intrinsic
```

Security refinement compares actor-visible observations under the contracts on each side. It does not require the same internal event vocabulary.

The source may expose an abstract `fhe.eval` event while the target exposes calls, buffers, and transfers. An abstraction function must show that the target does not reveal more to any protected actor coalition.

---

## 6. The four-execution picture

To check one program, self-composition uses two executions:

\[
P(x_0),\quad P(x_1).
\]

To check a compiler lowering, use four:

\[
S(x_0),
\quad
S(x_1),
\quad
T(x_0),
\quad
T(x_1).
\]

The bad case is

\[
\operatorname{Obs}(S,x_0)
\sim
\operatorname{Obs}(S,x_1)
\]

but

\[
\operatorname{Obs}(T,x_0)
\not\sim
\operatorname{Obs}(T,x_1).
\]

---

## 7. SMT regression query

The core formula is

\[
\begin{aligned}
\Phi_{\mathrm{regress}}(S,T)
={} &
\operatorname{LowEq}_{A,\Delta}(x_0,x_1)\\
&\land
\operatorname{Sem}(S,x_0,\tau^S_0)\\
&\land
\operatorname{Sem}(S,x_1,\tau^S_1)\\
&\land
\operatorname{TraceEq}^{S}_{A,\Theta}
(\tau^S_0,\tau^S_1)\\
&\land
\operatorname{Sem}(T,x_0,\tau^T_0)\\
&\land
\operatorname{Sem}(T,x_1,\tau^T_1)\\
&\land
\neg
\operatorname{TraceEq}^{T}_{A,\Theta}
(\tau^T_0,\tau^T_1).
\end{aligned}
\]

SAT means a compiler-introduced distinction exists.

UNSAT means

\[
S\preceq^{sec}T
\]

for the supported model.

---

## 8. Why source and target may use different event vocabularies

At tensor level, an event may be:

```text
gather(secret_index)
```

At memref level:

```text
memory(address)
```

At LLVM level:

```text
load(pointer)
```

The event names are different, but their security meaning can be related.

Define level-specific observation abstractions:

\[
\alpha_S:
Trace_S\to Obs,
\]

\[
\alpha_T:
Trace_T\to Obs.
\]

Then compare

\[
\alpha_S(\tau^S_0)
=
\alpha_S(\tau^S_1)
\]

and

\[
\alpha_T(\tau^T_0)
=
\alpha_T(\tau^T_1).
\]

The common abstract observation domain might contain:

```text
path class
address class
operation count
host exposure
release event
latency class
```

The source need not expose the same low-level details as the target. It must state which distinctions its abstraction promises to hide.

---

## 9. Strong source operations

Some source operations should carry explicit security contracts.

Example:

```mlir
%r = ifc.oblivious_select %c, %a, %b
```

Its source semantics promises:

\[
\operatorname{branchObs}=\mathsf{none},
\]

\[
\operatorname{latencyObs}=\mathsf{fixed}.
\]

Lowering to a branch violates the contract.

By contrast, a plain functional `arith.select` may not universally promise constant-time lowering on every backend. The project must decide whether:

1. to give it a target-dependent security contract;
2. to introduce a dedicated `ifc.oblivious_select`;
3. to generate an outstanding backend obligation.

Security guarantees should not be smuggled into ordinary operations without documentation.

---

## 10. Functional and security refinement are independent

A compiler result should satisfy both:

\[
S\preceq^{fun}T
\]

and

\[
S\preceq^{sec}T.
\]

Possible combinations:

| Functional | Security | Interpretation |
|---|---|---|
| pass | pass | desired |
| pass | fail | correct output, leaked secret |
| fail | pass | wrong output, perhaps constant-time |
| fail | fail | both incorrect and insecure |

Security refinement does not prove functional correctness.

Functional refinement does not prove confidentiality.

---

## 11. Main preservation theorem

Define program security:

\[
Secure(P)
\quad\Longleftrightarrow\quad
\forall x_0,x_1.
\ LowEq(x_0,x_1)
\Rightarrow
Obs(P,x_0)\sim Obs(P,x_1).
\]

Then:

\[
\boxed{
Secure(S)
\land
S\preceq^{sec}T
\Longrightarrow
Secure(T).
}
\]

### Proof sketch

Assume \(Secure(S)\) and \(S\preceq^{sec}T\).

Take arbitrary low-equivalent \(x_0,x_1\).

By source security,

\[
Obs(S,x_0)\sim Obs(S,x_1).
\]

By security refinement,

\[
Obs(T,x_0)\sim Obs(T,x_1).
\]

Therefore \(T\) is secure.

The theorem is simple because the work is in defining and proving the refinement relation correctly.

---

## 12. Transitivity and pass composition

Security refinement should be transitive:

\[
S\preceq^{sec}M
\land
M\preceq^{sec}T
\Longrightarrow
S\preceq^{sec}T.
\]

### Proof

If a pair is indistinguishable in \(S\), the first relation makes it indistinguishable in \(M\), and the second makes it indistinguishable in \(T\).

For a pass pipeline

\[
P_0\to P_1\to\cdots\to P_n,
\]

if

\[
P_i\preceq^{sec}P_{i+1}
\]

for every \(i\), then

\[
P_0\preceq^{sec}P_n.
\]

This supports per-pass validation and first-bad-pass localization.

---

## 13. Per-pass localization

Suppose the final target fails.

Rather than compare only \(P_0\) and \(P_n\), save each intermediate IR:

```text
P0 source
P1 canonicalized
P2 linalg lowered
P3 bufferized
P4 control flow lowered
P5 LLVM dialect
```

Check adjacent pairs.

If

\[
P_0\preceq^{sec}P_1,
\quad
P_1\preceq^{sec}P_2,
\]

but

\[
P_2\not\preceq^{sec}P_3,
\]

then `P2 -> P3` is the first security-breaking transformation.

A useful diagnostic reports:

```text
first bad pass: one-shot-bufferize
source operation: ifc.protected_tensor
target operation: memref.alloc
new event: expose(server, plaintext-buffer)
```

---

## 14. Cross-level input and memory relations

Source and target states may differ.

Tensor source:

\[
\sigma_S:
t\mapsto [v_0,\ldots,v_{n-1}].
\]

Memref target:

\[
\sigma_T:
m\mapsto
\langle base,offset,size,stride,\mu\rangle.
\]

Define

\[
RepRel(\sigma_S,\sigma_T).
\]

For contiguous rank-one data:

\[
\forall i<n.\quad
t[i]
=
\mu(base+i\cdot width).
\]

The validation query starts with:

\[
RepRel(\sigma^S_0,\sigma^T_0)
\]

and

\[
RepRel(\sigma^S_1,\sigma^T_1).
\]

For security, the relation also includes policy and representation facts:

- target buffer corresponds to source protected value;
- target aliases are permitted;
- host placement is related;
- extra scratch buffers have approved visibility.

---

## 15. Bufferization example

Source:

```mlir
%r = tensor.insert %x into %t[%i]
```

Source values `%t` and `%r` are distinct.

Target may reuse one buffer in place.

Functional validation proves the old source tensor is not used afterward or inserts a copy.

Security validation additionally asks:

- Does the new buffer appear on an unauthorized host?
- Does the in-place address pattern depend on secret `%i`?
- Is an extra copy count secret-dependent?
- Does an alias escape to a debug call?
- Is protected representation preserved?

This is why a source-target memory relation must include more than element equality.

---

## 16. Observation-transparent rewrites

For rewrite

\[
L\rightsquigarrow R,
\]

define semantic observation transparency:

\[
\forall x_0,x_1.\quad
Obs(L,x_0)\sim Obs(L,x_1)
\Longrightarrow
Obs(R,x_0)\sim Obs(R,x_1).
\]

A checkable sufficient criterion may require that the rewrite introduces no newly secret-dependent:

- branch;
- indirect call target;
- loop count;
- address;
- allocation size;
- transfer size;
- latency-relevant operand;
- host exposure;
- error class;
- release;
- opaque call.

If each rewrite in a pass is transparent and contextual closure holds, the whole pass preserves security.

This can certify simple canonicalizations without invoking SMT for every instance.

---

## 17. Contextual closure

A local rewrite appears inside a larger program context \(C[-]\).

We need

\[
L\preceq^{sec}R
\Longrightarrow
C[L]\preceq^{sec}C[R].
\]

This requires assumptions:

- the context is well typed;
- the rewrite's free variables and effects are accounted for;
- memory and release events do not interact in unmodeled ways;
- source and target observation abstractions compose.

Contextual closure is easier for pure expressions than for side-effecting memory transformations.

---

## 18. Source security versus preservation only

A pass may preserve insecurity.

Suppose source already has a secret branch, and target keeps it.

Then

\[
S\preceq^{sec}T
\]

may hold even though both are insecure.

Therefore, an end-to-end certification needs:

1. source security check;
2. functional refinement;
3. security refinement;
4. discharged obligations.

Preservation alone says no **new** distinction was introduced.

---

## 19. Example: full scan lowered to direct gather

Source promises oblivious lookup:

```text
for every table row:
    touch row
    mask-select requested row
```

Source addresses are equal for every secret index.

A bad optimization recognizes the result as `table[index]` and emits one load.

Functionally equivalent:

\[
result=table[index].
\]

Security regression:

\[
Addr_S(i_0)=Addr_S(i_1)
\]

as full trace sequences, but

\[
Addr_T(i_0)\neq Addr_T(i_1).
\]

The relational validator catches exactly the optimization ordinary equivalence rewards.

---

## 20. Example: multiply lowered to runtime helper

Source target profile says native multiplication has fixed latency.

A later lowering on a narrower target introduces:

```text
call __muldi3
```

If the helper has an unknown or operand-dependent timing contract, the target observation changes.

Possible outcomes:

```text
unsafe:
  helper contract proves variable time and secret operands differ

conditional:
  secure if __muldi3 is operand independent

unknown:
  no helper contract available
```

The obligations ledger is part of the preservation result.

---

## 21. Example: release moved earlier

Source:

```text
compute secret intermediate
sanitize
release final aggregate
```

Target:

```text
store intermediate in client-visible buffer
sanitize
return final aggregate
```

The final result remains correct.

But target exposes an intermediate value before the sanctioned release.

The release-aware trace detects

\[
\mathsf{expose}(client,intermediate)
\]

which is absent from the source's indistinguishability relation.

---

## 22. Challenges

### Differing control-flow structures

Lockstep comparison is not always possible. Use symbolic traces, product control flow, or event-sequence encodings.

### Undefined behavior

If source behavior is undefined, refinement conditions need care. Security claims should not rely on undefined source executions.

### Floating point

Exact relational reasoning may be expensive or require abstractions and refinement.

### Dynamic allocation

Source and target addresses are not equal. Compare abstract address classes and allocation correspondence.

### Opaque backend calls

Security stops at contracts.

### Solver scalability

Use static rewrite criteria, slicing, bounded kernels, and compositional summaries.

---

## 23. Common mistakes

### Mistake 1: requiring identical source and target traces

Lowering changes implementation structure.

### Mistake 2: validating only the final target

This loses first-bad-pass localization.

### Mistake 3: assuming a value mapping is enough

Security is about observations; SSA structure can change radically.

### Mistake 4: forgetting source security

Preservation can preserve an existing leak.

### Mistake 5: mixing functional and security claims

Run both checks and report both results.

---

## 24. Exercises

### Exercise 1

Give a functionally equivalent target for:

```c
r = secret ? a : b;
```

that violates a branch-observation model.

### Exercise 2

Prove transitivity of \(\preceq^{sec}\).

### Exercise 3

Why can a target have more operations than a source and still preserve security?

### Exercise 4

Define a representation relation between a \(2\times2\) tensor and a row-major memref.

### Exercise 5

List the new observations that could be introduced by loop unrolling, vectorization, and outlining.

### Exercise 6

Design a syntactic observation-transparency rule for replacing `addi x, 0` with `x`.

---

## 25. Summary

Security translation validation is not one global property. It is a family of preservation checks indexed by observer coalitions, host-control assumptions, and mechanism contracts.


Functional validation asks:

\[
\text{Did compilation preserve the answer?}
\]

Security translation validation asks:

\[
\text{Did compilation preserve which secret inputs are distinguishable?}
\]

The core bad case is

\[
\boxed{
\text{source indistinguishable}
\land
\text{target distinguishable}.
}
\]

The next module explains how intentional information release changes the equivalence relation.

---

## Further reading

- S. Bang et al., [MLIR-TV](https://github.com/aqjune/mlir-tv).
- Alive2 and translation validation for LLVM.
- Verified constant-time preservation in CompCert-style work.
- The later formal Viaduct work on simulation and robust hyperproperty preservation.

---

# Module 9 — Sanctioned Release and Robust Declassification

## Learning objectives

After this module, you should be able to:

1. explain declassification as a controlled exception to noninterference;
2. distinguish release payload, audience, authority, timing, and prerequisites;
3. define release-relative low-equivalence;
4. explain robust declassification and transparent endorsement;
5. analyze protocol-oracle examples;
6. separate decryption from authorization to release;
7. model release as an explicit principal-authorized expansion of an ACL or weakening of an authority label.

---

## 1. Why strict noninterference is too strong

A useful program often reveals something about a secret.

A password checker reveals

\[
R(password,guess)
=
[password=guess].
\]

A medical computation may reveal an approved diagnosis.

A private inference service may reveal

\[
R(W,x)=\operatorname{argmax}(\operatorname{model}(W,x)).
\]

Strict noninterference would reject any secret-dependent output.

We therefore need an explicit, controlled exception.

---

## 2. Declassification

In a two-level lattice,

\[
Low\sqsubseteq High.
\]

Normal information flow rejects

\[
High\to Low.
\]

Declassification authorizes one such downgrade:

\[
High
\xrightarrow{\mathsf{release}}
Low.
\]

But an unchecked operation

```text
declassify(secret)
```

is an escape hatch. A security theorem becomes meaningless if any code can declassify any value for any reason.

**Sanctioned release** attaches a policy to the downgrade.

---

## 3. Release is not necessarily global publication

In a principal-based system, release often expands the reader set only to a specific party.

Before:

```text
plaintext readers: nobody
```

After:

```text
plaintext readers: client
```

The value may remain hidden from:

```text
server
provider
other clients
```

So release means

\[
\text{controlled expansion of authorized observers},
\]

not necessarily "make public to everyone."

---

## 4. Five dimensions of release

A release policy \(k\) can be modeled as

\[
\Delta(k)=
\left\langle
A_k,
R_k,
O_k,
I_k,
Q_k
\right\rangle.
\]

### Audience \(A_k\)

Who may learn the result?

### Release function \(R_k\)

What exact function of protected state may be learned?

### Authority \(O_k\)

Whose permission is needed?

### Trusted influence \(I_k\)

Who may influence the payload, guard, policy choice, or occurrence?

### Requirements \(Q_k\)

What prerequisites must hold?

Examples:

- authenticate ciphertext;
- verify a proof;
- sanitize approximate-FHE noise;
- decrypt only on the client;
- use a constant-time comparison;
- rate-limit repeated queries.

---

## 5. Release as an ACL and authority transition

In the reader-set presentation, ordinary information flow requires

\[
R_{dest}\subseteq R_{source}.
\]

A release deliberately permits an expansion such as

\[
R_{source}=\{C\}
\quad\longrightarrow\quad
R_{released}=\{C,P\}.
\]

This is not an ordinary assignment. It requires evidence that the policy owner authorizes the new audience and that only the declared release function is exposed.

In the principal-formula presentation, release permits a flow that would otherwise fail

\[
\ell_{from}\not\sqsubseteq\ell_{to}.
\]

A release policy supplies the authority for that exception.

### Separate actor roles

For a release, name at least four roles:

1. **source owners** whose confidentiality is weakened;
2. **audience** that receives the new information;
3. **decision influencers** that can affect whether release occurs;
4. **executing hosts** that decrypt, sanitize, verify, or transmit the result.

These roles need not be the same principal.

### Example

For private inference:

```text
owners:       client and provider
release:      final class ID
recipient:    client
evaluator:    server
decryptor:    client or threshold key holders
```

The client being the recipient does not by itself authorize the client to control the release guard or to receive provider-owned intermediate logits.

### ACL-locality in SSA

The operation

```mlir
%released = ifc.release %protected {policy = @prediction_to_client}
```

creates a new value with the expanded audience. The input `%protected` keeps its old policy. Any alias or buffer containing the protected value remains protected unless the policy explicitly releases that representation too.

---

## 6. Release an expression, not the entire source secret

Suppose secret \(s\) is a salary.

Allowed:

\[
R(s)=[s>100000].
\]

Not automatically allowed:

\[
s,
\quad
s\bmod 1000,
\quad
\operatorname{bitlength}(s),
\quad
\text{timing dependent on }s.
\]

A release policy describes an information function, not merely a source label change.

Two implementations that return the same Boolean may still differ in timing and leak more.

---

## 7. SSA formulation

Release should create a new SSA value.

```mlir
%secret_result = ...
%released =
  ifc.release %secret_result
    {policy = @prediction_to_client}
```

The original remains protected.

\[
D(\%secretResult).\ell=High,
\]

\[
D(\%released).\ell=ClientReadable.
\]

This operation does not mutate all aliases or every future use of the secret.

That makes downgrading explicit in def-use chains.

---

## 8. Encryption, decryption, and release

These are separate transitions.

### Concealment

\[
\mathsf{Plain}
\rightarrow
\mathsf{Ciphertext}.
\]

Policy is unchanged.

### Decryption

\[
\mathsf{Ciphertext}
\rightarrow
\mathsf{Plain}.
\]

Policy is still unchanged. Decryption is legal only at a host authorized to hold the plaintext.

### Release

The audience policy changes.

\[
Readers_{before}
\subset
Readers_{after}.
\]

Therefore:

\[
\boxed{
\mathsf{encrypt}\neq\mathsf{release}
}
\]

and

\[
\boxed{
\mathsf{decrypt}\neq\mathsf{release}.
}
\]

HEIR's `secret.reveal` is a scheme-agnostic decryption boundary. A party-aware compiler should not automatically interpret it as policy declassification.

---

## 9. Release-relative low-equivalence

For observer \(A\), define

\[
\sigma_0\approx_A^\Delta\sigma_1
\]

when:

1. all initially \(A\)-visible facts are equal;
2. every release function authorized to \(A\) is equal.

Formally,

\[
\operatorname{PublicView}_A(\sigma_0)
=
\operatorname{PublicView}_A(\sigma_1)
\]

and

\[
\forall k\text{ visible to }A.\quad
R_k(\sigma_0)=R_k(\sigma_1).
\]

Security becomes

\[
\sigma_0\approx_A^\Delta\sigma_1
\Longrightarrow
Trace_{A,\Theta}(P,\sigma_0)
\sim
Trace_{A,\Theta}(P,\sigma_1).
\]

Read this as:

> Once all authorized released information is held constant, no remaining observation may vary with the secret.

---

## 10. Password protocol oracle

Policy:

\[
R(password,guess)
=
[password=guess].
\]

Two runs:

```text
run 0:
  invalid guess
  mismatch at byte 1

run 1:
  invalid guess
  mismatch at byte 12
```

Authorized result:

\[
R(\sigma_0)=R(\sigma_1)=false.
\]

An early-exit comparison produces counts

\[
count_0=1,
\qquad
count_1=12.
\]

Therefore the implementation releases:

```text
validity bit
plus mismatch-position information
```

The second part is not sanctioned.

This is the ideal example of release-relative trace security.

---

## 11. Release occurrence is information

Consider:

```c
if (secret)
    release(0);
```

The payload is constant, but the occurrence differs.

The trace contains

\[
\mathsf{release}(policy,audience,0)
\]

in one execution and no event in the other.

Therefore, a release policy must cover:

- whether release occurs;
- how many times;
- when relative to other events;
- to which audience;
- with what payload.

A policy may intentionally release an option:

\[
R(\sigma)=
\begin{cases}
Some(v)&condition\\
None&otherwise.
\end{cases}
\]

Then occurrence is part of the sanctioned result rather than an accidental side channel.

---

## 12. Release timing and surrounding behavior

Even when both runs release the same value, these can leak:

- one releases earlier;
- one performs more work first;
- one allocates an extra buffer;
- one returns a distinct error;
- one sends a different-sized message;
- one cleans up a different set of objects.

The release event belongs inside the full trace, not outside the security model.

---

## 13. Integrity

Confidentiality says who may learn information.

Integrity says who is trusted to influence information.

Use a label

\[
\ell=\langle C,I\rangle.
\]

A release guard controlled by an untrusted principal can be dangerous:

```mlir
scf.if %attacker_controlled {
  %r = ifc.release %secret {policy = @k}
}
```

The audience may be authorized, but the attacker may be using release occurrence as an oracle.

Integrity also matters when a server supplies a result to be released. The compiler may require authentication or proof verification before the value is considered trustworthy.

---

## 14. Robust declassification

Informally, robust declassification requires:

> The principal receiving newly declassified information should not be able to improperly control what gets declassified or whether declassification happens.

A release rule checks both:

- confidentiality authority;
- integrity of the payload and guard.

Viaduct incorporates this idea through nonmalleable information-flow control.

### Example

Suppose a client may learn whether its password guess is correct.

The client is allowed to choose `guess`, because the release function explicitly includes it:

\[
R(password,guess)=[password=guess].
\]

But the client should not be able to choose an arbitrary expression:

```text
release(password[guess])
```

or control a hidden branch that releases additional server state.

The policy must distinguish permitted inputs to the release function from arbitrary attacker influence.

---

## 15. Transparent endorsement

Endorsement raises integrity:

\[
Untrusted
\xrightarrow{\mathsf{endorse}}
Trusted.
\]

Unchecked endorsement is the integrity analogue of unchecked declassification.

Transparent endorsement roughly requires that a provider of untrusted information be allowed to know what information is being endorsed. This blocks using endorsement to smuggle secrets into trusted state in a way the provider cannot observe.

For an initial honest-but-curious compiler, full transparent endorsement may be deferred. Still, the architecture should reserve:

- integrity labels;
- explicit endorsement operations;
- authentication/proof contracts.

---

## 16. A release typing judgment

A conceptual rule is

\[
\Pi;\Delta;\Theta;\Gamma;pc;h
\vdash
\mathsf{release}_k(v)
:
D'
\triangleright
E;\Omega.
\]

Premises include:

1. \(k\in\Delta\);
2. current host may access the representation;
3. required owners authorize the release;
4. audience equals \(A_k\);
5. \(v\) computes the permitted function \(R_k\);
6. \(pc\) and release guard satisfy integrity requirements;
7. sanitizers, authentication, or proofs in \(Q_k\) are present;
8. release occurrence and trace effects conform to policy.

The result descriptor \(D'\) has the expanded reader set.

---

## 17. Static checks versus SMT checks

### Static checks

Good for:

- policy identifier exists;
- audience is correct;
- host is authorized to decrypt;
- required sanitizer operation dominates release;
- release is not under an obviously untrusted guard;
- required proof value is present;
- no direct use bypasses the release op.

### SMT checks

Good for:

- implementation expression equals \(R_k\);
- no extra observation varies when \(R_k\) is equal;
- two error paths reveal only the same authorized result;
- a masking expression really computes the approved function.

---

## 18. Checking expression equivalence to policy

Suppose policy permits

\[
R(s)=s\bmod2.
\]

Implementation releases

\[
v=s\bmod4.
\]

Ask SMT:

\[
\exists s.\quad v(s)\neq R(s).
\]

SAT proves the implementation does not match the policy.

A more subtle implementation may be extensionally equal but syntactically different; SMT can prove equality.

---

## 19. FHE private inference release

Inputs:

\[
\ell(x)=ClientOnly,
\]

\[
\ell(W)=ProviderOnly.
\]

Intermediate logits:

\[
z=model(W,x).
\]

Policy:

\[
R(W,x)=argmax(z).
\]

Allowed:

```text
class ID to client
```

Not automatically allowed:

```text
full logits
intermediate activations
model weights
client input
secret shape
server timing differences
```

A release may require:

```text
decryption at client
proof or authentication of evaluator result
circuit-privacy sanitization
```

The compiler verifies ordering and policy use. It relies on external contracts for cryptographic sufficiency.

---

## 20. Facet-specific release

A tensor policy can release only one facet.

Examples:

\[
R(T)=shape(T),
\]

\[
R(T)=sum(T),
\]

\[
R(T)=\#nonzero(T),
\]

\[
R(T)=argmax(T).
\]

Releasing shape does not release elements.

Releasing an aggregate does not release individual rows.

The descriptor for the released result should reflect the function's output facets, not relabel the original tensor.

---

## 21. Lowering preservation for release

A compiler pass must not:

- move release earlier;
- duplicate release;
- broaden the audience;
- decrypt on another host;
- expose a pre-release buffer;
- skip authentication;
- remove a sanitizer;
- replace one uniform error with several distinguishable errors;
- change release count or timing beyond policy.

Release events therefore participate in security translation validation.

---

## 22. Policy quality is outside basic enforcement

A compiler can prove that code follows a declared policy.

It cannot automatically decide that the policy is wise.

A policy

\[
R(s)=s
\]

authorizes full disclosure.

Repeated one-bit releases can reveal substantial information through adaptive querying.

Additional topics include:

- quantitative leakage;
- privacy budgets;
- differential privacy;
- rate limiting;
- adaptive composition.

Do not claim those from ordinary sanctioned-release noninterference.

---

## 23. Common mistakes

### Mistake 1: release means set the label to public

Audience may be narrower than global public.

### Mistake 2: decryption implies release

It changes representation only.

### Mistake 3: policy checks only payload

Occurrence, timing, audience, and surrounding events matter.

### Mistake 4: integrity is unrelated

Untrusted control can weaponize release.

### Mistake 5: delete release events before trace comparison

Hold authorized release values equal, then compare the complete remaining trace.

### Mistake 6: relabel the original SSA value

Create a new released value.

---

## 24. Exercises

### Exercise 1

Define a release policy for a medical model that releases only a Boolean risk flag to the patient.

### Exercise 2

Two invalid MAC tags produce the same `false` result but different error codes. Does the implementation satisfy release-relative noninterference?

### Exercise 3

Explain why `secret.reveal` should not automatically expand the reader set.

### Exercise 4

Give an example where release payload is constant but release occurrence leaks.

### Exercise 5

Describe an integrity requirement for releasing an FHE server's result to a client.

### Exercise 6

A policy releases tensor shape. Which other facets must remain protected?

---

## 25. Summary

Sanctioned release is an actor-specific policy transition: named owners authorize a precise function for a named audience, while integrity rules constrain which actors may influence the released value and release decision.


Sanctioned release is controlled declassification:

\[
\boxed{
\text{what}
+
\text{to whom}
+
\text{by whose authority}
+
\text{under whose influence}
+
\text{after which safeguards}.
}
\]

The relational guarantee is:

\[
\boxed{
\text{same authorized release}
\Longrightarrow
\text{same remaining observation}.
}
\]

The next module explains how cryptographic and backend mechanisms are represented as contracts and obligations.

---

## Further reading

- C. Acay et al., [Viaduct](https://www.cs.cornell.edu/andru/papers/viaduct/viaduct.pdf), especially label checking, declassification, endorsement, and protocol assignment.
- Literature on robust declassification, transparent endorsement, and nonmalleable information flow.
- HEIR [`secret` dialect](https://heir.dev/docs/dialects/secret/) for conceal/reveal representation boundaries.

---

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

\[
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
\]

This contract states both who must be trusted and what observations remain visible.

---

## 3. Viaduct-style authority labels for mechanisms

Viaduct associates every protocol \(M\) with an authority label \(L(M)\). A protocol may realize a component requiring label \(\ell\) only when

\[
L(M)\Rightarrow\ell.
\]

This gives a uniform way to compare local execution, replication, commitments, zero-knowledge proofs, and MPC.

### Local execution

For `Local(h)`, the protocol authority is the authority of host \(h\):

\[
L(Local(h))=L(h).
\]

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

\[
AllowedCoalition_M(A)
\]

rather than a vague statement that “MPC is secure.”

### Why our contract is richer than one authority label

An authority label is necessary but insufficient for tensor and side-channel verification. Our mechanism contract also records

\[
\langle
hosts,
representations,
visibleFacets,
traceContract,
coalitionModel,
assumptions
\rangle.
\]

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

\[
B\preceq^{contract}M
\]

when concrete backend \(B\) refines ideal mechanism \(M\).

Then a substitution theorem can state

\[
Secure(P[M])
\land
B\preceq^{contract}M
\Longrightarrow
Secure(P[B]).
\]

The compiler does not prove lattice hardness. It proves that the program uses the mechanism within its declared interface.

---

## 5. Local plaintext execution

Contract:

\[
M=Local(h).
\]

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

\[
M=FHE(pk,evaluator,decryptors).
\]

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

\[
\#mult,
\quad
\#rotate,
\quad
depth,
\quad
\#bootstrap,
\quad
ciphertextBytes.
\]

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

\[
M=MPC(H,t,model).
\]

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

\[
M=ObliviousGather(h).
\]

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

\[
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
\]

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

\[
Secure_\Theta(P).
\]

This means \(P\) is secure under target profile \(\Theta\).

To transfer the claim to a real platform, require

\[
Adequate(\Theta,platform).
\]

Then:

\[
Secure_\Theta(P)
\land
Adequate(\Theta,platform)
\Longrightarrow
Secure_{real}(P).
\]

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

\[
\Pi:Ops\to Mechanisms.
\]

An assignment is valid when every operation's inferred requirement is satisfied.

A conceptual judgment is

\[
\Sigma;\Delta;\Theta;\Pi
\models
op@M
:
D
\triangleright\Omega.
\]

Premises include:

\[
M\in Viable(op),
\]

\[
Authority(M)\Rightarrow Requirement(op),
\]

\[
RepresentationsCompatible,
\]

\[
FacetExposureSafe,
\]

\[
TraceSafe_\Theta,
\]

\[
ReleaseSafe_\Delta.
\]

A v1 verifier can check a programmer-provided assignment.

A later synthesizer can search for an optimal assignment.

---

## 17. Mechanism selection as constrained optimization

Security constraints are hard constraints:

\[
Valid(\Pi,P).
\]

Then optimize:

\[
\Pi^*
=
\arg\min_{\Pi:Valid(\Pi,P)}
Cost_\Theta(\Pi).
\]

A useful lexicographic objective is

\[
\left\langle
|\Omega_\Pi|,
TCBWeight(\Pi),
Latency(\Pi),
Bandwidth(\Pi),
Memory(\Pi)
\right\rangle.
\]

This first minimizes outstanding assumptions and trusted code, then performance.

Do not allow a weighted objective to trade confidentiality for speed.

---

## 18. Counterexample-guided mechanism synthesis

A future system can run:

\[
Synthesize
\to
Verify
\to
Block
\to
Resynthesize.
\]

Example:

1. optimizer chooses FHE with unpadded secret shape;
2. relational verifier finds different transfer sizes;
3. add constraint requiring public padding or shape-hiding mechanism;
4. optimizer selects padded FHE or MPC.

The validator becomes an independent certification layer for synthesized plans.

---

## 19. Two-owner example

Policy:

\[
Readers(x)=\{client\},
\]

\[
Readers(W)=\{provider\}.
\]

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

If \(M_1\) outputs representation \(\rho\), then \(M_2\) must accept \(\rho\).

If \(M_1\) exposes shape, the policy must authorize it.

If \(M_2\) returns a ciphertext lacking circuit privacy, the release policy may require a sanitizer before decryption.

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

\[
\boxed{
\text{what it computes}
+
\text{what it reveals}
+
\text{who participates}
+
\text{what it assumes}.
}
\]

An obligation is a missing premise in the end-to-end theorem, not a silent guess.

The next module assembles the individual definitions into a proof architecture.

---

## Further reading

- C. Acay et al., [Viaduct](https://www.cs.cornell.edu/andru/papers/viaduct/viaduct.pdf).
- C. Acay et al., [formal Viaduct security report](https://www.cs.cornell.edu/andru/papers/viaduct-formal/viaduct-formal-tr.pdf).
- HEIR [`secret` dialect](https://heir.dev/docs/dialects/secret/).
- Universal composability and ideal functionality as advanced follow-up topics.

---

# Module 11 — Proof Architecture

## Learning objectives

After this module, you should be able to:

1. identify the separate theorems needed for an end-to-end compiler claim;
2. understand the proof role of lattice properties and monotone dataflow;
3. outline a trace-sensitive IFC soundness proof;
4. state self-composition and SMT-encoding correctness;
5. prove the central security-refinement preservation theorem;
6. explain pass composition, target adequacy, and mechanism substitution;
7. state actor-indexed soundness theorems and coalition-parametric preservation results.

---

## 1. Why one giant theorem is a bad idea

A compiler security result depends on several layers:

```text
policy algebra
→ label inference
→ abstract analysis
→ source security
→ SMT encoding
→ compiler preservation
→ backend and cryptographic assumptions
```

Trying to prove all of this in one induction makes the statement hard to understand and the proof hard to maintain.

A better strategy is a stack of small theorems with explicit assumptions.

The final theorem then composes them.

---

## 2. The end-to-end shape

A useful final statement is:

\[
\frac{
\begin{array}{c}
Infer(S)=\Gamma^*\\
\Gamma^*\vdash S\triangleright\Omega\\
FuncRefine(S,T)\\
SecurityRefine_{A,\Theta,\Delta}(S,T)\\
Discharged(\Omega)
\end{array}
}{
Secure_{A,\Theta,\Delta}(T)
}.
\]

This conclusion depends on:

1. inference being correct;
2. typing implying source security;
3. translation validation establishing security refinement;
4. functional correctness being checked separately;
5. obligations being real premises.

---

## 3. Theorem family A: label algebra

Let

\[
\mathcal L=
\langle
L,\sqsubseteq,\sqcup,\sqcap,\bot,\top
\rangle.
\]

Prove:

### Partial order

\[
\ell\sqsubseteq\ell
\]

\[
\ell_1\sqsubseteq\ell_2
\land
\ell_2\sqsubseteq\ell_1
\Longrightarrow
\ell_1=\ell_2
\]

\[
\ell_1\sqsubseteq\ell_2
\land
\ell_2\sqsubseteq\ell_3
\Longrightarrow
\ell_1\sqsubseteq\ell_3.
\]

### Join

\[
\ell_1\sqsubseteq\ell_1\sqcup\ell_2,
\]

\[
\ell_2\sqsubseteq\ell_1\sqcup\ell_2,
\]

and if

\[
\ell_1\sqsubseteq u
\quad\text{and}\quad
\ell_2\sqsubseteq u,
\]

then

\[
\ell_1\sqcup\ell_2\sqsubseteq u.
\]

### Product facets

If each facet is a lattice, then

\[
L_{\mathrm{tensor}}
=
L_{\mathrm{val}}
\times
L_{\mathrm{idx}}
\times
L_{\mathrm{shape}}
\times
L_{\mathrm{layout}}
\]

is a lattice under componentwise order and join.

This supports fixed-point analysis.

---

## 4. Actor and authority algebra obligations

The proof stack needs a formal actor environment

\[
\Pi=\langle\mathcal P,\mathcal H,L,controllers,\mathcal A\rangle,
\]

where \(\mathcal A\) is the declared set of attacker coalitions.

The foundational results include:

1. **Acts-for order.** \(\Rightarrow\) is reflexive and transitive, and is antisymmetric modulo logical equivalence of principal formulas.
2. **Label lattice.** The confidentiality/integrity product with \(\sqsubseteq,\sqcup,\sqcap\) satisfies the lattice laws.
3. **ACL normalization.** Translating a reader/influencer ACL into the internal principal representation preserves `CanRead`, `CanInfluence`, flow, and join for the supported policy fragment.
4. **Host-authorization soundness.** If a plaintext facet is statically approved for host \(h\), every principal coalition able to observe that host is authorized to read the facet.
5. **Coalition-parametric IFC.** A well-typed program is noninterfering for every \(A\in\mathcal A\).

### Actor-indexed source theorem

The source-language theorem should be stated as

\[
\Pi;\Delta;\Theta\vdash P
\land Discharged(\Omega)
\Longrightarrow
\forall A\in\mathcal A.\;Secure_{A,\Theta,\Delta}(P).
\]

### Observer monotonicity

If observer \(A_2\) sees at least everything visible to \(A_1\), then proving security for \(A_2\) may imply security for \(A_1\), provided their low-equivalence relations are ordered compatibly. This can reduce duplicate proof work, but it requires a lemma about both observation inclusion and initial knowledge. Do not assume it merely from set inclusion.

### Placement and mechanism lemmas

For every exposed facet:

\[
Exposed(A,h,\rho,f)
\Longrightarrow
CanRead(A,\ell_f).
\]

For mechanism substitution:

\[
Concrete_M\preceq Contract_M
\]

must hold for every coalition covered by the contract. A single-protocol security claim without its corruption threshold is not sufficient.

---

## 5. Theorem family B: dataflow termination and inference

Let

\[
F:\widehat{State}\to\widehat{State}
\]

be the global transfer functional.

Prove:

### Monotonicity

\[
x\sqsubseteq y
\Longrightarrow
F(x)\sqsubseteq F(y).
\]

Each operation transfer function must be monotone.

### Termination

If the abstract domain has finite height, repeated joins reach a fixed point.

If not, use widening and prove the widening is sound.

### Fixed-point soundness

Let

\[
\widehat{\sigma}^*
=
lfp(F).
\]

Then every concrete reachable state is represented by the abstract state at the corresponding program point:

\[
Reach(P,p)\subseteq\gamma(\widehat{\sigma}^*_p).
\]

### Principality

If label inference computes \(\Gamma^*\), then every other valid assignment is at least as restrictive under the chosen order:

\[
\Gamma\models\mathcal C(P)
\Longrightarrow
\Gamma^*\preceq\Gamma.
\]

This gives minimum-authority inference.

---

## 6. Abstract-interpretation soundness

For an operation \(op\), let

\[
F_{op}(\widehat{\sigma})
=
\widehat{\sigma}'.
\]

A local soundness condition is:

\[
\sigma\in\gamma(\widehat{\sigma})
\land
\sigma\xrightarrow{op/e}\sigma'
\Longrightarrow
\sigma'\in\gamma(\widehat{\sigma}').
\]

For event dependency:

\[
ActualDeps(e)
\sqsubseteq
AbstractLabel(e).
\]

The analysis may claim extra dependencies. It must not omit a real dependency.

For memory, the theorem includes:

- points-to overapproximation;
- weak-update soundness;
- alias propagation;
- initialization state;
- address-event dependencies.

---

## 7. Source-language IFC soundness

The headline source theorem is:

\[
\Pi;\Delta;\Theta;\Gamma
\vdash
P
\triangleright
E;\Omega
\land
Discharged(\Omega)
\Longrightarrow
Secure_{A,\Theta,\Delta}(P).
\]

There are several standard proof styles.

### Unwinding proof

Show local conditions guaranteeing that low-equivalent states remain low-equivalent step by step.

### Two-run induction

Induct directly over paired executions.

### Logical relations

Define a relation indexed by labels and types, then prove the fundamental theorem.

For an undergrad-scale core language, an unwinding or two-run induction is easiest to understand.

---

## 8. Low-equivalence relation

For scalar stores:

\[
\sigma_0\approx_A\sigma_1
\]

when every variable readable by \(A\) has equal value.

For memory:

\[
\mu_0\approx_A\mu_1
\]

when authorized locations and visible metadata agree, modulo allocation correspondence.

For protected representations, use an observer projection:

\[
View_A(\rho_0)=View_A(\rho_1).
\]

With sanctioned release:

\[
\sigma_0\approx_A^\Delta\sigma_1
\]

also requires equal release functions.

The relation must match the observation theorem exactly.

---

## 9. Key lemmas for IFC soundness

### Expression agreement

If

\[
\Gamma\vdash e:\ell
\]

and observer \(A\) may read \(\ell\), then low-equivalent states give equal expression values:

\[
\sigma_0\approx_A\sigma_1
\Longrightarrow
\llbracket e\rrbracket\sigma_0
=
\llbracket e\rrbracket\sigma_1.
\]

### High expression confinement

If \(A\) cannot read \(\ell\), expression results may differ, but those differences cannot flow into an \(A\)-visible sink without a checked release.

### Low event agreement

If an event is visible to \(A\), typing guarantees its dependency label is readable by \(A\). Therefore paired executions generate equal event payloads.

### High-context confinement

If current \(pc\) is unreadable by \(A\), the command cannot:

- modify \(A\)-visible state;
- emit \(A\)-visible events;
- perform an \(A\)-visible release.

### Preservation of low-equivalence

Paired steps preserve low-equivalence of states.

Combine these lemmas by induction over execution length.

---

## 10. Loops and fixed points in the proof

For a `while` loop, the two runs may execute different numbers of iterations.

If iteration count is observable and the guard depends on an unreadable secret, typing should reject the loop.

For accepted loops, the guard observation is equal, so the two executions remain synchronized.

A termination-insensitive proof assumes both terminate. It still proves equal finite iteration traces.

---

## 11. Declassification soundness

A release theorem states:

\[
WellTypedRelease_\Delta(P)
\Longrightarrow
NoninterferenceModulo_\Delta(P).
\]

The proof relation already equates sanctioned release functions:

\[
R_k(\sigma_0)=R_k(\sigma_1).
\]

The release rule must ensure:

- emitted release payload equals \(R_k\);
- audience matches;
- occurrence and guard comply;
- integrity premises hold;
- no extra event depends on hidden distinctions.

Robust declassification requires a stronger attacker-aware theorem than basic honest-but-curious noninterference.

Be explicit about which one is proved.

---

## 12. Self-composition correctness

Let

\[
Product(P)
\]

be the self-composed program.

Prove a correspondence:

\[
\operatorname{Exec}
(
Product(P),
\langle\sigma_0,\sigma_1\rangle
)
=
\langle
\operatorname{Exec}(P,\sigma_0),
\operatorname{Exec}(P,\sigma_1)
\rangle
\]

up to renaming and product-state representation.

Then:

\[
Product(P)\text{ reaches bad}
\Longleftrightarrow
\exists \sigma_0,\sigma_1.
\ LowEq
\land
TraceDiff.
\]

This justifies reducing noninterference to safety.

---

## 13. SMT encoding correctness

Let

\[
Encode(P,\varphi)
\]

translate a bounded semantic problem into SMT.

Aim to prove:

### Soundness

\[
SAT(Encode(P,\varphi))
\Longrightarrow
\exists\text{ concrete modeled execution satisfying }\varphi.
\]

### Completeness

\[
\exists\text{ concrete modeled execution satisfying }\varphi
\Longrightarrow
SAT(Encode(P,\varphi)).
\]

Completeness may be limited by:

- bounds;
- abstractions;
- unsupported floating point;
- unknown calls;
- quantifier approximations.

State the fragment precisely.

---

## 14. Witness-lifting theorem

Suppose SMT returns model \(m\).

A witness-lifting function produces concrete inputs:

\[
Lift(m)=\langle x_0,x_1\rangle.
\]

Prove:

\[
SATModel(m)
\Longrightarrow
Replay(P,x_0,x_1)
\text{ exhibits the reported divergence}.
\]

This is not only a UI feature. It checks that model interpretation, bit widths, tensor layouts, and memory reconstruction are correct.

---

## 15. Security refinement theorem

Define

\[
S\preceq^{sec}T
\]

by

\[
\forall x_0,x_1.
\ LowEq(x_0,x_1)
\land
Obs(S,x_0)\sim Obs(S,x_1)
\Longrightarrow
Obs(T,x_0)\sim Obs(T,x_1).
\]

Then:

\[
Secure(S)
\land
S\preceq^{sec}T
\Longrightarrow
Secure(T).
\]

This is the central compiler theorem.

Its proof is one paragraph, but the relation depends on correct source and target semantics, observer mappings, representation relations, and release policies.

---

## 16. Reflexivity and transitivity

### Reflexivity

\[
P\preceq^{sec}P.
\]

Immediate because an indistinguishable pair in \(P\) remains indistinguishable in \(P\).

### Transitivity

\[
P_0\preceq^{sec}P_1
\land
P_1\preceq^{sec}P_2
\Longrightarrow
P_0\preceq^{sec}P_2.
\]

Take a pair indistinguishable in \(P_0\). The first relation gives indistinguishability in \(P_1\); the second gives it in \(P_2\).

### Pass composition

By induction:

\[
\bigwedge_{i=0}^{n-1}
P_i\preceq^{sec}P_{i+1}
\Longrightarrow
P_0\preceq^{sec}P_n.
\]

---

## 17. Observation-transparent rewrite theorem

For rewrite rule \(L\rightsquigarrow R\), define

\[
Transparent(L,R)
\]

when it preserves input indistinguishability.

Prove:

1. a syntactic criterion implies transparency;
2. transparency is preserved in well-formed contexts;
3. a pass made only of transparent rewrites security-refines its input.

The syntactic criterion must account for effects, not only value dependence.

This theorem can reduce solver use for simple rewrites.

---

## 18. Target adequacy theorem

Let modeled observation be

\[
Obs^\Theta.
\]

Let real observation be

\[
Obs^{real}.
\]

A strong adequacy condition is that real observation is a function of modeled observation:

\[
\exists g.\quad
Obs^{real}(P,\sigma)
=
g(Obs^\Theta(P,\sigma)).
\]

Then:

\[
Secure_\Theta(P)
\Longrightarrow
Secure_{real}(P).
\]

Proof:

If modeled observations are equal, applying \(g\) gives equal real observations.

When adequacy is not established, it becomes an obligation.

---

## 19. Mechanism substitution theorem

For ideal mechanism \(M\) and concrete backend \(B\):

\[
B\preceq^{contract}M.
\]

If

\[
Secure(P[M])
\]

and the concrete backend reveals no more than the ideal contract, then

\[
Secure(P[B]).
\]

This is the modular bridge from compiler reasoning to cryptographic or runtime implementations.

---

## 20. Choreography and distributed compilation

If the compiler later generates distributed endpoint programs, add:

- source-to-choreography simulation;
- endpoint projection soundness;
- communication progress;
- mechanism instantiation;
- robust hyperproperty preservation.

The later formal Viaduct work is a model for this proof decomposition.

This is a follow-on layer, not necessary for the first security-translation-validation theorem.

---

## 21. Trusted computing base

A theorem should name its trusted components.

Possible TCB:

```text
core MLIR semantics
security transfer functions
self-composition transform
SMT encoder
SMT solver
target profile
mechanism contracts
last verified IR boundary
```

Some components can be reduced later through proof-producing solvers, mechanized semantics, or validation of generated artifacts.

Do not hide the TCB in an appendix.

---

## 22. What not to claim

Do not infer:

\[
Secure_\Theta(P)
\]

means secure against every physical channel.

Do not infer:

\[
UNSAT
\]

means secure beyond the exact encoded fragment.

Do not infer:

\[
SecurityRefine(S,T)
\]

means \(S\) was secure or \(T\) functionally correct.

Do not infer:

\[
WellTyped(P)
\]

means policy annotations are wise.

Each theorem has a precise conclusion.

---

## 23. A realistic first-paper theorem package

A strong first system can prove:

1. lattice and transfer monotonicity;
2. label inference correctness;
3. source type-and-effect soundness;
4. self-composition correctness;
5. SMT encoding soundness for a bounded fragment;
6. security-refinement preservation;
7. pass composition;
8. conditional target adequacy.

Full distributed simulation and concrete cryptographic proofs can remain future work.

---

## 24. Exercises

### Exercise 1

Prove that a componentwise product of four lattices is a lattice.

### Exercise 2

State the abstract-interpretation soundness condition for `memref.store`.

### Exercise 3

Sketch a proof of high-context confinement.

### Exercise 4

Prove the main security-preservation theorem.

### Exercise 5

Prove transitivity of security refinement.

### Exercise 6

Suppose modeled observation is exact address and real observation is cache-line address. Define \(g\) and show adequacy.

### Exercise 7

Why does the converse fail? If a cache-line model is secure, exact-address security need not follow.

### Exercise 8

Write assumptions needed for an FHE mechanism-substitution theorem.

---

## 25. Summary

Every major theorem is quantified over a policy environment and a declared set of observer coalitions. Actor authority is therefore part of the formal statement, not an implementation annotation added after the proof.


The proof architecture is modular:

\[
\boxed{
\text{analysis soundness}
\to
\text{source security}
\to
\text{SMT correctness}
\to
\text{security refinement}
\to
\text{target security}
}
\]

with mechanism and platform assumptions represented as explicit premises.

The next module translates this architecture into MLIR implementation components.

---

## Further reading

- Standard texts on type soundness and abstract interpretation.
- G. Barthe et al., self-composition.
- Verified compilation work for constant-time preservation.
- C. Acay et al., [formal Viaduct report](https://www.cs.cornell.edu/andru/papers/viaduct-formal/viaduct-formal-tr.pdf).

---

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

\[
HostEnv(h)=\langle authority,controllers,addressSpace,targetProfile\rangle.
\]

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

\[
D_1\sqcup D_2
=
\langle
\ell^1_{val}\sqcup\ell^2_{val},
\ell^1_{idx}\sqcup\ell^2_{idx},
\ell^1_{shape}\sqcup\ell^2_{shape},
\ell^1_{layout}\sqcup\ell^2_{layout},
\ldots
\rangle.
\]

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

\[
pc_p.
\]

At function entry:

\[
pc=\bot.
\]

For a region entered under condition `%c`:

\[
pc_{region}
=
pc_{parent}
\sqcup
\ell_{\mathrm{val}}(\%c).
\]

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

\[
\ell_{val}(z)
=
pc
\sqcup
\ell_{val}(x)
\sqcup
\ell_{val}(y).
\]

Optional event:

\[
\mathsf{exec}(site,\mathsf{addi})
\]

with dependency \(pc\) if operation occurrence depends only on control.

If target marks `addi` fixed-latency, no operand-derived latency effect is needed.

---

## 12. Example transfer: conditional branch

```mlir
cf.cond_br %c, ^then, ^else
```

Effect:

\[
e=
\mathsf{branch}(site,c).
\]

Dependency:

\[
\ell(e)
=
pc\sqcup\ell_{val}(c).
\]

Successor control states:

\[
pc_{then}
=
pc\sqcup\ell_{val}(c),
\]

\[
pc_{else}
=
pc\sqcup\ell_{val}(c).
\]

The static checker compares event observers to the dependency label.

---

## 13. Example transfer: tensor extract

```mlir
%x = tensor.extract %t[%i]
```

Result:

\[
\ell_{val}(x)
=
pc
\sqcup
\ell_{val}(t)
\sqcup
\ell_{idx}(i).
\]

Effect:

\[
e=
\mathsf{memory}
(
site,
Address(t,i),
width,
read
).
\]

Dependency:

\[
pc
\sqcup
\ell_{idx}(i)
\sqcup
\ell_{shape}(t)
\sqcup
\ell_{layout}(t).
\]

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

\[
Policy(output)=Policy(input),
\]

\[
Representation(output)=Secret/FHEAbstract.
\]

For reveal:

\[
Policy(output)=Policy(input),
\]

\[
Representation(output)=Plain.
\]

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

For unresolved effect \(e\), compute a backward slice.

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

\[
\boxed{
\text{persistent policy boundaries}
}
\]

from

\[
\boxed{
\text{recomputed abstract security facts}.
}
\]

Dataflow finds possible dependencies. Operation interfaces define security effects. SMT decides unresolved relational obligations. Per-pass validation ensures that lowering does not introduce new distinctions.

---

## Further reading

- MLIR, [Writing DataFlow Analyses](https://mlir.llvm.org/docs/Tutorials/DataFlowAnalysis/).
- MLIR, [Interfaces](https://mlir.llvm.org/docs/Interfaces/).
- MLIR, [Bufferization](https://mlir.llvm.org/docs/Bufferization/).
- MLIR, [SMT Dialect](https://mlir.llvm.org/docs/Dialects/SMT/).
- HEIR, [`secret` dialect](https://heir.dev/docs/dialects/secret/).
- S. Bang et al., [MLIR-TV](https://github.com/aqjune/mlir-tv).

---

# Module 13 — Case Studies

## Learning objectives

After this module, you should be able to:

1. apply the full analysis pipeline to real or faithful vulnerability classes;
2. separate source-level leaks from compiler-introduced regressions;
3. write descriptors, observations, and SMT queries for each case;
4. identify what the compiler proves and what remains an obligation;
5. design an evaluation corpus with vulnerable/fixed pairs;
6. state the principals, hosts, coalitions, ACLs, and release audiences for every security case study.

---

## 1. Case-study template

For every case, ask:

1. What are the secret and public inputs?
2. Who is the observer?
3. What policy labels apply?
4. What representation and placement are used?
5. Which event can differ?
6. Can static IFC decide it?
7. What SMT query is generated?
8. Is the bug in the source or introduced by compilation?
9. What is the repair?
10. What assumptions remain?

This template prevents the evaluation from becoming a disconnected bug list.

---

# Case Study A — KyberSlash-style variable-time division

## 2. Actor table and observer matrix for every case

Before writing MLIR, create an actor table.

| Field | Questions |
|---|---|
| Principals | Who owns secrets, operates machines, or receives results? |
| Hosts | Where does each stage execute and store data? |
| Controllers | Which principals can inspect or modify each host? |
| Secret facets | Which actor may read values, indices, shapes, and layouts? |
| Observer coalitions | Against whom is the property proved? |
| Integrity assumptions | Who may influence inputs, guards, and releases? |
| Sanctioned release | What exact function is revealed to which audience? |
| Mechanism assumptions | FHE key holders, MPC threshold, trusted libraries, hardware obligations |

Then define an observer matrix for the expected events:

| Event | Client | Provider | Server |
|---|---:|---:|---:|
| encrypted upload size | yes | no | yes |
| plaintext query | yes | no | no |
| server memory address | no | no | yes |
| model plaintext | no | yes | no |
| released prediction | yes | policy-dependent | no |

This prevents a common evaluation error: declaring a program simply “secure” without naming who is being protected from whom.

### Applying the table to the flagship cases

- **KyberSlash:** the secret owner is the key holder; the local host or co-resident timing observer sees target-latency events. There may be only one application principal, but there is still a distinct attacker observer.
- **Clangover/select-to-branch:** the protected principal owns the secret condition; the target host observer sees the introduced branch.
- **Secret tensor gather:** the client owns the token/index; the server observer sees addresses or cache classes.
- **Two-owner FHE:** client and provider own disjoint inputs; server observes protected representations; the client receives only the sanctioned result.
- **Release oracle:** the protocol author sanctions one result bit; the adversarial caller must not learn mismatch position through trace differences.

Every vulnerable/fixed pair should keep the same actor table. Otherwise, a changed policy can make an insecure implementation appear “fixed.”

---

## 3. Security issue

KyberSlash identified secret-dependent division timing in several Kyber/ML-KEM implementations, including code derived from the official reference implementation. The attack literature demonstrates that operand-dependent division timing can support key recovery on affected targets.

The compiler lesson is:

> An arithmetic operation can be functionally correct and still leak because its latency class depends on a secret operand.

Primary reading: [KyberSlash project and paper](https://kyberslash.cr.yp.to/papers.html).

---

## 4. Faithful MLIR kernel

Illustrative reduction:

```mlir
func.func @decode_coeff(
    %secret_coeff: i32,
    %q: i32
) -> i32 {
  %scaled = arith.muli %secret_coeff, %c2 : i32
  %r = arith.divui %scaled, %q : i32
  return %r : i32
}
```

Policy:

\[
\ell(secretCoeff)=KeySecret.
\]

Target profile:

\[
Relevant_\Theta(divui)=\{lhs,rhs\}.
\]

Observer sees:

\[
\mathsf{variableLatency}
(
site,
divui,
lat_\Theta(scaled,q)
).
\]

---

## 5. Static result

\[
\ell(scaled)=KeySecret.
\]

Latency dependency:

\[
\ell_{lat}
=
\ell(scaled)\sqcup\ell(q).
\]

If the observer is not authorized for key material, the operation is rejected or sent to SMT.

A conservative target profile treats relevant operands as the latency observation, making the violation immediate.

---

## 6. Relational query

Choose two low-equivalent inputs:

\[
q_0=q_1,
\]

while

\[
secretCoeff_0,\ secretCoeff_1
\]

are independent.

Ask:

\[
lat_\Theta
(
divui,
2secretCoeff_0,
q
)
\neq
lat_\Theta
(
divui,
2secretCoeff_1,
q
).
\]

SAT produces two coefficients in different latency classes.

---

## 7. Repair and preservation

A source patch may replace division with constant-time arithmetic such as multiplication and shifting under appropriate arithmetic conditions.

The compiler then must check that lowering does not reintroduce:

- `div`;
- `rem`;
- a variable-time helper;
- a target-specific multiplication helper.

Result:

```text
source fixed:
  passes source trace check

lowering:
  conditionally verified if helper contracts hold
```

The tool should not claim that every multiply is constant-time on every target.

---

# Case Study B — Clangover-style compiler-introduced branch

## 8. Security issue

Reports on ML-KEM's `poly_frommsg` showed that recent Clang configurations could recognize a branchless source idiom and emit a secret-dependent branch. The functional result remained correct, but constant-time intent was broken.

Primary readings:

- [NIST PQC forum report](https://groups.google.com/a/list.nist.gov/g/pqc-forum/c/hqbtIGFKIpU)
- [PQShield technical description](https://pqshield.com/pqshield-plugs-timing-leaks-in-kyber-ml-kem-to-improve-pqc-implementation-maturity/)

This should be described carefully as a cross-level compiler-preservation example. Unless reproduced in an MLIR pass itself, it is not evidence that upstream MLIR contains the same bug.

---

## 9. Source and target

Source-level or high-level IR intent:

```mlir
%mask = arith.select %secret_bit, %all_ones, %zero : i32
```

Source observation contract:

\[
branchObs=\mathsf{none},
\]

\[
latencyObs=\mathsf{fixed}.
\]

Bad target:

```mlir
cf.cond_br %secret_bit, ^set, ^clear
```

Target observation:

\[
branchObs=secretBit.
\]

---

## 10. Functional validation

Both compute:

\[
mask=
\begin{cases}
2^{32}-1 & secretBit\\
0 & \neg secretBit.
\end{cases}
\]

So

\[
FuncRefine(S,T)
\]

can hold.

---

## 11. Security query

Choose:

\[
secretBit_0=false,
\qquad
secretBit_1=true.
\]

Source:

\[
Trace_S(x_0)\sim Trace_S(x_1).
\]

Target:

\[
branch_0=false,
\qquad
branch_1=true.
\]

Therefore,

\[
\Phi_{regress}(S,T)
\]

is SAT.

Diagnostic:

```text
functional refinement: passed
security refinement: failed
first new distinction: branch outcome
```

This is the defining demonstration for the project.

---

# Case Study C — Secret tensor gather and embedding lookup

## 12. Security issue

A token embedding lookup accesses a row selected by a token ID:

\[
embedding[token].
\]

Cache-side-channel research on local LLM inference has shown that embedding access patterns can reveal token information. Two relevant 2025 studies are:

- [I Know What You Said](https://arxiv.org/abs/2505.06738)
- [Spill The Beans](https://arxiv.org/abs/2505.00817)

The compiler-level point does not depend on one exact attack implementation:

> A secret tensor index can become a secret-dependent memory address after lowering.

---

## 13. MLIR example

```mlir
func.func @embedding_lookup(
    %embedding: tensor<50000x4096xf32>,
    %token: index
) -> tensor<4096xf32> {
  %row = tensor.extract_slice
      %embedding[%token, 0] [1, 4096] [1, 1]
      : tensor<50000x4096xf32>
        to tensor<1x4096xf32>
  ...
}
```

Descriptors:

```text
embedding values:
  provider-only

token index:
  client-only

shape:
  public

layout:
  public row-major

host:
  server
```

---

## 14. Address observation

After bufferization, row base is approximately

\[
a=
base
+
token\cdot4096\cdot4.
\]

Address label:

\[
\ell_{addr}
=
ClientOnly
\sqcup
PublicShape
\sqcup
PublicLayout
=
ClientOnly.
\]

The server-local address observer is unauthorized.

---

## 15. SMT query

\[
0\le token_0,token_1<50000
\]

and

\[
\mu_\Theta
(
base+16384token_0
)
\neq
\mu_\Theta
(
base+16384token_1
).
\]

Under cache-line observation, SAT finds tokens whose rows occupy different lines.

The loaded embeddings may also be provider-secret, but the address channel exists independently.

---

## 16. Repairs

### Oblivious full scan

Touch every row and mask-select the requested one.

Security:

\[
AddressTrace(token_0)=AddressTrace(token_1).
\]

Cost:

\[
O(V\cdot d)
\]

for vocabulary \(V\) and dimension \(d\).

### ORAM or oblivious backend

Use a contract guaranteeing index-independent observations.

### Trusted hardware

Possible, but requires a hardware contract and may not hide all traces.

### Reveal token to server

Only valid if policy explicitly authorizes it.

A compiler should make the security/performance tradeoff explicit.

---

# Case Study D — Two-owner FHE inference

## 17. Policy

Parties:

```text
client
provider
server
```

Data:

\[
Readers(x)=\{client\},
\]

\[
Readers(W)=\{provider\}.
\]

Goal:

\[
y=model(W,x).
\]

Server may execute only on protected representations.

Release:

\[
R(W,x)=argmax(y)
\]

to the client.

---

## 18. Illustrative IR

```mlir
%x_ct = ifc.conceal %x
  {key = @client_or_joint_key}

%w_ct = ifc.conceal %w
  {key = @provider_or_joint_key}

%x_srv = ifc.transfer %x_ct to @server
%w_srv = ifc.transfer %w_ct to @server

%y_ct = secret.generic(%x_srv, %w_srv) {
  ...
}

%class_ct = call @encrypted_argmax(%y_ct)

%class = ifc.release %class_ct
  {policy = @prediction_to_client}
```

This is schematic. A real FHE plan must define compatible key and mechanism contracts.

---

## 19. Descriptor evolution

Client input:

\[
D(x)=
\langle
ClientOnly,
Plain,
Client
\rangle.
\]

After conceal:

\[
D(x_{ct})=
\langle
ClientOnly,
FHE,
Client
\rangle.
\]

After transfer:

\[
D(x_{srv})=
\langle
ClientOnly,
FHE,
Server
\rangle.
\]

The policy stays client-only even though representation and placement change.

Provider weights evolve analogously.

Joint ciphertext result:

\[
\ell(y_{ct})
=
ClientOnly\sqcup ProviderOnly.
\]

It remains protected until sanctioned release.

---

## 20. Negative mutations

The evaluation should mutate the program.

### Missing conceal

```mlir
%x_srv = ifc.transfer %x to @server
```

Definite placement violation.

### Server decryption

```mlir
%plain = secret.reveal %y_ct
  {host = @server}
```

Representation exposure violation.

### Full logits released

Policy permits `argmax`, but implementation releases \(y\).

SMT checks:

\[
\exists W,x.\quad
y\neq argmax(y).
\]

More precisely, it checks the released value's type/function against the policy and finds two states with same class but different logits.

### Secret shape visible

Payload encrypted, but transfer size depends on secret sequence length.

Relational transfer event differs.

### Opaque backend call

No FHE contract.

Result: UNKNOWN or obligation.

---

## 21. What is proved

The compiler can prove, relative to contracts:

- no plaintext crosses to unauthorized host;
- only approved facets are visible;
- release matches declared function;
- lowering introduces no modeled new trace distinction.

It does not prove:

- FHE hardness;
- parameter security;
- key management;
- circuit privacy unless contracted;
- hardware power security;
- opaque library internals.

---

# Case Study E — Compiler-introduced regression catalog

## 22. Select to branch

Source indistinguishable; target branch differs.

Event:

\[
\mathsf{branch}.
\]

## 23. Fixed-count loop to early exit

Source:

```text
always N iterations
```

Target:

```text
stop when secret predicate holds
```

Event:

\[
\mathsf{execCount}.
\]

## 24. Full scan to direct gather

Source touches all addresses.

Target touches one secret-selected address.

Event:

\[
\mathsf{memory}.
\]

## 25. Arithmetic to variable-time helper

Source operation has fixed target contract.

Target calls helper with unknown or variable latency.

Event:

\[
\mathsf{variableLatency}
\quad\text{or}\quad
\mathsf{call}.
\]

## 26. Bufferization exposes plaintext alias

Source protected tensor.

Target creates server-visible plaintext memref or alias.

Event:

\[
\mathsf{expose}.
\]

## 27. Uniform error to detailed errors

Source releases one validity bit.

Target returns different error classes.

Event:

\[
\mathsf{error}.
\]

## 28. Sanitized release moved before sanitizer

Source release policy satisfied.

Target exposes pre-sanitized value.

Event:

\[
\mathsf{release}
\quad\text{or}\quad
\mathsf{expose}.
\]

---

## 29. Evaluation matrix

| Case | Static IFC | SMT | Security TV | Obligation |
|---|---:|---:|---:|---:|
| Secret division | yes | optional precision | lowering check | target latency |
| Select to branch | source may pass | yes | essential | backend |
| Secret gather | yes | witness | lowering check | memory model |
| Missing FHE conceal | definite | unnecessary | optional | crypto contract |
| Secret shape transfer | yes | witness | yes | network model |
| Full logits release | partial | semantic policy equality | yes | release contract |
| Opaque helper | no conclusion | no without summary | yes | call contract |

---

## 30. Designing vulnerable/fixed pairs

Every benchmark should include:

1. vulnerable source or lowering;
2. fixed version;
3. expected observer;
4. target profile;
5. policy annotations;
6. expected first divergence;
7. expected SAT/UNSAT/UNKNOWN;
8. provenance category:

```text
actual source import
faithful reduced reproduction
seeded mutation
```

Do not blur those categories.

---

## 31. Example diagnostic: secret gather

```text
observer: server
policy owner: client
property: exact-address trace noninterference

input pair:
  token_0 = 0
  token_1 = 1

first divergent event:
  operation: memref.load
  source location: embedding.mlir:27
  address_0: base
  address_1: base + 16384

first bad pass:
  lower-oblivious-gather

result:
  unsafe
```

---

## 32. Example diagnostic: backend obligation

```text
observer: local timing attacker
region: client_decrypt
source property: fixed-latency multiplication

lowered operation:
  call @__muldi3

result:
  conditional

outstanding obligation:
  @__muldi3 must have operand-independent latency
  for target riscv32
```

This is a correct, useful result even without a final green check.

---

## 33. Research lessons from the cases

### One property covers several domains

All cases reduce to:

\[
LowEq
\Longrightarrow
TraceEq.
\]

The event changes:

- division: latency;
- Clangover: branch;
- gather: address;
- FHE: exposure;
- release bug: unauthorized output.

### Tensor level adds real structure

Index, shape, sparsity, and placement exist explicitly.

### Lowering validation is the novelty center

Functionally equivalent transformations can split indistinguishability classes.

### Obligations protect credibility

GoFetch-style hardware effects, speculation, and physical leakage must not be silently included in a software trace theorem.

---

## 34. Exercises

### Exercise 1

Write the relational SMT condition for a fixed-count source loop and early-exit target loop.

### Exercise 2

For two-owner inference, define the server's visible projection of an FHE tensor.

### Exercise 3

Give a source operation contract for an oblivious gather.

### Exercise 4

Design a compiler mutation that keeps outputs equal but changes allocation size based on a secret shape.

### Exercise 5

Explain why Clangover is stronger evidence for security translation validation than a source-level branch bug.

### Exercise 6

For KyberSlash-style division, list the target assumptions that must be checked after lowering.

### Exercise 7

Create a release-relative witness where two executions have the same predicted class but different logits.

---

## 35. Final synthesis

For each program:

\[
\text{policy}
\to
\text{descriptors}
\to
\text{effects}
\to
\text{two-run query}
\to
\text{security verdict}.
\]

For each lowering:

\[
\text{source indistinguishability}
\to
\text{target indistinguishability}
\to
\text{preserved or regressed}.
\]

The complete research thesis is:

> A tensor-aware, principal-labeled information-flow analysis identifies which observations may depend on protected information. Relational SMT proves whether those observations can actually differ, and security translation validation proves that compiler lowering introduces no new distinction. Cryptographic, backend, and hardware assumptions remain explicit obligations.

---

## Primary references

- [KyberSlash](https://kyberslash.cr.yp.to/papers.html).
- [NIST PQC forum report on compiler-introduced ML-KEM branch](https://groups.google.com/a/list.nist.gov/g/pqc-forum/c/hqbtIGFKIpU).
- [PQShield description of the compiler-introduced timing leak](https://pqshield.com/pqshield-plugs-timing-leaks-in-kyber-ml-kem-to-improve-pqc-implementation-maturity/).
- [I Know What You Said](https://arxiv.org/abs/2505.06738).
- [Spill The Beans](https://arxiv.org/abs/2505.00817).
- HEIR [`secret` dialect](https://heir.dev/docs/dialects/secret/).
- MLIR [Bufferization](https://mlir.llvm.org/docs/Bufferization/).
- S. Bang et al., [MLIR-TV](https://github.com/aqjune/mlir-tv).
