// RUN: %mlir-opt %s | %FileCheck %s
//
// input invariant: %certificate_ok is a well-formed Boolean in {0, 1}
// private result: the function return is not in the public observer projection
// scope note: preflight diagnostic public-sink flow; production CKKS correctness,
// circuit privacy, and integrity are outside this Rev4 model claim
//
// CHECK-LABEL: llvm.func @ckks_unsafe_release_bad
// CHECK-SAME: %[[RAW:[a-zA-Z0-9_]+]]: i32, %[[MASK:[a-zA-Z0-9_]+]]: i32, %[[CERT:[a-zA-Z0-9_]+]]: i32, %[[SINK:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK: llvm.store %[[RAW]], %[[SINK]]
// CHECK-NOT: sps.release_policy
module {
  llvm.func @ckks_unsafe_release_bad(
      %raw_approximate_plaintext: i32,
      %public_sanitizer_mask: i32,
      %certificate_ok: i32,
      %public_release: !llvm.ptr) -> i32 {
    // PREFLIGHT FINDING: raw approximate plaintext reaches the public release sink
    // secret source: %raw_approximate_plaintext is an unsanitized decryption result
    // observable effect: the public release sink receives the raw value
    // reason: no approved sanitizer result or certificate check dominates this store
    // preflight expectation: unary scanner flags the raw candidate-secret public-sink store
    llvm.store %raw_approximate_plaintext, %public_release : i32, !llvm.ptr
    llvm.return %raw_approximate_plaintext : i32
  }
}
