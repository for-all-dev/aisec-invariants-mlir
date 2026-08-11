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

$$
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
$$

This conclusion depends on:

1. inference being correct;
2. typing implying source security;
3. translation validation establishing security refinement;
4. functional correctness being checked separately;
5. obligations being real premises.

---

## 3. Theorem family A: label algebra

Let

$$
\mathcal L=
\langle
L,\sqsubseteq,\sqcup,\sqcap,\bot,\top
\rangle.
$$

Prove:

### Partial order

$$
\ell\sqsubseteq\ell
$$

$$
\ell_1\sqsubseteq\ell_2
\land
\ell_2\sqsubseteq\ell_1
\Longrightarrow
\ell_1=\ell_2
$$

$$
\ell_1\sqsubseteq\ell_2
\land
\ell_2\sqsubseteq\ell_3
\Longrightarrow
\ell_1\sqsubseteq\ell_3.
$$

### Join

$$
\ell_1\sqsubseteq\ell_1\sqcup\ell_2,
$$

$$
\ell_2\sqsubseteq\ell_1\sqcup\ell_2,
$$

and if

$$
\ell_1\sqsubseteq u
\quad\text{and}\quad
\ell_2\sqsubseteq u,
$$

then

$$
\ell_1\sqcup\ell_2\sqsubseteq u.
$$

### Product facets

If each facet is a lattice, then

$$
L_{\mathrm{tensor}}
=
L_{\mathrm{val}}
\times
L_{\mathrm{idx}}
\times
L_{\mathrm{shape}}
\times
L_{\mathrm{layout}}
$$

is a lattice under componentwise order and join.

This supports fixed-point analysis.

---

## 4. Actor and authority algebra obligations

The proof stack needs a formal actor environment

$$
\Pi=\langle\mathcal P,\mathcal H,L,controllers,\mathcal A\rangle,
$$

where $\mathcal A$ is the declared set of attacker coalitions.

The foundational results include:

1. **Acts-for order.** $\Rightarrow$ is reflexive and transitive, and is antisymmetric modulo logical equivalence of principal formulas.
2. **Label lattice.** The confidentiality/integrity product with $\sqsubseteq,\sqcup,\sqcap$ satisfies the lattice laws.
3. **ACL normalization.** Translating a reader/influencer ACL into the internal principal representation preserves `CanRead`, `CanInfluence`, flow, and join for the supported policy fragment.
4. **Host-authorization soundness.** If a plaintext facet is statically approved for host $h$, every principal coalition able to observe that host is authorized to read the facet.
5. **Coalition-parametric IFC.** A well-typed program is noninterfering for every $A\in\mathcal A$.

### Actor-indexed source theorem

The source-language theorem should be stated as

$$
\Pi;\Delta;\Theta\vdash P
\land Discharged(\Omega)
\Longrightarrow
\forall A\in\mathcal A.\;Secure_{A,\Theta,\Delta}(P).
$$

### Observer monotonicity

If observer $A_2$ sees at least everything visible to $A_1$, then proving security for $A_2$ may imply security for $A_1$, provided their low-equivalence relations are ordered compatibly. This can reduce duplicate proof work, but it requires a lemma about both observation inclusion and initial knowledge. Do not assume it merely from set inclusion.

### Placement and mechanism lemmas

For every exposed facet:

$$
Exposed(A,h,\rho,f)
\Longrightarrow
CanRead(A,\ell_f).
$$

For mechanism substitution:

$$
Concrete_M\preceq Contract_M
$$

must hold for every coalition covered by the contract. A single-protocol security claim without its corruption threshold is not sufficient.

---

## 5. Theorem family B: dataflow termination and inference

Let

$$
F:\widehat{State}\to\widehat{State}
$$

be the global transfer functional.

Prove:

### Monotonicity

$$
x\sqsubseteq y
\Longrightarrow
F(x)\sqsubseteq F(y).
$$

Each operation transfer function must be monotone.

### Termination

If the abstract domain has finite height, repeated joins reach a fixed point.

If not, use widening and prove the widening is sound.

### Fixed-point soundness

Let

