// RUN: %mlir-opt %s | %FileCheck %s
//
// DESIGN EXAMPLE. Not part of the enforced corpus; see README.md.
//
// T9 -- incomplete placement table, and why the honest answer is
// `Unknown(ManifestMismatch)`.
//
// Two functions are reachable. `@serve_placed` has a declared host.
// `@serve_unplaced` does NOT appear in `sps.placement` at all.
//
// Without a unique host for a reachable function there is no host-visibility
// projection for its events, so the placement premise is simply absent. Neither
// safety nor a counterexample follows: placement is a global blocker and no
// product result may be promoted to an artifact theorem.
//
// This is the failure mode most likely to produce a confidently wrong green
// result, because the tempting default is to treat an unplaced function as
// local, trusted, or unobservable and continue. Any of those is an invented
// premise. Placement is also explicitly not inferable from LLVM names or entry
// scopes, so `@serve_unplaced` sounding local means nothing.
//
// The two functions sit in one module deliberately: the fixture must not be
// satisfiable by refusing every module that has a placement table, nor by
// accepting every module that has one. One function is placed and fine; the
// other is not placed and is a refusal.
//
// WHY THIS IS ABSENT FROM THE CURRENT CORPUS. `wrong_party_plaintext` and
// `wrong_host_fhe_reveal` both presuppose a COMPLETE audience and host policy.
// Neither exercises an incomplete one, so nothing today demonstrates that
// placement is consulted at all rather than hardcoded per fixture. Since the
// project frames itself as actor-based, an incomplete-manifest refusal is table
// stakes.
//
// Ideally ship this as one function body with two manifests that differ only in
// placement, asserting opposite outcomes -- the same "policy is an input"
// discipline as the t3/t4 pair.
//
// product rows (per entry):
//   @serve_placed    {}       ProductSafe
//   @serve_placed    {alice}  ProductSafe
//   @serve_unplaced  {}       Blocked(ManifestMismatch)
//   @serve_unplaced  {alice}  Blocked(ManifestMismatch)
// future artifact ModelStatus: Unknown(ManifestMismatch)
//
// CHECK-LABEL: llvm.func @serve_placed
// CHECK-LABEL: llvm.func @serve_unplaced
module attributes {
  sps.principals = ["alice"],
  sps.coalitions_maximal = [["alice"]],

  sps.visibility = [
    {item = "logits", visible_to = ["alice"]}
  ],

  sps.release_policies = [],

  // @serve_unplaced is reachable and deliberately missing here.
  sps.placement = [{func = "@serve_placed", host = "host_eu"}]
} {
  llvm.func @serve_placed(
      %logits: i32 {sps.label = "high", sps.item = "logits"},
      %alice_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["alice"]}) {
    llvm.store %logits, %alice_channel
        {sps.audience = ["alice"], sps.item = "logits"} : i32, !llvm.ptr
    llvm.return
  }

  // No host. No projection. No verdict -- and specifically not a safe one.
  llvm.func @serve_unplaced(
      %logits: i32 {sps.label = "high", sps.item = "logits"},
      %alice_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["alice"]}) {
    llvm.store %logits, %alice_channel
        {sps.audience = ["alice"], sps.item = "logits"} : i32, !llvm.ptr
    llvm.return
  }
}
