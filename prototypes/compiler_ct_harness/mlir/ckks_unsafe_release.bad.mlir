// case: CKKS release before sanitization and validation
// classification: seeded-semantic-harness
// c source: ../c/ckks_unsafe_release_bad.c
// upstream GitHub source: https://github.com/microsoft/SEAL
// upstream revision: none -- this is a policy model, not a Microsoft SEAL defect
// secret: %raw_approximate_plaintext
// public: certified value, certificate flag, and public release address
// expected verdict: reject
// exact incident boundary: L1 ordering/policy; real noise sufficiency is an L4 obligation
module {
  llvm.func @ckks_unsafe_release_bad(
      %raw_approximate_plaintext: i32,
      %certified_public_value: i32,
      %certificate_ok: i32,
      %public_release: !llvm.ptr) -> i32 {
    // CONFIDENTIALITY ERROR: raw approximate plaintext released without validation
    // secret source: %raw_approximate_plaintext is an unsanitized decryption result
    // observable effect: the public release sink receives the raw value
    // reason: no approved sanitizer or certificate dominates this release
    // detection boundary: L1 structural ordering check; L4 must justify a real sanitizer
    llvm.store %raw_approximate_plaintext, %public_release : i32, !llvm.ptr
    llvm.return %raw_approximate_plaintext : i32
  }
}
