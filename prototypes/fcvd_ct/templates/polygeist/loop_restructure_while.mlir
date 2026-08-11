// Polygeist `--loop-restructure` (pass at tools/cgeist/driver.cc:674, source
// lib/polygeist/Passes/LoopRestructure.cpp): natural loops found in the `cf` CFG are
// rebuilt as `scf.while`. Transcribed from the pass's own lit test,
// test/polygeist-opt/restructure.mlir:4-43 (@kernel_gemm): the back-edge loop
//
//     ^bb1(%i): %go = cmpi sle %i, %ub; cond_br %go, ^bb2, ^bb3
//     ^bb2: <body>; br ^bb1(%i + 1)
//
// becomes `scf.while` whose before-region re-computes the header, wraps the body in
// `scf.if %go`, and forwards the exit values through `scf.condition` (CHECK lines
// 24-40). The loop-carried result that is only defined on exit enters as
// `polygeist.undef`; it is never read (the before-region recomputes it each check), so
// it is transcribed as `arith.constant false` — an arbitrary constant in a dead slot.
//
// The body is a hole with one observation, so a body the rewrite ran under a different
// guard, on different values, or a different number of times would change the trace.
//
// Expected: CT-PRESERVING and EQUIVALENT, both bounded (the loop is unrolled). The
// falsifying twin is loop_restructure_dowhile.mlir — the same rewrite with the body
// hoisted ahead of the first check, which must break.
builtin.module {
  func.func @source(%ub: i64, %x: i32) -> i1 {
    %c0 = arith.constant 0 : i64
    %c1 = arith.constant 1 : i64
    cf.br ^bb1(%c0 : i64)
  ^bb1(%i: i64):
    %flag = arith.cmpi slt, %i, %c0 : i64
    %go = arith.cmpi sle, %i, %ub : i64
    cf.cond_br %go, ^bb2, ^bb3
  ^bb2:
    %seen = "fcvd.hole"(%x) {sym_name = "BODY", leaks = 1 : i64} : (i32) -> i32
    %next = arith.addi %i, %c1 : i64
    cf.br ^bb1(%next : i64)
  ^bb3:
    func.return %flag : i1
  }

  func.func @target(%ub: i64, %x: i32) -> i1 {
    %c0 = arith.constant 0 : i64
    %c1 = arith.constant 1 : i64
    %dead = arith.constant false
    %res:2 = scf.while (%i = %c0, %carried = %dead) : (i64, i1) -> (i64, i1) {
      %flag = arith.cmpi slt, %i, %c0 : i64
      %go = arith.cmpi sle, %i, %ub : i64
      %false = arith.constant false
      %step:3 = scf.if %go -> (i1, i64, i1) {
        %seen = "fcvd.hole"(%x) {sym_name = "BODY", leaks = 1 : i64} : (i32) -> i32
        %next = arith.addi %i, %c1 : i64
        %true = arith.constant true
        scf.yield %true, %next, %flag : i1, i64, i1
      } else {
        scf.yield %false, %i, %flag : i1, i64, i1
      }
      scf.condition(%step#0) %step#1, %step#2 : i64, i1
    } do {
    ^bb0(%i2: i64, %carried2: i1):
      scf.yield %i2, %carried2 : i64, i1
    }
    func.return %res#1 : i1
  }
}
