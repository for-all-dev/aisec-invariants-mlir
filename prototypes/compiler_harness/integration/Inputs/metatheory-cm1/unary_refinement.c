/*
 * Case: MT-CM1 unary P4 refinement does not preserve confidentiality
 *
 * WHAT THIS IS.
 *   Encodes countermodel MT-CM1 from the SPS Rev-4 metatheory, whose invalid
 *   principle is "unary P4 refinement preserves confidentiality" (metatheory
 *   section 0.2 table). Section 15 states the tempting rule as: if each
 *   concrete one-run trace is allowed by an ideal contract and the ideal
 *   contract is secure, then the concrete mechanism is secure.
 *
 *   The ideal component makes a nondeterministic choice r in {64,128} that is
 *   INDEPENDENT of the secret bit h and emits send_length(r). Its declared
 *   two-run coupling requires the SAME r on both sides, so for any two secret
 *   values and every coupled ideal choice the visible lengths agree: the ideal
 *   is secure.
 *
 *   The concrete component emits send_length(64) when h=0 and send_length(128)
 *   when h=1. Every single concrete trace is a member of the ideal trace set
 *   {send_length(64), send_length(128)}, so ordinary unary trace refinement
 *   holds. The pair h1=0, h2=1 nevertheless emits different lengths and leaks
 *   the bit.
 *
 *   The two unary ideal witnesses that certify the concrete runs choose 64 and
 *   128 respectively, which violates the ideal same-choice coupling. So
 *   PairedRefines_A(C,J) fails, exactly where it should. Metatheory section
 *   13.1 is explicit that the ideal witnesses "cannot be chosen independently
 *   for the two runs" and that "that jointness is the property missing from
 *   unary trace refinement"; A-P4 (section on paired conformance and closed
 *   deployment) requires PairedRefines_A of every refinement-bearing backend,
 *   library, runtime, and mechanism component before any real-deployment claim.
 *
 * WHAT THIS IS NOT.
 *   This program computes no ModelStatus, no DeploymentStatus, and no
 *   PolicyReviewStatus. It is a concrete two-run witness for one arithmetic
 *   fact about refinement, at the PreflightV1 tier.
 *
 * Canonical compiler command:
 *   clang -std=c11 -O2 --target=x86_64-unknown-linux-gnu -S -emit-llvm \
 *     unary_refinement.c
 *
 * License note:
 *   Written for this harness; no upstream code is reproduced.
 */
/* Declared rather than included: the harness compiles this file both natively
 * and with a cross target that has no C library headers available. */
extern int printf(const char *format, ...);

/* Ideal: the emitted length is a function of the ideal choice alone. The
 * secret is accepted and ignored, which is what makes the ideal secure. */
unsigned int mt_cm1_ideal_send_length(unsigned int secret_bit,
                                      unsigned int ideal_choice) {
  (void)secret_bit;
  return ideal_choice ? 128u : 64u;
}

/* Concrete: the same two lengths, selected by the secret bit. */
unsigned int mt_cm1_concrete_send_length(unsigned int secret_bit) {
  return secret_bit ? 128u : 64u;
}

/* Membership in the ideal one-run trace set {send_length(64),
 * send_length(128)}. This is the whole content of unary refinement. */
static int in_ideal_trace_set(unsigned int length) {
  return length == 64u || length == 128u;
}

int main(void) {
  unsigned int concrete_low = mt_cm1_concrete_send_length(0u);
  unsigned int concrete_high = mt_cm1_concrete_send_length(1u);
  unsigned int ideal_coupled_zero_lane1 = mt_cm1_ideal_send_length(0u, 0u);
  unsigned int ideal_coupled_zero_lane2 = mt_cm1_ideal_send_length(1u, 0u);
  unsigned int ideal_coupled_one_lane1 = mt_cm1_ideal_send_length(0u, 1u);
  unsigned int ideal_coupled_one_lane2 = mt_cm1_ideal_send_length(1u, 1u);

  printf("MT-CM1 two-run witness; tier=PreflightV1; no status is computed\n");
  printf("ideal one-run trace set: send_length(64) send_length(128)\n");

  printf("unary h=0: send_length(%u) in-ideal-set=%s\n", concrete_low,
         in_ideal_trace_set(concrete_low) ? "yes" : "no");
  printf("unary h=1: send_length(%u) in-ideal-set=%s\n", concrete_high,
         in_ideal_trace_set(concrete_high) ? "yes" : "no");
  printf("UnaryRefines(C,J): HOLDS\n");

  printf("ideal coupled pair r=0: lane1=%u lane2=%u equal=%s\n",
         ideal_coupled_zero_lane1, ideal_coupled_zero_lane2,
         ideal_coupled_zero_lane1 == ideal_coupled_zero_lane2 ? "yes" : "no");
  printf("ideal coupled pair r=1: lane1=%u lane2=%u equal=%s\n",
         ideal_coupled_one_lane1, ideal_coupled_one_lane2,
         ideal_coupled_one_lane1 == ideal_coupled_one_lane2 ? "yes" : "no");
  printf("Secure(J): the ideal agrees on every coupled choice\n");

  printf("concrete pair h1=0 h2=1: lane1=%u lane2=%u equal=%s\n", concrete_low,
         concrete_high, concrete_low == concrete_high ? "yes" : "no");
  printf("ideal witnesses needed for that concrete pair: r_lane1=0 r_lane2=1\n");
  printf("same-choice coupling: VIOLATED\n");
  printf("PairedRefines_A(C,J): FAILS\n");
  printf("conclusion: unary refinement does not lift to the two-run property\n");
  return 0;
}
