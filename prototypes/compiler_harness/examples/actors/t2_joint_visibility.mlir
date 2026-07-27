// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// BRING-UP GATE. The second RUN fails today with "expected error ... was not
// produced", exactly like the 17 bad fixtures in ../../mlir/. That is the
// intended state: the diagnostic names the stable reason a future analysis must
// emit at the decisive operation, and implementing that analysis is what turns
// this green. It is not a disabled test and must not be marked XFAIL.
//
// DESIGN EXAMPLE. Not part of the enforced corpus; see README.md.
//
// T2 -- joint visibility: the downward closure is not reconstructible from
// per-principal rows.
//
// `kv_cache` is declared visible to the JOINT set {alice, bob} and to neither
// singleton. Concretely: alice holds one share and bob holds the other, and the
// item is only recoverable by both together.
//
//   - At {alice} the projection conceals the item, so the store is not observable.
//   - At {bob} likewise.
//   - At {alice, bob} the item becomes visible and the store is a leak.
//
// Consequence for the data structure: a visibility relation stored as
// principal -> set-of-items cannot express this, and a report built by
// evaluating singletons and unioning cannot derive it. Visibility needs a
// minimal-joint-set relation, and the coalition family must be enumerated as a
// downward closure rather than inferred from its members.
//
// Minimal joint sets must be nonempty, inclusion-minimal for the same item, and
// subsets of the declared principals. `{alice, bob}` below is minimal precisely
// because neither singleton suffices.
//
// coalition rows:
//   {}             verified  item-concealed-by-projection
//   {alice}        verified  item-concealed-by-projection
//   {bob}          verified  item-concealed-by-projection
//   {alice,bob}    unsafe    joint-visibility-reveals-item
// artifact aggregate: unsafe
//
// CHECK-LABEL: llvm.func @serve_kv_cache
// CHECK: llvm.store %{{.*}} {sps.audience = ["alice", "bob"]}
module attributes {
  sps.principals = ["alice", "bob"],
  sps.coalitions_maximal = [["alice", "bob"]],

  sps.visibility = [
    // Visible to the pair, and to NEITHER singleton. This is the whole point.
    {item = "kv_cache", minimally_joint_visible = [["alice", "bob"]]}
  ],

  sps.release_policies = [],
  sps.placement = [{func = "@serve_kv_cache", host = "host_eu"}]
} {
  llvm.func @serve_kv_cache(
      %kv_entry: i32 {sps.label = "high", sps.item = "kv_cache"},
      // A channel both principals can read. Neither alone can reconstruct the
      // item; together they can.
      %shared_channel: !llvm.ptr {sps.sink_class = "principal",
                                  sps.audience = ["alice", "bob"]}) {

    // No release policy covers kv_cache, so nothing equalizes this flow.
    // Whether it is a leak depends entirely on which coalition is asking.
    //
    // CONFIDENTIALITY ERROR: jointly visible item reaches a shared channel
    // secret source: %kv_entry is declared high and carries item kv_cache
    // observable effect: the shared channel holds 11 and 22 for two cache entries
    // reason: kv_cache is minimally joint visible to {alice,bob}, so the pair is concealed at each singleton and revealed to the pair
    // detection boundary: L1 resolves visibility per coalition; L2 supplies the 11/22 witness at {alice,bob} only
    // expected-error @+1 {{joint-visibility-reveals-item}}
    llvm.store %kv_entry, %shared_channel {sps.audience = ["alice", "bob"]} : i32, !llvm.ptr

    llvm.return
  }
}
