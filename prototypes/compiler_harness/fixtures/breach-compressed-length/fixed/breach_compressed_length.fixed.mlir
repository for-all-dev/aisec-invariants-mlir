// RUN: %checkpoint-runner run --snapshot fixtures/breach-compressed-length/fixed/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/breach-compressed-length/fixed/breach_compressed_length.fixed.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic output-memory flow; exact product observes equal length 32 in both runs
// scope limit: no compressor, padding, or transport event is encoded here
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @breach_compressed_length_fixed(
      %secret_byte: i8 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %public_guess: i8,
      %encrypted_body: i32,
      %public_wire_length: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}) -> i32 {
    %fixed_length = llvm.mlir.constant(32 : i32) : i32
    // PREFLIGHT CONTROL: write one public length in the reduced model
    // secret source: %secret_byte is deliberately absent from %fixed_length
    // safe effect: the attacker observes wire length 32 for every secret and guess
    // reason: the stored length is a public constant independent of compression gain
    // preflight expectation: unary scanner sees only the fixed public-length store
    llvm.store %fixed_length, %public_wire_length {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return %encrypted_body : i32
  }
}