$$
\widehat{\sigma}^*
=
lfp(F).
$$

Then every concrete reachable state is represented by the abstract state at the corresponding program point:

$$
Reach(P,p)\subseteq\gamma(\widehat{\sigma}^*_p).
$$

### Principality

If label inference computes $\Gamma^*$, then every other valid assignment is at least as restrictive under the chosen order:

$$
\Gamma\models\mathcal C(P)
\Longrightarrow
\Gamma^*\preceq\Gamma.
$$

This gives minimum-authority inference.

---

## 6. Abstract-interpretation soundness

For an operation $op$, let

$$
F_{op}(\widehat{\sigma})
=
\widehat{\sigma}'.
$$

A local soundness condition is:

$$
\sigma\in\gamma(\widehat{\sigma})
\land
\sigma\xrightarrow{op/e}\sigma'
\Longrightarrow
\sigma'\in\gamma(\widehat{\sigma}').
$$

For event dependency:

$$
ActualDeps(e)
\sqsubseteq
AbstractLabel(e).
$$

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

$$
\Pi;\Delta;\Theta;\Gamma
\vdash
P
\triangleright
E;\Omega
\land
Discharged(\Omega)
\Longrightarrow
Secure_{A,\Theta,\Delta}(P).
$$

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

$$
\sigma_0\approx_A\sigma_1
$$

when every variable readable by $A$ has equal value.

For memory:

$$
\mu_0\approx_A\mu_1
$$

when authorized locations and visible metadata agree, modulo allocation correspondence.

For protected representations, use an observer projection:

$$
View_A(\rho_0)=View_A(\rho_1).
$$

With sanctioned release:

$$
\sigma_0\approx_A^\Delta\sigma_1
$$

also requires equal release functions.

The relation must match the observation theorem exactly.

---

## 9. Key lemmas for IFC soundness

### Expression agreement

If

$$
\Gamma\vdash e:\ell
$$

and observer $A$ may read $\ell$, then low-equivalent states give equal expression values:

$$
\sigma_0\approx_A\sigma_1
\Longrightarrow
\llbracket e\rrbracket\sigma_0
=
\llbracket e\rrbracket\sigma_1.
$$

### High expression confinement

If $A$ cannot read $\ell$, expression results may differ, but those differences cannot flow into an $A$-visible sink without a checked release.

### Low event agreement

If an event is visible to $A$, typing guarantees its dependency label is readable by $A$. Therefore paired executions generate equal event payloads.

### High-context confinement

If current $pc$ is unreadable by $A$, the command cannot:

- modify $A$-visible state;
- emit $A$-visible events;
- perform an $A$-visible release.

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

$$
WellTypedRelease_\Delta(P)
\Longrightarrow
NoninterferenceModulo_\Delta(P).
$$

The proof relation already equates sanctioned release functions:

$$
R_k(\sigma_0)=R_k(\sigma_1).
$$

The release rule must ensure:

- emitted release payload equals $R_k$;
- audience matches;
- occurrence and guard comply;
- integrity premises hold;
- no extra event depends on hidden distinctions.

Robust declassification requires a stronger attacker-aware theorem than basic honest-but-curious noninterference.

Be explicit about which one is proved.

---

## 12. Self-composition correctness

Let

$$
Product(P)
$$

be the self-composed program.

Prove a correspondence:

$$
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
$$

up to renaming and product-state representation.

Then:

$$
Product(P)\text{ reaches bad}
\Longleftrightarrow
\exists \sigma_0,\sigma_1.
\ LowEq
\land
TraceDiff.
$$

This justifies reducing noninterference to safety.

---

## 13. SMT encoding correctness

Let

$$
Encode(P,\varphi)
$$

translate a bounded semantic problem into SMT.

Aim to prove:

### Soundness

$$
SAT(Encode(P,\varphi))
\Longrightarrow
\exists\text{ concrete modeled execution satisfying }\varphi.
$$

### Completeness

$$
\exists\text{ concrete modeled execution satisfying }\varphi
\Longrightarrow
SAT(Encode(P,\varphi)).
$$

Completeness may be limited by:

