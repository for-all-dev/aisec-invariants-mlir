; ModuleID = 'spill.c'
source_filename = "spill.c"
target datalayout = "e-m:o-i64:64-i128:128-n32:64-S128"
target triple = "arm64-apple-macosx16.0.0"

@.str = private unnamed_addr constant [63 x i8] c"result=%llu  SECRET residue in freed frame = %u occurrence(s)\0A\00", align 1, !dbg !0

; Function Attrs: noinline nounwind ssp uwtable(sync)
define i64 @crypt_region(i64 noundef %0, ptr nocapture noundef readonly %1, i32 noundef %2) local_unnamed_addr #0 align 64 !dbg !19 {
  call void @llvm.dbg.value(metadata i64 %0, metadata !28, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata ptr %1, metadata !29, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i32 %2, metadata !30, metadata !DIExpression()), !dbg !51
  %4 = load i64, ptr %1, align 8, !dbg !52, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %4, metadata !31, metadata !DIExpression()), !dbg !51
  %5 = getelementptr inbounds i64, ptr %1, i64 1, !dbg !57
  %6 = load i64, ptr %5, align 8, !dbg !57, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %6, metadata !32, metadata !DIExpression()), !dbg !51
  %7 = getelementptr inbounds i64, ptr %1, i64 2, !dbg !58
  %8 = load i64, ptr %7, align 8, !dbg !58, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %8, metadata !33, metadata !DIExpression()), !dbg !51
  %9 = getelementptr inbounds i64, ptr %1, i64 3, !dbg !59
  %10 = load i64, ptr %9, align 8, !dbg !59, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %10, metadata !34, metadata !DIExpression()), !dbg !51
  %11 = getelementptr inbounds i64, ptr %1, i64 4, !dbg !60
  %12 = load i64, ptr %11, align 8, !dbg !60, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %12, metadata !35, metadata !DIExpression()), !dbg !51
  %13 = getelementptr inbounds i64, ptr %1, i64 5, !dbg !61
  %14 = load i64, ptr %13, align 8, !dbg !61, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %14, metadata !36, metadata !DIExpression()), !dbg !51
  %15 = getelementptr inbounds i64, ptr %1, i64 6, !dbg !62
  %16 = load i64, ptr %15, align 8, !dbg !62, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %16, metadata !37, metadata !DIExpression()), !dbg !51
  %17 = getelementptr inbounds i64, ptr %1, i64 7, !dbg !63
  %18 = load i64, ptr %17, align 8, !dbg !63, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %18, metadata !38, metadata !DIExpression()), !dbg !51
  %19 = getelementptr inbounds i64, ptr %1, i64 8, !dbg !64
  %20 = load i64, ptr %19, align 8, !dbg !64, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %20, metadata !39, metadata !DIExpression()), !dbg !51
  %21 = getelementptr inbounds i64, ptr %1, i64 9, !dbg !65
  %22 = load i64, ptr %21, align 8, !dbg !65, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %22, metadata !40, metadata !DIExpression()), !dbg !51
  %23 = getelementptr inbounds i64, ptr %1, i64 10, !dbg !66
  %24 = load i64, ptr %23, align 8, !dbg !66, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %24, metadata !41, metadata !DIExpression()), !dbg !51
  %25 = getelementptr inbounds i64, ptr %1, i64 11, !dbg !67
  %26 = load i64, ptr %25, align 8, !dbg !67, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %26, metadata !42, metadata !DIExpression()), !dbg !51
  %27 = getelementptr inbounds i64, ptr %1, i64 12, !dbg !68
  %28 = load i64, ptr %27, align 8, !dbg !68, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %28, metadata !43, metadata !DIExpression()), !dbg !51
  %29 = getelementptr inbounds i64, ptr %1, i64 13, !dbg !69
  %30 = load i64, ptr %29, align 8, !dbg !69, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %30, metadata !44, metadata !DIExpression()), !dbg !51
  %31 = getelementptr inbounds i64, ptr %1, i64 14, !dbg !70
  %32 = load i64, ptr %31, align 8, !dbg !70, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %32, metadata !45, metadata !DIExpression()), !dbg !51
  %33 = getelementptr inbounds i64, ptr %1, i64 15, !dbg !71
  %34 = load i64, ptr %33, align 8, !dbg !71, !tbaa !53
  call void @llvm.dbg.value(metadata i64 %34, metadata !46, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i32 0, metadata !47, metadata !DIExpression()), !dbg !72
  call void @llvm.dbg.value(metadata i64 %4, metadata !31, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %32, metadata !45, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %30, metadata !44, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %28, metadata !43, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %26, metadata !42, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %24, metadata !41, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %22, metadata !40, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %20, metadata !39, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %18, metadata !38, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %16, metadata !37, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %14, metadata !36, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %12, metadata !35, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %10, metadata !34, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %8, metadata !33, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %6, metadata !32, metadata !DIExpression()), !dbg !51
  %35 = icmp eq i32 %2, 0, !dbg !73
  br i1 %35, label %38, label %36, !dbg !75

