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

If an event visible to observer $A$ is influenced only by information $A$ may know, the event is safe.

The type system may reject some secure programs. That is acceptable if it is sound. In this module, `Low` and `High` are teaching abbreviations. The next module replaces them with policies indexed by named principals and coalitions:

$$
\text{well typed}
\Longrightarrow
\text{noninterfering}.
$$

SMT can later recover precision for cases the type system cannot decide.

---

## 2. Security labels and lattices

A simple two-point lattice is

$$
\mathsf{Low}\sqsubseteq\mathsf{High}.
$$

Interpretation:

- `Low` information may flow into either `Low` or `High`;
- `High` information may flow only into `High`.

The lattice has:

$$
\bot=\mathsf{Low},
\qquad
\top=\mathsf{High}.
$$

The join is

$$
\begin{aligned}
\mathsf{Low}\sqcup\mathsf{Low}&=\mathsf{Low},\\
\mathsf{Low}\sqcup\mathsf{High}&=\mathsf{High},\\
\mathsf{High}\sqcup\mathsf{High}&=\mathsf{High}.
\end{aligned}
$$

A join combines dependencies.

If

$$
z=x+y,
$$

then

$$
\ell(z)=\ell(x)\sqcup\ell(y).
$$

---

## 3. Reader-set labels

For multiple parties, a useful confidentiality label can be a reader set

$$
R\subseteq\mathcal P.
$$

A smaller reader set is more restrictive.

A flow from $R_1$ to $R_2$ is safe when

$$
R_2\subseteq R_1.
$$

For example:

$$
\{\mathsf{client},\mathsf{provider}\}
\sqsubseteq
\{\mathsf{client}\}
$$

under the convention that information may move to a value readable by fewer principals.

The join is set intersection:

$$
R_1\sqcup R_2=R_1\cap R_2.
$$

If client-only input and provider-only weights jointly influence a plaintext value,

$$
\{\mathsf{client}\}
\cap
\{\mathsf{provider}\}
=
\varnothing.
$$

No party is authorized to see that joint value in plaintext unless a release policy says otherwise.

Different papers choose different order conventions. Always define the direction of $\sqsubseteq$ explicitly.

---

## 4. Explicit flow

Consider:

```c
low = high;
```

The assignment is permitted only when

$$
\ell(high)\sqsubseteq \ell(low).
$$

In the two-point lattice:

$$
\mathsf{High}\not\sqsubseteq\mathsf{Low},
$$

so the assignment is rejected.

For an expression:

$$
\frac{
\Gamma\vdash e_1:\ell_1
\qquad
\Gamma\vdash e_2:\ell_2
}{
\Gamma\vdash e_1\oplus e_2:
\ell_1\sqcup\ell_2
}.
$$

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

The standard solution is a program-counter label $pc$.

Inside a branch guarded by $g$,

$$
pc' = pc\sqcup\ell(g).
$$

An assignment to variable $x$ is allowed only if

$$
pc\sqcup\ell(e)\sqsubseteq\ell(x).
$$

So the branch above requires

$$
\mathsf{High}\sqsubseteq\mathsf{Low},
$$

and is rejected.

---

## 6. Typing judgments

A simple expression judgment is

$$
\Gamma\vdash e:\ell.
$$

A command judgment tracks control context:

$$
\Gamma;pc\vdash c.
$$

### Constants

$$
\frac{}{ \Gamma\vdash n:\bot }.
$$

### Variables

$$
\frac{\Gamma(x)=\ell_x}{\Gamma\vdash x:\ell_x}.
$$

### Binary operations

$$
\frac{
\Gamma\vdash e_1:\ell_1
\qquad
\Gamma\vdash e_2:\ell_2
}{
\Gamma\vdash e_1\oplus e_2:\ell_1\sqcup\ell_2
}.
$$

### Assignment

$$
\frac{
\Gamma\vdash e:\ell_e
\qquad
pc\sqcup\ell_e\sqsubseteq\Gamma(x)
}{
\Gamma;pc\vdash x:=e
}.
$$

### Conditional

$$
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
$$

### Output

If host $h$ has authority label $L(h)$,

