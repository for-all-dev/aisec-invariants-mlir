// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// scope note: with the configuration binding public bound set below public_count, both
// exact product lanes reach the same modeled BoundExhausted transition; bound adequacy stays
// open and no replayable bad execution is produced.
//
// Countermodel MT-CM2, which refutes the invalid principle "bounded-run
// filtering is a sound proof domain".
//
// The paired `bound_secret_trip_count.bad.mlir` covers the immediate structural
// counterexample. This fixture isolates the different question: two low-equal
// lanes follow the same public loop, but the configured proof bound is too small.
//
// THE UNSOUND SHORTCUT THIS PINS: an implementation that DELETES the execution
// exceeding its unrolling guard silently narrows the proof domain and reports a
// safe result. Rev-4 leaves the admitted execution in scope; bound adequacy fails
// because the public execution exceeds the guard, and the guarded expansion
// produces BoundExhausted instead of deleting the path. Execution-bound adequacy
// and universal definedness are deliberately NOT pair filters inside Admitted;
// they are universal proof obligations. Filtering an execution after it exhausts
// a bound, faults, fails, or risks undefined behavior is forbidden.
//
// WHY Unknown RATHER THAN Counterexample: a reachable, exactly modeled BoundExhausted
// transition that does not yield a replayed bad execution is Unknown with the
// bound-adequacy obligation open. Promoting it to a counterexample without a
// replayable witness is exactly what the spec forbids.
//
// REASON-CODE CONFLATION TO AVOID: loop-remainder denotes an exactly modeled
// reachable BoundExhausted transition. It must NEVER denote an insufficient
// engine cap, which is a separate resource-limit result. Collapsing the two into
// one identifier is the easiest wrong reduction here.
//
// CHECK-LABEL: llvm.func @bound_exhausted_public_loop
// CHECK-SAME: {{.*}}sps.label = "public"
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
  llvm.func @bound_exhausted_public_loop(
      %public_count: i32 {sps.label = "public", sps.bound_candidate = "public_trip_count_v1"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %one = llvm.mlir.constant(1 : i32) : i32
    llvm.br ^loop(%zero : i32)
  ^loop(%i: i32):
    %continue = llvm.icmp "slt" %i, %public_count : i32
    llvm.cond_br %continue, ^body, ^exit
  ^body:
    %next = llvm.add %i, %one : i32
    llvm.br ^loop(%next : i32)
  ^exit:
    llvm.store %zero, %public_sink {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
