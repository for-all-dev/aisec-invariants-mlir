// CIRCT `--convert-comb-to-arith`, unsigned division, transcribed from the pattern
// itself (lib/Conversion/CombToArith/CombToArith.cpp:196-218):
//
//     divu(a, b)  ~>  isZero = (b == 0); divisor = isZero ? 1 : b; divu(a, divisor)
//
// This step runs when hardware is *simulated in software*: arcilator's pipeline reaches
// it through `--lower-arc-to-llvm`, which pulls in the same patterns
// (lib/Tools/arcilator/pipelines.cpp:170 -> lib/Conversion/ArcToLLVM/LowerArcToLLVM.cpp:1910).
//
// The divider that was a fixed-delay circuit becomes an x86 `div`, whose latency
// depends on its operands. The zero-guard the pattern adds does not change that: it
// only replaces one data-dependent divisor with another.
//
// Expected: CT-BREAKING (0 -> 2). The simulator leaks what the hardware did not.
builtin.module {
  func.func @source(%a: i32, %b: i32) {
    %q = comb.divu %a, %b : i32
    func.return
  }

  func.func @target(%a: i32, %b: i32) {
    %zero = arith.constant 0 : i32
    %one = arith.constant 1 : i32
    %is_zero = arith.cmpi eq, %b, %zero : i32
    %divisor = arith.select %is_zero, %one, %b : i32
    %q = arith.divui %a, %divisor : i32
    func.return
  }
}
