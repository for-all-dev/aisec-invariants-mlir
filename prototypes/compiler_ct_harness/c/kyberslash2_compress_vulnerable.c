/*
 * KyberSlash2 reduced compression kernel.
 * Paper: https://kyberslash.cr.yp.to/kyberslash-20240628.pdf
 * Fix:   https://github.com/pq-crystals/kyber/commit/11d00ff1f20cfca1f72d819e5a45165c1e0a2816
 * Secret: normalized coefficient in [0, 3329).
 * CONFIDENTIALITY BREAK: secret-derived compression uses division by Q.
 * Compile: clang -O0 -Xclang -disable-O0-optnone -target aarch64.
 * Expected unsafe operation: `udiv`/secret-dependent division.
 * Classification: vulnerable source reduction.
 */
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;

__attribute__((noinline))
uint8_t kyberslash2_compress_vulnerable(uint16_t coefficient) {
  unsigned int t = coefficient;
  return (uint8_t)((((t << 4) + 1664u) / 3329u) & 15u);
}
