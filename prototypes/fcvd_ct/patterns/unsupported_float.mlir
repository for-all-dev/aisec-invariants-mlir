// Coverage control: floating point has no semantics upstream, so this rewrite must
// come back UNKNOWN. A tool that reported CT-PRESERVING here would be reporting the
// absence of a model as the absence of a leak.
builtin.module {
  pdl.pattern @unsupported_float : benefit(1) {
    %type = pdl.type : f32

    %x = pdl.operand : %type
    %y = pdl.operand : %type

    %add = pdl.operation "arith.addf" (%x, %y : !pdl.value, !pdl.value) -> (%type : !pdl.type)

    pdl.rewrite %add {
      %swapped = pdl.operation "arith.addf" (%y, %x : !pdl.value, !pdl.value) -> (%type : !pdl.type)
      pdl.replace %add with %swapped
    }
  }
}
