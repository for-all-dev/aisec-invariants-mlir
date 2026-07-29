// The same circuit after CIRCT's `--convert-comb-to-arith`, i.e. what arcilator runs on
// the host CPU. Transcribed from lib/Conversion/CombToArith/CombToArith.cpp:196-218,
// zero-guard included.
//
// Expected: INSECURE on `latency`. Same circuit, same secret, different verdict --
// the step is what introduced the channel.
func.func @hw_divide_simulated(%public: i32, %secret: i32 {fcvdct.secret}) -> i32 {
  %zero = arith.constant 0 : i32
  %one = arith.constant 1 : i32
  %is_zero = arith.cmpi eq, %secret, %zero : i32
  %divisor = arith.select %is_zero, %one, %secret : i32
  %q = arith.divui %public, %divisor : i32
  func.return %q : i32
}
