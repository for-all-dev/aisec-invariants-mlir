; PEDAGOGICAL CAPTURE SHAPE ONLY: not canonical frozen.bc.

define i8 @fixture_entry(i8 %secret) {
entry:
  %is_zero = icmp eq i8 %secret, 0
  br i1 %is_zero, label %zero, label %nonzero

zero:
  br label %join

nonzero:
  br label %join

join:
  %private = phi i8 [ 17, %zero ], [ 34, %nonzero ]
  ret i8 %private
}
