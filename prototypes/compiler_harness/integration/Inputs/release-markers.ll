target triple = "x86_64-unknown-linux-gnu"

declare void @sink(i32)

define i32 @function_marker(i32 %raw) alwaysinline {
entry:
  ret i32 %raw
}

define void @function_user(i32 %raw) {
entry:
  %released = call i32 @function_marker(i32 %raw)
  call void @sink(i32 %released)
  ret void
}

define void @asm_user(i32 %raw) {
entry:
  %released = call i32 asm sideeffect "# sps.declassify id=$2", "=r,0,i,~{memory}"(i32 %raw, i32 7)
  call void @sink(i32 %released)
  ret void
}

define void @asm_returned_bypass(i32 %raw) {
entry:
  %released = call i32 asm sideeffect "# sps.declassify returned", "=r,0,~{memory}"(i32 returned %raw)
  call void @sink(i32 %released)
  ret void
}
