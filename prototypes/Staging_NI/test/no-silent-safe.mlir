// RUN: %staging-ni-opt --verify-staging-ni --verify-diagnostics --split-input-file %s

// Every case here was SILENT before -- no violation and no UNKNOWN -- i.e.
// reported as safe by omission. They are the same leak the suite already
// covers (a protected value reaching a loop bound), reachable through a
// construct the analysis did not model. Silent-safe is the failure mode
// this checker exists to avoid, so each one is pinned.

// 1. Memory round-trip. Store the secret into a buffer, read it back, use
// it as a bound. Taint was lost at the store (a store has no results, so
// generic propagation never saw it) and the leak downstream read clean.

func.func @taint_survives_memory(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  %slot = memref.alloc() : memref<1xindex>
  memref.store %dim, %slot[%c0] : memref<1xindex>
  %back = memref.load %slot[%c0] : memref<1xindex>
  // expected-error @+1 {{loop upper bound depends on protected runtime data}}
  scf.for %i = %c0 to %back step %c1 {
  }
  return
}

// -----

// 2. An operation that was not on the old arith whitelist. arith.shli is
// ordinary integer arithmetic, but it was not enumerated, so staging taint
// silently died at it -- as it did for every op in every dialect the list
// did not name.

func.func @taint_survives_unlisted_op(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  %i = arith.index_cast %dim : index to i64
  %sh = arith.shli %i, %i : i64
  %b = arith.index_cast %sh : i64 to index
  // expected-error @+1 {{loop upper bound depends on protected runtime data}}
  scf.for %x = %c0 to %b step %c1 {
  }
  return
}

// -----

// 3. A call boundary. Interprocedural flow is not modeled, so the callee
// could do anything with the secret; previously the call simply returned a
// clean value and laundered it.

func.func private @helper(%x: index) -> index

func.func @call_boundary_is_unknown(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  // expected-remark @+1 {{crosses a call boundary}}
  %r = func.call @helper(%dim) : (index) -> index
  return
}

// -----

// 4. A second SSA handle onto a tainted buffer. The memory model is
// per-SSA-value, so aliasing defeats it; report UNKNOWN rather than assume
// either way.

func.func @aliasing_is_unknown(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  %slot = memref.alloc() : memref<1xindex>
  memref.store %dim, %slot[%c0] : memref<1xindex>
  // expected-remark @+1 {{second handle onto a tainted buffer}}
  %alias = memref.cast %slot : memref<1xindex> to memref<?xindex>
  return
}
