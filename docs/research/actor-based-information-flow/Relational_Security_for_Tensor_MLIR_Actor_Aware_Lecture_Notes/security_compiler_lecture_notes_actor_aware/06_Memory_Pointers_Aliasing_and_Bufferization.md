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

$$
\mu:\mathrm{Addr}\to\mathrm{Val}.
$$

A pointer value is an address:

$$
p\in\mathrm{Addr}.
$$

A load evaluates as

$$
\operatorname{load}(\mu,p)=\mu(p).
$$

A store produces

$$
\operatorname{store}(\mu,p,v)=\mu[p\mapsto v].
$$

For arrays or memrefs, an address is calculated from a base, offset, indices, strides, and element size:

$$
\operatorname{addr}
=
base
+
offset
+
\sum_{k=0}^{r-1} i_k\cdot stride_k.
$$

In bytes, multiply element units by the element size if the stride representation requires it.

Security cares about both:

1. the value read or written;
2. the address used.

---

## 3. Three distinct security questions about a pointer

It is helpful to distinguish three labels.

### Pointer-value label

$$
\ell_{\mathrm{ptr}}(p)
$$

protects the pointer value itself.

If a pointer selects one of two objects based on a secret, the pointer value is secret-dependent.

### Address-observation label

$$
\ell_{\mathrm{addr}}(p)
$$

protects which concrete address or address class is accessed.

An observer may learn the address through cache behavior even if the pointer bits are never output.

### Pointee-content label

$$
\ell_{\mathrm{content}}(\lambda)
$$

protects data stored in abstract location $\lambda$.

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

$$
M:\mathcal H\rightarrow(\mathsf{Addr}\rightharpoonup\mathsf{Byte}),
$$

so every host has an address space $M_h$.

An allocation descriptor can contain

$$
D_{alloc}(a)=
\langle
h_a,\ell_{content},\ell_{address},\rho,\operatorname{controllers}(h_a)
\rangle.
$$

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

$$
\langle
\ell_{pointerBits},
\ell_{addressChoice},
\ell_{pointee},
h_{addressSpace},
capabilities
\rangle.
$$

The pointer bits may be public while the pointee is client-confidential. Conversely, a public table may be indexed by a client-secret address choice.

### Allocation ACLs and aliasing

For an allocation $a$, define a reader set or principal policy for its plaintext contents. A host access is permitted only if the host's controllers are authorized for the exposed representation.

Aliasing can widen exposure without copying data. If bufferization creates an alias to client-confidential plaintext in a server-controlled address space, the policy is violated even if the compiler never inserts an explicit `send`.

This is why allocation placement is a security event:

$$
expose(site,h,facet,representation).
$$

### Memory traces are actor-relative

A load performed on the client may be invisible to the server. The same load performed on the server may reveal an address to the server controller.

For observer $A$, include the event only when

$$
\operatorname{CanObserveMemory}(A,h,\Theta).
$$

Then compare

$$
\mu_{A,\Theta}(addr_0)
\quad\text{and}\quad
\mu_{A,\Theta}(addr_1).
$$

The target profile can give different observers different granularities, such as exact address for a local host controller and page number for a remote observer.

---

## 5. Abstract locations

A static analysis cannot usually track every concrete address. It groups addresses into **abstract locations**.

Let

$$
\Lambda
$$

be the set of abstract locations.

Examples:

- one allocation site;
- one global variable;
- one stack slot;
- one struct field;
- one array region;
- one memref base plus an index abstraction.

An abstract memory state is

$$
\widehat{\mu}:\Lambda\to D_{\mathrm{mem}},
$$

where $D_{\mathrm{mem}}$ contains a content security descriptor and perhaps initialization, placement, and representation facts.

A pointer analysis computes

$$
\operatorname{Pt}(p)\subseteq\Lambda,
$$

the set of abstract locations that pointer $p$ may reference.

---

## 6. May-alias and must-alias

Two pointers may alias when

$$
\operatorname{Pt}(p)\cap\operatorname{Pt}(q)\neq\varnothing.
$$

They must alias when the analysis proves they always denote the same location.

A simple sufficient condition is

$$
\operatorname{Pt}(p)=\operatorname{Pt}(q)=\{\lambda\},
$$

plus a proof that offsets agree.

### Why the distinction matters

A store through a must-alias pointer can overwrite the unique abstract location precisely.

A store through a may-alias pointer may affect several locations, so the analysis must conservatively join the new information into each candidate.

---

## 7. Strong updates

Suppose

$$
\operatorname{Pt}(p)=\{\lambda\}
$$

and $\lambda$ represents one unique concrete cell.

For

```text
*p = v
```

a strong update replaces the old abstract content:

$$
\widehat{\mu}'(\lambda)=D(v).
$$

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

