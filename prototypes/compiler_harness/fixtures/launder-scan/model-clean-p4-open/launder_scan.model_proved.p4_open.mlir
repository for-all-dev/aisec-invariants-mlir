// RUN: %checkpoint-runner run --snapshot fixtures/launder-scan/model-clean-p4-open/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/launder-scan/model-clean-p4-open/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner check-existing --snapshot fixtures/launder-scan/model-clean-p4-open/snapshot.yaml --pipeline candidate-bitcode --endpoint fixtures/launder-scan/model-clean-p4-open/candidate/artifact.bc --records %t.checkpoints
// RUN: %checkpoint-runner finalize --test fixtures/launder-scan/model-clean-p4-open/launder_scan.model_proved.p4_open.mlir --records %t.checkpoints

//
// candidate target tuple: x86_64-unknown-linux-gnu/generic/O2
// scope note: this source shape contains one unconditional load and one select;
// target-bound backend control is intentionally outside the MLIR seed.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// THE TRAP FIXTURE. This is the -O2 LLVM IR of a program that leaks.
//
// It is branchless. There is no llvm.cond_br, no secret-dependent control flow,
// and its differing selected value reaches only an authorized private output. Both
// launder_scan_bad.c (written with a ternary) and the paired case-local
// ../folded-mask-p4-open/launder_scan_folded_bad.c (written with the standard arithmetic-mask
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
// CLAIM BOUNDARY: despite its compatibility filename, this is a CandidateOnly
// shape and computes no ModelStatus or DeploymentStatus. A future conformance
// run must independently bind frozen bitcode, run the exact product, and assess
// paired final-machine observation refinement.
//
//
// The branchlessness must survive canonicalization, or the fixture stops being
// the analyzed-clean artifact it is modelling.
module {
  llvm.func @launder_scan_model_proved(
      %secret: i32 {sps.component_ref = "secret", sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %fallback: i64 {sps.component_ref = "fallback", sps.label = "public"},
      %buffer: !llvm.ptr {sps.abi_root_ref = "buffer", sps.label = "public"},
      %owner_private_sink: !llvm.ptr {sps.abi_root_ref = "owner-private-sink", sps.output_ref = "owner-private-result", sps.sink_class = "private"}) {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %loaded = llvm.load %buffer : !llvm.ptr -> i64
    %taken = llvm.icmp "ne" %secret, %zero : i32
    // Branchless here. The x86 backend converts this to a conditional jump
    // because the select has a memory operand; aarch64 emits csel and does not.
    %blended = llvm.select %taken, %loaded, %fallback
        {sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]", "snapshot.public[2]"],
         sps.observable_candidate = ["control", "address", "timing"]} : i1, i64
    llvm.store %blended, %owner_private_sink
        {sps.output_ref = "owner-private-result", sps.sink_class = "private"} : i64, !llvm.ptr
    llvm.return
  }
}
