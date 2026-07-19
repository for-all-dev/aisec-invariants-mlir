// case: BREACH compressed-length disclosure analogue
// classification: reduced-runtime-model
// c source: ../c/breach_compressed_length_bad.c
// upstream GitHub source: https://github.com/nealharris/BREACH/tree/71a9fcbe261b50486be88664046c478956dac857
// upstream revision: 71a9fcbe261b50486be88664046c478956dac857
// secret: %secret_byte
// public: %public_guess, %encrypted_body, and wire length
// expected verdict: unsafe for the reduced public-wire-length-output model
// exact incident boundary: L1 direct output-memory flow; L2 witnesses lengths 31 and 32
// L4 extrapolation: the match-to-length relation is already inlined; no compressor is encoded
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
    // observable effect: the public output is length 31 for a match and 32 otherwise
    // reason: with the same public guess, two secret bytes can produce unequal stored lengths
    // detection boundary: L1 tracks the secret-derived store; L2 supplies the 31/32 witness
    llvm.store %wire_length, %public_wire_length : i32, !llvm.ptr
    llvm.return %encrypted_body : i32
  }
}
