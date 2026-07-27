// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// BRING-UP GATE. The second RUN fails today with "expected error ... was not
// produced", exactly like the 17 bad fixtures in ../../mlir/. That is the
// intended state: the diagnostic names the stable reason a future analysis must
// emit at the decisive operation, and implementing that analysis is what turns
// this green. It is not a disabled test and must not be marked XFAIL.
//
// DESIGN EXAMPLE. Not part of the enforced corpus; see README.md in this
// directory. The coalition rows below are aspirational: no tool reads them yet.
//
// T1 -- audience mismatch, and why coalition verdicts are NOT monotonic.
//
// THIS IS THE CENTREPIECE EXAMPLE. It is the reason the result record has to be
// keyed by (entry, coalition) rather than by a single observer.
//
// One value is released exactly once, under a policy whose declared audience is
// {alice}. It is then stored to two principal channels. The IR of the two stores
// is identical apart from the destination.
//
//   - For any coalition containing alice, the release is authorized, so the
//     release-equality premise R(p,s0) == R(p,s1) holds and the store is fine.
//   - For coalition {bob}, that same release is NOT authorized. The premise does
//     not hold, so the identical store is a leak.
//
// So the verdict is `verified` at {alice} and `unsafe` at {bob}, with no
// containment relation between those two coalitions. A checker that evaluates
// only the authored maximal coalition {alice, bob} never visits {bob} alone and
// reports the artifact clean.
//
// This is why the specification forbids deduplicating results from coalition
// monotonicity, and why a report may not omit a derived coalition.
//
// coalition rows:
//   {}             unsafe    raw-item-not-world-releasable
//   {alice}        verified  authorized-audience
//   {bob}          unsafe    release-audience-mismatch
//   {alice,bob}    unsafe    release-audience-mismatch
// artifact aggregate: unsafe
//
// LIMIT OF THE DIAGNOSTIC ORACLE, VISIBLE HERE. The expected-error below names
// one reason at one site. The rows above name TWO distinct reasons at two
// distinct coalitions: the store to bob is release-audience-mismatch, while at
// the empty coalition the store to alice is already a leak, because a raw item
// is not world-releasable. A single expected-error per operation cannot express
// a per-coalition reason map, so the directive pins only the {bob} case.
//
// This is not a defect in the fixture; it is the record-shape gap made concrete.
// Closing it needs the (entry, coalition) row keying, after which each row
// carries its own reason and each decisive site can be checked per coalition.
//
// CHECK-LABEL: llvm.func @serve_logits
// CHECK: llvm.call @sps_release_argmax_v1
// CHECK-SAME: sps.authorized_by = "auditor"
// CHECK-SAME: sps.release_id = "argmax_v1"
// CHECK: llvm.store %{{.*}} {sps.audience = ["alice"]}
// CHECK: llvm.store %{{.*}} {sps.audience = ["bob"]}
module attributes {
  sps.principals = ["alice", "bob", "auditor"],

  // Only the maximal coalition is authored. The derived set is its downward
  // closure: {}, {alice}, {bob}, {alice, bob}. Every member must be checked,
  // including ones absent from this list.
  sps.coalitions_maximal = [["alice", "bob"]],

  sps.visibility = [
    {item = "logits", visible_to = ["alice"]}
  ],

  // authorizers and audience are deliberately different sets: the auditor may
  // authorize this release but is not one of its recipients.
  sps.release_policies = [
    {id = "argmax_v1", authorizers = ["auditor"], audience = ["alice"],
     function = "argmax", carrier = "@sps_release_argmax_v1"}
  ],

  sps.placement = [{func = "@serve_logits", host = "host_eu"}]
} {
  // The release rides a direct call to a manifest-named outlined carrier, not an
  // attribute on a store. That gives a stable site identity and a countable call
  // occurrence; release identity is not established by a name alone.
  llvm.func @sps_release_argmax_v1(i32) -> i32

  llvm.func @serve_logits(
      %logits: i32 {sps.label = "high", sps.item = "logits"},
      %alice_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["alice"]},
      %bob_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["bob"]}) {

    %released = llvm.call @sps_release_argmax_v1(%logits)
        {sps.release_id = "argmax_v1", sps.authorized_by = "auditor"} : (i32) -> i32

    // Authorized: alice is the declared audience of argmax_v1.
    llvm.store %released, %alice_channel {sps.audience = ["alice"]} : i32, !llvm.ptr

    // NOT authorized for {bob}. Byte-identical operation, different verdict.
    //
    // CONFIDENTIALITY ERROR: released value delivered outside its declared audience
    // secret source: %released is derived from high %logits by argmax_v1
    // observable effect: bob_channel receives class indices 3 and 5 for two logit vectors
    // reason: argmax_v1 declares audience alice, so nothing retires the obligation for the coalition {bob}
    // detection boundary: L1 compares the store's audience against the release policy; L2 supplies the 3/5 witness
    // expected-error @+1 {{release-audience-mismatch}}
    llvm.store %released, %bob_channel {sps.audience = ["bob"]} : i32, !llvm.ptr

    llvm.return
  }
}
