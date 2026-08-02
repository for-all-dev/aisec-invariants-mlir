; ModuleID = 'artifact.bc'
source_filename = "LLVMDialectModule"

declare ptr @malloc(i64)

declare void @free(ptr)

define void @pointer_rebinding_same_allocation_control(i32 %0, ptr %1, ptr %2, ptr %3) {
  %5 = icmp ne i32 %0, 0
  %6 = select i1 %5, ptr %2, ptr %1
  %7 = load i8, ptr %6, align 1
  store i8 %7, ptr %3, align 1
  ret void
}

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
