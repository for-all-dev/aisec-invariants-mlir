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

A compiler transforms source program $S$ into target program $T$.

Ordinary translation validation checks the particular compilation result rather than proving the compiler correct once and for all.

A simplified functional property is

$$
\forall x.\quad
\operatorname{Result}(S,x)
=
\operatorname{Result}(T,x).
$$

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

$$
r=
\begin{cases}
a & secret\\
b & \neg secret.
\end{cases}
$$

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

$$
\operatorname{Trace}(S,x)
=
\operatorname{Trace}(T,x).
$$

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

For program $P$, define

$$
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
$$

This is the set of low-equivalent input pairs that $P$ keeps indistinguishable.

The target is security-refining when

$$
\mathcal K(S)\subseteq\mathcal K(T).
$$

The target may not split a source indistinguishability class.

We write

$$
S\preceq^{sec}_{A,\Theta,\Delta}T.
$$

---

## 5. Actor-indexed indistinguishability kernels

For every observer coalition $A$, define an indistinguishability kernel

$$
\mathcal K_A(P)=
\{(x_0,x_1)\mid x_0\approx_A x_1
\land Obs_A(P,x_0)\sim Obs_A(P,x_1)\}.
$$

Security refinement is actor-indexed:

$$
S\preceq^{sec}_A T
\quad\Longleftrightarrow\quad
\mathcal K_A(S)\subseteq\mathcal K_A(T).
$$

The compiler satisfies the declared threat model when

$$
\forall A\in\mathcal A.\;S\preceq^{sec}_A T.
$$

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

$$
\eta_H:\mathcal H_T\rightarrow\mathcal H_S\cup\{\mathsf{new}\}
$$

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

$$
P(x_0),\quad P(x_1).
$$

To check a compiler lowering, use four:

$$
S(x_0),
\quad
S(x_1),
\quad
T(x_0),
\quad
T(x_1).
$$

The bad case is

$$
\operatorname{Obs}(S,x_0)
\sim
\operatorname{Obs}(S,x_1)
$$

but

$$
\operatorname{Obs}(T,x_0)
\not\sim
\operatorname{Obs}(T,x_1).
$$

---

## 7. SMT regression query

The core formula is

$$
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
$$

SAT means a compiler-introduced distinction exists.

UNSAT means

$$
S\preceq^{sec}T
$$

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

$$
\alpha_S:
Trace_S\to Obs,
$$

$$
\alpha_T:
Trace_T\to Obs.
$$

Then compare

$$
\alpha_S(\tau^S_0)
=
\alpha_S(\tau^S_1)
$$

and

$$
\alpha_T(\tau^T_0)
=
\alpha_T(\tau^T_1).
$$

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

$$
\operatorname{branchObs}=\mathsf{none},
$$

$$
\operatorname{latencyObs}=\mathsf{fixed}.
$$

Lowering to a branch violates the contract.

By contrast, a plain functional `arith.select` may not universally promise constant-time lowering on every backend. The project must decide whether:

1. to give it a target-dependent security contract;
2. to introduce a dedicated `ifc.oblivious_select`;
3. to generate an outstanding backend obligation.

Security guarantees should not be smuggled into ordinary operations without documentation.

---

## 10. Functional and security refinement are independent

A compiler result should satisfy both:

$$
S\preceq^{fun}T
$$

and

$$
S\preceq^{sec}T.
$$

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

$$
Secure(P)
\quad\Longleftrightarrow\quad
\forall x_0,x_1.
\ LowEq(x_0,x_1)
\Rightarrow
Obs(P,x_0)\sim Obs(P,x_1).
$$

Then:

$$
\boxed{
Secure(S)
\land
S\preceq^{sec}T
\Longrightarrow
Secure(T).
}
$$

### Proof sketch

Assume $Secure(S)$ and $S\preceq^{sec}T$.

Take arbitrary low-equivalent $x_0,x_1$.

