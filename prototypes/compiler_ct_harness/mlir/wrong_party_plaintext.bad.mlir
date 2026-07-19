// case: wrong-party plaintext delivery
// classification: seeded-semantic-harness
// c source: ../c/wrong_party_plaintext_bad.c
// upstream GitHub source: none -- report: https://www.wiz.io/blog/wiz-research-discovers-critical-vulnerability-in-replicate
// upstream revision: none
// secret: %plaintext, owned by the authorized party
// public: mailbox addresses and party authorization policy
// expected verdict: reject
// exact incident boundary: L1 for this semantic harness; the linked hosted incident is outside this model
module {
  llvm.func @wrong_party_plaintext_bad(
      %plaintext: i32,
      %authorized_mailbox: !llvm.ptr,
      %unauthorized_mailbox: !llvm.ptr) {
    llvm.store %plaintext, %authorized_mailbox : i32, !llvm.ptr
    // CONFIDENTIALITY ERROR: wrong-party plaintext store
    // secret source: %plaintext is owned by the authorized party
    // observable effect: the unauthorized party can read its mailbox contents
    // reason: this store copies the secret verbatim across the audience boundary
    // detection boundary: direct L1 placement and output-policy violation
    llvm.store %plaintext, %unauthorized_mailbox : i32, !llvm.ptr
    llvm.return
  }
}
