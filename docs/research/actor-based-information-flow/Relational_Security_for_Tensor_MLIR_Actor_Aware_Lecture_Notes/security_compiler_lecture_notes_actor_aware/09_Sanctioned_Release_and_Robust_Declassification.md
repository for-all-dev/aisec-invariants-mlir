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

$$
R(password,guess)
=
[password=guess].
$$

A medical computation may reveal an approved diagnosis.

A private inference service may reveal

$$
R(W,x)=\operatorname{argmax}(\operatorname{model}(W,x)).
$$

Strict noninterference would reject any secret-dependent output.

We therefore need an explicit, controlled exception.

---

## 2. Declassification

In a two-level lattice,

$$
Low\sqsubseteq High.
$$

Normal information flow rejects

$$
High\to Low.
$$

Declassification authorizes one such downgrade:

$$
High
\xrightarrow{\mathsf{release}}
Low.
$$

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

$$
\text{controlled expansion of authorized observers},
$$

not necessarily "make public to everyone."

---

## 4. Five dimensions of release

A release policy $k$ can be modeled as

$$
\Delta(k)=
\left\langle
A_k,
R_k,
O_k,
I_k,
Q_k
\right\rangle.
$$

### Audience $A_k$

Who may learn the result?

### Release function $R_k$

What exact function of protected state may be learned?

### Authority $O_k$

Whose permission is needed?

### Trusted influence $I_k$

Who may influence the payload, guard, policy choice, or occurrence?

### Requirements $Q_k$

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

$$
R_{dest}\subseteq R_{source}.
$$

A release deliberately permits an expansion such as

$$
R_{source}=\{C\}
\quad\longrightarrow\quad
R_{released}=\{C,P\}.
$$

This is not an ordinary assignment. It requires evidence that the policy owner authorizes the new audience and that only the declared release function is exposed.

In the principal-formula presentation, release permits a flow that would otherwise fail

$$
\ell_{from}\not\sqsubseteq\ell_{to}.
$$

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

Suppose secret $s$ is a salary.

Allowed:

$$
R(s)=[s>100000].
$$

Not automatically allowed:

$$
s,
\quad
s\bmod 1000,
\quad
\operatorname{bitlength}(s),
\quad
\text{timing dependent on }s.
$$

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

$$
D(\%secretResult).\ell=High,
$$

$$
D(\%released).\ell=ClientReadable.
$$

This operation does not mutate all aliases or every future use of the secret.

That makes downgrading explicit in def-use chains.

---

## 8. Encryption, decryption, and release

These are separate transitions.

### Concealment

$$
\mathsf{Plain}
\rightarrow
\mathsf{Ciphertext}.
$$

Policy is unchanged.

### Decryption

$$
\mathsf{Ciphertext}
\rightarrow
\mathsf{Plain}.
$$

Policy is still unchanged. Decryption is legal only at a host authorized to hold the plaintext.

### Release

The audience policy changes.

$$
Readers_{before}
\subset
Readers_{after}.
$$

Therefore:

$$
\boxed{
\mathsf{encrypt}\neq\mathsf{release}
}
$$

and

$$
\boxed{
\mathsf{decrypt}\neq\mathsf{release}.
}
$$

HEIR's `secret.reveal` is a scheme-agnostic decryption boundary. A party-aware compiler should not automatically interpret it as policy declassification.

---

## 9. Release-relative low-equivalence

For observer $A$, define

$$
\sigma_0\approx_A^\Delta\sigma_1
$$

when:

1. all initially $A$-visible facts are equal;
2. every release function authorized to $A$ is equal.

Formally,

$$
\operatorname{PublicView}_A(\sigma_0)
=
\operatorname{PublicView}_A(\sigma_1)
$$

and

$$
\forall k\text{ visible to }A.\quad
R_k(\sigma_0)=R_k(\sigma_1).
$$

Security becomes

$$
\sigma_0\approx_A^\Delta\sigma_1
\Longrightarrow
Trace_{A,\Theta}(P,\sigma_0)
\sim
Trace_{A,\Theta}(P,\sigma_1).
$$

