// RUN: %checkpoint-runner run --snapshot fixtures/breach-compressed-length/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/breach-compressed-length/bad/breach_compressed_length.bad.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic direct output-memory flow; exact product witnesses lengths 31 and 32
// scope limit: the match-to-length relation is already inlined; no compressor is encoded
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @breach_compressed_length_bad(
      %secret_byte: i8 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %public_guess: i8,
      %encrypted_body: i32,
      %public_wire_length: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}) -> i32 {
    %base_length = llvm.mlir.constant(32 : i32) : i32
    %match = llvm.icmp "eq" %secret_byte, %public_guess : i8
    %compression_gain = llvm.zext %match : i1 to i32
    %wire_length = llvm.sub %base_length, %compression_gain : i32
    // PREFLIGHT FINDING: secret-dependent compressed transfer length
    // secret source: %wire_length depends on whether %secret_byte equals the guess
    // observable effect: the public output is length 31 for a match and 32 otherwise
    // reason: with the same public guess, two secret bytes can produce unequal stored lengths
    // preflight expectation: unary scanner flags the candidate-secret-derived public-length store
    llvm.store %wire_length, %public_wire_length {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return %encrypted_body : i32
  }
}
