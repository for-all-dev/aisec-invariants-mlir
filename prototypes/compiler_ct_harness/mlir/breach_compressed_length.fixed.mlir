// case: BREACH compressed-length disclosure analogue
// classification: reduced-runtime-model
// c source: ../c/breach_compressed_length_fixed.c
// upstream GitHub source: https://github.com/nealharris/BREACH/tree/71a9fcbe261b50486be88664046c478956dac857
// upstream revision: 71a9fcbe261b50486be88664046c478956dac857
// secret: %secret_byte
// public: %public_guess, %encrypted_body, and fixed wire length
// expected verdict: pass for the modeled fixed-length transport
// exact incident boundary: L2 with compressor semantics; production mitigation remains an L4 obligation
module {
  llvm.func @breach_compressed_length_fixed(
      %secret_byte: i8,
      %public_guess: i8,
      %encrypted_body: i32,
      %public_wire_length: !llvm.ptr) -> i32 {
    %fixed_length = llvm.mlir.constant(32 : i32) : i32
    // CONFIDENTIALITY REPAIR: pad to one public transfer length
    // secret source: %secret_byte is deliberately absent from %fixed_length
    // safe effect: the attacker observes wire length 32 for every secret and guess
    // reason: the stored length is a public constant independent of compression gain
    // detection boundary: L2 relational size check passes for this modeled transport
    llvm.store %fixed_length, %public_wire_length : i32, !llvm.ptr
    llvm.return %encrypted_body : i32
  }
}
