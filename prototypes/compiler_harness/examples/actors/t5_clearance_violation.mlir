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
// T5 -- an actor must not receive certain high information.
//
// This is the direct encoding of the requirement that some actors cannot hold
// certain high items. Two items exist. `alice` has visibility for `embeddings`
// and NOT for `raw_prompt`. Both are delivered to her channel.
//
//   - The `embeddings` store is within her visibility, so it is not a violation
//     at {alice}. Note this is a per-ITEM decision, not a per-principal one:
//     alice is not "cleared" in general, she is cleared for one specific item.
//   - The `raw_prompt` store is outside it and is a violation at {alice}.
//
// The pairing inside one function is the point. It makes the fixture impossible
// to satisfy by a blanket rule about principal channels: an implementation that
// forbids all high-to-principal stores flags the first store too, and one that
// permits them misses the second. The manifest has to be consulted per item.
//
// This is also the case where the ACL is expressed by ABSENCE. There is no
// "deny" entry for (alice, raw_prompt); the item simply does not list her. A
// closed-world reading of `sps.visibility` is therefore required: anything not
// granted is denied. An open-world reading would make this artifact look clean.
//
// coalition rows:
//   {}             unsafe    item-outside-declared-visibility
//   {alice}        unsafe    item-outside-declared-visibility
// artifact aggregate: unsafe
//
// CHECK-LABEL: llvm.func @serve_two_items
// CHECK: llvm.store %{{.*}}sps.item = "embeddings"
// CHECK: llvm.store %{{.*}}sps.item = "raw_prompt"
module attributes {
  sps.principals = ["alice"],
  sps.coalitions_maximal = [["alice"]],

  // Closed world: alice is granted `embeddings` only. `raw_prompt` lists no
  // principal at all, so no coalition may observe it.
  sps.visibility = [
    {item = "embeddings", visible_to = ["alice"]},
    {item = "raw_prompt", visible_to = []}
  ],

  sps.release_policies = [],
  sps.placement = [{func = "@serve_two_items", host = "host_eu"}]
} {
  llvm.func @serve_two_items(
      %embeddings: i32 {sps.label = "high", sps.item = "embeddings"},
      %raw_prompt: i32 {sps.label = "high", sps.item = "raw_prompt"},
      %alice_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["alice"]}) {

    // Within alice's declared visibility for this specific item.
    llvm.store %embeddings, %alice_channel
        {sps.audience = ["alice"], sps.item = "embeddings"} : i32, !llvm.ptr

    // Outside it. Same destination, same operation, different item, different
    // verdict.
    //
    // CONFIDENTIALITY ERROR: item delivered to a principal with no visibility for it
    // secret source: %raw_prompt is declared high and carries item raw_prompt
    // observable effect: alice_channel receives 4 and 8 for two prompts
    // reason: raw_prompt grants visibility to no principal, and absence of a grant is a denial under the closed-world reading
    // detection boundary: L1 resolves visibility per item, not per principal; L2 supplies the 4/8 witness
    // expected-error @+1 {{item-outside-declared-visibility}}
    llvm.store %raw_prompt, %alice_channel
        {sps.audience = ["alice"], sps.item = "raw_prompt"} : i32, !llvm.ptr

    llvm.return
  }
}
