// RUN: %checkpoint-runner run --snapshot fixtures/clangover-poly-frommsg/source/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/clangover-poly-frommsg/source/clangover_poly_frommsg.source.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic source boundary; the separate lowered model records the compiler-introduced regression
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @clangover_poly_frommsg_source(
      %bit: i16 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    %mask = llvm.sub %zero, %bit {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["timing"]
    } : i16
    %coefficient = llvm.and %mask, %constant : i16
    llvm.return %coefficient : i16
  }
}
