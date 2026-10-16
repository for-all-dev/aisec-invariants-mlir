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

Let $\mathrm{Traces}$ be the set of all traces.

A trace property is a set

$$
P \subseteq \mathrm{Traces}.
$$

A program satisfies $P$ when each of its traces belongs to $P$.

A hyperproperty is a set of sets of traces:

$$
H \subseteq \mathcal P(\mathrm{Traces}).
$$

A program denotes a trace set $T$, and satisfies $H$ when

$$
T\in H.
$$

You do not need category theory to use this distinction. The practical lesson is:

> Confidentiality is about relationships among possible executions, not merely whether one execution contains a locally forbidden event.

---

## 3. Public and secret components

Suppose an input state is

$$
\sigma =
\langle
\mathsf{publicInput},
\mathsf{clientSecret},
\mathsf{providerSecret}
\rangle.
$$

An observer $A$ is allowed to know only some components.

Define an observation of the initial state:

$$
\operatorname{low}_A(\sigma).
$$

Two states are **low-equivalent** for $A$ when

$$
\sigma_0\approx_A\sigma_1
\quad\Longleftrightarrow\quad
\operatorname{low}_A(\sigma_0)
=
\operatorname{low}_A(\sigma_1).
$$

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

$$
\sigma_0\approx_{\mathsf{server}}\sigma_1.
$$

---

## 4. Noninterference

A deterministic program is termination-insensitively noninterfering for observer $A$ when

$$
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
$$

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

A $k$-safety property can be refuted by $k$ finite traces.

For basic deterministic noninterference, two traces suffice:

1. one execution with secret $s_0$;
2. one execution with secret $s_1$;
3. equal public inputs;
4. different visible observations.

The pair is a counterexample.

This makes noninterference a form of **2-safety** for the relevant finite semantics.

That observation is important because it suggests self-composition:

$$
P\times P
$$

runs two renamed copies of $P$ and checks an ordinary safety assertion comparing their observations.

Not every security hyperproperty is reducible this simply, but the core property in this course is.

---

## 6. Output noninterference

Suppose observations include only final public output:

$$
\operatorname{Obs}^{\mathrm{out}}_A(P,\sigma)
=
\operatorname{PublicOutput}_A(P,\sigma).
$$

Then noninterference says changing secrets cannot change unauthorized outputs.

Example:

```c
public_result = secret & 1;
```

Choose $secret_0=0$ and $secret_1=1$. The public outputs differ, so the program violates output noninterference.

This is useful but incomplete for low-level security.

---

## 7. Trace noninterference and constant time

Let the observer see branch outcomes, memory addresses, operation counts, and target latency classes:

$$
\operatorname{Obs}^{\mathrm{ct}}_{A,\Theta}
=
\langle
\mathsf{branches},
\mathsf{addresses},
\mathsf{counts},
\mathsf{latencyClasses}
\rangle.
$$

Then

$$
\sigma_0\approx_A\sigma_1
\Longrightarrow
\operatorname{Obs}^{\mathrm{ct}}_{A,\Theta}(P,\sigma_0)
=
\operatorname{Obs}^{\mathrm{ct}}_{A,\Theta}(P,\sigma_1)
$$

is a constant-time-style noninterference property.

It does not mean physical wall-clock readings are identical. It means the specific software-level leakage observations in $\Theta$ are identical.

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

$$
\operatorname{Obs}_{A,\Theta}
$$

rather than one global trace because parties have different views.

This is essential for distributed cryptographic compilation.

---

## 9. Coalitions and collusion

A policy should often quantify over coalitions

$$
A\subseteq\mathcal P
$$

rather than only individual principals.

For secret sharing, one server share may reveal nothing, while a threshold coalition can reconstruct the secret.

Low-equivalence and observation projection become coalition-relative:

$$
\sigma_0\approx_A\sigma_1,
\qquad
\pi_{A,\Theta}(\tau).
$$

A mechanism contract must state which coalitions it protects against.

---

## 10. Termination sensitivity

There are two common forms.

### Termination-insensitive noninterference

Compare executions only when both terminate:

$$
P(\sigma_0)\Downarrow
\land
P(\sigma_1)\Downarrow.
$$

This does not treat divergence itself as a leak.

However, finite loop-count differences remain observable if `exec` events are in the trace.

### Termination-sensitive noninterference

Require termination behavior to agree:

$$
P(\sigma_0)\Downarrow
\Longleftrightarrow
P(\sigma_1)\Downarrow.
$$

This is stronger and substantially harder, especially with unbounded loops and distributed systems.

A realistic first compiler can use termination-insensitive security while still checking finite operation-count leakage.

---

## 11. Nondeterministic programs

If a program produces a set of traces, several relational definitions are possible.

A strong possibilistic property may require:

$$
\forall \tau_0\in\llbracket P\rrbracket(\sigma_0).
\ \exists \tau_1\in\llbracket P\rrbracket(\sigma_1).
\ \tau_0\sim_A\tau_1
$$

and symmetrically.

Other settings quantify over schedulers, couple random choices, or use probabilistic indistinguishability.

For the core MLIR validator, the recommended starting point is deterministic sequential semantics with external nondeterminism represented as explicit symbolic inputs or contracts.

---

## 12. Noninterference modulo release

Useful programs intentionally reveal results.

A password checker may reveal

$$
R(s,g)=[s=g].
$$

A private inference service may reveal

$$
R(w,x)=\operatorname{argmax}(\operatorname{model}(w,x)).
$$

Strict noninterference would reject those programs.

We therefore define release-relative low-equivalence:

$$
\sigma_0\approx_A^\Delta\sigma_1
$$

when:

1. initial public information is equal;
2. every sanctioned release function visible to $A$ has equal value.

Then require

$$
\sigma_0\approx_A^\Delta\sigma_1
\Longrightarrow
\operatorname{Trace}_{A,\Theta}(P,\sigma_0)
\sim
\operatorname{Trace}_{A,\Theta}(P,\sigma_1).
$$

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

- run 0 mismatches at byte $1$;
- run 1 mismatches at byte $12$.

The authorized result is false in both runs:

$$
R(\sigma_0)=R(\sigma_1)=\mathsf{false}.
$$

But operation counts differ:

$$
\operatorname{count}(\tau_0)=1,
\qquad
\operatorname{count}(\tau_1)=12.
$$

Therefore, the program leaks more than the sanctioned Boolean.

---

## 14. Hyperproperties and compiler correctness

Functional compiler correctness commonly states

$$
\forall x.\quad
\operatorname{Result}(S,x)
=
\operatorname{Result}(T,x).
$$

Security preservation must relate four executions:

$$
S(x_0),\quad S(x_1),\quad T(x_0),\quad T(x_1).
$$

The core condition is

$$
\operatorname{Obs}(S,x_0)
\sim
\operatorname{Obs}(S,x_1)
\Longrightarrow
\operatorname{Obs}(T,x_0)
\sim
\operatorname{Obs}(T,x_1).
$$

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

$$
\text{equal authorized knowledge}
\Longrightarrow
\text{equal observable behavior}.
$$

This is a hyperproperty because it compares multiple executions. The next module shows how an information-flow type system proves a conservative approximation of this property.

---

## Further reading

- M. Clarkson and F. Schneider, work introducing hyperproperties.
- A. Sabelfeld and A. Myers, language-based information-flow surveys.
- G. Barthe et al., self-composition for secure information flow.
