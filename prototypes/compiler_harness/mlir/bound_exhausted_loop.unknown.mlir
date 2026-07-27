// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// case: metatheory/MT-CM2-bound-filtering
// classification: seeded-semantic-harness
// c source: ../c/bound_exhausted_loop.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/mlir/test/Dialect/LLVMIR/roundtrip.mlir
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret_count, which decides the backedge count
// public: the start value 0, the increment 1, and the public sink target
// expected outcome: unknown
// observer/model: operation-count-trace
// reason id: loop-remainder
// outstanding obligations: bound-adequacy
// evidence boundary: L1 reaches a modeled BoundExhausted transition on the
// backedge; no replayable bad execution is produced, so no L2 conclusion follows.
//
// Countermodel MT-CM2, which refutes the invalid principle "bounded-run
// filtering is a sound proof domain".
//
// FIRST SECRET-DEPENDENT TRIP COUNT IN THIS CORPUS. Two earlier fixtures already
// contain loops with loop-carried block arguments -- secret_embedding_index.fixed
// (a 16-iteration public-induction table scan) and wolfssl_3579_mul.target_fixed
// (a 64-iteration mask/add multiply) -- so backedge joins were already exercised.
// What was absent is a backedge whose ITERATION COUNT depends on a secret, and
// therefore any exercise of bound adequacy at all. The stored value here is a
// public constant: the channel is purely the number of executed operations.
//
// THE UNSOUND SHORTCUT THIS PINS: an implementation that DELETES the execution
// exceeding its unrolling guard silently narrows the proof domain and reports a
// safe result. Rev-4 leaves both secret values in Admitted; bound adequacy fails
// because the larger execution exceeds the guard, and the guarded expansion
// produces BoundExhausted instead of deleting the path. Execution-bound adequacy
// and universal definedness are deliberately NOT pair filters inside Admitted;
// they are universal proof obligations. Filtering an execution after it exhausts
// a bound, faults, fails, or risks undefined behavior is forbidden.
//
// WHY unknown RATHER THAN unsafe: a reachable, exactly modeled BoundExhausted
// transition that does not yield a replayed bad execution is Unknown with the
// bound-adequacy obligation open. Promoting it to a counterexample without a
// replayable witness is exactly what the spec forbids.
//
// REASON-CODE CONFLATION TO AVOID: loop-remainder denotes an exactly modeled
// reachable BoundExhausted transition. It must NEVER denote an insufficient
// engine cap, which is a separate resource-limit result. Collapsing the two into
// one identifier is the easiest wrong reduction here.
//
// CHECK-LABEL: llvm.func @bound_exhausted_loop
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK: llvm.br ^[[LOOP:bb[0-9]+]]
// CHECK: ^[[LOOP]](%[[I:[0-9]+]]: i32):
// CHECK: %[[CONT:[0-9]+]] = llvm.icmp "slt" %[[I]], %{{.*}} : i32
// CHECK: llvm.cond_br %[[CONT]], ^[[BODY:bb[0-9]+]], ^[[EXIT:bb[0-9]+]]
// CHECK: ^[[BODY]]:
// CHECK: llvm.br ^[[LOOP]]
// CHECK: ^[[EXIT]]:
// CHECK: llvm.store %{{.*}} {sps.sink_class = "public"}
//
// The backedge must survive: a fixture whose loop is unrolled or deleted stops
// testing bound adequacy entirely.
// STABLE: llvm.icmp "slt"
// STABLE: llvm.cond_br
module {
  llvm.func @bound_exhausted_loop(
      %secret_count: i32 {sps.label = "high"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %one = llvm.mlir.constant(1 : i32) : i32
    llvm.br ^loop(%zero : i32)
  ^loop(%i: i32):
    %continue = llvm.icmp "slt" %i, %secret_count : i32
    llvm.cond_br %continue, ^body, ^exit
  ^body:
    %next = llvm.add %i, %one : i32
    llvm.br ^loop(%next : i32)
  ^exit:
    llvm.store %zero, %public_sink {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
