// The falsifying twin of mem2reg_if.mlir: the forwarding picks the WRONG store — the
// second if forwards the pre-if value of m0 (the %u initializer) instead of the value
// the first if left there. A stale-value bug adds no observation, so the leakage half
// must PASS it; the equivalence half is the one that must refuse. This is the same
// division of labour the canonicalize-for iteration recorded on 2026-07-29, now with
// the equivalence gate present to actually catch it.
//
// Expected: CT-PRESERVING (nothing new is observed) and NOT-EQUIVALENT (on
// %arg1 = true, %arg2 = true the source returns %arg0, this target returns %u).
builtin.module attributes {fcvdct.values_only} {
  func.func @source(%arg0: i8, %arg1: i1, %arg2: i1, %arg3: i8) -> i8 {
    %c0 = arith.constant 0 : index
    %u = arith.constant 11 : i8
    %m0 = "memref.alloca"() <{operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<1xi8>
    memref.store %u, %m0[%c0] : memref<1xi8>
    %m2 = "memref.alloca"() <{operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<1xi8>
    memref.store %arg3, %m2[%c0] : memref<1xi8>
    %r1 = scf.if %arg1 -> (i8) {
      memref.store %u, %m2[%c0] : memref<1xi8>
      memref.store %arg0, %m0[%c0] : memref<1xi8>
      scf.yield %arg0 : i8
    } else {
      scf.yield %u : i8
    }
    scf.if %arg2 {
      %dead = memref.load %m0[%c0] : memref<1xi8>
      memref.store %r1, %m2[%c0] : memref<1xi8>
    }
    %out = memref.load %m2[%c0] : memref<1xi8>
    func.return %out : i8
  }

  func.func @target(%arg0: i8, %arg1: i1, %arg2: i1, %arg3: i8) -> i8 {
    %u = arith.constant 11 : i8
    %v:2 = scf.if %arg1 -> (i8, i8) {
      scf.yield %arg0, %u : i8, i8
    } else {
      scf.yield %u, %arg3 : i8, i8
    }
    %out = scf.if %arg2 -> (i8) {
      scf.yield %u : i8
    } else {
      scf.yield %v#1 : i8
    }
    func.return %out : i8
  }
}
