// RUN: %mlir-opt %s | %FileCheck %s
//
// DESIGN EXAMPLE. Not part of the enforced corpus; see README.md.
//
// T2 -- joint visibility: the downward closure is not reconstructible from
// per-principal rows.
//
// The INPUT `private_state` is High for every checked coalition. The OUTPUT
// `joint_result` is visible to the JOINT set {alice, bob} and to neither
// singleton. Keeping those two policy objects distinct is essential: if the
// input itself were jointly visible, LowEq for {alice,bob} would force its two
// lane values equal and the claimed joint counterexample would be vacuous.
//
//   - At {alice} the projection conceals the item, so the store is not observable.
//   - At {bob} likewise.
//   - At {alice, bob} the output becomes visible and the differing store is a leak.
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
// product rows:
//   {}             ProductSafe
//   {alice}        ProductSafe
//   {bob}          ProductSafe
//   {alice,bob}    ReplayableCounterexample  joint-visibility-reveals-item
// future artifact ModelStatus: Counterexample(ReplayableWitness)
//
// CHECK-LABEL: llvm.func @serve_kv_cache
// CHECK: llvm.store %{{.*}} {sps.audience = ["alice", "bob"]}
module attributes {
  sps.principals = ["alice", "bob"],
  sps.coalitions_maximal = [["alice", "bob"]],

  sps.visibility = [
    // Visible to the pair, and to NEITHER singleton. This is the whole point.
    {output = "joint_result", minimally_joint_visible = [["alice", "bob"]]}
  ],

  sps.release_policies = [],
  sps.placement = [{func = "@serve_kv_cache", host = "host_eu"}]
} {
  llvm.func @serve_kv_cache(
      %private_value: i32 {sps.label = "high", sps.item = "private_state"},
      // A channel both principals can read. Neither alone can reconstruct the
      // item; together they can.
      %shared_channel: !llvm.ptr {sps.sink_class = "principal",
                                  sps.output = "joint_result",
                                  sps.audience = ["alice", "bob"]}) {

    // No release policy covers private_state, so nothing equalizes this flow.
    // Whether it is a leak depends entirely on which coalition is asking.
    //
    // CONFIDENTIALITY ERROR: jointly visible item reaches a shared channel
    // secret source: %private_value is declared high and carries item private_state
    // observable effect: the shared channel holds 11 and 22 for two cache entries
    // reason: joint_result is minimally joint visible to {alice,bob}, while private_state remains High to that pair
    // detection boundary: L1 resolves visibility per coalition; L2 supplies the 11/22 witness at {alice,bob} only
    llvm.store %private_value, %shared_channel
        {sps.output = "joint_result", sps.audience = ["alice", "bob"]} : i32, !llvm.ptr

    llvm.return
  }
}
