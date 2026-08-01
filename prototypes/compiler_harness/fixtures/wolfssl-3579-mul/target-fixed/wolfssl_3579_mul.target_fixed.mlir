// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not='llvm.call @__muldi3' --implicit-check-not=llvm.cond_br
// RUN: %mlir-opt %s | %FileCheck %s --check-prefix=COUNT --implicit-check-not='llvm.call @__muldi3' --implicit-check-not=llvm.cond_br
//
// scope note: preflight diagnostic verifies the fixed loop; target-operation and backend-conformance facts remain deployment obligations
// artifact status: hand-written fixed target model
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @wolfssl_3579_mul_fixed_model
// CHECK-SAME: %[[SECRET_A:[a-zA-Z0-9_]+]]: i64 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}, %[[SECRET_B:[a-zA-Z0-9_]+]]: i64 {sps.fixture_refs = ["snapshot.secret[1]"], sps.label = "high"}
// CHECK: %[[ZERO64:[0-9]+]] = llvm.mlir.constant(0 : i64) : i64
// CHECK: %[[ONE64:[0-9]+]] = llvm.mlir.constant(1 : i64) : i64
// CHECK: %[[ZERO32:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK: %[[ONE32:[0-9]+]] = llvm.mlir.constant(1 : i32) : i32
// CHECK: %[[BOUND:[0-9]+]] = llvm.mlir.constant(64 : i32) : i32
// CHECK-NOT: llvm.call @__muldi3
// CHECK: llvm.br ^bb1(%[[ZERO32]], %[[ZERO64]], %[[SECRET_A]], %[[SECRET_B]] : i32, i64, i64, i64)
// CHECK: ^bb1(%[[INDEX:[0-9]+]]: i32, %[[ACC:[0-9]+]]: i64, %[[ADDEND:[0-9]+]]: i64, %[[MULT:[0-9]+]]: i64)
// CHECK: %[[DONE:[0-9]+]] = llvm.icmp "eq" %[[INDEX]], %[[BOUND]] : i32
// CHECK-NOT: llvm.call @__muldi3
// CHECK: llvm.cond_br %[[DONE]], {{.*}} {sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]"], sps.observable_candidate = ["control", "timing"]}
// CHECK-NOT: llvm.call @__muldi3
// CHECK: %[[LOW_BIT:[0-9]+]] = llvm.and %[[MULT]], %[[ONE64]] {sps.fixture_refs = ["snapshot.secret[1]"]}
// CHECK: %[[NEXT_INDEX:[0-9]+]] = llvm.add %[[INDEX]], %[[ONE32]]
// CHECK: llvm.br ^bb1(%[[NEXT_INDEX]],
// CHECK-NOT: llvm.call @__muldi3
// CHECK: llvm.return
//
// COUNT-COUNT-1: llvm.cond_br
module {
  llvm.func @wolfssl_3579_mul_fixed_model(
      %secret_a: i64 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %secret_b: i64 {sps.fixture_refs = ["snapshot.secret[1]"], sps.label = "high"}) -> i64 {
    %zero64 = llvm.mlir.constant(0 : i64) : i64
    %one64 = llvm.mlir.constant(1 : i64) : i64
    %zero32 = llvm.mlir.constant(0 : i32) : i32
    %one32 = llvm.mlir.constant(1 : i32) : i32
    %sixty_four = llvm.mlir.constant(64 : i32) : i32
    llvm.br ^loop(%zero32, %zero64, %secret_a, %secret_b : i32, i64, i64, i64)
  ^loop(%i: i32, %acc: i64, %addend: i64, %mult: i64):
    %done = llvm.icmp "eq" %i, %sixty_four : i32
    llvm.cond_br %done, ^exit(%acc : i64), ^body {
      sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]"],
      sps.observable_candidate = ["control", "timing"]
    }
  ^body:
    %low_bit = llvm.and %mult, %one64 {
      sps.fixture_refs = ["snapshot.secret[1]"]
    } : i64
    // PREFLIGHT CONTROL: fixed-iteration mask/add multiplication
    // secret source: %low_bit is a secret bit of %secret_b
    // safe effect: it affects only a mask operand, not loop count, branch direction, address, or helper selection
    // reason: all 64 iterations execute for every input and no __muldi3 call is emitted
    // preflight expectation: preflight diagnostic accepts this shape with a constant-time RV32I operation profile
    %mask = llvm.sub %zero64, %low_bit : i64
    %masked_addend = llvm.and %addend, %mask : i64
    %acc_next = llvm.add %acc, %masked_addend : i64
    %addend_next = llvm.shl %addend, %one64 : i64
    %mult_next = llvm.lshr %mult, %one64 : i64
    %i_next = llvm.add %i, %one32 : i32
    llvm.br ^loop(%i_next, %acc_next, %addend_next, %mult_next : i32, i64, i64, i64)
  ^exit(%result: i64):
    llvm.return %result : i64
  }
}
