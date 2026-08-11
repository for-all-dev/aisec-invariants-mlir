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

$$
\ell(x)=\ell(secret).
$$

But bitvector semantics gives

$$
x=0.
$$

If `%x` controls a branch, a static IFC checker may report a possible leak even though the branch is constant.

SMT can reason about actual symbolic values and prove the observation equal.

The division of labor is:

$$
\boxed{
\text{dataflow finds where a leak may occur}
}
$$

$$
\boxed{
\text{SMT decides whether an actual distinguishing pair exists}
}
$$

for a bounded, exactly encoded fragment.

---

## 2. Self-composition

Given program $P$, create two renamed copies:

$$
P^0
\qquad\text{and}\qquad
P^1.
$$

Every variable and SSA value is duplicated:

$$
x^0,\ x^1.
$$

Public inputs are constrained equal:

$$
x^0=x^1.
$$

Secret inputs remain independent:

$$
s^0,\ s^1
$$

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

$$
b_0=secret_0.
$$

### Copy 1

$$
b_1=secret_1.
$$

Output values are equal:

$$
out_0=0,
\qquad
out_1=0.
$$

If the observer sees only output, the violation formula is

$$
out_0\neq out_1,
$$

which is UNSAT.

If the observer sees branches, the formula is

$$
b_0\neq b_1,
$$

which is SAT with

$$
secret_0=\mathsf{false},
\qquad
secret_1=\mathsf{true}.
$$

The same program is secure under one observation model and insecure under another.

---

## 4. General leak query

Let:

- $\operatorname{Sem}(P,\sigma,\tau)$ encode program semantics;
- $\operatorname{LowEq}_{A,\Delta}$ encode equal authorized initial knowledge and equal sanctioned releases;
- $\operatorname{TraceEq}_{A,\Theta}$ compare visible traces.

The query is

$$
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
$$

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

The relational formula is indexed by an observer coalition $A$. Labels and ACLs determine which equalities are inserted.

For each input facet $f$:

$$
\operatorname{CanRead}(A,\ell_f)
\Longrightarrow
f_0=f_1.
$$

If $A$ is not authorized to read the facet, the two copies remain independent.

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

$$
shape_0=shape_1,
$$

while query and model elements may differ. The solver asks whether server-visible placement, branch, memory, transfer, or latency events differ.

For the **client** query, the query is constrained equal because the client already knows it, while model weights may differ. The solver checks whether the client learns anything about the model beyond the sanctioned prediction.

For a **client-server coalition**, both the client-known query and server-visible metadata are fixed. The coalition query determines whether combining their views reveals additional provider information.

### Visibility projection

Not every symbolic event is compared for every actor. Define

$$
visible_{A,\Theta}(e)
$$

and construct

$$
Trace_{A,\Theta}=filter(visible_{A,\Theta},Trace).
$$

Representation contracts participate in this projection. For an FHE value on the server, the payload expression may be hidden while shape and ciphertext-count expressions are included.

### Query scheduling

A practical compiler should not enumerate all $2^{|\mathcal P|}$ coalitions blindly. The policy environment declares a finite threat set

$$
\mathcal A=\{A_1,\ldots,A_k\}.
$$

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

$$
z_0=bvadd(x_0,y_0),
$$

$$
z_1=bvadd(x_1,y_1).
$$

Use bitvectors for fixed-width integer semantics. Infinite mathematical integers can be unsound when overflow matters.

For

```mlir
%r = arith.select %c, %a, %b
```

encode

$$
r_j=ite(c_j,a_j,b_j)
$$

for $j\in\{0,1\}$.

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

$$
x=ite(c,e_t,e_f).
$$

Observable branch behavior remains separate:

$$
event_{\mathrm{branch}}=c.
$$

For more complicated control flow, maintain path conditions:

$$
PC_t=PC\land c,
\qquad
PC_f=PC\land\neg c.
$$

Events are guarded by their path conditions.

---

## 9. Memory encoding

A byte-addressed memory can be modeled as an SMT array:

$$
M:\mathrm{BV}_{w_a}\to\mathrm{BV}_8.
$$

A byte load is

$$
v=select(M,a).
$$

A byte store is

$$
M'=store(M,a,v).
$$