36:                                               ; preds = %3
  %37 = zext i32 %2 to i64, !dbg !73
  br label %72, !dbg !75

38:                                               ; preds = %72, %3
  %39 = phi i64 [ %6, %3 ], [ %93, %72 ], !dbg !51
  %40 = phi i64 [ %8, %3 ], [ %95, %72 ], !dbg !51
  %41 = phi i64 [ %10, %3 ], [ %97, %72 ], !dbg !51
  %42 = phi i64 [ %12, %3 ], [ %99, %72 ], !dbg !51
  %43 = phi i64 [ %14, %3 ], [ %101, %72 ], !dbg !51
  %44 = phi i64 [ %16, %3 ], [ %103, %72 ], !dbg !51
  %45 = phi i64 [ %18, %3 ], [ %105, %72 ], !dbg !51
  %46 = phi i64 [ %20, %3 ], [ %107, %72 ], !dbg !51
  %47 = phi i64 [ %22, %3 ], [ %109, %72 ], !dbg !51
  %48 = phi i64 [ %24, %3 ], [ %111, %72 ], !dbg !51
  %49 = phi i64 [ %26, %3 ], [ %113, %72 ], !dbg !51
  %50 = phi i64 [ %28, %3 ], [ %115, %72 ], !dbg !51
  %51 = phi i64 [ %30, %3 ], [ %117, %72 ], !dbg !51
  %52 = phi i64 [ %32, %3 ], [ %119, %72 ], !dbg !51
  %53 = phi i64 [ %34, %3 ], [ %121, %72 ], !dbg !51
  %54 = phi i64 [ %4, %3 ], [ %91, %72 ], !dbg !51
  %55 = xor i64 %40, %39, !dbg !76
  %56 = xor i64 %55, %41, !dbg !77
  %57 = xor i64 %56, %42, !dbg !78
  %58 = xor i64 %57, %43, !dbg !79
  %59 = xor i64 %58, %44, !dbg !80
  %60 = xor i64 %59, %45, !dbg !81
  %61 = xor i64 %60, %46, !dbg !82
  %62 = xor i64 %61, %47, !dbg !83
  %63 = xor i64 %62, %48, !dbg !84
  %64 = xor i64 %63, %49, !dbg !85
  %65 = xor i64 %64, %50, !dbg !86
  %66 = xor i64 %65, %51, !dbg !87
  %67 = xor i64 %66, %52, !dbg !88
  %68 = xor i64 %67, %53, !dbg !89
  %69 = xor i64 %68, %54, !dbg !90
  call void @llvm.dbg.value(metadata i64 %69, metadata !49, metadata !DIExpression()), !dbg !51
  %70 = lshr i64 %0, 60, !dbg !91
  %71 = add i64 %69, %70, !dbg !92
  call void @llvm.dbg.value(metadata i64 %71, metadata !50, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !28, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !38, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !37, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !36, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !35, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !34, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !33, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !32, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !31, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !46, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !45, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !44, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !43, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !42, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !41, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !40, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !39, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 0, metadata !49, metadata !DIExpression()), !dbg !51
  tail call void asm sideeffect "", "r,r,~{memory}"(i64 0, i64 0) #8, !dbg !93, !srcloc !94
  ret i64 %71, !dbg !95

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
  call void @llvm.dbg.value(metadata i64 %74, metadata !31, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %73, metadata !47, metadata !DIExpression()), !dbg !72
  call void @llvm.dbg.value(metadata i64 %75, metadata !46, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %76, metadata !45, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %77, metadata !44, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %78, metadata !43, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %79, metadata !42, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %80, metadata !41, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %81, metadata !40, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %82, metadata !39, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %83, metadata !38, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %84, metadata !37, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %85, metadata !36, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %86, metadata !35, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %87, metadata !34, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %88, metadata !33, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.value(metadata i64 %89, metadata !32, metadata !DIExpression()), !dbg !51
  %90 = xor i64 %74, %73, !dbg !96
  %91 = tail call i64 @opaque(i64 noundef %90) #8, !dbg !98
  call void @llvm.dbg.value(metadata i64 %91, metadata !31, metadata !DIExpression()), !dbg !51
  %92 = add i64 %91, %89, !dbg !99
  %93 = tail call i64 @opaque(i64 noundef %92) #8, !dbg !100
  call void @llvm.dbg.value(metadata i64 %93, metadata !32, metadata !DIExpression()), !dbg !51
  %94 = xor i64 %93, %88, !dbg !101
  %95 = tail call i64 @opaque(i64 noundef %94) #8, !dbg !102
  call void @llvm.dbg.value(metadata i64 %95, metadata !33, metadata !DIExpression()), !dbg !51
  %96 = add i64 %95, %87, !dbg !103
  %97 = tail call i64 @opaque(i64 noundef %96) #8, !dbg !104
  call void @llvm.dbg.value(metadata i64 %97, metadata !34, metadata !DIExpression()), !dbg !51
  %98 = xor i64 %97, %86, !dbg !105
  %99 = tail call i64 @opaque(i64 noundef %98) #8, !dbg !106
  call void @llvm.dbg.value(metadata i64 %99, metadata !35, metadata !DIExpression()), !dbg !51
  %100 = add i64 %99, %85, !dbg !107
  %101 = tail call i64 @opaque(i64 noundef %100) #8, !dbg !108
  call void @llvm.dbg.value(metadata i64 %101, metadata !36, metadata !DIExpression()), !dbg !51
  %102 = xor i64 %101, %84, !dbg !109
  %103 = tail call i64 @opaque(i64 noundef %102) #8, !dbg !110
  call void @llvm.dbg.value(metadata i64 %103, metadata !37, metadata !DIExpression()), !dbg !51
  %104 = add i64 %103, %83, !dbg !111
  %105 = tail call i64 @opaque(i64 noundef %104) #8, !dbg !112
  call void @llvm.dbg.value(metadata i64 %105, metadata !38, metadata !DIExpression()), !dbg !51
  %106 = xor i64 %105, %82, !dbg !113
  %107 = tail call i64 @opaque(i64 noundef %106) #8, !dbg !114
  call void @llvm.dbg.value(metadata i64 %107, metadata !39, metadata !DIExpression()), !dbg !51
  %108 = add i64 %107, %81, !dbg !115
  %109 = tail call i64 @opaque(i64 noundef %108) #8, !dbg !116
  call void @llvm.dbg.value(metadata i64 %109, metadata !40, metadata !DIExpression()), !dbg !51
  %110 = xor i64 %109, %80, !dbg !117
  %111 = tail call i64 @opaque(i64 noundef %110) #8, !dbg !118
  call void @llvm.dbg.value(metadata i64 %111, metadata !41, metadata !DIExpression()), !dbg !51
  %112 = add i64 %111, %79, !dbg !119
  %113 = tail call i64 @opaque(i64 noundef %112) #8, !dbg !120
  call void @llvm.dbg.value(metadata i64 %113, metadata !42, metadata !DIExpression()), !dbg !51
  %114 = xor i64 %113, %78, !dbg !121
  %115 = tail call i64 @opaque(i64 noundef %114) #8, !dbg !122
  call void @llvm.dbg.value(metadata i64 %115, metadata !43, metadata !DIExpression()), !dbg !51
  %116 = add i64 %115, %77, !dbg !123
  %117 = tail call i64 @opaque(i64 noundef %116) #8, !dbg !124
  call void @llvm.dbg.value(metadata i64 %117, metadata !44, metadata !DIExpression()), !dbg !51
  %118 = xor i64 %117, %76, !dbg !125
  %119 = tail call i64 @opaque(i64 noundef %118) #8, !dbg !126
  call void @llvm.dbg.value(metadata i64 %119, metadata !45, metadata !DIExpression()), !dbg !51
  %120 = add i64 %119, %75, !dbg !127
  %121 = tail call i64 @opaque(i64 noundef %120) #8, !dbg !128
  call void @llvm.dbg.value(metadata i64 %121, metadata !46, metadata !DIExpression()), !dbg !51
  %122 = add nuw nsw i64 %73, 1, !dbg !129
  call void @llvm.dbg.value(metadata i64 %122, metadata !47, metadata !DIExpression()), !dbg !72
  %123 = icmp eq i64 %122, %37, !dbg !73
  br i1 %123, label %38, label %72, !dbg !75, !llvm.loop !130
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.start.p0(i64 immarg, ptr nocapture) #2

declare !dbg !133 i64 @opaque(i64 noundef) local_unnamed_addr #3

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.end.p0(i64 immarg, ptr nocapture) #2

; Function Attrs: nounwind ssp uwtable(sync)
define i32 @main() local_unnamed_addr #4 !dbg !136 {
  %1 = alloca [16 x i64], align 16
  call void @llvm.lifetime.start.p0(i64 128, ptr nonnull %1) #8, !dbg !149
  call void @llvm.dbg.declare(metadata ptr %1, metadata !141, metadata !DIExpression()), !dbg !150
  call void @llvm.dbg.value(metadata i32 0, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 0, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 1, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 1, metadata !145, metadata !DIExpression()), !dbg !151
  store <2 x i64> <i64 4096, i64 4097>, ptr %1, align 16, !dbg !152, !tbaa !53
  call void @llvm.dbg.value(metadata i64 2, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 2, metadata !145, metadata !DIExpression()), !dbg !151
  %2 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 2, !dbg !154
  call void @llvm.dbg.value(metadata i64 3, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 3, metadata !145, metadata !DIExpression()), !dbg !151
  store <2 x i64> <i64 4098, i64 4099>, ptr %2, align 16, !dbg !152, !tbaa !53
  call void @llvm.dbg.value(metadata i64 4, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 4, metadata !145, metadata !DIExpression()), !dbg !151
  %3 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 4, !dbg !154
  call void @llvm.dbg.value(metadata i64 5, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 5, metadata !145, metadata !DIExpression()), !dbg !151
  store <2 x i64> <i64 4100, i64 4101>, ptr %3, align 16, !dbg !152, !tbaa !53
  call void @llvm.dbg.value(metadata i64 6, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 6, metadata !145, metadata !DIExpression()), !dbg !151
  %4 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 6, !dbg !154
  call void @llvm.dbg.value(metadata i64 7, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 7, metadata !145, metadata !DIExpression()), !dbg !151
  store <2 x i64> <i64 4102, i64 4103>, ptr %4, align 16, !dbg !152, !tbaa !53
  call void @llvm.dbg.value(metadata i64 8, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 8, metadata !145, metadata !DIExpression()), !dbg !151
  %5 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 8, !dbg !154
  call void @llvm.dbg.value(metadata i64 9, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 9, metadata !145, metadata !DIExpression()), !dbg !151
  store <2 x i64> <i64 4104, i64 4105>, ptr %5, align 16, !dbg !152, !tbaa !53
  call void @llvm.dbg.value(metadata i64 10, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 10, metadata !145, metadata !DIExpression()), !dbg !151
  %6 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 10, !dbg !154
  call void @llvm.dbg.value(metadata i64 11, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 11, metadata !145, metadata !DIExpression()), !dbg !151
  store <2 x i64> <i64 4106, i64 4107>, ptr %6, align 16, !dbg !152, !tbaa !53
  call void @llvm.dbg.value(metadata i64 12, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 12, metadata !145, metadata !DIExpression()), !dbg !151
  %7 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 12, !dbg !154
  call void @llvm.dbg.value(metadata i64 13, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 13, metadata !145, metadata !DIExpression()), !dbg !151
  store <2 x i64> <i64 4108, i64 4109>, ptr %7, align 16, !dbg !152, !tbaa !53
  call void @llvm.dbg.value(metadata i64 14, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 14, metadata !145, metadata !DIExpression()), !dbg !151
  %8 = getelementptr inbounds [16 x i64], ptr %1, i64 0, i64 14, !dbg !154
  call void @llvm.dbg.value(metadata i64 15, metadata !145, metadata !DIExpression()), !dbg !151
  call void @llvm.dbg.value(metadata i64 15, metadata !145, metadata !DIExpression()), !dbg !151
  store <2 x i64> <i64 4110, i64 4111>, ptr %8, align 16, !dbg !152, !tbaa !53
  call void @llvm.dbg.value(metadata i64 16, metadata !145, metadata !DIExpression()), !dbg !151
  %9 = call i64 @crypt_region(i64 noundef -4539648156078575603, ptr noundef nonnull %1, i32 noundef 3), !dbg !155
  call void @llvm.dbg.value(metadata i64 %9, metadata !147, metadata !DIExpression()), !dbg !156
  tail call void @sink(i64 noundef %9) #8, !dbg !157
  %10 = tail call fastcc i32 @probe_residue(), !dbg !158
  call void @llvm.dbg.value(metadata i32 %10, metadata !148, metadata !DIExpression()), !dbg !156
  %11 = tail call i32 (ptr, ...) @printf(ptr noundef nonnull dereferenceable(1) @.str, i64 noundef %9, i32 noundef %10), !dbg !159
  call void @llvm.lifetime.end.p0(i64 128, ptr nonnull %1) #8, !dbg !160
  ret i32 0, !dbg !161
}

