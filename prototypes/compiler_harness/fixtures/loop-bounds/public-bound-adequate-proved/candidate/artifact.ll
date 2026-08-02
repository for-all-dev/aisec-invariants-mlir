; ModuleID = 'artifact.bc'
source_filename = "LLVMDialectModule"

declare ptr @malloc(i64)

declare void @free(ptr)

define void @bound_adequate_public_loop(i32 %0, ptr %1) {
  br label %3

3:                                                ; preds = %6, %2
  %4 = phi i32 [ %7, %6 ], [ 0, %2 ]
  %5 = icmp slt i32 %4, %0
  br i1 %5, label %6, label %8

6:                                                ; preds = %3
  %7 = add i32 %4, 1
  br label %3

8:                                                ; preds = %3
  store i32 0, ptr %1, align 4
  ret void
}

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