Multi-byte values require concatenation and endianness rules.

At tensor level, an $n$-dimensional tensor may instead be encoded as an array from index tuples to values:

$$
T:
I_0\times\cdots\times I_{n-1}\to V.
$$

The security event for a memory operation is still encoded separately:

$$
e_{\mathrm{addr}}
=
\mu_\Theta(a).
$$

Memory contents being equal does not imply addresses are equal.

---

## 10. Bounded loops

Unbounded loops are difficult for quantifier-free SMT.

A first implementation can:

1. require a static bound $N$;
2. unroll $N$ iterations;
3. give each iteration a validity condition.

For loop condition $c_i$,

$$
valid_0=true,
$$

$$
valid_{i+1}=valid_i\land c_i.
$$

An operation event in iteration $i$ is guarded by $valid_i$.

Operation count can be encoded as

$$
count=\sum_{i=0}^{N-1} ite(valid_i,1,0).
$$

A leak query asks

$$
count_0\neq count_1.
$$

If the loop can exceed $N$, the result is bounded and must be reported as such.

---

## 11. Trace encoding

### Explicit bounded event vector

Represent a trace by

$$
\tau=
\langle
e_0,\ldots,e_{N-1},n
\rangle.
$$

Each event may have fields:

$$
e_i=
\langle
valid_i,
kind_i,
site_i,
payload_i
\rangle.
$$

Trace equality requires:

$$
n_0=n_1
$$

and, for each position,

$$
valid_i^0=valid_i^1
$$

and equal visible fields when valid.

### Event-specific proof obligations

Instead of building one global trace, verify each possible effect:

$$
\exists \sigma_0,\sigma_1.
\ LowEq
\land
event_0\neq event_1.
$$

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

$$
x_0=s_0\oplus s_0=0,
\qquad
b_0=(0\neq0)=false.
$$

Copy 1:

$$
x_1=s_1\oplus s_1=0,
\qquad
b_1=false.
$$

The divergence formula

$$
b_0\neq b_1
$$

is UNSAT.

The static label remains conservative; SMT discharges this particular effect.

---

## 14. Tensor-index example

Source:

```mlir
%x = tensor.extract %table[%secret_i]
```

Assume table and base are equal across runs.

$$
a_0=base+4i_0,
$$

$$
a_1=base+4i_1.
$$

The address leak query is

$$
0\le i_0,i_1<1024
\land
\mu_\Theta(a_0)\neq\mu_\Theta(a_1).
$$

Under exact addresses, SAT is immediate with

$$
i_0=0,\quad i_1=1.
$$

Under cache-line observation, adjacent indices may be equal, so the solver finds indices on different lines.

---

## 15. Variable latency

For operation $op$, the target profile defines

$$
\operatorname{lat}_\Theta(op,\bar v).
$$

The query is

$$
\operatorname{lat}_\Theta(op,\bar v_0)
\neq
\operatorname{lat}_\Theta(op,\bar v_1).
$$

Three levels of modeling are possible:

1. relevant operands themselves;
2. documented timing buckets;
3. a constant-time contract returning `fixed`.

If no reliable model exists, emit an obligation rather than asserting safety.

---

## 16. Sanctioned release in the query

Suppose policy $k$ permits release function $R_k$.

Add

$$
R_k(\sigma_0)=R_k(\sigma_1)
$$

to low-equivalence.

Then ask whether any other observation differs.

For password checking:

$$
[s_0=g_0]=[s_1=g_1].
$$

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

$$
SAT(\Phi_{\mathrm{leak}})
\Longleftrightarrow
\exists\text{ modeled violating pair}.
$$

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

$$
secret_0\neq secret_1
$$

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

$$
\text{two-run confidentiality}
$$

into

$$
\text{one safety query over a product program}.
$$

Metadata determines what must be equal and what can be observed. Symbolic semantics determines whether the observations can actually differ.

The next module uses the same idea to compare source and target compiler IRs.

---

## Further reading

- G. Barthe et al., self-composition for secure information flow.
- ct-verif and other product-program constant-time verifiers.
- MLIR, [SMT Dialect](https://mlir.llvm.org/docs/Dialects/SMT/).
- S. Bang et al., [MLIR-TV](https://github.com/aqjune/mlir-tv).
