; ModuleID = 'artifact.bc'
source_filename = "LLVMDialectModule"

declare ptr @malloc(i64)

declare void @free(ptr)

define void @alloca_size_high_count(i1 %0, ptr %1) {
  %3 = select i1 %0, i32 64, i32 128
  %4 = alloca i8, i32 %3, align 1
  store i8 0, ptr %4, align 1
  store i32 0, ptr %1, align 4
  ret void
}

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
