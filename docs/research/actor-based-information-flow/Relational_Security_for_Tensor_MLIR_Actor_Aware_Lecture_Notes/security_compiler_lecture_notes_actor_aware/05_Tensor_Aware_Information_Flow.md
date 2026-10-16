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

$$
T =
\langle
\text{elements},
\text{indices},
\text{shape},
\text{layout},
\text{placement}
\rangle.
$$

Those components can have different policies.

Example:

```text
element values: client-confidential
shape:          public
layout:         public
representation: FHE ciphertext
placement:      server
```

This is common in outsourced encrypted computation. The server may know that a ciphertext represents a $128\times 128$ matrix without learning its entries.

The reverse is also possible:

```text
elements:       public
shape:          client-confidential
```

For example, the number of medical records or sequence length may itself be sensitive.

A single `secret<T>` wrapper cannot express all of these distinctions precisely.

---

## 2. The security descriptor

For an MLIR SSA value $v$, define

$$
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
$$

The fields are:

- $\tau$: ordinary MLIR type;
- $\ell_{\mathrm{val}}$: policy for scalar or tensor element values;
- $\ell_{\mathrm{idx}}$: policy for logical indices, selectors, token identifiers, or permutation choices;
- $\ell_{\mathrm{shape}}$: policy for ranks, dimensions, lengths, and batch sizes;
- $\ell_{\mathrm{layout}}$: policy for strides, sparsity patterns, nonzero locations, tiling, routing, and storage format;
- $\rho$: representation, such as plaintext, FHE ciphertext, share, or opaque handle;
- $h$: actual host or device placement;
- $\Omega$: outstanding proof or platform obligations.

Each facet label may itself contain confidentiality and integrity:

$$
\ell_f=\langle C_f,I_f\rangle.
$$

For an honest-but-curious first version, confidentiality may dominate, but retaining the full structure makes release and authentication cleaner.

---

## 3. Principal-indexed facet policies

Every facet label is a principal-indexed policy, not an unqualified `secret` bit.

For a tensor facet $f$, we may use either the ACL view

$$
ACL_f(v)=\langle R_f(v),I_f(v)\rangle
$$

or the authority-formula view

$$
\ell_f(v)=\langle C_f(v),I_f(v)\rangle.
$$

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

$$
\operatorname{CanRead}(A,\ell_{shape})
$$

for the specific observer coalition $A$.

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

$$
\operatorname{Exposed}(A,h,\rho,f)
\Longrightarrow
\operatorname{CanRead}(A,\ell_f).
$$

For example, an FHE representation may hide element values from the server while exposing rank, dimensions, ciphertext count, and parameter identifiers. A packed representation may also make layout choices observable.

### Two-owner join

If client input elements have policy $\ell_C$ and provider weight elements have policy $\ell_P$, then a joint tensor result has

$$
\ell_{val}(r)=pc\sqcup\ell_C\sqcup\ell_P.
$$

In a reader-set presentation, the plaintext reader set becomes

$$
R_C\cap R_P.
$$

This may be empty. That does not prohibit the computation; it prohibits an unprotected plaintext realization. The mechanism and placement layers must choose an FHE, MPC, or otherwise protected representation.

---

## 4. Does every matrix have all four labels?

Conceptually, yes: every tensor value has all four **facets**. That does not mean all four are secret or even operationally interesting.

For a fixed-size dense matrix

```mlir
tensor<32x32xf32>
```

we might have

$$
\ell_{\mathrm{shape}}=\mathsf{Public},
\qquad
\ell_{\mathrm{layout}}=\mathsf{Public}.
$$

If the matrix is not used as an index, then $\ell_{\mathrm{idx}}$ may be irrelevant or set to bottom.

For a scalar index value

```mlir
%token : index
```

the meaningful facet is often

$$
\ell_{\mathrm{idx}}(\%token).
$$

The descriptor is a uniform analysis structure. Operation-specific transfer functions decide which facets matter.

---

## 5. Element-value confidentiality

$\ell_{\mathrm{val}}$ protects the logical payload.

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

$$
\ell_{\mathrm{val}}(z)
=
pc
\sqcup
\ell_{\mathrm{val}}(x)
\sqcup
\ell_{\mathrm{val}}(y).
$$