By source security,

$$
Obs(S,x_0)\sim Obs(S,x_1).
$$

By security refinement,

$$
Obs(T,x_0)\sim Obs(T,x_1).
$$

Therefore $T$ is secure.

The theorem is simple because the work is in defining and proving the refinement relation correctly.

---

## 12. Transitivity and pass composition

Security refinement should be transitive:

$$
S\preceq^{sec}M
\land
M\preceq^{sec}T
\Longrightarrow
S\preceq^{sec}T.
$$

### Proof

If a pair is indistinguishable in $S$, the first relation makes it indistinguishable in $M$, and the second makes it indistinguishable in $T$.

For a pass pipeline

$$
P_0\to P_1\to\cdots\to P_n,
$$

if

$$
P_i\preceq^{sec}P_{i+1}
$$

for every $i$, then

$$
P_0\preceq^{sec}P_n.
$$

This supports per-pass validation and first-bad-pass localization.

---

## 13. Per-pass localization

Suppose the final target fails.

Rather than compare only $P_0$ and $P_n$, save each intermediate IR:

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

$$
P_0\preceq^{sec}P_1,
\quad
P_1\preceq^{sec}P_2,
$$

but

$$
P_2\not\preceq^{sec}P_3,
$$

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

$$
\sigma_S:
t\mapsto [v_0,\ldots,v_{n-1}].
$$

Memref target:

$$
\sigma_T:
m\mapsto
\langle base,offset,size,stride,\mu\rangle.
$$

Define

$$
RepRel(\sigma_S,\sigma_T).
$$

For contiguous rank-one data:

$$
\forall i<n.\quad
t[i]
=
\mu(base+i\cdot width).
$$

The validation query starts with:

$$
RepRel(\sigma^S_0,\sigma^T_0)
$$

and

$$
RepRel(\sigma^S_1,\sigma^T_1).
$$

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

$$
L\rightsquigarrow R,
$$

define semantic observation transparency:

$$
\forall x_0,x_1.\quad
Obs(L,x_0)\sim Obs(L,x_1)
\Longrightarrow
Obs(R,x_0)\sim Obs(R,x_1).
$$

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

A local rewrite appears inside a larger program context $C[-]$.

We need

$$
L\preceq^{sec}R
\Longrightarrow
C[L]\preceq^{sec}C[R].
$$

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

$$
S\preceq^{sec}T
$$

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

$$
result=table[index].
$$

Security regression:

$$
Addr_S(i_0)=Addr_S(i_1)
$$

as full trace sequences, but

$$
Addr_T(i_0)\neq Addr_T(i_1).
$$

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

$$
\mathsf{expose}(client,intermediate)
$$

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

Prove transitivity of $\preceq^{sec}$.

### Exercise 3

Why can a target have more operations than a source and still preserve security?

### Exercise 4

Define a representation relation between a $2\times2$ tensor and a row-major memref.

### Exercise 5

List the new observations that could be introduced by loop unrolling, vectorization, and outlining.

### Exercise 6

Design a syntactic observation-transparency rule for replacing `addi x, 0` with `x`.

---

## 25. Summary

Security translation validation is not one global property. It is a family of preservation checks indexed by observer coalitions, host-control assumptions, and mechanism contracts.


Functional validation asks:

$$
\text{Did compilation preserve the answer?}
$$

Security translation validation asks:

$$
\text{Did compilation preserve which secret inputs are distinguishable?}
$$

The core bad case is

$$
\boxed{
\text{source indistinguishable}
\land
\text{target distinguishable}.
}
$$

The next module explains how intentional information release changes the equivalence relation.

---

## Further reading

- S. Bang et al., [MLIR-TV](https://github.com/aqjune/mlir-tv).
- Alive2 and translation validation for LLVM.
- Verified constant-time preservation in CompCert-style work.
- The later formal Viaduct work on simulation and robust hyperproperty preservation.
