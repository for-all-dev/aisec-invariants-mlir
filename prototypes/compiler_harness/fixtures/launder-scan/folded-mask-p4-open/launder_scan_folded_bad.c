/*
 * Case: laundering -- the constant-time mask that the optimizer folds back
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-compiler-introduced-reduction
 *
 * Relationship to upstream:
 *   Written for this harness. The idiom below is the standard branchless-select
 *   pattern used throughout cryptographic code; no specific body is copied.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   x, the buffer contents at p, and the returned blend
 *
 * Expected confidentiality issue:
 *   This file is written as a REPAIR of launder_scan_bad.c, using the standard
 *   arithmetic-mask idiom, and it does not work.
 *
 *   MEASURED, clang 17.0.6 -O2, x86_64-unknown-linux-gnu:
 *
 *     InstCombine recognizes (v & mask) | (x & ~mask) and folds it back:
 *         %5 = icmp eq i32 %0, 0
 *         %6 = select i1 %5, i64 %1, i64 %4     <- the mask is GONE
 *
 *     The emitted IR is BYTE-IDENTICAL to launder_scan_bad.c's, and the
 *     x86 backend then converts the select to a branch exactly as it does
 * there: testl %edi, %edi je    .LBB0_2
 *
 *   So the author wrote branchless code, the compiler recognized the intent,
 *   converted it to the very construct the author was avoiding, and a later
 * pass turned that into the branch the author was avoiding.
 *
 * Why this is the most instructive member of the family:
 *   launder_scan_bad.c leaks because it was written with a branch. This file
 *   leaks despite being written correctly. The difference matters because the
 *   first is a coding error and the second is not -- no amount of source review
 *   or developer training prevents it, and the two files are indistinguishable
 *   at LLVM IR, which is where an IR-level checker looks.
 *
 *   It also means "the corpus contains a fixed twin" is not evidence that a
 *   repair works. Only measuring the emitted code is.
 *
 * The repair that does work:
 *   launder_scan_fixed.c, which differs from this file by one inline-asm
 *   barrier on the mask. That barrier denies the optimizer the pattern match.
 *
 * Canonical compiler command:
 *   clang -I../../../include -O2 --target=x86_64-unknown-linux-gnu -S launder_scan_folded_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>
typedef unsigned long uint64_t;

SPS_ENTRY("launder_scan_folded_bad")
SPS_RETURN_OUTPUT("return")
uint64_t launder_scan_folded_bad(int secret SPS_COMPONENT("secret"),
                                 uint64_t x SPS_COMPONENT("x"),
                                 const uint64_t *p SPS_ROOT("p")) {
  uint64_t v = *p;
  uint64_t mask = (uint64_t)0 - (uint64_t)(secret != 0); /* all ones, or zero */
  /* Standard branchless blend. InstCombine folds this back into a select. */
  return (v & mask) | (x & ~mask);
}
