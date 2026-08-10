; PEDAGOGICAL CAPTURE SHAPE ONLY: not canonical frozen.bc.

define i8 @fixture_entry(i8 %secret) {
entry:
  %is_zero = icmp eq i8 %secret, 0
  %private = select i1 %is_zero, i8 17, i8 34
  ret i8 %private
}