- bounds;
- abstractions;
- unsupported floating point;
- unknown calls;
- quantifier approximations.

State the fragment precisely.

---

## 14. Witness-lifting theorem

Suppose SMT returns model $m$.

A witness-lifting function produces concrete inputs:

$$
Lift(m)=\langle x_0,x_1\rangle.
$$

Prove:

$$
SATModel(m)
\Longrightarrow
Replay(P,x_0,x_1)
\text{ exhibits the reported divergence}.
$$

This is not only a UI feature. It checks that model interpretation, bit widths, tensor layouts, and memory reconstruction are correct.

---

## 15. Security refinement theorem

Define

$$
S\preceq^{sec}T
$$

by

$$
\forall x_0,x_1.
\ LowEq(x_0,x_1)
\land
Obs(S,x_0)\sim Obs(S,x_1)
\Longrightarrow
Obs(T,x_0)\sim Obs(T,x_1).
$$

Then:

$$
Secure(S)
\land
S\preceq^{sec}T
\Longrightarrow
Secure(T).
$$

This is the central compiler theorem.

Its proof is one paragraph, but the relation depends on correct source and target semantics, observer mappings, representation relations, and release policies.

---

## 16. Reflexivity and transitivity

### Reflexivity

$$
P\preceq^{sec}P.
$$

Immediate because an indistinguishable pair in $P$ remains indistinguishable in $P$.

### Transitivity

$$
P_0\preceq^{sec}P_1
\land
P_1\preceq^{sec}P_2
\Longrightarrow
P_0\preceq^{sec}P_2.
$$

Take a pair indistinguishable in $P_0$. The first relation gives indistinguishability in $P_1$; the second gives it in $P_2$.

### Pass composition

By induction:

$$
\bigwedge_{i=0}^{n-1}
P_i\preceq^{sec}P_{i+1}
\Longrightarrow
P_0\preceq^{sec}P_n.
$$

---

## 17. Observation-transparent rewrite theorem

For rewrite rule $L\rightsquigarrow R$, define

$$
Transparent(L,R)
$$

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

$$
Obs^\Theta.
$$

Let real observation be

$$
Obs^{real}.
$$

A strong adequacy condition is that real observation is a function of modeled observation:

$$
\exists g.\quad
Obs^{real}(P,\sigma)
=
g(Obs^\Theta(P,\sigma)).
$$

Then:

$$
Secure_\Theta(P)
\Longrightarrow
Secure_{real}(P).
$$

Proof:

If modeled observations are equal, applying $g$ gives equal real observations.

When adequacy is not established, it becomes an obligation.

---

## 19. Mechanism substitution theorem

For ideal mechanism $M$ and concrete backend $B$:

$$
B\preceq^{contract}M.
$$

If

$$
Secure(P[M])
$$

and the concrete backend reveals no more than the ideal contract, then

$$
Secure(P[B]).
$$

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

$$
Secure_\Theta(P)
$$

means secure against every physical channel.

Do not infer:

$$
UNSAT
$$

means secure beyond the exact encoded fragment.

Do not infer:

$$
SecurityRefine(S,T)
$$

means $S$ was secure or $T$ functionally correct.

Do not infer:

$$
WellTyped(P)
$$

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

Suppose modeled observation is exact address and real observation is cache-line address. Define $g$ and show adequacy.

### Exercise 7

Why does the converse fail? If a cache-line model is secure, exact-address security need not follow.

### Exercise 8

Write assumptions needed for an FHE mechanism-substitution theorem.

---

## 25. Summary

Every major theorem is quantified over a policy environment and a declared set of observer coalitions. Actor authority is therefore part of the formal statement, not an implementation annotation added after the proof.


The proof architecture is modular:

$$
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
$$

with mechanism and platform assumptions represented as explicit premises.

The next module translates this architecture into MLIR implementation components.

---

## Further reading

- Standard texts on type soundness and abstract interpretation.
- G. Barthe et al., self-composition.
- Verified compilation work for constant-time preservation.
- C. Acay et al., [formal Viaduct report](https://www.cs.cornell.edu/andru/papers/viaduct-formal/viaduct-formal-tr.pdf).