$$
\operatorname{Pt}(p)=\{\lambda_1,\lambda_2\}.
$$

The store may affect either location. For each candidate,

$$
\widehat{\mu}'(\lambda_i)
=
\widehat{\mu}(\lambda_i)
\sqcup
D(v).
$$

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

$$
\operatorname{Pt}(p)=\{\lambda_a,\lambda_b\}.
$$

A weak update labels both locations secret:

$$
\widehat{\mu}'(\lambda_a)
=
Public\sqcup Secret
=
Secret,
$$

$$
\widehat{\mu}'(\lambda_b)
=
Public\sqcup Secret
=
Secret.
$$

That is conservative. In one run only one cell receives the secret, but the public output of `a` may differ across secret control choices, so rejecting is reasonable.

The address event also leaks which object was selected:

$$
\mathsf{memory}(addr(a))
\quad\text{versus}\quad
\mathsf{memory}(addr(b)).
$$

---

## 10. Flow sensitivity for memory

A flow-sensitive memory analysis computes a different abstract memory state at each program point:

$$
\widehat{\mu}_p.
$$

A flow-insensitive analysis has one global summary:

$$
\widehat{\mu}.
$$

Flow sensitivity is much more precise for stores and overwrites, but requires control-flow fixed points.

At a CFG merge:

$$
\widehat{\mu}_{join}
=
\widehat{\mu}_{left}
\sqcup
\widehat{\mu}_{right},
$$

joining each abstract location.

For loops, the analysis iterates until a fixed point.

---

## 11. Field sensitivity and index sensitivity

An abstract location can be coarse or precise.

### Field-insensitive

One struct object is one location:

$$
\lambda_{\mathsf{object}}.
$$

Writing a secret into one field taints the whole object.

### Field-sensitive

Use separate locations:

$$
\lambda_{\mathsf{object.field1}},
\qquad
\lambda_{\mathsf{object.field2}}.
$$

This is more precise.

### Index-insensitive array abstraction

One location represents all elements:

$$
\lambda_{\mathsf{array[*]}}.
$$

Any secret store can label every future load secret.

### Index-sensitive abstraction

Use exact constant indices or intervals:

$$
\lambda_{\mathsf{array[0]}},
\quad
\lambda_{\mathsf{array[1..15]}}.
$$

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

$$
a=base+width\cdot secretIndex.
$$

A static IFC checker should generate:

$$
\ell_{\mathrm{contentResult}}
=
\ell_{\mathrm{val}}(table)
\sqcup
\ell_{\mathrm{idx}}(secretIndex),
$$

and separately:

$$
\ell_{\mathrm{memoryEvent}}
=
pc
\sqcup
\ell_{\mathrm{idx}}(secretIndex)
\sqcup
\ell_{\mathrm{layout}}(table).
$$

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

$$
\ell_{\mathrm{ptr}}(r)
=
\ell_{\mathrm{ptr}}(p)
\sqcup
\ell_{\mathrm{idx}}(secretOffset).
$$

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

$$
\mathsf{Reads}(f),
\quad
\mathsf{Writes}(f),
\quad
\mathsf{Escapes}(f),
\quad
\mathsf{Effects}(f),
\quad
\mathsf{Contract}(f).
$$

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

$$
Init(\lambda)\in
\{
\mathsf{Uninitialized},
\mathsf{Initialized}(D)
\}.
$$

Reading uninitialized memory should be rejected or treated as an obligation.

### Lifetime and deallocation

After `dealloc`, aliases become dangling. A use-after-free is primarily memory safety, but allocator reuse can also reveal residual secrets.

### Zeroization

A security policy may require:

$$
\mathsf{secretBuffer}
\Longrightarrow
\mathsf{clearedBeforeDomainTransition}.
$$

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

$$
\langle
base,
alignedBase,
offset,
sizes,
strides
\rangle.
$$

The address of element $(i_0,\ldots,i_{r-1})$ is approximately

$$
alignedBase
+
offset
+
\sum_k i_k\cdot stride_k.
$$

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

$$
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
$$

The subview's layout label depends on:

$$
\ell_{\mathrm{layout}}(\%base)
\sqcup
\ell(\%off)
\sqcup
\ell(\%size)
\sqcup
\ell(\%stride).
$$

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

$$
\operatorname{Pt}(result)
\supseteq
\operatorname{Pt}(operand).
$$

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

$$
r = store(t,i,x).
$$

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

$$
\mathsf{expose}
(
server,
value,
Plain,
\%buf
).
$$

This violates placement confidentiality.

A source-level label attached only to `%secret_tensor` is not enough. The lowering validator must reconstruct or propagate the semantic policy into the target memory representation and inspect aliases and calls.

---

## 23. Security regression: secret-dependent copying

A bufferization or optimization may choose whether to copy based on a secret-dependent condition.

Then the trace differs through:

