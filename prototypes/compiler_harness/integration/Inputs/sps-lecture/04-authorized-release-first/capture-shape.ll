; PEDAGOGICAL CAPTURE SHAPE ONLY: not canonical frozen.bc.

declare void @__sps_release_emit_v1_7fb6e6e656fdabb14c8552c05bb74c9301e07b8282418fa4fc4d99442fa85d0d(i8) #1

define internal void @release_secret(i8 %value) #0 {
entry:
  call ccc void @__sps_release_emit_v1_7fb6e6e656fdabb14c8552c05bb74c9301e07b8282418fa4fc4d99442fa85d0d(i8 %value) #1
  ret void
}

define i8 @fixture_entry(i8 %secret) {
entry:
  call ccc void @release_secret(i8 %secret)
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

attributes #0 = { noinline noduplicate nomerge nobuiltin "nooutline" }
attributes #1 = { nounwind willreturn memory(none) }
