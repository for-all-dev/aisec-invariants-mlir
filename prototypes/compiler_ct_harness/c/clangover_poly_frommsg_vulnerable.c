/*
 * Clangover / ML-KEM poly_frommsg reduced reproduction.
 *
 * Provenance: https://github.com/antoonpurnal/clangover
 * Reference:  https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c
 * Report:     https://pqshield.com/pqshield-plugs-timing-leaks-in-kyber-ml-kem-to-improve-pqc-implementation-maturity/
 * Canonical check: Clang 16, x86-64, -Os (also try -O1 and -O2/-O3 -fno-vectorize).
 * Secret: msg.  The loop counters are public.
 * Expected unsafe instruction: secret-dependent x86 jcc (observed `jae`).
 * Classification: vulnerable compiler-reproduction reduction.
 *
 * The source is branchless.  Some Clang configurations recognize that mask
 * as either all zeroes or all ones and select a conditional branch instead.
 */
typedef unsigned char uint8_t;
typedef signed short int16_t;

__attribute__((noinline))
void clangover_poly_frommsg_vulnerable(int16_t out[256], const uint8_t msg[32]) {
  for (unsigned i = 0; i < 32; ++i) {
    for (unsigned j = 0; j < 8; ++j) {
      int16_t bit = (int16_t)((msg[i] >> j) & 1u);
      int16_t mask = (int16_t)-bit;
      out[8 * i + j] = (int16_t)(mask & 1665);
    }
  }
}