$$
\mathsf{allocation},
\quad
\mathsf{memory},
\quad
\mathsf{execCount}.
$$

In ordinary MLIR bufferization, compile-time analysis decisions do not depend on runtime secrets. However, generated target control flow or dynamic-shape conditions may.

The principle is:

> Compile-time choice being deterministic does not imply that generated runtime behavior is secret-independent.

---

## 24. Source-target representation relation

Tensor and memref states have different structures.

To validate bufferization, define

$$
\operatorname{RepRel}
(
\sigma_S,
\sigma_T
).
$$

For a tensor value $t$ and target memref $m$, the relation may require:

$$
\forall \bar i\in\operatorname{bounds}(t).\quad
t[\bar i]
=
\mu_T(\operatorname{addr}(m,\bar i)).
$$

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

$$
\operatorname{View}_{A,\Theta}(\mu)
$$

include:

- contents of authorized locations;
- allocation metadata visible to $A$;
- protected projections of ciphertext buffers;
- not the plaintext content of protected representations.

Then

$$
\mu_0\approx_{A,\Theta}\mu_1
\quad\Longleftrightarrow\quad
\operatorname{View}_{A,\Theta}(\mu_0)
=
\operatorname{View}_{A,\Theta}(\mu_1).
$$

For aliased memory, equality must respect the same abstract object graph or a relation between corresponding allocations.

---

## 26. Encoding memory in SMT

A common bounded model represents memory as an SMT array:

$$
M:\mathrm{BitVec}_{w_a}\to\mathrm{BitVec}_{8}.
$$

A load of $n$ bytes uses array selects; a store uses nested array stores.

Alternatively, tensor-shaped buffers can be represented as mathematical arrays indexed by tuples:

$$
T:
I_0\times\cdots\times I_{r-1}
\to
V.
$$

The choice depends on the IR level.

### Address trace

Even when memory contents are modeled abstractly, emit a symbolic address event:

$$
e_{\mathrm{addr}}
=
\mu_\Theta
(
base+offset+\sum_k i_k stride_k
).
$$

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

$$
R=
\langle
base,
offsets,
sizes,
strides
\rangle.
$$

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

$$
a=
base
+
secretOff\cdot stride
+
i.
$$

Even if `%i` is public,

$$
\ell_{\mathrm{address}}
=
\ell(secretOff)
\sqcup
\ell(layout(base)).
$$

The subview descriptor must retain the secret offset provenance. If an analysis labels only `%i`, it is unsound.

---

## 32. Worked example: public pointer to secret content

Suppose `%p` always points to the same secret buffer.

$$
\ell_{\mathrm{ptr}}(p)=Public,
\qquad
\ell_{\mathrm{content}}(\lambda)=ClientOnly.
$$

The fixed address may be safe to observe.

A load result is still secret:

$$
\ell_{\mathrm{val}}(load(p))
=
ClientOnly.
$$

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

$$
Pt(p)=\{\lambda_1\},
\qquad
Pt(q)=\{\lambda_1,\lambda_2\},
$$

which stores permit strong updates?

### Exercise 2

Analyze:

```c
*p = secret;
x = *q;
```

under the assumption that $p$ and $q$ may alias.

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

Define a simple $\operatorname{RepRel}$ between a rank-one tensor and a contiguous memref.

### Exercise 6

Why can a weak update cause false positives? Why is replacing it with a strong update without proof unsound?

### Exercise 7

Design an opaque-call memory summary for a constant-time cryptographic helper that reads one input buffer and writes one output buffer without retaining aliases.

---

## 35. Summary

Memory security is indexed by host and observer. A pointer identifies a location in a host address space; an allocation policy limits which principals may inspect its contents; and an address-event policy limits which principals may learn how it is accessed.


Memory analysis requires two related but distinct models:

$$
\boxed{
\text{abstract contents and aliases}
}
$$

and

$$
\boxed{
\text{observable addresses, sizes, and lifetimes}.
}
$$

For each pointer or memref, track:

$$
\text{where it may point}
+
\text{what those locations contain}
+
\text{how the address was chosen}
+
\text{who can observe the storage}.
$$

Bufferization is a security-critical lowering because it turns immutable tensor values into mutable, aliased physical storage. Secure translation validation must relate source tensor states to target memory states explicitly.

---

## Further reading

- MLIR, [Bufferization](https://mlir.llvm.org/docs/Bufferization/).
- MLIR, [`bufferization` dialect](https://mlir.llvm.org/docs/Dialects/BufferizationOps/).
- MLIR, [Ownership-Based Buffer Deallocation](https://mlir.llvm.org/docs/OwnershipBasedBufferDeallocation/).
- Standard compiler texts on points-to analysis, abstract interpretation, and memory SSA.
- Research on information flow for heap-allocated and object-oriented languages.
