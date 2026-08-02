; ModuleID = 'artifact.bc'
source_filename = "LLVMDialectModule"

declare ptr @malloc(i64)

declare void @free(ptr)

define void @pointer_rebinding_pointer_spill_unsupported(i32 %0, ptr %1, ptr %2, ptr %3) {
  %5 = icmp ne i32 %0, 0
  %6 = select i1 %5, ptr %2, ptr %1
  %7 = alloca ptr, i64 1, align 8
  store ptr %6, ptr %7, align 8
  %8 = load ptr, ptr %7, align 8
  %9 = load i8, ptr %8, align 1
  store i8 %9, ptr %3, align 1
  ret void
}

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
