/*
 * KyberSlash1 fixed multiply/shift reduction from the official patch.
 * The input domain is the same normalized coefficient as the vulnerable
 * function.  The division is replaced by a Barrett-style constant multiply.
 * Paper: https://kyberslash.cr.yp.to/kyberslash-20240628.pdf
 * Compile: clang -O0 -Xclang -disable-O0-optnone -target aarch64.
 * Secret input: coefficient; expected unsafe operation: secret-derived udiv.
 * Classification: fixed regression reduction.
 */
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;

__attribute__((noinline))
uint8_t kyberslash1_poly_tomsg_fixed(uint16_t coefficient) {
  unsigned int t = coefficient;
  t <<= 1;
  t += 1665u;
  t *= 80635u;
  t >>= 28;
  return (uint8_t)(t & 1u);
}
