// RUN: %checkpoint-runner run --snapshot fixtures/alloca-size/fixed-region-copy-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner check-existing --snapshot fixtures/alloca-size/fixed-region-copy-bad/snapshot.yaml --pipeline candidate-bitcode --endpoint fixtures/alloca-size/fixed-region-copy-bad/candidate/artifact.bc --records %t.checkpoints
// RUN: %checkpoint-runner finalize --test fixtures/alloca-size/fixed-region-copy-bad/alloca_size_fixed_region_copy.bad.mlir --records %t.checkpoints

// Both product lanes allocate exactly eight bytes, so WorldStructuralAlloca is
// available. The two internal offsets are not independently visible regions:
// they retain secret-derived state until the final store crosses the declared
// public-output boundary.
//
// Concrete fixture pair:
//   left.secret  = 0x00000000 -> public-out[0] = 0x00
//   right.secret = 0x00000001 -> public-out[0] = 0x01
//
// The sidecars and snapshot are authoritative. The sps.* attributes below are
// discardable review locators and unary preflight hints.
module {
  llvm.func @alloca_size_fixed_region_copy_bad(
      %secret: i32 {
        sps.component_ref = "secret",
        sps.fixture_refs = ["secret:secret"],
        sps.label = "high"},
      %public_out: !llvm.ptr {
        sps.abi_root_ref = "public-out",
        sps.fixture_refs = ["public-memory:public_out"],
        sps.output_ref = "public-out",
        sps.sink_class = "public"}) {
    %count = llvm.mlir.constant(8 : i32) : i32
    %private_offset = llvm.mlir.constant(0 : i32) : i32
    %staging_offset = llvm.mlir.constant(4 : i32) : i32
    %secret_byte = llvm.trunc %secret : i32 to i8
    %scratch = llvm.alloca %count x i8 {
      sps.fixture_refs = ["observable:allocation-size"],
      sps.observable_candidate = ["allocation-size"]
    } : (i32) -> !llvm.ptr
    %private_slot = llvm.getelementptr %scratch[%private_offset]
      : (!llvm.ptr, i32) -> !llvm.ptr, i8
    %staging_slot = llvm.getelementptr %scratch[%staging_offset]
      : (!llvm.ptr, i32) -> !llvm.ptr, i8
    llvm.store %secret_byte, %private_slot {sps.label = "high"} : i8, !llvm.ptr
    %from_private = llvm.load %private_slot : !llvm.ptr -> i8
    llvm.store %from_private, %staging_slot {sps.label = "high"} : i8, !llvm.ptr
    %from_staging = llvm.load %staging_slot : !llvm.ptr -> i8
    // PREFLIGHT FINDING: a secret-derived byte crosses the public output boundary
    // secret source: %secret_byte is stored at scratch offset 0
    // observable effect: public-out receives the byte copied through scratch offset 4
    // reason: secret values 0 and 1 produce unequal terminal public output bytes
    // preflight expectation: preserve the fixed-allocation store/load/output shape for exact replay
    llvm.store %from_staging, %public_out {
      sps.fixture_refs = ["store:staging-to-public-out"],
      sps.output_ref = "public-out",
      sps.sink_class = "public"
    } : i8, !llvm.ptr
    llvm.return
  }
}
