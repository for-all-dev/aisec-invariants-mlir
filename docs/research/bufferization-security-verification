
# Bufferization Security Verification – Design Notes

## Motivation

Our overall research focuses on verifying that compiler lowering preserves security properties. While looking at different MLIR lowering passes, **bufferization** stood out because it performs physical resource allocation decisions that can introduce a unique confidentiality risk.

Unlike most lowering passes, bufferization decides **which logical tensors share the same physical memory**. From a performance perspective this is desirable because it reduces allocations and improves memory reuse. From a security perspective, however, buffer reuse can accidentally create storage-based information leaks if reuse is not performed safely.

This document proposes a verification methodology for checking whether compiler-generated buffer reuse preserves storage isolation between different security domains.

---

# The problem

Consider two tensors:

```
Tensor A   (Secret)
Tensor B   (Public)
```

At the tensor level these are completely separate SSA values.

During bufferization the compiler may decide that Tensor A is dead and therefore reuse its physical storage for Tensor B.

```
Tensor A
      │
      ▼
Buffer X

...

Tensor B
      │
      ▼
Buffer X
```

This is normally considered correct because their lifetimes do not overlap.

However, the physical memory still contains Tensor A's bytes.

If Tensor B reads from the reused buffer before fully overwriting those bytes, the computation can observe residual secret data.

```
Secret writes
      │
      ▼
Buffer X

↓

Buffer reused

↓

Public reads

↓

Residual secret bytes become observable
```

This is **not** a cache-timing attack.

It is a direct storage confidentiality violation caused entirely by compiler-generated memory reuse.

Unlike timing channels, this property is visible directly in the compiler IR and can therefore be verified statically.

---

# Scope

The work intentionally focuses on **storage isolation**.

In scope:

* compiler-generated buffer reuse
* storage aliasing
* residual data leaks
* overwrite safety
* static verification

Out of scope:

* cache timing attacks
* Prime+Probe / Flush+Reload
* GPU cache contention
* speculative execution
* microarchitectural side channels

---

# Proposed verification

The verification consists of two properties.

---

## Property A – Detect cross-domain sharing

First determine which buffers may be shared.

MLIR already provides alias analyses capable of identifying buffers that may refer to the same storage.

For every alias pair we recover its originating tensor and associated security label.

Example:

```
Buffer X

↓

Secret Tensor A

and

↓

Public Tensor B
```

If both originate from the same security domain

```
Secret → Secret

or

Public → Public
```

the pair is ignored.

If storage is shared across security domains

```
Secret → Public
```

the pair becomes a candidate for deeper analysis.

This stage is inexpensive and entirely static.

---

## Property B – Verify overwrite safety

Sharing storage is not automatically a leak.

Sequential reuse is safe if the new owner completely overwrites the reused region before reading it.

Safe reuse:

```
Secret writes

↓

Buffer reused

↓

Public overwrites entire buffer

↓

Public reads
```

Unsafe reuse:

```
Secret writes

↓

Buffer reused

↓

Public overwrites only part

↓

Public reads

↓

Remaining bytes still contain secret data
```

Property B verifies that every public read is dominated by sufficient writes covering the entire region being read.

If this property holds, reuse is considered safe.

If not, the verification reports a confidentiality violation together with a concrete counterexample.

---

# Why SMT is needed

Simple cases can often be decided using compiler analyses alone.

Examples:

* alias analysis
* dominance
* liveness

However, partial overwrites quickly become difficult.

Example:

```
Secret writes bytes 0–1023

↓

Public overwrites bytes 512–1023

↓

Public reads bytes 0–1023
```

Now only half the buffer has been overwritten.

Reasoning about these byte ranges becomes an SMT problem.

Rather than introducing a new solver infrastructure, the proposal adds these overwrite obligations to the same SMT query already used elsewhere in the verification pipeline.

Conceptually the solver checks

```
Security preserved

AND

Storage reuse is safe
```

instead of checking only the original security property.

---

# Counterexamples

When verification fails the goal is not merely to report

```
Unsafe buffer reuse detected
```

Instead the verifier should produce an actionable witness.

Example:

```
Buffer:
    %42

Originally allocated for:
    Secret Tensor A

Reused by:
    Public Tensor B

Reason:
    Read before complete overwrite

Leaking region:
    bytes 128–255
```

This makes debugging compiler transformations significantly easier.

---

# Why this belongs inside the existing verification pipeline

This is **not** intended to become a separate project.

Instead it becomes one additional verification obligation for the bufferization pass.

The same infrastructure is reused:

* existing security labels
* existing solver
* existing counterexample generation
* existing verification pipeline

Only three new components are needed:

* provenance tracking (tensor → buffer)
* alias/liveness classification
* overwrite-coverage obligation generation

---

# OS analogy

The underlying philosophy is very similar to resource isolation in operating systems.

Suppose Process A exits.

Its physical page still contains

* passwords
* cryptographic keys
* confidential application state

The operating system does **not** immediately hand that page to Process B.

Instead it either

* allocates a different page, or
* clears the page before reuse.

Otherwise Process B could read Process A's leftover memory.

Compiler bufferization creates an analogous situation.

```
Secret Tensor

↓

Physical Buffer

↓

Public Tensor
```

The compiler is effectively acting as a memory allocator.

Whenever it decides to reuse storage across security domains, that decision should be justified by a security argument rather than accepted automatically.

This is the philosophical connection to systems like **Tornado** and **Corey**.

Those operating systems argued that sharing physical resources should be an explicit, policy-governed decision rather than an implicit optimization.

We adopt exactly that philosophy.

We are **not** implementing clustered objects, per-core kernels, or any OS resource-management mechanisms.

The connection is conceptual:

> **Sharing a physical resource between logically independent computations is acceptable only when the sharing can be justified.**

Here, the justification is a formal proof that buffer reuse cannot expose residual secret data.

---

# Relationship to timing side channels

This work does **not** eliminate cache timing attacks.

For example, it does not prevent

* Prime+Probe
* Flush+Reload
* cache contention
* GPU cache interference

Those arise from hardware resource contention rather than residual storage.

However, reducing unsafe storage reuse can indirectly reduce opportunities for certain side-channel attacks because fewer unrelated security domains share physical resources.

That should be viewed as a secondary benefit rather than the primary security claim.

The primary claim is **storage isolation**, not **timing-channel elimination**.

---

# Future directions

The current proposal is purely a **verification pass**.

It detects unsafe compiler decisions but does not modify them.

Future work could extend this into a security-aware bufferization strategy that automatically:

* allocates separate buffers,
* inserts explicit buffer clearing,
* inserts copies when reuse is unsafe, or
* re-runs allocation until the verification succeeds.

That would transform the verifier into a verification-guided optimization framework, but this is intentionally outside the scope of the current work.

---

# Summary

The key idea is to treat **buffer reuse as a security-sensitive resource-sharing decision**, not merely a memory optimization.

Instead of assuming that liveness alone justifies reuse, we require additional proof obligations:

1. **Property A:** Detect storage shared across different security domains.
2. **Property B:** Prove that any such reuse is safe because residual data cannot be observed before being overwritten.

By integrating these obligations into the existing solver-based verification pipeline, we can verify that compiler-generated memory reuse preserves storage isolation while reusing the same infrastructure for security labels, SMT solving, and counterexample generation. This keeps the work tightly scoped, technically defensible, and naturally aligned with the broader verification framework while introducing a practically relevant security property for MLIR bufferization.



