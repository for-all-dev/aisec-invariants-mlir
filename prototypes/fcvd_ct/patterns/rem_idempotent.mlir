// Idempotence: (x urem 8) urem 8 -> x urem 8.
// Both sides run divisions, so both traces carry observations; the rewrite is
// CT-preserving because everything the target observes, the source observed too.
builtin.module {
  pdl.pattern @rem_idempotent : benefit(1) {
    %type = pdl.type : i8

    %x = pdl.operand : %type
    %eight = pdl.attribute = 8 : i8
    %eight_op = pdl.operation "arith.constant" {"value" = %eight} -> (%type : !pdl.type)
    %eight_val = pdl.result 0 of %eight_op

    %inner = pdl.operation "arith.remui" (%x, %eight_val : !pdl.value, !pdl.value) -> (%type : !pdl.type)
    %inner_val = pdl.result 0 of %inner
    %outer = pdl.operation "arith.remui" (%inner_val, %eight_val : !pdl.value, !pdl.value) -> (%type : !pdl.type)

    pdl.rewrite %outer {
      pdl.replace %outer with (%inner_val : !pdl.value)
    }
  }
}
