// CIRCT `--map-arith-to-comb`, the half that matters: integer division and remainder
// become `comb` operations (lib/Transforms/MapArithToComb.cpp:258-261).
//
// This is a *hardening*, and the models are what make it one. On x86, `div` latency
// depends on its operands, so the source leaks both. In synthesised logic a divider is
// a fixed-delay circuit -- the same operands take the same number of cycles -- so the
// target leaks nothing. The step therefore removes four observations and adds none.
//
// Expected: CT-PRESERVING (4 -> 0). The interesting direction is the other one, in
// comb_to_arith_div.mlir.
builtin.module {
  func.func @source(%a: i32, %b: i32) {
    %divu = arith.divui %a, %b : i32
    %divs = arith.divsi %a, %b : i32
    func.return
  }

  func.func @target(%a: i32, %b: i32) {
    %divu = comb.divu %a, %b : i32
    %divs = comb.divs %a, %b : i32
    func.return
  }
}
