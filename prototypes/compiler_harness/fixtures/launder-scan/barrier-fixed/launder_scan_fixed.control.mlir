// RUN: %checkpoint-runner run --snapshot fixtures/launder-scan/barrier-fixed/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/launder-scan/barrier-fixed/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner finalize --test fixtures/launder-scan/barrier-fixed/launder_scan_fixed.control.mlir --records %t.checkpoints

//
// C evidence: launder_scan_fixed.c
// modeled boundary: optimized LLVM before instruction selection
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// LLVM 17's LLVM-to-MLIR importer rejects the inline-asm value barrier, so this
// is a hand-authored transcription of the emitted LLVM shape. The integration
// test separately compiles the C source and checks that the mask remains
// arithmetic, while the P4 test checks that x86 emits no conditional jump.
//
// This is a preflight control only. Inline-asm opacity remains a compiler
// convention and this fixture does not claim SPS normal-form conformance.
//
//
module {
  llvm.func @launder_scan_fixed(
      %secret: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %fallback: i64 {sps.label = "public"},
      %buffer: !llvm.ptr {sps.abi_root_ref = "buffer", sps.label = "public"},
      %owner_private_sink: !llvm.ptr {sps.abi_root_ref = "owner-private-sink", sps.output_ref = "owner-private-result", sps.sink_class = "private"}) {
    %loaded = llvm.load %buffer : !llvm.ptr -> i64
    %zero = llvm.mlir.constant(0 : i32) : i32
    %nonzero = llvm.icmp "ne" %secret, %zero : i32
    %mask = llvm.sext %nonzero : i1 to i64
    %opaque_mask = llvm.inline_asm has_side_effects "", "=r,0,~{dirflag},~{fpsr},~{flags}" %mask : (i64) -> i64
    %taken = llvm.and %opaque_mask, %loaded : i64
    %all_ones = llvm.mlir.constant(-1 : i64) : i64
    %inverse = llvm.xor %opaque_mask, %all_ones : i64
    %fallback_part = llvm.and %fallback, %inverse : i64
    %blended = llvm.or %taken, %fallback_part {
      sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]", "snapshot.public[2]"],
      sps.observable_candidate = ["control", "address", "timing"]
    } : i64
    llvm.store %blended, %owner_private_sink {
      sps.output_ref = "owner-private-result",
      sps.sink_class = "private"
    } : i64, !llvm.ptr
    llvm.return
  }
}
