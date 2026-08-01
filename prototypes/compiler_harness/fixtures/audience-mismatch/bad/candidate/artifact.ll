; ModuleID = 'artifact.bc'
source_filename = "LLVMDialectModule"

declare ptr @malloc(i64)

declare void @free(ptr)

declare i32 @sps_release_masked_class_candidate(i32)

define void @audience_mismatch_bad(i32 %0, ptr %1, ptr %2) {
  %4 = call i32 @sps_release_masked_class_candidate(i32 %0)
  store i32 %4, ptr %1, align 4
  store i32 %4, ptr %2, align 4
  ret void
}

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
