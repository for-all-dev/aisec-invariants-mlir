// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic only. No ModelStatus claim.
//
// PAIRED CONTROL for
// mlir/release-carrier/lost-bad/release_carrier_lost.bad.mlir and
// mlir/release-carrier/marker-only-bad/release_carrier_marker_only.bad.mlir.
//
// This fixture is release-relative noninterferent and correctly carried. Its
// required disposition is silence. It exists to stop the cheapest wrong fix to
// the carrier family: an implementation that refuses every module containing an
// inlined-looking release, or that refuses whenever a release is present at all,
// passes both bad fixtures and is useless.
//
// WHAT MAKES THE CARRIER VALID HERE. The release is a direct call to the
// manifest-named outlined wrapper, and the wrapper carries the NF-A08 attribute
// set through `passthrough`:
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
// THE PROPERTY WORTH TESTING SEPARATELY. This module must remain carrier-valid
// after optimisation. See integration/release-carrier-inline-survival.test,
// which runs `mlir-opt --inline --cse` over this fixture and asserts the call
// survives, alongside an unpinned twin where it does not.
//
// CHECK-LABEL: llvm.func @sps_release_p_v1
// CHECK-SAME: passthrough = ["noinline", "nomerge", "noduplicate", "nobuiltin"]
// CHECK-LABEL: llvm.func @release_carrier_pinned_control
// CHECK: llvm.call @sps_release_p_v1
// CHECK: llvm.store
module {
  // The outlined release wrapper. Its body is ordinary optimisable arithmetic;
  // only the boundary is pinned.
  llvm.func @sps_release_p_v1(%raw: i32, %mask: i32) -> i32
      attributes {passthrough = ["noinline", "nomerge", "noduplicate", "nobuiltin"],
                  sps.release_id = "p_v1",
                  sps.release_expression = "raw & public_mask"} {
    %v = llvm.and %raw, %mask : i32
    llvm.return %v : i32
  }

  llvm.func @release_carrier_pinned_control(
      %raw: i32 {sps.label = "high"},
      %mask: i32 {sps.label = "low"},
      %sink: !llvm.ptr {sps.sink_class = "public"}) {
    // The release occurrence is the CALL. The store that follows is an ordinary
    // public Output event, not the release site.
    %released = llvm.call @sps_release_p_v1(%raw, %mask) : (i32, i32) -> i32
    llvm.store %released, %sink : i32, !llvm.ptr
    llvm.return
  }
}
