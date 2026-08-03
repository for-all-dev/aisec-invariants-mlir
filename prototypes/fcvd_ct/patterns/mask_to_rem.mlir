// A plausible-looking canonicalization: x and 7 -> x urem 8.
// Correct on unsigned values, and it turns a constant-time mask into a
// variable-latency remainder. Expected: CT-BREAKING.
builtin.module {
  pdl.pattern @mask_to_rem : benefit(1) {
    %type = pdl.type : i8

    %x = pdl.operand : %type
    %seven = pdl.attribute = 7 : i8
    %seven_op = pdl.operation "arith.constant" {"value" = %seven} -> (%type : !pdl.type)
    %seven_val = pdl.result 0 of %seven_op

    %mask = pdl.operation "arith.andi" (%x, %seven_val : !pdl.value, !pdl.value) -> (%type : !pdl.type)

    pdl.rewrite %mask {
      %eight = pdl.attribute = 8 : i8
      %eight_op = pdl.operation "arith.constant" {"value" = %eight} -> (%type : !pdl.type)
      %eight_val = pdl.result 0 of %eight_op
      %rem = pdl.operation "arith.remui" (%x, %eight_val : !pdl.value, !pdl.value) -> (%type : !pdl.type)
      pdl.replace %mask with %rem
    }
  }
}
