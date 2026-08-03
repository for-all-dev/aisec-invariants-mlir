// CIRCT `--map-arith-to-comb`, the min/max patterns: `max(a, b)` becomes
// `mux(icmp sge a, b, a, b)` -- lib/Transforms/MapArithToComb.cpp:174-190. The lowering
// introduces a *comparison*, which in software would be a branch and here is not: the
// mux is a circuit, not a jump, so no observation appears.
//
// Expected: CT-PRESERVING (0 -> 0).
builtin.module {
  func.func @source(%a: i32, %b: i32) {
    %max = arith.maxsi %a, %b : i32
    %min = arith.minui %max, %b : i32
    func.return
  }

  func.func @target(%a: i32, %b: i32) {
    %cmp = comb.icmp sge %a, %b : i32
    %max = comb.mux %cmp, %a, %b : i32
    %cmp2 = comb.icmp ule %max, %b : i32
    %min = comb.mux %cmp2, %max, %b : i32
    func.return
  }
}