For matrix multiplication,

$$
C=A\cdot B,
$$

the result elements depend on both operands:

$$
\ell_{\mathrm{val}}(C)
=
pc
\sqcup
\ell_{\mathrm{val}}(A)
\sqcup
\ell_{\mathrm{val}}(B).
$$

If $A$ is client-only and $B$ is provider-only, the joint plaintext result may be readable by neither party.

---

## 6. Index confidentiality

$\ell_{\mathrm{idx}}$ protects which logical item is selected.

Examples:

- token ID used in an embedding lookup;
- table index in a cryptographic lookup table;
- gather/scatter indices;
- selected expert in a mixture-of-experts model;
- permutation or shuffle indices;
- secret row or column;
- top-$k$ selected positions.

Consider

```mlir
%x = tensor.extract %table[%i]
```

The returned value depends on both table contents and the selector:

$$
\ell_{\mathrm{val}}(x)
=
pc
\sqcup
\ell_{\mathrm{val}}(table)
\sqcup
\ell_{\mathrm{idx}}(i).
$$

Even if all table elements are public, the chosen value reveals the index.

More importantly, the memory address depends on the index:

$$
\ell_{\mathrm{address}}
=
pc
\sqcup
\ell_{\mathrm{idx}}(i)
\sqcup
\ell_{\mathrm{shape}}(table)
\sqcup
\ell_{\mathrm{layout}}(table).
$$

A direct gather can therefore violate constant-time trace noninterference.

---

## 7. Shape confidentiality

$\ell_{\mathrm{shape}}$ protects information such as:

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

$$
\mathsf{shape}(\bar d),
\quad
\mathsf{allocation}(n),
\quad
\mathsf{transfer}(n),
\quad
\mathsf{kernelLaunch}(k),
\quad
\mathsf{execCount}(n).
$$

Example:

```mlir
%buffer = memref.alloc(%secret_len) : memref<?xi32>
```

The allocation event exposes

$$
n=4\cdot secretLen.
$$

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

$\ell_{\mathrm{layout}}$ protects how values are arranged or scheduled.

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

$$
\ell_{\mathrm{schedule}}
=
pc
\sqcup
\ell_{\mathrm{layout}}(T).
$$

A dense oblivious implementation may have a public schedule even when logical sparsity is secret.

---

## 9. Policy, representation, and placement are different

This distinction is central.

### Policy

Who is authorized to learn the underlying information?

$$
\ell_{\mathrm{val}}=\mathsf{ClientOnly}.
$$

### Representation

How is the information currently encoded?

$$
\rho\in
\{
\mathsf{Plain},
\mathsf{FHE}(pk),
\mathsf{Share}(t,n),
\mathsf{Opaque}(K)
\}.
$$

### Placement

Where does the representation exist?

$$
h\in
\{
\mathsf{Client},
\mathsf{Server},
\mathsf{Provider},
\mathsf{GPU}
\}.
$$

Encryption changes representation:

$$
\rho_{\mathsf{plain}}
\rightarrow
\rho_{\mathsf{FHE}}.
$$

Transfer changes placement:

$$
h_{\mathsf{client}}
\rightarrow
h_{\mathsf{server}}.
$$

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

$$
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
$$

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

$$
\ell_{\mathrm{val}}(r)
=
pc\sqcup
\ell_{\mathrm{val}}(x)
\sqcup
\ell_{\mathrm{val}}(y),
$$

$$
\ell_{\mathrm{shape}}(r)
=
\ell_{\mathrm{shape}}(x)
\sqcup
\ell_{\mathrm{shape}}(y),
$$

while layout is determined by result construction and target scheduling.

### Reshape

For

```mlir
%r = tensor.reshape %x(%shape)
```

the output payload policy is inherited:

$$
\ell_{\mathrm{val}}(r)
=
\ell_{\mathrm{val}}(x).
$$

The output shape depends on the shape operand:

$$
\ell_{\mathrm{shape}}(r)
=
pc
\sqcup
\ell_{\mathrm{shape}}(x)
\sqcup
\ell_{\mathrm{val}}(\%shape).
$$

