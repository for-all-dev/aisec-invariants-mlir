// case: wrong-party plaintext delivery
// classification: seeded-semantic-harness
// c source: ../c/wrong_party_plaintext_fixed.c
// upstream GitHub source: none -- report: https://www.wiz.io/blog/wiz-research-discovers-critical-vulnerability-in-replicate
// upstream revision: none
// secret: %plaintext, owned by the authorized party
// public: mailbox addresses, zero sentinel, and party authorization policy
// expected verdict: pass
// exact incident boundary: L1 for this semantic harness; the linked hosted incident is outside this model
module {
  llvm.func @wrong_party_plaintext_fixed(
      %plaintext: i32,
      %authorized_mailbox: !llvm.ptr,
      %unauthorized_mailbox: !llvm.ptr) {
    llvm.store %plaintext, %authorized_mailbox : i32, !llvm.ptr
    %zero = llvm.mlir.constant(0 : i32) : i32
    // CONFIDENTIALITY REPAIR: redact the unauthorized mailbox
    // secret source: %plaintext remains available only to the authorized party
    // safe effect: the unauthorized party observes the same public zero sentinel
    // reason: the stored value has no data dependence on %plaintext
    // detection boundary: direct L1 placement and output-policy check passes
    llvm.store %zero, %unauthorized_mailbox : i32, !llvm.ptr
    llvm.return
  }
}
