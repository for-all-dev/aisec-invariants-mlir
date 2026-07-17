// Layer A corpus — variable-latency instruction leaks (formal, software-only).
//
// Standard constant-time (`-checkct` default: control-flow + memory-access)
// forbids the secret from steering a BRANCH or a memory ADDRESS. Layer A adds
// the point that variable-latency ARITHMETIC (integer division and, on some
// microarchitectures, multiplication) also leaks the operands through timing.
// binsec exposes these as experimental check points:
//     -checkct-features multiplication,dividend,divisor
//
// Every function shares the harness signature (secret, a, b): `secret` is the
// protected input, `a`/`b` are public. Pick one with -DFUNC=<name>.
//
// Expected under the FULL layer-A feature set
// (control-flow,memory-access,multiplication,dividend,divisor):
//   a_ct_baseline    secure    — branchless, no mul/div on the secret
//   a_div_public     secure    — divides, but by a PUBLIC divisor
//   a_div_divisor    INSECURE  — secret is the divisor  (variable-latency)
//   a_div_dividend   INSECURE  — secret is the dividend (variable-latency)
//   a_mul_operand    INSECURE  — secret is a multiply operand (experimental)
//
// The point of the corpus is the DELTA vs default CT: a_div_* and a_mul_operand
// verify `secure` under default checkct (no branch, no secret address) and only
// turn `insecure` once layer A's features are enabled. run.sh prints both
// columns so the added coverage is visible, not asserted.
#include <stdint.h>

// ---- secure controls -------------------------------------------------------

// Branchless select: the textbook oblivious idiom, no mul/div on the secret.
int a_ct_baseline(int secret, int a, int b) {
    int m = -(!!secret);
    return (m & a) | (~m & b);
}

// Division is not the problem — a SECRET operand is. Dividing by a public value
// is constant-time-safe under layer A (guards against over-flagging "any div").
int a_div_public(int secret, int a, int b) {
    (void)b;
    return (secret & 0) + a / (b | 1) + a;  // divisor `b|1` is public
}

// ---- variable-latency leaks (layer A catches, default CT misses) -----------

// Secret divisor: latency of `idiv` depends on the divisor magnitude.
int a_div_divisor(int secret, int a, int b) {
    (void)b;
    return a / (secret | 1);  // `|1` only avoids div-by-zero; still secret-dep
}

// Secret dividend: latency of `idiv` depends on the dividend magnitude.
int a_div_dividend(int secret, int a, int b) {
    (void)b;
    return secret / (a | 1);
}

// Secret multiply operand: `imul` is data-dependent on some microarchitectures;
// binsec's multiplication check is conservative and flags it.
int a_mul_operand(int secret, int a, int b) {
    (void)b;
    return a * secret;
}