declare !dbg !162 void @sink(i64 noundef) local_unnamed_addr #3

; Function Attrs: nofree noinline nounwind ssp memory(inaccessiblemem: readwrite) uwtable(sync)
define internal fastcc i32 @probe_residue() unnamed_addr #5 align 64 !dbg !165 {
  %1 = alloca [512 x i64], align 8
  call void @llvm.dbg.value(metadata i64 -4539648156078575603, metadata !169, metadata !DIExpression()), !dbg !179
  call void @llvm.dbg.value(metadata i32 512, metadata !170, metadata !DIExpression()), !dbg !179
  call void @llvm.lifetime.start.p0(i64 4096, ptr nonnull %1) #8, !dbg !180
  call void @llvm.dbg.declare(metadata ptr %1, metadata !171, metadata !DIExpression()), !dbg !181
  call void @llvm.dbg.value(metadata i32 0, metadata !176, metadata !DIExpression()), !dbg !179
  call void @llvm.dbg.value(metadata i32 0, metadata !177, metadata !DIExpression()), !dbg !182
  br label %3, !dbg !183

2:                                                ; preds = %3
  call void @llvm.lifetime.end.p0(i64 4096, ptr nonnull %1) #8, !dbg !184
  ret i32 %10, !dbg !185

3:                                                ; preds = %0, %3
  %4 = phi i64 [ 0, %0 ], [ %11, %3 ]
  %5 = phi i32 [ 0, %0 ], [ %10, %3 ]
  call void @llvm.dbg.value(metadata i64 %4, metadata !177, metadata !DIExpression()), !dbg !182
  call void @llvm.dbg.value(metadata i32 %5, metadata !176, metadata !DIExpression()), !dbg !179
  %6 = getelementptr inbounds [512 x i64], ptr %1, i64 0, i64 %4, !dbg !186
  %7 = load volatile i64, ptr %6, align 8, !dbg !186, !tbaa !53
  %8 = icmp eq i64 %7, -4539648156078575603, !dbg !189
  %9 = zext i1 %8 to i32, !dbg !190
  %10 = add i32 %5, %9, !dbg !190
  call void @llvm.dbg.value(metadata i32 %10, metadata !176, metadata !DIExpression()), !dbg !179
  %11 = add nuw nsw i64 %4, 1, !dbg !191
  call void @llvm.dbg.value(metadata i64 %11, metadata !177, metadata !DIExpression()), !dbg !182
  %12 = icmp eq i64 %11, 512, !dbg !192
  br i1 %12, label %2, label %3, !dbg !183, !llvm.loop !193
}

