// The same rewrite backwards: x lshr 3 -> x udiv 8.
// Still value-correct -- `verify-pdl` calls it sound -- but it puts a
// variable-latency division where there was none. Expected: CT-BREAKING, with a
// counterexample: two inputs the shift cannot distinguish and the division can.
builtin.module {
  pdl.pattern @shift_to_div : benefit(1) {
    %type = pdl.type : i8

    %x = pdl.operand : %type
    %three = pdl.attribute = 3 : i8
    %three_op = pdl.operation "arith.constant" {"value" = %three} -> (%type : !pdl.type)
    %three_val = pdl.result 0 of %three_op

    %shift = pdl.operation "arith.shrui" (%x, %three_val : !pdl.value, !pdl.value) -> (%type : !pdl.type)

    pdl.rewrite %shift {
      %eight = pdl.attribute = 8 : i8
      %eight_op = pdl.operation "arith.constant" {"value" = %eight} -> (%type : !pdl.type)
      %eight_val = pdl.result 0 of %eight_op
      %div = pdl.operation "arith.divui" (%x, %eight_val : !pdl.value, !pdl.value) -> (%type : !pdl.type)
      pdl.replace %shift with %div
    }
  }
}
