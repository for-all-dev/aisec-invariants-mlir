// CIRCT `--map-arith-to-comb`, the leak-free half of its table: every one-to-one
// pattern in `populateArithToCombPatterns`, lib/Transforms/MapArithToComb.cpp:255-268,
// plus the constant and truncation patterns at :159 and :107.
//
// Software and hardware disagree about which of these leak, which is the whole point of
// checking the step: on x86 nothing here is variable-latency, and in synthesised logic
// nothing here is either, so the honest expectation is that neither side observes
// anything at all. A template that came back CT-BREAKING would mean one of the models
// attributes a leak to a plain adder.
//
// Expected: CT-PRESERVING (0 -> 0).
builtin.module {
  func.func @source(%a: i32, %b: i32, %c: i1) {
    %add = arith.addi %a, %b : i32
    %sub = arith.subi %add, %b : i32
    %mul = arith.muli %sub, %b : i32
    %and = arith.andi %mul, %b : i32
    %or = arith.ori %and, %b : i32
    %xor = arith.xori %or, %b : i32
    %shl = arith.shli %xor, %b : i32
    %shrs = arith.shrsi %shl, %b : i32
    %shru = arith.shrui %shrs, %b : i32
    %sel = arith.select %c, %shru, %a : i32
    %k = arith.constant 7 : i32
    %fin = arith.addi %sel, %k : i32
    func.return
  }

  func.func @target(%a: i32, %b: i32, %c: i1) {
    %add = comb.add %a, %b : i32
    %sub = comb.sub %add, %b : i32
    %mul = comb.mul %sub, %b : i32
    %and = comb.and %mul, %b : i32
    %or = comb.or %and, %b : i32
    %xor = comb.xor %or, %b : i32
    %shl = comb.shl %xor, %b : i32
    %shrs = comb.shrs %shl, %b : i32
    %shru = comb.shru %shrs, %b : i32
    %sel = comb.mux %c, %shru, %a : i32
    %k = hw.constant 7 : i32
    %fin = comb.add %sel, %k : i32
    func.return
  }
}
