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
// Swept over the width W of the induction variable and bound (issue #63): the pass
// restructures the CFG whatever type the header compares.
//
// Expected on every instance: CT-PRESERVING and EQUIVALENT, both bounded (the loop
// is unrolled). The falsifying twin is loop_restructure_dowhile.mlir — the same
// rewrite with the body hoisted ahead of the first check, which must break.
// fcvdct.sweep W = i8, i16, i32, i64
builtin.module {
  func.func @source(%ub: ${W}, %x: i32) -> i1 {
    %c0 = arith.constant 0 : ${W}
    %c1 = arith.constant 1 : ${W}
    cf.br ^bb1(%c0 : ${W})
  ^bb1(%i: ${W}):
    %flag = arith.cmpi slt, %i, %c0 : ${W}
    %go = arith.cmpi sle, %i, %ub : ${W}
    cf.cond_br %go, ^bb2, ^bb3
  ^bb2:
    %seen = "fcvd.hole"(%x) {sym_name = "BODY", leaks = 1 : i64} : (i32) -> i32
    %next = arith.addi %i, %c1 : ${W}
    cf.br ^bb1(%next : ${W})
  ^bb3:
    func.return %flag : i1
  }

  func.func @target(%ub: ${W}, %x: i32) -> i1 {
    %c0 = arith.constant 0 : ${W}
    %c1 = arith.constant 1 : ${W}
    %dead = arith.constant false
    %res:2 = scf.while (%i = %c0, %carried = %dead) : (${W}, i1) -> (${W}, i1) {
      %flag = arith.cmpi slt, %i, %c0 : ${W}
      %go = arith.cmpi sle, %i, %ub : ${W}
      %false = arith.constant false
      %step:3 = scf.if %go -> (i1, ${W}, i1) {
        %seen = "fcvd.hole"(%x) {sym_name = "BODY", leaks = 1 : i64} : (i32) -> i32
        %next = arith.addi %i, %c1 : ${W}
        %true = arith.constant true
        scf.yield %true, %next, %flag : i1, ${W}, i1
      } else {
        scf.yield %false, %i, %flag : i1, ${W}, i1
      }
      scf.condition(%step#0) %step#1, %step#2 : ${W}, i1
    } do {
    ^bb0(%i2: ${W}, %carried2: i1):
      scf.yield %i2, %carried2 : ${W}, i1
    }
    func.return %res#1 : i1
  }
}
