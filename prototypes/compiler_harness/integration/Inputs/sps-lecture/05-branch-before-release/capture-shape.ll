; PEDAGOGICAL CAPTURE SHAPE ONLY: not canonical frozen.bc.

declare void @llvm.sps.release(...)

define internal void @release_secret(i8 %value) #0 {
entry:
  call void (...) @llvm.sps.release(i8 %value)
  ret void
}

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
  call ccc void @release_secret(i8 %secret)
  ret i8 %private
}

attributes #0 = { noinline noduplicate nomerge nobuiltin "nooutline" }