; Function Attrs: nofree nounwind
declare !dbg !195 noundef i32 @printf(ptr nocapture noundef readonly, ...) local_unnamed_addr #6

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.value(metadata, metadata, metadata) #7

attributes #0 = { noinline nounwind ssp uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+crc,+dotprod,+fp-armv8,+fp16fml,+fullfp16,+lse,+neon,+ras,+rcpc,+rdm,+sha2,+sha3,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #1 = { mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #2 = { mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite) }
attributes #3 = { "frame-pointer"="non-leaf" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+crc,+dotprod,+fp-armv8,+fp16fml,+fullfp16,+lse,+neon,+ras,+rcpc,+rdm,+sha2,+sha3,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #4 = { nounwind ssp uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+crc,+dotprod,+fp-armv8,+fp16fml,+fullfp16,+lse,+neon,+ras,+rcpc,+rdm,+sha2,+sha3,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #5 = { nofree noinline nounwind ssp memory(inaccessiblemem: readwrite) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+crc,+dotprod,+fp-armv8,+fp16fml,+fullfp16,+lse,+neon,+ras,+rcpc,+rdm,+sha2,+sha3,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #6 = { nofree nounwind "frame-pointer"="non-leaf" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+crc,+dotprod,+fp-armv8,+fp16fml,+fullfp16,+lse,+neon,+ras,+rcpc,+rdm,+sha2,+sha3,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a,+zcm,+zcz" }
attributes #7 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #8 = { nounwind }

