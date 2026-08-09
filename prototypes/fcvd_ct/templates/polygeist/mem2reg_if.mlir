// Polygeist `--polygeist-mem2reg` (pass at tools/cgeist/driver.cc:663, source
// lib/polygeist/Passes/PolygeistMem2Reg.cpp, `forwardStoreToLoad` at :1075):
// stores to a local alloca are forwarded to its loads, the alloca disappears, and
// values that were routed through memory travel as SSA values yielded out of `scf.if`.
//
// Transcribed from the pass's lit test test/polygeist-opt/mem2regIf2.mlir:4-39
// (@_Z26__device_stub__hotspotOpt1...), with two declared deviations:
//   - f32 -> i8 (floats have no SMT semantics upstream, and upstream's memref
//     model stores bytes only; the pass keys on the
//     load/store structure, not the element type — `forwardStoreToLoad` reads
//     `elType` only to build the forwarded value's type);
//   - `llvm.mlir.undef` -> a named constant %u (no undef semantics; a constant is
//     the *stronger* check, since the forwarding must now route a distinguishable
//     value, not an arbitrary one), and rank-0 memref<f32> -> memref<1xi8>[%c0]
//     (rank-0 loads carry no index operand; the 1-element form is what
//     mem2regaff.mlir:5-9 exercises and gives the address channel something to say).
//
// Leakage-wise the step REMOVES observations: every store/load address of the two
// allocas is observed in the source, and none survive in the target. The interesting
// half is equivalence — the forwarding must pick, per path, the same store the memory
// would have supplied. The falsifying twin is mem2reg_if_stale.mlir.
//
// Expected: CT-PRESERVING (target observations a strict subset) and EQUIVALENT.
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

  // CHECK block of mem2regIf2.mlir:26-39: the first if yields (m0, m2) as a pair, the
  // second selects between them, no memory operation survives.
  func.func @target(%arg0: i8, %arg1: i1, %arg2: i1, %arg3: i8) -> i8 {
    %u = arith.constant 11 : i8
    %v:2 = scf.if %arg1 -> (i8, i8) {
      scf.yield %arg0, %u : i8, i8
    } else {
      scf.yield %u, %arg3 : i8, i8
    }
    %out = scf.if %arg2 -> (i8) {
      scf.yield %v#0 : i8
    } else {
      scf.yield %v#1 : i8
    }
    func.return %out : i8
  }
}
