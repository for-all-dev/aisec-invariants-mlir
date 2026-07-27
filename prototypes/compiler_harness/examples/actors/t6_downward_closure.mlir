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
// T6 -- the leak exists ONLY at a derived coalition that was never authored.
//
// This example tests the coalition DERIVATION rather than any information flow.
// The manifest authors exactly one maximal coalition, {alice, bob}. The derived
// family is its downward closure:
//
//     {}   {alice}   {bob}   {alice, bob}
//
// `carol_item` is visible only to carol, who is a declared principal but appears
// in no authored maximal coalition. The singleton {carol} is nonetheless a
// derived coalition and must be checked. The store below leaks at {carol} and
// nowhere else.
//
// So an implementation that iterates the AUTHORED list finds nothing wrong, and
// an implementation that iterates the DERIVED closure finds the leak. That is
// the entire content of this fixture, and it is why the specification states
// that every member of the coalition family must be checked including those
// omitted from the authored maximal list.
//
// A checker that passes t1 and t2 can still fail this one, because t1 and t2
// both have their leak inside an authored coalition or a subset of one.
//
// Enumeration note: the closure over 3 principals has 8 members. Every one needs
// a row, including the empty coalition, which represents the world-visible
// observer. Report size is exponential in the principal count by construction;
// that is a property of the specification, not an implementation shortcut to
// optimize away by collapsing rows.
//
// coalition rows:
//   {}                    verified  item-concealed-by-projection
//   {alice}               verified  item-concealed-by-projection
//   {bob}                 verified  item-concealed-by-projection
//   {carol}               unsafe    derived-coalition-observes-item
//   {alice,bob}           verified  item-concealed-by-projection
//   {alice,carol}         unsafe    derived-coalition-observes-item
//   {bob,carol}           unsafe    derived-coalition-observes-item
//   {alice,bob,carol}     unsafe    derived-coalition-observes-item
// artifact aggregate: unsafe
//
// CHECK-LABEL: llvm.func @serve_carol_item
// CHECK: llvm.store %{{.*}}sps.item = "carol_item"
module attributes {
  // carol is a declared principal.
  sps.principals = ["alice", "bob", "carol"],

  // ...but appears in NO authored maximal coalition. {carol} is still derived.
  sps.coalitions_maximal = [["alice", "bob"]],

  sps.visibility = [
    {item = "carol_item", visible_to = ["carol"]}
  ],

  sps.release_policies = [],
  sps.placement = [{func = "@serve_carol_item", host = "host_eu"}]
} {
  llvm.func @serve_carol_item(
      %carol_item: i32 {sps.label = "high", sps.item = "carol_item"},
      %carol_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["carol"]}) {

    // Invisible to every authored coalition, visible to a derived one.
    //
    // CONFIDENTIALITY ERROR: item observed only at a coalition nobody authored
    // secret source: %carol_item is declared high and carries item carol_item
    // observable effect: carol_channel receives 13 and 26 for two items
    // reason: carol appears in no authored maximal coalition, so the leak exists only at derived {carol}
    // detection boundary: L1 enumerates the downward closure rather than the authored list; L2 supplies the 13/26 witness at {carol}
    // expected-error @+1 {{derived-coalition-observes-item}}
    llvm.store %carol_item, %carol_channel
        {sps.audience = ["carol"], sps.item = "carol_item"} : i32, !llvm.ptr

    llvm.return
  }
}
