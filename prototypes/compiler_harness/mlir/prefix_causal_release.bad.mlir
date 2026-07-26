// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// case: metatheory/MT-CM3-prefix-causal-release
// classification: seeded-semantic-harness
// c source: ../c/prefix_causal_release_bad.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/mlir/test/Dialect/LLVMIR/roundtrip.mlir
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret, declared by sps.label on the argument
// public: the sps.sink_class public channel and the release policy identity
// expected outcome: unsafe
// observer/model: release-relative-public-channel
// reason id: pre-release-observation
// outstanding obligations: none
// evidence boundary: L1 orders the observation before the release carrier; L2
// replays two secrets whose authorized releases agree while the step-1 channel
// words differ. No L3 or L4 claim.
//
// Countermodel MT-CM3, which refutes the invalid principle "a future release may
// condition an earlier observation".
//
// The secret reaches a public channel at step 1, and only afterwards reaches the
// authorized release wrapper at step 2. An end-of-run relation that requires
// equal COMPLETE release histories compares only lanes with equal secret, so it
// declares the step-1 outputs equal and misses this leak entirely.
//
// The rev-4 ledger is prefix-causal: the release transition has no parameter
// through which a future release can affect an earlier step, so the artifact is
// rejected at step 1. LowEq^0 likewise never conditions a pair on equality of a
// FUTURE release.
//
// DATA-STRUCTURE CONSEQUENCE, which is why this two-op fixture is worth its
// keep: the release ledger must be a prefix-indexed SEQUENCE consulted at each
// aligned step, not a whole-run equality installed at query setup. An
// implementation that installs release equality as an initial whole-run
// constraint reports this artifact safe.
//
// Distinct from ckks_unsafe_release.bad.mlir, which covers an UNAUTHORIZED
// release. Here the release is entirely legitimate; the defect is that it occurs
// after the observation it would be used to excuse.
//
// CHECK-LABEL: llvm.func @prefix_causal_release_bad
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK: llvm.store %[[SECRET:.*]], %{{.*}} {sps.sink_class = "public"}
// CHECK: llvm.call @sps_release_policy_h_v1(%[[SECRET]])
module {
  llvm.func @sps_release_policy_h_v1(i32) -> i32

  llvm.func @prefix_causal_release_bad(
      %secret: i32 {sps.label = "high"},
      %public_channel: !llvm.ptr {sps.sink_class = "public"}) {
    // CONFIDENTIALITY ERROR: secret observed before its authorized release
    // secret source: %secret reaches the public channel at step 1
    // observable effect: the public channel word differs between two secrets
    // reason: the prefix-causal ledger cannot let a later release excuse step 1
    // detection boundary: L1 prefix-ordered release ledger over the entry
    // expected-error @+1 {{pre-release-observation}}
    llvm.store %secret, %public_channel {sps.sink_class = "public"} : i32, !llvm.ptr
    %released = llvm.call @sps_release_policy_h_v1(%secret) : (i32) -> i32
    llvm.return
  }
}
