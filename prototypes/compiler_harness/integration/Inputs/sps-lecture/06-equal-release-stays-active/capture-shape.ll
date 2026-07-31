; PEDAGOGICAL CAPTURE SHAPE ONLY: not canonical frozen.bc.

declare void @__sps_release_emit_v1_28fe3bc98c4bf216de7f7bb9f982275a4b96866e157ce19cea364d25eda1f7ec(i1) #1

define internal void @release_bit(i1 %value) #0 {
entry:
  call ccc void @__sps_release_emit_v1_28fe3bc98c4bf216de7f7bb9f982275a4b96866e157ce19cea364d25eda1f7ec(i1 %value) #1
  ret void
}

define i8 @fixture_entry(i8 %secret) {
entry:
  %low = trunc i8 %secret to i1
  call ccc void @release_bit(i1 %low)
  %high_mask = and i8 %secret, 2
  %high = icmp ne i8 %high_mask, 0
  br i1 %high, label %one, label %zero

one:
  br label %join

zero:
  br label %join

join:
  %private = phi i8 [ 34, %one ], [ 17, %zero ]
  ret i8 %private
}

attributes #0 = { noinline noduplicate nomerge nobuiltin "nooutline" }
attributes #1 = { nounwind willreturn memory(none) }