!llvm.module.flags = !{!7, !8, !9, !10, !11, !12, !13}
!llvm.dbg.cu = !{!14}
!llvm.ident = !{!18}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(scope: null, file: !2, line: 92, type: !3, isLocal: true, isDefinition: true)
!2 = !DIFile(filename: "spill.c", directory: "/Users/johnwu/code/aisec-invariants-mlir/prototypes/compiler_harness/ext")
!3 = !DICompositeType(tag: DW_TAG_array_type, baseType: !4, size: 504, elements: !5)
!4 = !DIBasicType(name: "char", size: 8, encoding: DW_ATE_signed_char)
!5 = !{!6}
!6 = !DISubrange(count: 63)
!7 = !{i32 2, !"SDK Version", [2 x i32] [i32 26, i32 5]}
!8 = !{i32 7, !"Dwarf Version", i32 4}
!9 = !{i32 2, !"Debug Info Version", i32 3}
!10 = !{i32 1, !"wchar_size", i32 4}
!11 = !{i32 8, !"PIC Level", i32 2}
!12 = !{i32 7, !"uwtable", i32 1}
!13 = !{i32 7, !"frame-pointer", i32 1}
!14 = distinct !DICompileUnit(language: DW_LANG_C11, file: !2, producer: "Homebrew clang version 17.0.6", isOptimized: true, runtimeVersion: 0, emissionKind: FullDebug, retainedTypes: !15, globals: !17, splitDebugInlining: false, nameTableKind: Apple, sysroot: "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk", sdk: "MacOSX.sdk")
!15 = !{!16}
!16 = !DIBasicType(name: "unsigned long long", size: 64, encoding: DW_ATE_unsigned)
!17 = !{!0}
!18 = !{!"Homebrew clang version 17.0.6"}
!19 = distinct !DISubprogram(name: "crypt_region", scope: !2, file: !2, line: 31, type: !20, scopeLine: 32, flags: DIFlagPrototyped | DIFlagAllCallsDescribed, spFlags: DISPFlagDefinition | DISPFlagOptimized, unit: !14, retainedNodes: !27)
!20 = !DISubroutineType(types: !21)
!21 = !{!22, !22, !24, !26}
!22 = !DIDerivedType(tag: DW_TAG_typedef, name: "uint64_t", file: !23, line: 31, baseType: !16)
!23 = !DIFile(filename: "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include/_types/_uint64_t.h", directory: "")
!24 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: !25, size: 64)
!25 = !DIDerivedType(tag: DW_TAG_const_type, baseType: !22)
!26 = !DIBasicType(name: "unsigned int", size: 32, encoding: DW_ATE_unsigned)
!27 = !{!28, !29, !30, !31, !32, !33, !34, !35, !36, !37, !38, !39, !40, !41, !42, !43, !44, !45, !46, !47, !49, !50}
!28 = !DILocalVariable(name: "key", arg: 1, scope: !19, file: !2, line: 31, type: !22)
!29 = !DILocalVariable(name: "in", arg: 2, scope: !19, file: !2, line: 31, type: !24)
!30 = !DILocalVariable(name: "n", arg: 3, scope: !19, file: !2, line: 31, type: !26)
!31 = !DILocalVariable(name: "a", scope: !19, file: !2, line: 33, type: !22)
!32 = !DILocalVariable(name: "b", scope: !19, file: !2, line: 33, type: !22)
!33 = !DILocalVariable(name: "c", scope: !19, file: !2, line: 33, type: !22)
!34 = !DILocalVariable(name: "d", scope: !19, file: !2, line: 33, type: !22)
!35 = !DILocalVariable(name: "e", scope: !19, file: !2, line: 34, type: !22)
!36 = !DILocalVariable(name: "f", scope: !19, file: !2, line: 34, type: !22)
!37 = !DILocalVariable(name: "g", scope: !19, file: !2, line: 34, type: !22)
!38 = !DILocalVariable(name: "h", scope: !19, file: !2, line: 34, type: !22)
!39 = !DILocalVariable(name: "i", scope: !19, file: !2, line: 35, type: !22)
!40 = !DILocalVariable(name: "j", scope: !19, file: !2, line: 35, type: !22)
!41 = !DILocalVariable(name: "k", scope: !19, file: !2, line: 35, type: !22)
!42 = !DILocalVariable(name: "l", scope: !19, file: !2, line: 35, type: !22)
!43 = !DILocalVariable(name: "m", scope: !19, file: !2, line: 36, type: !22)
!44 = !DILocalVariable(name: "o", scope: !19, file: !2, line: 36, type: !22)
!45 = !DILocalVariable(name: "p", scope: !19, file: !2, line: 36, type: !22)
!46 = !DILocalVariable(name: "q", scope: !19, file: !2, line: 36, type: !22)
!47 = !DILocalVariable(name: "t", scope: !48, file: !2, line: 38, type: !26)
!48 = distinct !DILexicalBlock(scope: !19, file: !2, line: 38, column: 5)
!49 = !DILocalVariable(name: "acc", scope: !19, file: !2, line: 59, type: !22)
!50 = !DILocalVariable(name: "res", scope: !19, file: !2, line: 61, type: !22)
!51 = !DILocation(line: 0, scope: !19)
!52 = !DILocation(line: 33, column: 18, scope: !19)
!53 = !{!54, !54, i64 0}
!54 = !{!"long long", !55, i64 0}
!55 = !{!"omnipotent char", !56, i64 0}
!56 = !{!"Simple C/C++ TBAA"}
!57 = !DILocation(line: 33, column: 29, scope: !19)
!58 = !DILocation(line: 33, column: 40, scope: !19)
!59 = !DILocation(line: 33, column: 51, scope: !19)
!60 = !DILocation(line: 34, column: 18, scope: !19)
!61 = !DILocation(line: 34, column: 29, scope: !19)
!62 = !DILocation(line: 34, column: 40, scope: !19)
!63 = !DILocation(line: 34, column: 51, scope: !19)
!64 = !DILocation(line: 35, column: 18, scope: !19)
!65 = !DILocation(line: 35, column: 29, scope: !19)
!66 = !DILocation(line: 35, column: 40, scope: !19)
!67 = !DILocation(line: 35, column: 52, scope: !19)
!68 = !DILocation(line: 36, column: 18, scope: !19)
!69 = !DILocation(line: 36, column: 30, scope: !19)
!70 = !DILocation(line: 36, column: 42, scope: !19)
!71 = !DILocation(line: 36, column: 54, scope: !19)
!72 = !DILocation(line: 0, scope: !48)
!73 = !DILocation(line: 38, column: 28, scope: !74)
!74 = distinct !DILexicalBlock(scope: !48, file: !2, line: 38, column: 5)
!75 = !DILocation(line: 38, column: 5, scope: !48)
!76 = !DILocation(line: 59, column: 22, scope: !19)
!77 = !DILocation(line: 59, column: 26, scope: !19)
!78 = !DILocation(line: 59, column: 30, scope: !19)
!79 = !DILocation(line: 59, column: 34, scope: !19)
!80 = !DILocation(line: 59, column: 38, scope: !19)
!81 = !DILocation(line: 59, column: 42, scope: !19)
!82 = !DILocation(line: 59, column: 46, scope: !19)
!83 = !DILocation(line: 60, column: 18, scope: !19)
!84 = !DILocation(line: 60, column: 22, scope: !19)
!85 = !DILocation(line: 60, column: 26, scope: !19)
!86 = !DILocation(line: 60, column: 30, scope: !19)
!87 = !DILocation(line: 60, column: 34, scope: !19)
!88 = !DILocation(line: 60, column: 38, scope: !19)
!89 = !DILocation(line: 60, column: 42, scope: !19)
!90 = !DILocation(line: 60, column: 46, scope: !19)
!91 = !DILocation(line: 61, column: 31, scope: !19)
!92 = !DILocation(line: 61, column: 24, scope: !19)
!93 = !DILocation(line: 67, column: 5, scope: !19)
!94 = !{i64 2566}
!95 = !DILocation(line: 69, column: 5, scope: !19)
!96 = !DILocation(line: 39, column: 22, scope: !97)
!97 = distinct !DILexicalBlock(scope: !74, file: !2, line: 38, column: 38)
!98 = !DILocation(line: 39, column: 13, scope: !97)
!99 = !DILocation(line: 40, column: 22, scope: !97)
!100 = !DILocation(line: 40, column: 13, scope: !97)
!101 = !DILocation(line: 41, column: 22, scope: !97)
!102 = !DILocation(line: 41, column: 13, scope: !97)
!103 = !DILocation(line: 42, column: 22, scope: !97)
!104 = !DILocation(line: 42, column: 13, scope: !97)
!105 = !DILocation(line: 43, column: 22, scope: !97)
!106 = !DILocation(line: 43, column: 13, scope: !97)
!107 = !DILocation(line: 44, column: 22, scope: !97)
!108 = !DILocation(line: 44, column: 13, scope: !97)
!109 = !DILocation(line: 45, column: 22, scope: !97)
!110 = !DILocation(line: 45, column: 13, scope: !97)
!111 = !DILocation(line: 46, column: 22, scope: !97)
!112 = !DILocation(line: 46, column: 13, scope: !97)
!113 = !DILocation(line: 47, column: 22, scope: !97)
!114 = !DILocation(line: 47, column: 13, scope: !97)
!115 = !DILocation(line: 48, column: 22, scope: !97)
!116 = !DILocation(line: 48, column: 13, scope: !97)
!117 = !DILocation(line: 49, column: 22, scope: !97)
!118 = !DILocation(line: 49, column: 13, scope: !97)
!119 = !DILocation(line: 50, column: 22, scope: !97)
!120 = !DILocation(line: 50, column: 13, scope: !97)
!121 = !DILocation(line: 51, column: 22, scope: !97)
!122 = !DILocation(line: 51, column: 13, scope: !97)
!123 = !DILocation(line: 52, column: 22, scope: !97)
!124 = !DILocation(line: 52, column: 13, scope: !97)
!125 = !DILocation(line: 53, column: 22, scope: !97)
!126 = !DILocation(line: 53, column: 13, scope: !97)
!127 = !DILocation(line: 54, column: 22, scope: !97)
!128 = !DILocation(line: 54, column: 13, scope: !97)
!129 = !DILocation(line: 38, column: 34, scope: !74)
!130 = distinct !{!130, !75, !131, !132}
!131 = !DILocation(line: 55, column: 5, scope: !48)
!132 = !{!"llvm.loop.mustprogress"}
!133 = !DISubprogram(name: "opaque", scope: !2, file: !2, line: 22, type: !134, flags: DIFlagPrototyped, spFlags: DISPFlagOptimized)
!134 = !DISubroutineType(types: !135)
!135 = !{!22, !22}
!136 = distinct !DISubprogram(name: "main", scope: !2, file: !2, line: 83, type: !137, scopeLine: 84, flags: DIFlagPrototyped | DIFlagAllCallsDescribed, spFlags: DISPFlagDefinition | DISPFlagOptimized, unit: !14, retainedNodes: !140)
!137 = !DISubroutineType(types: !138)
!138 = !{!139}
!139 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!140 = !{!141, !145, !147, !148}
!141 = !DILocalVariable(name: "in", scope: !136, file: !2, line: 85, type: !142)
!142 = !DICompositeType(tag: DW_TAG_array_type, baseType: !22, size: 1024, elements: !143)
!143 = !{!144}
!144 = !DISubrange(count: 16)
!145 = !DILocalVariable(name: "x", scope: !146, file: !2, line: 86, type: !26)
!146 = distinct !DILexicalBlock(scope: !136, file: !2, line: 86, column: 5)
!147 = !DILocalVariable(name: "r", scope: !136, file: !2, line: 88, type: !22)
!148 = !DILocalVariable(name: "hits", scope: !136, file: !2, line: 91, type: !26)
!149 = !DILocation(line: 85, column: 5, scope: !136)
!150 = !DILocation(line: 85, column: 14, scope: !136)
!151 = !DILocation(line: 0, scope: !146)
!152 = !DILocation(line: 86, column: 45, scope: !153)
!153 = distinct !DILexicalBlock(scope: !146, file: !2, line: 86, column: 5)
!154 = !DILocation(line: 86, column: 39, scope: !153)
!155 = !DILocation(line: 88, column: 18, scope: !136)
!156 = !DILocation(line: 0, scope: !136)
!157 = !DILocation(line: 89, column: 5, scope: !136)
!158 = !DILocation(line: 91, column: 21, scope: !136)
!159 = !DILocation(line: 92, column: 5, scope: !136)
!160 = !DILocation(line: 95, column: 1, scope: !136)
!161 = !DILocation(line: 94, column: 5, scope: !136)
!162 = !DISubprogram(name: "sink", scope: !2, file: !2, line: 23, type: !163, flags: DIFlagPrototyped, spFlags: DISPFlagOptimized)
!163 = !DISubroutineType(types: !164)
!164 = !{null, !22}
!165 = distinct !DISubprogram(name: "probe_residue", scope: !2, file: !2, line: 74, type: !166, scopeLine: 75, flags: DIFlagPrototyped | DIFlagAllCallsDescribed, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition | DISPFlagOptimized, unit: !14, retainedNodes: !168)
!166 = !DISubroutineType(cc: DW_CC_nocall, types: !167)
!167 = !{!26, !22, !26}
!168 = !{!169, !170, !171, !176, !177}
!169 = !DILocalVariable(name: "pattern", arg: 1, scope: !165, file: !2, line: 74, type: !22)
!170 = !DILocalVariable(name: "words", arg: 2, scope: !165, file: !2, line: 74, type: !26)
!171 = !DILocalVariable(name: "buf", scope: !165, file: !2, line: 76, type: !172)
!172 = !DICompositeType(tag: DW_TAG_array_type, baseType: !173, size: 32768, elements: !174)
!173 = !DIDerivedType(tag: DW_TAG_volatile_type, baseType: !22)
!174 = !{!175}
!175 = !DISubrange(count: 512)
!176 = !DILocalVariable(name: "hits", scope: !165, file: !2, line: 77, type: !26)
!177 = !DILocalVariable(name: "x", scope: !178, file: !2, line: 78, type: !26)
!178 = distinct !DILexicalBlock(scope: !165, file: !2, line: 78, column: 5)
!179 = !DILocation(line: 0, scope: !165)
!180 = !DILocation(line: 76, column: 5, scope: !165)
!181 = !DILocation(line: 76, column: 23, scope: !165)
!182 = !DILocation(line: 0, scope: !178)
!183 = !DILocation(line: 78, column: 5, scope: !178)
!184 = !DILocation(line: 81, column: 1, scope: !165)
!185 = !DILocation(line: 80, column: 5, scope: !165)
!186 = !DILocation(line: 79, column: 13, scope: !187)
!187 = distinct !DILexicalBlock(scope: !188, file: !2, line: 79, column: 13)
!188 = distinct !DILexicalBlock(scope: !178, file: !2, line: 78, column: 5)
!189 = !DILocation(line: 79, column: 20, scope: !187)
!190 = !DILocation(line: 79, column: 13, scope: !188)
!191 = !DILocation(line: 78, column: 49, scope: !188)
!192 = !DILocation(line: 78, column: 36, scope: !188)
!193 = distinct !{!193, !183, !194, !132}
!194 = !DILocation(line: 79, column: 36, scope: !178)
!195 = !DISubprogram(name: "printf", scope: !196, file: !196, line: 34, type: !197, flags: DIFlagPrototyped, spFlags: DISPFlagOptimized)
!196 = !DIFile(filename: "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include/_printf.h", directory: "")
!197 = !DISubroutineType(types: !198)
!198 = !{!139, !199, null}
!199 = !DIDerivedType(tag: DW_TAG_restrict_type, baseType: !200)
!200 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: !201, size: 64)
!201 = !DIDerivedType(tag: DW_TAG_const_type, baseType: !4)
