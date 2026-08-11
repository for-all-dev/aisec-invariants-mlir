/*
 * Case: laundering -- branchless IR, secret-dependent branch in the binary
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-compiler-introduced-reduction
 *
 * Relationship to upstream:
 *   Written for this harness. No upstream body is copied. This reduces no
 * single incident; the mechanism is a default-enabled backend pass.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   x, the buffer contents at p, and the returned blend
 *
 * Expected confidentiality issue:
 *   MEASURED with clang/llc 17.0.6, all three steps:
 *
 *     LLVM IR, -O2, any target:
 *         %4 = load i64, ptr %2
 *         %6 = select i1 %5, i64 %1, i64 %4      <- NO br i1. Branchless.
 *
 *     x86-64 asm, -O2, DEFAULT flags:
 *         testl %edi, %edi
 *         je    .LBB0_2                          <- BRANCH ON THE SECRET
 *         movq  (%rdx), %rax                     <- load now CONDITIONAL
 *
 *     aarch64 asm, -O2, same IR:
 *         csel  x0, x1, x8, eq                   <- branchless, no leak
 *
 *   So the artifact is clean at LLVM IR, leaky on one target, and safe on
 *   another. An IR-level checker reports verified for all targets.
 *
 * Mechanism:
 *   X86CmovConversion is enabled by default, and its ForceMemOperand path
 *   ("convert cmovs to branches whenever they have memory operands") is also
 *   default-on and runs with NO profitability check -- it rewrites every such
 *   cmov in every block. The select here has a memory operand, so it is
 *   unconditionally converted.
 *
 * Second-order damage:
 *   The load moves from unconditional to conditional. So it is not only the
 *   timing that becomes secret-dependent: the MEMORY EVENT TRACE does too. A
 *   model that reasons only about branch direction misses half of this.
 *
 * Why this fixture is not like the others:
 *   Every other bad fixture here describes a leak a PROGRAMMER wrote, present
 * in the source and findable by review. This leak is absent from the source and
 *   absent from the analysed IR. It is a missing AXIS rather than a missing
 *   case: nothing else in the corpus asserts anything about a level below the
 *   one it analyses.
 *
 * Canonical compiler command:
 *   clang -I../../../include -O2 --target=x86_64-unknown-linux-gnu -S launder_scan_bad.c
 *   (contrast: -x86-cmov-converter-force-mem-operand=false emits cmovneq)
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>
typedef unsigned long uint64_t;

SPS_ENTRY("launder_scan_model_proved")
SPS_RETURN_OUTPUT("return")
uint64_t launder_scan_bad(int secret SPS_COMPONENT("secret"),
                          uint64_t x SPS_COMPONENT("x"),
                          const uint64_t *p SPS_ROOT("p")) {
  uint64_t v = *p; /* unconditional load, so the ternary becomes a select */
  return secret
             ? v
             : x; /* select with a memory operand -> forcibly branched on x86 */
}
