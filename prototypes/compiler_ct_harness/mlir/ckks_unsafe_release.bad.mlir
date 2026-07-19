// case: CKKS release before sanitization and validation
// classification: seeded-semantic-harness
// c source: ../c/ckks_unsafe_release_bad.c
// upstream GitHub source: https://github.com/microsoft/SEAL
// upstream revision: none -- this is a policy model, not a Microsoft SEAL defect
// secret: %raw_approximate_plaintext
// public: trusted-integrity sanitizer mask and certificate flag, plus the public-release stored value
// input invariant: %certificate_ok is a well-formed Boolean in {0, 1}
// private result: the function return is not in the public observer projection
// expected verdict: unsafe
// exact incident boundary: L1 public-sink flow; real CKKS semantics are outside this reduction
module {
  llvm.func @ckks_unsafe_release_bad(
      %raw_approximate_plaintext: i32,
      %public_sanitizer_mask: i32,
      %certificate_ok: i32,
      %public_release: !llvm.ptr) -> i32 {
    // CONFIDENTIALITY ERROR: raw approximate plaintext reaches the public release sink
    // secret source: %raw_approximate_plaintext is an unsanitized decryption result
    // observable effect: the public release sink receives the raw value
    // reason: no approved sanitizer result or certificate check dominates this store
    // detection boundary: direct L1 output-flow violation; no L4 fact can repair this path
    llvm.store %raw_approximate_plaintext, %public_release : i32, !llvm.ptr
    llvm.return %raw_approximate_plaintext : i32
  }
}
