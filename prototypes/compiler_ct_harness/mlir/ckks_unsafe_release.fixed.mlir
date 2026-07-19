// case: CKKS release after modeled sanitization and validation
// classification: seeded-semantic-harness
// c source: ../c/ckks_unsafe_release_fixed.c
// upstream GitHub source: https://github.com/microsoft/SEAL
// upstream revision: none -- this is a policy model, not a Microsoft SEAL defect
// secret: %raw_approximate_plaintext
// public: certified value, certificate flag, and public release address
// expected verdict: pass structurally; unresolved L4 certificate obligation
// exact incident boundary: L1 ordering/policy; real noise sufficiency remains L4
module {
  llvm.func @ckks_unsafe_release_fixed(
      %raw_approximate_plaintext: i32,
      %certified_public_value: i32,
      %certificate_ok: i32,
      %public_release: !llvm.ptr) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %zero = llvm.mlir.constant(0 : i32) : i32
    %valid = llvm.and %certificate_ok, %one : i32
    %mask = llvm.sub %zero, %valid : i32
    %approved_public_value = llvm.and %certified_public_value, %mask : i32
    // CONFIDENTIALITY REPAIR: release only a certificate-gated public input
    // secret source: %raw_approximate_plaintext is absent from %approved_public_value
    // removed observable: the sink no longer receives unsanitized plaintext
    // reason: the released value depends only on declared public inputs
    // detection boundary: L1 structure passes; L4 must discharge real sanitizer sufficiency
    llvm.store %approved_public_value, %public_release : i32, !llvm.ptr
    llvm.return %raw_approximate_plaintext : i32
  }
}
