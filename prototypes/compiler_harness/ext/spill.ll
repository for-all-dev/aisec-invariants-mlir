; ModuleID = 'spill.c'
source_filename = "spill.c"
target datalayout = "e-m:o-i64:64-i128:128-n32:64-S128"
target triple = "arm64-apple-macosx16.0.0"

@.str = private unnamed_addr constant [63 x i8] c"result=%llu  SECRET residue in freed frame = %u occurrence(s)\0A\00", align 1

; Function Attrs: noinline nounwind ssp uwtable(sync)
define i64 @crypt_region(i64 noundef %0, ptr nocapture noundef readonly %1, i32 noundef %2) local_unnamed_addr #0 align 64 {
  %4 = load i64, ptr %1, align 8, !tbaa !6
  %5 = getelementptr inbounds i64, ptr %1, i64 1
  %6 = load i64, ptr %5, align 8, !tbaa !6
  %7 = getelementptr inbounds i64, ptr %1, i64 2
  %8 = load i64, ptr %7, align 8, !tbaa !6
  %9 = getelementptr inbounds i64, ptr %1, i64 3
  %10 = load i64, ptr %9, align 8, !tbaa !6
  %11 = getelementptr inbounds i64, ptr %1, i64 4
  %12 = load i64, ptr %11, align 8, !tbaa !6
  %13 = getelementptr inbounds i64, ptr %1, i64 5
  %14 = load i64, ptr %13, align 8, !tbaa !6
  %15 = getelementptr inbounds i64, ptr %1, i64 6
  %16 = load i64, ptr %15, align 8, !tbaa !6
  %17 = getelementptr inbounds i64, ptr %1, i64 7
  %18 = load i64, ptr %17, align 8, !tbaa !6
  %19 = getelementptr inbounds i64, ptr %1, i64 8
  %20 = load i64, ptr %19, align 8, !tbaa !6
  %21 = getelementptr inbounds i64, ptr %1, i64 9
  %22 = load i64, ptr %21, align 8, !tbaa !6
  %23 = getelementptr inbounds i64, ptr %1, i64 10
  %24 = load i64, ptr %23, align 8, !tbaa !6
  %25 = getelementptr inbounds i64, ptr %1, i64 11
  %26 = load i64, ptr %25, align 8, !tbaa !6
  %27 = getelementptr inbounds i64, ptr %1, i64 12
  %28 = load i64, ptr %27, align 8, !tbaa !6
  %29 = getelementptr inbounds i64, ptr %1, i64 13
  %30 = load i64, ptr %29, align 8, !tbaa !6
  %31 = getelementptr inbounds i64, ptr %1, i64 14
  %32 = load i64, ptr %31, align 8, !tbaa !6
  %33 = getelementptr inbounds i64, ptr %1, i64 15
  %34 = load i64, ptr %33, align 8, !tbaa !6
  %35 = icmp eq i32 %2, 0
  br i1 %35, label %38, label %36

36:                                               ; preds = %3
  %37 = zext i32 %2 to i64
  br label %72

38:                                               ; preds = %72, %3
  %39 = phi i64 [ %6, %3 ], [ %93, %72 ]
  %40 = phi i64 [ %8, %3 ], [ %95, %72 ]
  %41 = phi i64 [ %10, %3 ], [ %97, %72 ]
  %42 = phi i64 [ %12, %3 ], [ %99, %72 ]
  %43 = phi i64 [ %14, %3 ], [ %101, %72 ]
  %44 = phi i64 [ %16, %3 ], [ %103, %72 ]
  %45 = phi i64 [ %18, %3 ], [ %105, %72 ]
  %46 = phi i64 [ %20, %3 ], [ %107, %72 ]
  %47 = phi i64 [ %22, %3 ], [ %109, %72 ]
  %48 = phi i64 [ %24, %3 ], [ %111, %72 ]
  %49 = phi i64 [ %26, %3 ], [ %113, %72 ]
  %50 = phi i64 [ %28, %3 ], [ %115, %72 ]
  %51 = phi i64 [ %30, %3 ], [ %117, %72 ]
  %52 = phi i64 [ %32, %3 ], [ %119, %72 ]
  %53 = phi i64 [ %34, %3 ], [ %121, %72 ]
  %54 = phi i64 [ %4, %3 ], [ %91, %72 ]
  %55 = xor i64 %40, %39
  %56 = xor i64 %55, %41
  %57 = xor i64 %56, %42
  %58 = xor i64 %57, %43
  %59 = xor i64 %58, %44
  %60 = xor i64 %59, %45
  %61 = xor i64 %60, %46
  %62 = xor i64 %61, %47
  %63 = xor i64 %62, %48
  %64 = xor i64 %63, %49
  %65 = xor i64 %64, %50
  %66 = xor i64 %65, %51
  %67 = xor i64 %66, %52
  %68 = xor i64 %67, %53
  %69 = xor i64 %68, %54
  %70 = lshr i64 %0, 60
  %71 = add i64 %69, %70
  tail call void asm sideeffect "", "r,r,~{memory}"(i64 0, i64 0) #6, !srcloc !10
  ret i64 %71

