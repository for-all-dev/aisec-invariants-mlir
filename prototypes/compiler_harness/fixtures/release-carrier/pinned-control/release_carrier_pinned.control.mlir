// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic only. No ModelStatus claim.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// PAIRED INVALID-CALLABLE CONTROL for
// fixtures/release-carrier/lost-bad/release_carrier_lost.bad.mlir and
// fixtures/release-carrier/marker-only-bad/release_carrier_marker_only.bad.mlir.
//
// This fixture is release-relative noninterferent at its modeled MLIR boundary,
// but its outlined wrapper is not an SPS-LLVM-NF-v2 carrier. Its preflight
// expectation remains silence. It exists to stop the cheapest wrong fix to
// the carrier family: an implementation that refuses every module containing an
// inlined-looking release, or that refuses whenever a release is present at all,
// passes both bad fixtures and is useless.
//
// WHAT THE INVALID-CALLABLE EXPERIMENT PINS. The release-shaped operation is a
// direct call to a manifest-named outlined wrapper, and the wrapper carries the
// old NF-A08 attribute set through `passthrough`:
//
//   noinline    -- body spliced into the caller  => site identity gone
//   nomerge     -- many occurrences become one   => multiplicity wrong
//   noduplicate -- one occurrence becomes many   => multiplicity wrong
//   nobuiltin   -- recognised as a libcall and substituted
//
// One attribute per way of altering occurrence or site structure without
// altering value. The set is closed over exactly the intensional properties the
// carrier has to preserve; the wrapper BODY is free to be optimised, and the
// caller is free to be optimised around it.
//
// THE PROPERTY WORTH TESTING SEPARATELY. The invalid wrapper remains findable
// after this MLIR optimisation. See
// integration/invalid-callable-mlir-survival.test, which runs
// `mlir-opt --inline --cse` and asserts the call survives alongside an unpinned
// twin where it does not. That compiler fact does not grant NFv2 conformance.
//
// CHECK-LABEL: llvm.func @sps_release_invalid_callable
// CHECK-SAME: passthrough = ["noinline", "nomerge", "noduplicate", "nobuiltin"]
// CHECK-LABEL: llvm.func @release_carrier_pinned_control
// CHECK-SAME: sps.fixture_refs = ["snapshot.secret[0]"]
// CHECK-SAME: sps.label = "high"
// CHECK-SAME: sps.fixture_refs = ["snapshot.public[0]"]
// CHECK-SAME: sps.sink_class = "public"
// CHECK: llvm.call @sps_release_invalid_callable
// CHECK-SAME: sps.fixture_refs = ["snapshot.public[1]"]
// CHECK-SAME: sps.observable_candidate = ["release-identity"]
// CHECK-SAME: sps.site_alias = "p-invalid-callable-release-carrier-call"
// CHECK: llvm.store {{.*}}sps.fixture_refs = ["snapshot.public[0]"]
// CHECK-SAME: sps.sink_class = "public"
module {
  // The outlined release wrapper. Its body is ordinary optimisable arithmetic;
  // only the boundary is pinned.
  llvm.func @sps_release_invalid_callable(%raw: i32, %mask: i32) -> i32
      attributes {passthrough = ["noinline", "nomerge", "noduplicate", "nobuiltin"],
                  sps.release_id = "p_invalid_callable",
                  sps.release_expression = "raw & public_mask"} {
    %v = llvm.and %raw, %mask : i32
    llvm.return %v : i32
  }

  llvm.func @release_carrier_pinned_control(
      %raw: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %mask: i32 {sps.label = "low"},
      %sink: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}) {
    // The release occurrence is the CALL. The store that follows is an ordinary
    // public Output event, not the release site.
    %released = llvm.call @sps_release_invalid_callable(%raw, %mask)
        {sps.fixture_refs = ["snapshot.public[1]"],
         sps.observable_candidate = ["release-identity"],
         sps.site_alias = "p-invalid-callable-release-carrier-call"} : (i32, i32) -> i32
    llvm.store %released, %sink
        {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
