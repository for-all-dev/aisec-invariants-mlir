// RUN: %mlir-opt %s | %FileCheck %s
//
// DESIGN EXAMPLE. Not part of the enforced corpus; see README.md.
//
// T6 -- every derived coalition row must be emitted, even when maximal also fails.
//
// This example tests the coalition DERIVATION rather than any information flow.
// The manifest authors exactly one maximal coalition, {alice, bob, carol}. The derived
// family is its downward closure:
//
//     {}   {alice}   {bob}   {carol}
//     {alice,bob}   {alice,carol}   {bob,carol}   {alice,bob,carol}
//
// `private_state` remains High to the family, while `carol_output` is visible to
// coalitions containing carol. The singleton {carol} is absent from the authored
// maximal list but present in its downward closure, and must be checked.
//
// The authored maximal row is not a substitute for the derived rows even when it
// also observes the output: the report must still contain every coalition and
// its own result. This fixture pins completeness of enumeration, not a monotonic
// inference rule.
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
// AuditAll fixture expectations (not computed results):
//   {}                    UNSAT / Discharged
//   {alice}               UNSAT / Discharged
//   {bob}                 UNSAT / Discharged
//   {carol}               SAT / CandidateOnly / accepted Bad_A replay required
//   {alice,bob}           UNSAT / Discharged
//   {alice,carol}         SAT / CandidateOnly / accepted Bad_A replay required
//   {bob,carol}           SAT / CandidateOnly / accepted Bad_A replay required
//   {alice,bob,carol}     SAT / CandidateOnly / accepted Bad_A replay required
// future ModelStatus matcher: Counterexample(receiptId), contingent on replay
//
// CHECK-LABEL: llvm.func @serve_carol_item
// CHECK: llvm.store %{{.*}}sps.output = "carol_output"
module attributes {
  // carol is a declared principal.
  sps.principals = ["alice", "bob", "carol"],

  // Carol belongs to the authored maximal coalition, so {carol} is genuinely in
  // its downward closure even though the singleton itself was not authored.
  sps.coalitions_maximal = [["alice", "bob", "carol"]],

  sps.visibility = [
    {output = "carol_output", visible_to = ["carol"]}
  ],

  sps.release_policies = [],
  sps.placement = [{func = "@serve_carol_item", host = "host_eu"}]
} {
  llvm.func @serve_carol_item(
      %private_state: i32 {sps.label = "high", sps.item = "private_state"},
      %carol_channel: !llvm.ptr {sps.sink_class = "principal",
                                 sps.output = "carol_output",
                                 sps.audience = ["carol"]}) {

    // Visible to every coalition containing carol, including required derived rows.
    //
    // CONFIDENTIALITY ERROR: private item reaches a coalition-visible output
    // secret source: %private_state is declared high and carries item private_state
    // observable effect: carol_channel receives 13 and 26 for two items
    // reason: {carol} is a required derived row of maximal {alice,bob,carol}
    // fixture check: enumerate the exact downward closure; values 13/26 in each
    // visible AuditAll row remain candidates until independent Bad_A replay
    llvm.store %private_state, %carol_channel
        {sps.audience = ["carol"], sps.output = "carol_output"} : i32, !llvm.ptr

    llvm.return
  }
}
