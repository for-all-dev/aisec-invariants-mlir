/*
 * KyberSlash2 fixed multiply/shift compression reduction.
 * Paper: https://kyberslash.cr.yp.to/kyberslash-20240628.pdf
 * Compile: clang -O0 -Xclang -disable-O0-optnone -target aarch64.
 * Secret input: coefficient; expected unsafe operation: secret-derived udiv.
 * Classification: fixed regression reduction.
 */
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;

__attribute__((noinline))
uint8_t kyberslash2_compress_fixed(uint16_t coefficient) {
  unsigned int t = coefficient;
  t <<= 4;
  t += 1665u;
  t *= 80635u;
  t >>= 28;
  return (uint8_t)(t & 15u);
}
