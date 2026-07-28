// Sanity control: x * 8 -> x shl 3. Neither side contains an operation the
// leakage model considers observable, so the property holds vacuously.
// Expected: CT-PRESERVING with zero observations on both sides.
builtin.module {
  pdl.pattern @mul_to_shl : benefit(1) {
    %type = pdl.type : i8

    %x = pdl.operand : %type
    %eight = pdl.attribute = 8 : i8
    %eight_op = pdl.operation "arith.constant" {"value" = %eight} -> (%type : !pdl.type)
    %eight_val = pdl.result 0 of %eight_op

    %mul = pdl.operation "arith.muli" (%x, %eight_val : !pdl.value, !pdl.value) -> (%type : !pdl.type)

    pdl.rewrite %mul {
      %three = pdl.attribute = 3 : i8
      %three_op = pdl.operation "arith.constant" {"value" = %three} -> (%type : !pdl.type)
      %three_val = pdl.result 0 of %three_op
      %shl = pdl.operation "arith.shli" (%x, %three_val : !pdl.value, !pdl.value) -> (%type : !pdl.type)
      pdl.replace %mul with %shl
    }
  }
}
