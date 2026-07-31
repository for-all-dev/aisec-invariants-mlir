// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// case: compiler-introduced/laundering-analyzed-clean
// entry: launder_scan_model_proved
// classification: compiler-generated-minimized
// c source: ../c/launder_scan_bad.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/llvm/lib/Target/X86/X86CmovConversion.cpp
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret, declared by sps.label on the argument
// public: %fallback, the buffer address/content, and world-level LLVM structure
// diagnostic focus: llvm-world-structural-trace
// evidence target tuple: x86_64-unknown-linux-gnu/generic/O2
// evidence boundary: L2 sees one unconditional load, one select,
// and an owner-private output; DeploymentStatus remains Open for target-bound
// backend-control-delta and paired P4 evidence.
//
// THE TRAP FIXTURE. This is the -O2 LLVM IR of a program that leaks.
//
// It is branchless. There is no llvm.cond_br, no secret-dependent control flow,
// and its differing selected value reaches only an authorized private output. Both
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
// STATUS SPLIT: under the LLVM model this fixture is eligible for ModelStatus
// Proved once the ordinary artifact/policy/product premises close. The observed
// x86 branch does not change that model result; it keeps DeploymentStatus Open.
// Promoting backend risk to ModelStatus Unknown or Counterexample would conflate
// the ideal artifact theorem with paired concrete-to-ideal refinement.
//
// CHECK-LABEL: llvm.func @launder_scan_model_proved
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK-NOT: llvm.cond_br
// CHECK: %[[V:[0-9]+]] = llvm.load
// CHECK: %[[C:[0-9]+]] = llvm.icmp "ne" %{{.*}}, %{{.*}} : i32
// CHECK: %[[R:[0-9]+]] = llvm.select %[[C]], %[[V]], %{{.*}}
// CHECK-NOT: llvm.cond_br
// CHECK: llvm.store %[[R]], %{{.*}} {sps.audience = ["owner"], sps.sink_class = "private"
//
// The branchlessness must survive canonicalization, or the fixture stops being
// the analyzed-clean artifact it is modelling.
// STABLE-NOT: llvm.cond_br
// STABLE: llvm.select
module {
  llvm.func @launder_scan_model_proved(
      %secret: i32 {sps.label = "high"},
      %fallback: i64 {sps.label = "public"},
      %buffer: !llvm.ptr {sps.label = "public"},
      %owner_private_sink: !llvm.ptr {sps.sink_class = "private", sps.audience = ["owner"]}) {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %loaded = llvm.load %buffer : !llvm.ptr -> i64
    %taken = llvm.icmp "ne" %secret, %zero : i32
    // Branchless here. The x86 backend converts this to a conditional jump
    // because the select has a memory operand; aarch64 emits csel and does not.
    %blended = llvm.select %taken, %loaded, %fallback : i1, i64
    llvm.store %blended, %owner_private_sink
        {sps.sink_class = "private", sps.audience = ["owner"]} : i64, !llvm.ptr
    llvm.return
  }
}