72:                                               ; preds = %36, %72
  %73 = phi i64 [ 0, %36 ], [ %122, %72 ]
  %74 = phi i64 [ %4, %36 ], [ %91, %72 ]
  %75 = phi i64 [ %34, %36 ], [ %121, %72 ]
  %76 = phi i64 [ %32, %36 ], [ %119, %72 ]
  %77 = phi i64 [ %30, %36 ], [ %117, %72 ]
  %78 = phi i64 [ %28, %36 ], [ %115, %72 ]
  %79 = phi i64 [ %26, %36 ], [ %113, %72 ]
  %80 = phi i64 [ %24, %36 ], [ %111, %72 ]
  %81 = phi i64 [ %22, %36 ], [ %109, %72 ]
  %82 = phi i64 [ %20, %36 ], [ %107, %72 ]
  %83 = phi i64 [ %18, %36 ], [ %105, %72 ]
  %84 = phi i64 [ %16, %36 ], [ %103, %72 ]
  %85 = phi i64 [ %14, %36 ], [ %101, %72 ]
  %86 = phi i64 [ %12, %36 ], [ %99, %72 ]
  %87 = phi i64 [ %10, %36 ], [ %97, %72 ]
  %88 = phi i64 [ %8, %36 ], [ %95, %72 ]
  %89 = phi i64 [ %6, %36 ], [ %93, %72 ]
  %90 = xor i64 %74, %73
  %91 = tail call i64 @opaque(i64 noundef %90) #6
  %92 = add i64 %91, %89
  %93 = tail call i64 @opaque(i64 noundef %92) #6
  %94 = xor i64 %93, %88
  %95 = tail call i64 @opaque(i64 noundef %94) #6
  %96 = add i64 %95, %87
  %97 = tail call i64 @opaque(i64 noundef %96) #6
  %98 = xor i64 %97, %86
  %99 = tail call i64 @opaque(i64 noundef %98) #6
  %100 = add i64 %99, %85
  %101 = tail call i64 @opaque(i64 noundef %100) #6
  %102 = xor i64 %101, %84
  %103 = tail call i64 @opaque(i64 noundef %102) #6
  %104 = add i64 %103, %83
  %105 = tail call i64 @opaque(i64 noundef %104) #6
  %106 = xor i64 %105, %82
  %107 = tail call i64 @opaque(i64 noundef %106) #6
  %108 = add i64 %107, %81
  %109 = tail call i64 @opaque(i64 noundef %108) #6
  %110 = xor i64 %109, %80
  %111 = tail call i64 @opaque(i64 noundef %110) #6
  %112 = add i64 %111, %79
  %113 = tail call i64 @opaque(i64 noundef %112) #6
  %114 = xor i64 %113, %78
  %115 = tail call i64 @opaque(i64 noundef %114) #6
  %116 = add i64 %115, %77
  %117 = tail call i64 @opaque(i64 noundef %116) #6
  %118 = xor i64 %117, %76
  %119 = tail call i64 @opaque(i64 noundef %118) #6
  %120 = add i64 %119, %75
  %121 = tail call i64 @opaque(i64 noundef %120) #6
  %122 = add nuw nsw i64 %73, 1
  %123 = icmp eq i64 %122, %37
  br i1 %123, label %38, label %72, !llvm.loop !11
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.start.p0(i64 immarg, ptr nocapture) #1

declare i64 @opaque(i64 noundef) local_unnamed_addr #2

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.end.p0(i64 immarg, ptr nocapture) #1

