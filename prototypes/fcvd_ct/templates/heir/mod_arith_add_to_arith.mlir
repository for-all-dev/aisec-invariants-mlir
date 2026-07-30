// HEIR `--mod-arith-to-arith`, the addition pattern, transcribed from
// lib/Dialect/ModArith/Conversions/ModArithToArith/ModArithToArith.cpp:350-364:
//
//     mod_arith.add %a, %b  ~>  %s = arith.addi %a, %b; arith.remui %s, %modulus
//
// The source operation is a hole with no leakage: at the `mod_arith` level a modular
// addition is a value operation with no timing meaning, which is exactly the claim the
// dialect makes. The target reduces with `arith.remui`, and on x86 `div` latency
// depends on its operands -- the modulus is a constant, but the dividend is the secret.
//
// Expected: CT-BREAKING (0 -> 2). Scope, stated plainly: this is a statement about the
// MLIR, not about the binary. LLVM turns division by a *constant* into a multiply-shift
// sequence, so the channel may well be closed further down -- which is what layers A/B
// (binsec, on the binary) are for. The point here is that the MLIR-level lowering
// introduces a variable-latency instruction on secret data, and nothing in HEIR's
// pipeline states that the backend has to remove it again.
builtin.module {
  func.func @source(%a: i32, %b: i32) {
    %sum = "fcvd.hole"(%a, %b) {sym_name = "mod_add", leaks = 0 : i64} : (i32, i32) -> i32
    func.return
  }

  func.func @target(%a: i32, %b: i32) {
    %modulus = arith.constant 65537 : i32
    %sum = arith.addi %a, %b : i32
    %reduced = arith.remui %sum, %modulus : i32
    func.return
  }
}
