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

$$
\ell(secretCoeff)=KeySecret.
$$

Target profile:

$$
Relevant_\Theta(divui)=\{lhs,rhs\}.
$$

Observer sees:

$$
\mathsf{variableLatency}
(
site,
divui,
lat_\Theta(scaled,q)
).
$$

---

## 5. Static result

$$
\ell(scaled)=KeySecret.
$$

Latency dependency:

$$
\ell_{lat}
=
\ell(scaled)\sqcup\ell(q).
$$

If the observer is not authorized for key material, the operation is rejected or sent to SMT.

A conservative target profile treats relevant operands as the latency observation, making the violation immediate.

---

## 6. Relational query

Choose two low-equivalent inputs:

$$
q_0=q_1,
$$

while

$$
secretCoeff_0,\ secretCoeff_1
$$

are independent.

Ask:

$$
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
$$

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

$$
branchObs=\mathsf{none},
$$

$$
latencyObs=\mathsf{fixed}.
$$

Bad target:

```mlir
cf.cond_br %secret_bit, ^set, ^clear
```

Target observation:

$$
branchObs=secretBit.
$$

---

## 10. Functional validation

Both compute:

$$
mask=
\begin{cases}
2^{32}-1 & secretBit\\
0 & \neg secretBit.
\end{cases}
$$

So

$$
FuncRefine(S,T)
$$

can hold.

---

## 11. Security query

Choose:

$$
secretBit_0=false,
\qquad
secretBit_1=true.
$$

Source:

$$
Trace_S(x_0)\sim Trace_S(x_1).
$$

Target:

$$
branch_0=false,
\qquad
branch_1=true.
$$

Therefore,

$$
\Phi_{regress}(S,T)
$$

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

$$
embedding[token].
$$

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

$$
a=
base
+
token\cdot4096\cdot4.
$$

Address label:

$$
\ell_{addr}
=
ClientOnly
\sqcup
PublicShape
\sqcup
PublicLayout
=
ClientOnly.
$$

The server-local address observer is unauthorized.

---

## 15. SMT query

$$
0\le token_0,token_1<50000
$$

and

$$
\mu_\Theta
(
base+16384token_0
)
\neq
\mu_\Theta
(
base+16384token_1
).
$$

Under cache-line observation, SAT finds tokens whose rows occupy different lines.

The loaded embeddings may also be provider-secret, but the address channel exists independently.

---

## 16. Repairs

### Oblivious full scan

Touch every row and mask-select the requested one.

Security:

$$
AddressTrace(token_0)=AddressTrace(token_1).
$$

Cost:

$$
O(V\cdot d)
$$

for vocabulary $V$ and dimension $d$.

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

$$
Readers(x)=\{client\},
$$

$$
Readers(W)=\{provider\}.
$$

Goal:

$$
y=model(W,x).
$$

Server may execute only on protected representations.

Release:

$$
R(W,x)=argmax(y)
$$

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

$$
D(x)=
\langle
ClientOnly,
Plain,
Client
\rangle.
$$

After conceal:

$$
D(x_{ct})=
\langle
ClientOnly,
FHE,
Client
\rangle.
$$

After transfer:

$$
D(x_{srv})=
\langle
ClientOnly,
FHE,
Server
\rangle.
$$

The policy stays client-only even though representation and placement change.

Provider weights evolve analogously.

Joint ciphertext result:

$$
\ell(y_{ct})
=
ClientOnly\sqcup ProviderOnly.
$$

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

Policy permits `argmax`, but implementation releases $y$.

SMT checks:

$$
\exists W,x.\quad
y\neq argmax(y).
$$

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

$$
\mathsf{branch}.
$$

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

$$
\mathsf{execCount}.
$$

## 24. Full scan to direct gather

Source touches all addresses.

Target touches one secret-selected address.

Event:

$$
\mathsf{memory}.
$$

## 25. Arithmetic to variable-time helper

Source operation has fixed target contract.

Target calls helper with unknown or variable latency.

Event:

$$
\mathsf{variableLatency}
\quad\text{or}\quad
\mathsf{call}.
$$

## 26. Bufferization exposes plaintext alias

Source protected tensor.

Target creates server-visible plaintext memref or alias.

Event:

$$
\mathsf{expose}.
$$

## 27. Uniform error to detailed errors

Source releases one validity bit.

Target returns different error classes.

Event:

$$
\mathsf{error}.
$$

## 28. Sanitized release moved before sanitizer

Source release policy satisfied.

Target exposes pre-sanitized value.

Event:

$$
\mathsf{release}
\quad\text{or}\quad
\mathsf{expose}.
$$

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

$$
LowEq
\Longrightarrow
TraceEq.
$$

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

$$
\text{policy}
\to
\text{descriptors}
\to
\text{effects}
\to
\text{two-run query}
\to
\text{security verdict}.
$$

For each lowering:

$$
\text{source indistinguishability}
\to
\text{target indistinguishability}
\to
\text{preserved or regressed}.
$$

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
