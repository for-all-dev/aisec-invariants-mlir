; ModuleID = 'artifact.bc'
source_filename = "LLVMDialectModule"

declare ptr @malloc(i64)

declare void @free(ptr)

define void @alloca_size_fixed_region_copy_bad(i32 %0, ptr %1) {
  %3 = trunc i32 %0 to i8
  %4 = alloca i8, i32 8, align 1
  %5 = getelementptr i8, ptr %4, i32 0
  %6 = getelementptr i8, ptr %4, i32 4
  store i8 %3, ptr %5, align 1
  %7 = load i8, ptr %5, align 1
  store i8 %7, ptr %6, align 1
  %8 = load i8, ptr %6, align 1
  store i8 %8, ptr %1, align 1
  ret void
}

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