Read this as:

> Once all authorized released information is held constant, no remaining observation may vary with the secret.

---

## 10. Password protocol oracle

Policy:

$$
R(password,guess)
=
[password=guess].
$$

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

$$
R(\sigma_0)=R(\sigma_1)=false.
$$

An early-exit comparison produces counts

$$
count_0=1,
\qquad
count_1=12.
$$

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

$$
\mathsf{release}(policy,audience,0)
$$

in one execution and no event in the other.

Therefore, a release policy must cover:

- whether release occurs;
- how many times;
- when relative to other events;
- to which audience;
- with what payload.

A policy may intentionally release an option:

$$
R(\sigma)=
\begin{cases}
Some(v)&condition\\
None&otherwise.
\end{cases}
$$

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

$$
\ell=\langle C,I\rangle.
$$

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

$$
R(password,guess)=[password=guess].
$$

But the client should not be able to choose an arbitrary expression:

```text
release(password[guess])
```

or control a hidden branch that releases additional server state.

The policy must distinguish permitted inputs to the release function from arbitrary attacker influence.

---

## 15. Transparent endorsement

Endorsement raises integrity:

$$
Untrusted
\xrightarrow{\mathsf{endorse}}
Trusted.
$$

Unchecked endorsement is the integrity analogue of unchecked declassification.

Transparent endorsement roughly requires that a provider of untrusted information be allowed to know what information is being endorsed. This blocks using endorsement to smuggle secrets into trusted state in a way the provider cannot observe.

For an initial honest-but-curious compiler, full transparent endorsement may be deferred. Still, the architecture should reserve:

- integrity labels;
- explicit endorsement operations;
- authentication/proof contracts.

---

## 16. A release typing judgment

A conceptual rule is

$$
\Pi;\Delta;\Theta;\Gamma;pc;h
\vdash
\mathsf{release}_k(v)
:
D'
\triangleright
E;\Omega.
$$

Premises include:

1. $k\in\Delta$;
2. current host may access the representation;
3. required owners authorize the release;
4. audience equals $A_k$;
5. $v$ computes the permitted function $R_k$;
6. $pc$ and release guard satisfy integrity requirements;
7. sanitizers, authentication, or proofs in $Q_k$ are present;
8. release occurrence and trace effects conform to policy.

The result descriptor $D'$ has the expanded reader set.

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

- implementation expression equals $R_k$;
- no extra observation varies when $R_k$ is equal;
- two error paths reveal only the same authorized result;
- a masking expression really computes the approved function.

---

## 18. Checking expression equivalence to policy

Suppose policy permits

$$
R(s)=s\bmod2.
$$

Implementation releases

$$
v=s\bmod4.
$$

Ask SMT:

$$
\exists s.\quad v(s)\neq R(s).
$$

SAT proves the implementation does not match the policy.

A more subtle implementation may be extensionally equal but syntactically different; SMT can prove equality.

---

## 19. FHE private inference release

Inputs:

$$
\ell(x)=ClientOnly,
$$

$$
\ell(W)=ProviderOnly.
$$

Intermediate logits:

$$
z=model(W,x).
$$

Policy:

$$
R(W,x)=argmax(z).
$$

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

$$
R(T)=shape(T),
$$

$$
R(T)=sum(T),
$$

$$
R(T)=\#nonzero(T),
$$

$$
R(T)=argmax(T).
$$

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

$$
R(s)=s
$$

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

$$
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
$$

The relational guarantee is:

$$
\boxed{
\text{same authorized release}
\Longrightarrow
\text{same remaining observation}.
}
$$

The next module explains how cryptographic and backend mechanisms are represented as contracts and obligations.

---

## Further reading

- C. Acay et al., [Viaduct](https://www.cs.cornell.edu/andru/papers/viaduct/viaduct.pdf), especially label checking, declassification, endorsement, and protocol assignment.
- Literature on robust declassification, transparent endorsement, and nonmalleable information flow.
- HEIR [`secret` dialect](https://heir.dev/docs/dialects/secret/) for conceal/reveal representation boundaries.
