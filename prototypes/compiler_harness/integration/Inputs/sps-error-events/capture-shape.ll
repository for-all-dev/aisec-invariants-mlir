; HAND-AUTHORED FUTURE CAPTURE SHAPE. This is LLVM 17-readable source for a
; Pending PreflightV1 contract, not frozen LLVM 22.1.8 artifact.bc and not an
; SPS theorem input. The future materializer must recapture and bind stable IDs.
;
; The public selector gives the entry two static top-level return sites. The
; failure site is intended to bind DeclaredFailure(app.error); the ordinary
; site binds NormalValue. A zero public divisor exercises the separate
; verifier-UB totalization path and its mandatory verifier.ub-risk error field.
;
; CHECK-LABEL: define i8 @sps_error_fixture(
; CHECK: br i1 %public_fail, label %declared_failure, label %ordinary
; CHECK: declared_failure:
; CHECK-NEXT: ret i8 %secret_detail
; CHECK: ordinary:
; CHECK-NEXT: %quotient = udiv i8 42, %public_divisor
; CHECK-NEXT: ret i8 %quotient

target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"

define i8 @sps_error_fixture(i1 %public_fail, i8 %secret_detail, i8 %public_divisor) {
entry:
  br i1 %public_fail, label %declared_failure, label %ordinary

declared_failure:
  ret i8 %secret_detail

ordinary:
  %quotient = udiv i8 42, %public_divisor
  ret i8 %quotient
}
