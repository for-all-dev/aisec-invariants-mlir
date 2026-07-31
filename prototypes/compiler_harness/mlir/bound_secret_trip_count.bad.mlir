// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// case: metatheory/secret-dependent-loop-continuation
// entry: bound_secret_trip_count_bad
// classification: seeded-semantic-harness
// c source: ../c/bound_exhausted_loop.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/mlir/test/Dialect/LLVMIR/roundtrip.mlir
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret_count, which decides the first and subsequent loop branches
// public: the start value 0, increment 1, and public sink target
// diagnostic focus: world-structural-control-trace
// evidence boundary: L2 replays secret counts 0 and 1; the first conditional
// branch chooses exit in one lane and body in the other before any bound exhausts.
//
// This is deliberately separate from bound_exhausted_loop.unknown.mlir. A secret
// trip count is already a replayable structural counterexample; it cannot be
// relabeled Unknown merely because a later execution might exceed a proof bound.
//
// CHECK-LABEL: llvm.func @bound_secret_trip_count_bad
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK: ^[[LOOP:bb[0-9]+]](%[[I:[0-9]+]]: i32):
// CHECK: %[[CONT:[0-9]+]] = llvm.icmp "slt" %[[I]], %{{.*}} : i32
// CHECK: llvm.cond_br %[[CONT]], ^[[BODY:bb[0-9]+]], ^[[EXIT:bb[0-9]+]]
// STABLE: llvm.icmp "slt"
// STABLE: llvm.cond_br
module {
  llvm.func @bound_secret_trip_count_bad(
      %secret_count: i32 {sps.label = "high"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %one = llvm.mlir.constant(1 : i32) : i32
    llvm.br ^loop(%zero : i32)
  ^loop(%i: i32):
    %continue = llvm.icmp "slt" %i, %secret_count : i32
    // CONFIDENTIALITY ERROR: secret changes loop-continuation control
    // secret source: %secret_count differs between the two admitted lanes
    // observable effect: the first branch chooses body for count 1 and exit for count 0
    // reason: world-level control locations must remain in lockstep while active
    // detection boundary: exact L2 product and replay, before bound adequacy matters
    llvm.cond_br %continue, ^body, ^exit
  ^body:
    %next = llvm.add %i, %one : i32
    llvm.br ^loop(%next : i32)
  ^exit:
    llvm.store %zero, %public_sink {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
