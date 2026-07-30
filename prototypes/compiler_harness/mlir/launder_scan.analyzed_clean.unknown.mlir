// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// case: compiler-introduced/laundering-analyzed-clean
// classification: compiler-generated-minimized
// c source: ../c/launder_scan_bad.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/llvm/lib/Target/X86/X86CmovConversion.cpp
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret, declared by sps.label on the argument
// public: %fallback, the loaded word, and the sps.sink_class return
// expected outcome: unknown
// observer/model: target-control-flow-timing
// target tuple: x86_64-unknown-linux-gnu/generic/O2
// reason id: backend-may-reintroduce-branch
// outstanding obligations: backend-trace-preservation,target-tuple-binding
// evidence boundary: L1 confirms the IR is branchless; L3 is required to relate
// this module to emitted code, and the emitted code differs per target tuple.
//
// THE TRAP FIXTURE. This is the -O2 LLVM IR of a program that leaks.
//
// It is branchless. There is no llvm.cond_br, no secret-dependent control flow,
// and nothing an IR-level information-flow analysis would object to. Both
// ../c/launder_scan_bad.c (written with a ternary) and
// ../c/launder_scan_folded_bad.c (written with the standard arithmetic-mask
// constant-time idiom) compile to exactly this shape -- byte-identical IR --
// because InstCombine folds the mask back into a select.
//
// MEASURED with clang/llc 17.0.6 on this IR shape:
//
//   x86-64, -O2, DEFAULT flags:      testl %edi,%edi / je .LBB0_2 / movq (%rdx),%rax
//   x86-64, force-mem-operand=false: cmovneq (%rdx), %rax
//   aarch64, -O2:                    csel x0, x1, x8, eq
//
// So the same module is leaky on one target and safe on another, and the leak
// is invisible here. X86CmovConversion is enabled by default and its
// ForceMemOperand path rewrites every cmov with a memory operand with NO
// profitability check.
//
// SECOND-ORDER DAMAGE: after conversion the load is CONDITIONAL. The memory
// event trace becomes secret-dependent too, not only the timing. A model that
// reasons about branch direction alone misses half of it.
//
// WHY unknown AND NOT verified: nothing here is wrong, and that is the point.
// The honest verdict for an IR-level analysis on this module is a refusal naming
// what it cannot see, because the artifact that runs is not this one. Reporting
// verified would be correct about this module and wrong about the program.
//
// WHY unknown AND NOT unsafe: no replayable counterexample exists at this level.
// The leak is not in this artifact. Promoting a backend possibility to a
// counterexample would be unsound in the other direction.
//
// This is the only fixture in the corpus whose obligations can be discharged
// only by evidence from a LOWER level. It is the axis the corpus was missing.
//
// CHECK-LABEL: llvm.func @launder_scan_analyzed_clean
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK-NOT: llvm.cond_br
// CHECK: %[[V:[0-9]+]] = llvm.load
// CHECK: %[[C:[0-9]+]] = llvm.icmp "ne" %{{.*}}, %{{.*}} : i32
// CHECK: %[[R:[0-9]+]] = llvm.select %[[C]], %[[V]], %{{.*}}
// CHECK-NOT: llvm.cond_br
// CHECK: llvm.store %[[R]], %{{.*}} {sps.sink_class = "public"}
//
// The branchlessness must survive canonicalization, or the fixture stops being
// the analyzed-clean artifact it is modelling.
// STABLE-NOT: llvm.cond_br
// STABLE: llvm.select
module {
  llvm.func @launder_scan_analyzed_clean(
      %secret: i32 {sps.label = "high"},
      %fallback: i64 {sps.label = "public"},
      %buffer: !llvm.ptr {sps.label = "public"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %loaded = llvm.load %buffer : !llvm.ptr -> i64
    %taken = llvm.icmp "ne" %secret, %zero : i32
    // Branchless here. The x86 backend converts this to a conditional jump
    // because the select has a memory operand; aarch64 emits csel and does not.
    %blended = llvm.select %taken, %loaded, %fallback : i1, i64
    llvm.store %blended, %public_sink {sps.sink_class = "public"} : i64, !llvm.ptr
    llvm.return
  }
}
