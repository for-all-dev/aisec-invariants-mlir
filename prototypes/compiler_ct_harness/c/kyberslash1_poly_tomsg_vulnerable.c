/*
 * KyberSlash1 reduced kernel: the division in Kyber's poly_tomsg.
 * Paper: https://kyberslash.cr.yp.to/kyberslash-20240628.pdf
 * Fix:   https://github.com/pq-crystals/kyber/commit/dda29cc63af721981ee2c831cf00822e69be3220
 * Secret: coefficient, assumed normalized to [0, 3329).
 * CONFIDENTIALITY BREAK: a secret-derived value reaches division by KYBER_Q.
 * Compile: clang -O0 -Xclang -disable-O0-optnone -target aarch64.
 * Expected unsafe operation: `udiv`/secret-dependent division.
 * Classification: vulnerable source reduction.
 */
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;

__attribute__((noinline))
uint8_t kyberslash1_poly_tomsg_vulnerable(uint16_t coefficient) {
  unsigned int t = coefficient;
  return (uint8_t)((((t << 1) + 1664u) / 3329u) & 1u);
}