### Transpose

Logical values are unchanged, but layout changes:

$$
\ell_{\mathrm{val}}(r)=\ell_{\mathrm{val}}(x),
$$

$$
\ell_{\mathrm{layout}}(r)
=
pc
\sqcup
\ell_{\mathrm{layout}}(x)
\sqcup
\ell_{\mathrm{idx}}(\mathsf{permutation}).
$$

If the permutation is secret, later addresses may leak it.

### Slice

For

```mlir
%r = tensor.extract_slice %x[%offsets][%sizes][%strides]
```

$$
\ell_{\mathrm{val}}(r)
=
\ell_{\mathrm{val}}(x)
\sqcup
\ell_{\mathrm{idx}}(\mathsf{offsets})
\sqcup
\ell_{\mathrm{shape}}(\mathsf{sizes}).
$$

The result shape depends on `sizes`; layout depends on offsets and strides.

### Top-$k$

The selected values and indices depend on the input values:

$$
\ell_{\mathrm{val}}(values)
=
\ell_{\mathrm{val}}(x),
$$

$$
\ell_{\mathrm{idx}}(indices)
=
\ell_{\mathrm{val}}(x).
$$

A data-dependent algorithm may also leak through operation counts or memory accesses.

---

## 12. Tensor effects

A tensor operation can produce observable effects independent of its result descriptor.

### Allocation

$$
e_{\mathrm{alloc}}
=
\mathsf{allocation}
\left(
s,
\operatorname{bytes}(\bar d,\tau)
\right).
$$

Dependency:

$$
\ell(e_{\mathrm{alloc}})
=
pc\sqcup\ell_{\mathrm{shape}}.
$$

### Kernel selection

$$
e_{\mathrm{kernel}}
=
\mathsf{kernelLaunch}(s,k).
$$

If $k$ depends on a secret shape, sparsity pattern, or value, the kernel identity becomes a channel.

### Transfer

$$
e_{\mathrm{transfer}}
=
\mathsf{transfer}(s,h_1,h_2,n).
$$

The size $n$ may depend on shape, layout, compression, or ciphertext packing.

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

$$
\ell_{\mathrm{val}}(e)
=
ProviderOnly
\sqcup
ClientOnly.
$$

The address is

$$
a=
base
+
secretToken\cdot 4096\cdot 4.
$$

The server-local memory observer sees

$$
\mu_\Theta(a).
$$

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

$$
\ell_{\mathrm{val}}(x)=ClientOnly
$$

and

$$
\ell_{\mathrm{val}}(W)=ProviderOnly.
$$

For

$$
y=W x,
$$

the joint plaintext result is

$$
\ell_{\mathrm{val}}(y)
=
ClientOnly\sqcup ProviderOnly.
$$

In a reader-set lattice, this may yield no plaintext reader.

That does not mean the computation is impossible. It means the representation must remain protected, for example:

$$
\rho(y)=FHE
\quad\text{or}\quad
\rho(y)=MPCShare.
$$

A policy can later sanction release of

$$
R(W,x)=\operatorname{argmax}(Wx)
$$

to the client without releasing $W$, $x$, or full logits.

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

A top-$k$ operation returns public values but secret indices. Is that policy coherent? Give a use case or explain why it may be dangerous.

### Exercise 5

For two-owner inference, define a release policy that reveals only the predicted class to the client.

---

## 18. Summary

Every statement in this chapter is actor-relative. A facet label says which principal authority is required to observe or influence that facet; host placement and representation determine whether the facet is actually exposed to a given observer.


Tensor security is facet-sensitive:

$$
\boxed{
\text{elements}
\neq
\text{indices}
\neq
\text{shape}
\neq
\text{layout}
}
$$

and orthogonal to

$$
\boxed{
\text{policy}
\neq
\text{representation}
\neq
\text{placement}.
}
$$

The next module explains what happens when immutable tensor SSA values become mutable buffers, pointers, and aliases.

---

## Further reading

- HEIR [`secret` dialect](https://heir.dev/docs/dialects/secret/).
- MLIR tensor, linalg, sparse tensor, and bufferization documentation.
- The project threat model's tensor metadata event classes.
