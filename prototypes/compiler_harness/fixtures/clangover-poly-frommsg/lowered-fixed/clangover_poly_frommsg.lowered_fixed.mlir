// RUN: %checkpoint-runner run --snapshot fixtures/clangover-poly-frommsg/lowered-fixed/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/clangover-poly-frommsg/lowered-fixed/clangover_poly_frommsg.lowered_fixed.mlir --records %t.checkpoints

//
// scope note: preflight checks the in-module helper shape; separately bound
// backend evidence is required for deployment refinement
// artifact status: hand-written target model; the helper body is included in the verified region
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @clangover_ct_cmov_model(%if_zero: i16, %if_one: i16, %bit: i16) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %all_ones = llvm.mlir.constant(-1 : i16) : i16
    // PREFLIGHT CONTROL: mask-based conditional move
    // secret source: %bit is used only to construct a full-word mask
    // safe effect: control flow and memory addresses are independent of %bit
    // reason: both values are combined through dataflow rather than successor selection
    // preflight expectation: unary scanner sees no candidate-secret branch in the modeled helper
    %mask = llvm.sub %zero, %bit {
      sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]"],
      sps.observable_candidate = ["control", "timing"]
    } : i16
    %not_mask = llvm.xor %mask, %all_ones : i16
    %left = llvm.and %if_zero, %not_mask : i16
    %right = llvm.and %if_one, %mask : i16
    %selected = llvm.or %left, %right : i16
    llvm.return %selected : i16
  }

  llvm.func @clangover_poly_frommsg_fixed(
      %out: !llvm.ptr {sps.abi_root_ref = "out", sps.output_ref = "out"},
      %msg: !llvm.ptr {
        sps.abi_root_ref = "msg",
        sps.fixture_refs = ["snapshot.secret[0]"],
        sps.label = "high"}) {
    %message_byte = llvm.load %msg : !llvm.ptr -> i8
    %one8 = llvm.mlir.constant(1 : i8) : i8
    %bit8 = llvm.and %message_byte, %one8 : i8
    %bit16 = llvm.zext %bit8 : i8 to i16
    %zero16 = llvm.mlir.constant(0 : i16) : i16
    %constant16 = llvm.mlir.constant(1665 : i16) : i16
    %coefficient = llvm.call @clangover_ct_cmov_model(%zero16, %constant16, %bit16) : (i16, i16, i16) -> i16
    llvm.store %coefficient, %out : i16, !llvm.ptr
    llvm.return
  }
}
