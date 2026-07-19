// case: BREACH compressed-length disclosure analogue
// classification: reduced-runtime-model
// c source: ../c/breach_compressed_length_bad.c
// upstream GitHub source: https://github.com/nealharris/BREACH/tree/71a9fcbe261b50486be88664046c478956dac857
// upstream revision: 71a9fcbe261b50486be88664046c478956dac857
// secret: %secret_byte
// public: %public_guess, %encrypted_body, and wire length
// expected verdict: reject for the modeled compressor summary
// exact incident boundary: L2 with compressor semantics; real compressor behavior is an L4 summary obligation
module {
  llvm.func @breach_compressed_length_bad(
      %secret_byte: i8,
      %public_guess: i8,
      %encrypted_body: i32,
      %public_wire_length: !llvm.ptr) -> i32 {
    %base_length = llvm.mlir.constant(32 : i32) : i32
    %match = llvm.icmp "eq" %secret_byte, %public_guess : i8
    %compression_gain = llvm.zext %match : i1 to i32
    %wire_length = llvm.sub %base_length, %compression_gain : i32
    // CONFIDENTIALITY ERROR: secret-dependent compressed transfer length
    // secret source: %wire_length depends on whether %secret_byte equals the guess
    // observable effect: the attacker observes wire length 31 for a match and 32 otherwise
    // reason: equal application payloads produce different public sizes across secret runs
    // detection boundary: L2 relational check with a compressor summary; real compression is L4
    llvm.store %wire_length, %public_wire_length : i32, !llvm.ptr
    llvm.return %encrypted_body : i32
  }
}
