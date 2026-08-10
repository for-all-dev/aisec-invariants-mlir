; ModuleID = 'artifact.bc'
source_filename = "LLVMDialectModule"

declare ptr @malloc(i64)

declare void @free(ptr)

define void @abi_alias_disjoint_control(i32 %0, ptr %1, ptr %2, ptr %3) {
  store i32 %0, ptr %1, align 4
  %5 = load i32, ptr %2, align 4
  store i32 %5, ptr %3, align 4
  ret void
}

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
