// A control for the checker itself, not a rewrite anyone would write: replace
// x udiv 8 by y udiv 8, where y is a second operand the pattern binds.
// Both sides divide, so both traces carry observations -- but the target divides a
// value the source never touched, so two runs agreeing on x can still differ on y.
// Expected: CT-BREAKING. Without this case, a checker that reported "preserving"
// whenever the source leaks anything at all would still look correct on the rest of
// the corpus. `verify-pdl` calls this one unsound, as it should.
builtin.module {
  pdl.pattern @div_swap_operand : benefit(1) {
    %type = pdl.type : i8

    %x = pdl.operand : %type
    %y = pdl.operand : %type
    %eight = pdl.attribute = 8 : i8
    %eight_op = pdl.operation "arith.constant" {"value" = %eight} -> (%type : !pdl.type)
    %eight_val = pdl.result 0 of %eight_op

    %div = pdl.operation "arith.divui" (%x, %eight_val : !pdl.value, !pdl.value) -> (%type : !pdl.type)

    pdl.rewrite %div {
      %other = pdl.operation "arith.divui" (%y, %eight_val : !pdl.value, !pdl.value) -> (%type : !pdl.type)
      pdl.replace %div with %other
    }
  }
}
