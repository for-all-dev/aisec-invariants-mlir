// Strength reduction: x udiv 8 -> x lshr 3.
// Value-preserving *and* leakage-removing: the source runs a variable-latency
// division, the target does not. Expected: CT-PRESERVING.
builtin.module {
  pdl.pattern @div_to_shift : benefit(1) {
    %type = pdl.type : i8

    %x = pdl.operand : %type
    %eight = pdl.attribute = 8 : i8
    %eight_op = pdl.operation "arith.constant" {"value" = %eight} -> (%type : !pdl.type)
    %eight_val = pdl.result 0 of %eight_op

    %div = pdl.operation "arith.divui" (%x, %eight_val : !pdl.value, !pdl.value) -> (%type : !pdl.type)

    pdl.rewrite %div {
      %three = pdl.attribute = 3 : i8
      %three_op = pdl.operation "arith.constant" {"value" = %three} -> (%type : !pdl.type)
      %three_val = pdl.result 0 of %three_op
      %shift = pdl.operation "arith.shrui" (%x, %three_val : !pdl.value, !pdl.value) -> (%type : !pdl.type)
      pdl.replace %div with %shift
    }
  }
}
