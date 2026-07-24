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

$$
\langle c,\sigma\rangle \Downarrow \sigma',
$$

meaning that command $c$, starting from state $\sigma$, terminates in state $\sigma'$.

For an expression, we might write

$$
\langle e,\sigma\rangle \Downarrow v.
$$

This is enough for many compiler-correctness questions. If two programs produce the same result for every input, they may be functionally equivalent.

Security needs more information. Two executions can return the same result while taking different branches, touching different addresses, or placing plaintext on different hosts.

We therefore enrich the semantics:

$$
\langle c,\sigma\rangle \Downarrow (\sigma',\tau),
$$

where $\tau$ is a sequence of security-relevant events.

The trace is a **ghost object** in the semantics. A deployed program does not have to write it to a log. It is a mathematical record of what the threat model says an observer can distinguish.

---

## 2. A small language

Consider this toy language.

### Expressions

$$
e ::= n \mid x \mid e_1 \oplus e_2
$$

### Commands

$$
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
$$

A concrete state is

$$
\sigma = \langle \rho,\mu\rangle,
$$

where:

- $\rho : \mathrm{Var}\to\mathrm{Val}$ maps variables to values;
- $\mu : \mathrm{Addr}\to\mathrm{Val}$ maps memory addresses to values.

---

## 3. Events

A useful event alphabet for the toy language is

$$
\begin{aligned}
\alpha ::= {}&
\epsilon\\
&\mid \mathsf{branch}(s,b)\\
&\mid \mathsf{exec}(s,op)\\
&\mid \mathsf{memory}(s,a,w,k)\\
&\mid \mathsf{output}(s,h,v)\\
&\mid \mathsf{error}(s,k).
\end{aligned}
$$

Here:

- $s$ is a static program site;
- $b$ is a branch outcome;
- $a$ is an address or an abstract address class;
- $w$ is an access width;
- $k$ distinguishes read and write, or identifies an error class;
- $\epsilon$ is an unobservable internal step.

For tensor MLIR, we will later add events such as

$$
\mathsf{shape},\quad
\mathsf{allocation},\quad
\mathsf{kernelLaunch},\quad
\mathsf{transfer},\quad
\mathsf{variableLatency},\quad
\mathsf{release}.
$$

The event alphabet defines the **security envelope**. A theorem cannot protect observations omitted from the model.

---

## 4. Labeled small-step semantics

A labeled transition has the form

$$
\langle c,\sigma\rangle
\xrightarrow{\alpha}
\langle c',\sigma'\rangle.
$$

The trace of a complete execution is the concatenation of all nonempty labels.

### Assignment

Assignment is usually not directly observable:

$$
\frac{
\langle e,\sigma\rangle \Downarrow v
}{
\langle x:=e,\sigma\rangle
\xrightarrow{\epsilon}
\langle \mathbf{skip},\sigma[x\mapsto v]\rangle
}.
$$

We may optionally emit an `exec` event if operation counts are observable.

### Conditional

Let site $s$ identify this conditional.

$$
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
$$

and similarly for false.

The branch result is in the trace even when both branches compute the same final value.

### Load

$$
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
$$

### Store

$$
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
$$

### Output

$$
\frac{
\langle e,\sigma\rangle\Downarrow v
}{
\langle \mathbf{output}^{s}_h(e),\sigma\rangle
\xrightarrow{\mathsf{output}(s,h,v)}
\langle\mathbf{skip},\sigma\rangle
}.
$$

---

## 5. Traces

A finite trace is a sequence

$$
\tau = \alpha_0\alpha_1\cdots\alpha_{n-1}.
$$

The empty trace is $\varepsilon$. Concatenation is written $\tau_1\cdot\tau_2$.

A big-step judgment with traces can be defined by taking the reflexive transitive closure of the small-step relation:

$$
\langle c,\sigma\rangle
\xRightarrow{\tau}
\langle \mathbf{skip},\sigma'\rangle.
$$

We may then abbreviate this as

$$
\langle c,\sigma\rangle\Downarrow(\sigma',\tau).
$$

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

$$
\pi_{A,\Theta}(\tau)
$$

project trace $\tau$ to events observable by principal or coalition $A$, under target profile $\Theta$.

The observer trace is

$$
\operatorname{Trace}_{A,\Theta}(P,\sigma)
=
\pi_{A,\Theta}
\left(
\operatorname{Trace}(P,\sigma)
\right).
$$

Examples:

- A server sees operations and memory accesses executed on the server.
- The server may see a ciphertext's size but not its idealized plaintext payload.
- A cache-line observer sees $\lfloor a/64\rfloor$, not the exact byte address.
- A client may see the final released result but not server-local intermediate buffers.

A target profile can define

$$
\mu_\Theta(a)=
\begin{cases}
a & \text{exact-address model}\\
\left\lfloor a/64\right\rfloor & \text{cache-line model}\\
\left\lfloor a/4096\right\rfloor & \text{page model}.
\end{cases}
$$

The memory event exposed to the observer is then

$$
\mathsf{memory}(s,\mu_\Theta(a),w,k).
$$

---

## 7. Worked example: same result, different trace

Consider:

```c
if (secret)
    result = 5;
else
    result = 5;
```

Both executions return $5$. Functionally,

$$
\operatorname{Result}(P,\mathsf{false})
=
\operatorname{Result}(P,\mathsf{true})
=
5.
$$

But the traces are

$$
\tau_0=
[\mathsf{branch}(s,\mathsf{false})]
$$

and

$$
\tau_1=
[\mathsf{branch}(s,\mathsf{true})].
$$

If branch outcomes are observable,

$$
\tau_0\not\sim\tau_1.
$$

This is the smallest example showing why functional equivalence does not imply confidentiality.

---

## 8. Worked example: same control path, different address

Consider:

```c
x = table[secret_index];
```

Both executions perform one load and follow the same control-flow graph. If array elements have width $4$,

$$
a = base + 4\cdot secretIndex.
$$

Two executions may generate

$$
\mathsf{memory}(s,base,\;4,\mathsf{read})
$$

and

$$
\mathsf{memory}(s,base+400,\;4,\mathsf{read}).
$$

The control-flow path is identical, but the security traces differ.

This is why a trace is broader than a path.

---

## 9. Variable-latency events

Suppose the target has operand-dependent division timing. We can emit

$$
\mathsf{variableLatency}
\left(
s,\mathsf{div},
\operatorname{lat}_\Theta(x,y)
\right).
$$

The function $\operatorname{lat}_\Theta$ need not be an exact cycle count. It can return an abstract equivalence class.

For a conservative model,

$$
\operatorname{lat}_\Theta(\mathsf{div},x,y)
=
\langle x,y\rangle.
$$

That means different latency-relevant operands are treated as potentially distinguishable.

For a trusted constant-time helper,

$$
\operatorname{lat}_\Theta(\mathsf{ctDiv},x,y)
=
\mathsf{fixed}.
$$

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

$$
\llbracket P\rrbracket(\sigma)
\subseteq \mathrm{Trace}.
$$

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

$$
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
$$

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

A target observer sees only cache-line numbers. Let the cache line size be $64$. Are addresses $128$ and $160$ distinguishable? What about $128$ and $192$?

### Exercise 4

Add a `call(target)` event for indirect calls. Explain why a secret-dependent call target can leak even when every callee returns the same value.

### Exercise 5

Write trace semantics for a bounded `for` loop. Make operation-count leakage explicit.

---

## 14. Summary

The central move is

$$
\text{ordinary semantics}
\quad\longrightarrow\quad
\text{ordinary result plus observer trace}.
$$

Once traces exist, we can define confidentiality by comparing traces from two executions. The next module explains why that comparison is a hyperproperty.

---

## Further reading

- A. Sabelfeld and A. Myers, surveys on language-based information-flow security.
- D. Clark et al., work on observational determinism and trace-based confidentiality.
- The project threat model for the proposed tensor-MLIR event alphabet.
