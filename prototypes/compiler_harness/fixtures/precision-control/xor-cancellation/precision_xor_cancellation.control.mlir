// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/xor-cancellation/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/xor-cancellation/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner finalize --test fixtures/precision-control/xor-cancellation/precision_xor_cancellation.control.mlir --records %t.checkpoints

//
// scope note: the unary scanner flags a relational review site because its
// taint abstraction cannot see value congruence; the exact product decides it.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// This is a NEGATIVE CONTROL. The stored value is secret-DEPENDENT by
// dependence and secret-INDEPENDENT by value: both lanes store zero. A forward
// unary taint abstraction necessarily flags the value here, which is exactly
// the imprecision this fixture pins.
//
// A more precise preflight may add a non-authoritative value-congruence aid;
// it must not weaken the eventual coalition-indexed product. Measured with mlir-opt
// 17.0.6: --canonicalize does NOT fold llvm.xor %a, %a, so the tool will not
// discharge this on the harness's behalf and the control stays meaningful.
//
//
module {
  llvm.func @xor_cancellation_control(
      %secret: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %public_sink: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}) {
    %cancelled = llvm.xor %secret, %secret : i32
    llvm.store %cancelled, %public_sink
        {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
