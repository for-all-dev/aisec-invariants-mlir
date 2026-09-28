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
//     value, not an arbitrary one), and rank-0 memref<f32> -> memref<Nxi8>[%cK]
//     (rank-0 loads carry no index operand; the 1-element form is what
//     mem2regaff.mlir:5-9 exercises and gives the address channel something to say).
//
// Leakage-wise the step REMOVES observations: every store/load address of the two
// allocas is observed in the source, and none survive in the target. The interesting
// half is equivalence — the forwarding must pick, per path, the same store the memory
// would have supplied. The falsifying twin is mem2reg_if_stale.mlir.
//
// Generalised (issue #63: the transcription was one closed program pair, no hole):
//   - the values routed through memory are holes -- THEN computes what the first arm
//     stores into both allocas, SECOND what the second arm stores -- so the check holds
//     for whatever those arms compute, and the forwarding has to route the right
//     hole output to the right use rather than one of two known constants;
//   - SWEPT: the allocas' extent N and the cell K they are accessed at (the pass keys
//     on "same alloca, same indices", not on a 1-element buffer at index 0), and the
//     value U standing for `llvm.mlir.undef`.
//
// Expected on every instance: CT-PRESERVING (target observations a strict subset) and
// EQUIVALENT.
// fcvdct.sweep N = 1, 2, 4
// fcvdct.sweep K = 0, N - 1
// fcvdct.sweep U = 0, 11
builtin.module attributes {fcvdct.values_only} {
  func.func @source(%arg0: i8, %arg1: i1, %arg2: i1, %arg3: i8) -> i8 {
    %ck = arith.constant ${K} : index
    %u = arith.constant ${U} : i8
    %m0 = memref.alloca() : memref<${N}xi8>
    memref.store %u, %m0[%ck] : memref<${N}xi8>
    %m2 = memref.alloca() : memref<${N}xi8>
    memref.store %arg3, %m2[%ck] : memref<${N}xi8>
    %r1 = scf.if %arg1 -> (i8) {
      %t:2 = "fcvd.hole"(%arg0, %arg3) {sym_name = "THEN", leaks = 1 : i64} : (i8, i8) -> (i8, i8)
      memref.store %t#1, %m2[%ck] : memref<${N}xi8>
      memref.store %t#0, %m0[%ck] : memref<${N}xi8>
      scf.yield %t#0 : i8
    } else {
      scf.yield %u : i8
    }
    scf.if %arg2 {
      %dead = memref.load %m0[%ck] : memref<${N}xi8>
      %s = "fcvd.hole"(%r1) {sym_name = "SECOND", leaks = 1 : i64} : (i8) -> i8
      memref.store %s, %m2[%ck] : memref<${N}xi8>
    }
    %out = memref.load %m2[%ck] : memref<${N}xi8>
    func.return %out : i8
  }

  // CHECK block of mem2regIf2.mlir:26-39: the first if yields (m0, m2) as a pair, the
  // second selects between them, no memory operation survives.
  func.func @target(%arg0: i8, %arg1: i1, %arg2: i1, %arg3: i8) -> i8 {
    %u = arith.constant ${U} : i8
    %v:2 = scf.if %arg1 -> (i8, i8) {
      %t:2 = "fcvd.hole"(%arg0, %arg3) {sym_name = "THEN", leaks = 1 : i64} : (i8, i8) -> (i8, i8)
      scf.yield %t#0, %t#1 : i8, i8
    } else {
      scf.yield %u, %arg3 : i8, i8
    }
    %out = scf.if %arg2 -> (i8) {
      %s = "fcvd.hole"(%v#0) {sym_name = "SECOND", leaks = 1 : i64} : (i8) -> i8
      scf.yield %s : i8
    } else {
      scf.yield %v#1 : i8
    }
    func.return %out : i8
  }
}