$$
\frac{
\Gamma\vdash e:\ell
\qquad
pc\sqcup\ell\sqsubseteq L(h)
}{
\Gamma;pc\vdash \mathbf{output}_h(e)
}.
$$

For a trace-sensitive system, the branch itself also creates an observable effect whose dependency is

$$
pc\sqcup\ell_g.
$$

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

$$
\Gamma;pc;h
\vdash
op(\bar v)
:
\bar D
\triangleright E.
$$

Here $E$ is a set of abstract observable effects.

An effect can be represented as

$$
e=
\langle
\mathsf{kind},
\mathsf{symbolicExpression},
\ell_e,
\mathsf{observers}
\rangle.
$$

The static sufficient condition is

$$
A\in\mathsf{observers}(e)
\Longrightarrow
A\text{ is authorized for }\ell_e.
$$

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

The else branch is unreachable, but a simple lattice join labels $x$ secret.

SMT can prove

$$
secret=secret
$$

and recover precision.

The intended architecture is:

$$
\text{fast path-insensitive IFC}
\quad+\quad
\text{selected path-sensitive SMT}.
$$

---

## 10. Confidentiality and integrity

Confidentiality asks:

> Who may learn this information?

Integrity asks:

> Who is trusted to influence this information?

Viaduct uses labels of the form

$$
\ell=\langle C,I\rangle.
$$

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

Introduce a label variable $L_v$ for each SSA value and generate constraints.

For

```mlir
%z = arith.addi %x, %y
```

generate

$$
L_x\sqsubseteq L_z,
\qquad
L_y\sqsubseteq L_z,
\qquad
pc\sqsubseteq L_z.
$$

For a branch result, add the guard:

$$
L_g\sqsubseteq L_r.
$$

For an output to host $h$,

$$
L_v\sqsubseteq L(h).
$$

Solve for a least or minimum-authority assignment.

A desirable principality theorem is:

$$
\Gamma^*=\operatorname{Infer}(P)
\Longrightarrow
\forall\Gamma.
\ \Gamma\models\mathcal C(P)
\Rightarrow
\Gamma^*\preceq\Gamma.
$$

Viaduct follows this broad approach: infer labels by solving flow constraints, then use the inferred requirements to guide protocol selection.

---

## 12. Soundness statement

A source-level soundness theorem has the form

$$
\Gamma;pc_0\vdash P
\Longrightarrow
\operatorname{Secure}_{A,\Theta}(P)
$$

for observers covered by the policy.

A proof usually needs several lemmas.

### Expression confinement

If two states agree on all values visible at label $\ell$, then evaluating an expression labeled at most $\ell$ produces equal low results.

### Low-step preservation

If two low-equivalent states take corresponding steps, their low-equivalence is preserved and their low events agree.

### High-context confinement

Commands executing under a high $pc$ cannot change low state or produce low-observable events.

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

$$
\ell(x)=\ell(secret).
$$

Semantically,

$$
x=0.
$$

The checker is sound because it overapproximates possible dependence, but incomplete because it cannot prove the cancellation.

SMT can discharge the relational obligation

$$
x_0\ne x_1.
$$

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

Write a typing rule for `while e do c` using $pc$.

### Exercise 4

For reader-set labels, compute the join of:

$$
\{\mathsf{client},\mathsf{provider}\}
\quad\text{and}\quad
\{\mathsf{client}\}.
$$

### Exercise 5

Explain why integrity is relevant to an attacker-controlled release guard.

---

## 16. Summary

The type system computes a conservative dependency structure:

$$
\text{labels on data}
+
pc
+
\text{labels on observable effects}.
$$

Well-typedness is intended to imply relational noninterference. The next module first explains who the labels are about: principals, actors, hosts, ACLs, authority, and observer coalitions. Tensor facets, representations, and placements then build on that actor-aware policy model.

---

## Further reading

- A. Sabelfeld and A. Myers, language-based information-flow security.
- C. Acay et al., [Viaduct](https://www.cs.cornell.edu/andru/papers/viaduct/viaduct.pdf), especially label checking and inference.
- Jif and the decentralized label model for principal-based policies.
