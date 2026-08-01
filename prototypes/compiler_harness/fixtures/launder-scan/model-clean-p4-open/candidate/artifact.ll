; ModuleID = 'artifact.bc'
source_filename = "LLVMDialectModule"

declare ptr @malloc(i64)

declare void @free(ptr)

define void @launder_scan_model_proved(i32 %0, i64 %1, ptr %2, ptr %3) {
  %5 = load i64, ptr %2, align 4
  %6 = icmp ne i32 %0, 0
  %7 = select i1 %6, i64 %5, i64 %1
  store i64 %7, ptr %3, align 4
  ret void
}

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