; Function Attrs: nounwind ssp uwtable(sync)
define i32 @main() local_unnamed_addr #3 {
  %1 = alloca [16 x i64], align 16
  call void @llvm.lifetime.start.p0(i64 128, ptr nonnull %1) #6
  store <2 x i64> <i64 4096, i64 4097>, ptr %1, align 16, !tbaa !6
  %2 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 2
  store <2 x i64> <i64 4098, i64 4099>, ptr %2, align 16, !tbaa !6
  %3 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 4
  store <2 x i64> <i64 4100, i64 4101>, ptr %3, align 16, !tbaa !6
  %4 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 6
  store <2 x i64> <i64 4102, i64 4103>, ptr %4, align 16, !tbaa !6
  %5 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 8
  store <2 x i64> <i64 4104, i64 4105>, ptr %5, align 16, !tbaa !6
  %6 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 10
  store <2 x i64> <i64 4106, i64 4107>, ptr %6, align 16, !tbaa !6
  %7 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 12
  store <2 x i64> <i64 4108, i64 4109>, ptr %7, align 16, !tbaa !6
  %8 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 14
  store <2 x i64> <i64 4110, i64 4111>, ptr %8, align 16, !tbaa !6
  %9 = call i64 @crypt_region(i64 noundef -4539648156078575603, ptr noundef nonnull %1, i32 noundef 3)
  tail call void @sink(i64 noundef %9) #6
  %10 = tail call fastcc i32 @probe_residue()
  %11 = tail call i32 (ptr, ...) @printf(ptr noundef nonnull dereferenceable(1) @.str, i64 noundef %9, i32 noundef %10)
  call void @llvm.lifetime.end.p0(i64 128, ptr nonnull %1) #6
  ret i32 0
}

declare void @sink(i64 noundef) local_unnamed_addr #2

; Function Attrs: nofree noinline nounwind ssp memory(inaccessiblemem: readwrite) uwtable(sync)
define internal fastcc i32 @probe_residue() unnamed_addr #4 align 64 {
  %1 = alloca [512 x i64], align 8
  call void @llvm.lifetime.start.p0(i64 4096, ptr nonnull %1) #6
  br label %3

2:                                                ; preds = %3
  call void @llvm.lifetime.end.p0(i64 4096, ptr nonnull %1) #6
  ret i32 %10

3:                                                ; preds = %0, %3
  %4 = phi i64 [ 0, %0 ], [ %11, %3 ]
  %5 = phi i32 [ 0, %0 ], [ %10, %3 ]
  %6 = getelementptr inbounds [512 x i64], ptr %1, i64 0, i64 %4
  %7 = load volatile i64, ptr %6, align 8, !tbaa !6
  %8 = icmp eq i64 %7, -4539648156078575603
  %9 = zext i1 %8 to i32
  %10 = add i32 %5, %9
  %11 = add nuw nsw i64 %4, 1
  %12 = icmp eq i64 %11, 512
  br i1 %12, label %2, label %3, !llvm.loop !13
}

; Function Attrs: nofree nounwind
declare noundef i32 @printf(ptr nocapture noundef readonly, ...) local_unnamed_addr #5

attributes #0 = { noinline nounwind ssp uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+crc,+dotprod,+fp-armv8,+fp16fml,+fullfp16,+lse,+neon,+ras,+rcpc,+rdm,+sha2,+sha3,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #1 = { mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite) }
attributes #2 = { "frame-pointer"="non-leaf" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+crc,+dotprod,+fp-armv8,+fp16fml,+fullfp16,+lse,+neon,+ras,+rcpc,+rdm,+sha2,+sha3,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #3 = { nounwind ssp uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+crc,+dotprod,+fp-armv8,+fp16fml,+fullfp16,+lse,+neon,+ras,+rcpc,+rdm,+sha2,+sha3,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #4 = { nofree noinline nounwind ssp memory(inaccessiblemem: readwrite) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+crc,+dotprod,+fp-armv8,+fp16fml,+fullfp16,+lse,+neon,+ras,+rcpc,+rdm,+sha2,+sha3,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #5 = { nofree nounwind "frame-pointer"="non-leaf" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+crc,+dotprod,+fp-armv8,+fp16fml,+fullfp16,+lse,+neon,+ras,+rcpc,+rdm,+sha2,+sha3,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #6 = { nounwind }

!llvm.module.flags = !{!0, !1, !2, !3, !4}
!llvm.ident = !{!5}

!0 = !{i32 2, !"SDK Version", [2 x i32] [i32 26, i32 5]}
!1 = !{i32 1, !"wchar_size", i32 4}
!2 = !{i32 8, !"PIC Level", i32 2}
!3 = !{i32 7, !"uwtable", i32 1}
!4 = !{i32 7, !"frame-pointer", i32 1}
!5 = !{!"Homebrew clang version 17.0.6"}
!6 = !{!7, !7, i64 0}
!7 = !{!"long long", !8, i64 0}
!8 = !{!"omnipotent char", !9, i64 0}
!9 = !{!"Simple C/C++ TBAA"}
!10 = !{i64 2566}
!11 = distinct !{!11, !12}
!12 = !{!"llvm.loop.mustprogress"}
!13 = distinct !{!13, !12}
