// The 2x2 differential matrix for compiler effect on constant-time.
// Every function has the SAME signature (secret, a, b) so one harness+cfg fits.
// Pick one at compile time with -DFUNC=<name>. `secret` is protected; a,b public.
//
// Quadrant = (does source/-O0 leak?) x (does compiled/-O2 leak?)
#include <stdint.h>

// Public lookup table (contents public; only the INDEX is secret).
int pub_table[16] = {3,1,4,1,5,9,2,6,5,3,5,8,9,7,9,3};

// ---- нет / нет : branchless, oblivious at every -O -------------------------
int q_oblivious(int secret, int a, int b) {
    int m = -(!!secret);                 // 0x0 or 0xFFFFFFFF
    return (m & a) | (~m & b);
}

// ---- есть / убрал : secret-dependent branch that -O2 lowers to cmov --------
int q_removed(int secret, int a, int b) {
    if (secret) return a;
    return b;
}

// ---- есть / оставил : secret-indexed load -> memory-access leak at all -O ---
int q_kept_mem(int secret, int a, int b) {
    (void)a; (void)b;
    return pub_table[secret & 0xF];      // address depends on secret
}

// ---- есть / оставил (control-flow) : data-dependent loop trip count --------
int q_kept_cf(int secret, int a, int b) {
    (void)a; (void)b;
    int acc = 0;
    for (int i = 0; i < (secret & 0x7); i++) acc += i;   // #iters = secret
    return acc;
}

// ---- нет / добавил CANDIDATES : branchless source, hope -O2 branches -------
// C1: expensive arm may make the optimizer guard it with a branch on the mask.
int q_intro1(int secret, int a, int b) {
    int m = -(secret & 1);
    int acc = 0;
    for (int i = 0; i < 64; i++) acc += a * i + b;       // "expensive" arm
    return (m & acc) | (~m & b);
}
// C2: multiply-select (Simon et al. "What you get is what you C" style).
int q_intro2(int secret, int a, int b) {
    int bit = (secret != 0);
    return a * bit + b * (1 - bit);
}
// C3: division arms (variable-latency AND may trigger branch on zero-check).
int q_intro3(int secret, int a, int b) {
    int m = -(secret & 1);
    return (m & (a / (b | 1))) | (~m & (b / (a | 1)));
}
// C4: mask built from a ternary; some compilers lower the ?: to a branch.
int q_intro4(int secret, int a, int b) {
    int mask = (secret & 1) ? -1 : 0;
    return (a & mask) | (b & ~mask);
}
// C5: short-circuit && on a secret-derived predicate -> may become a branch.
int q_intro5(int secret, int a, int b) {
    int bit = (secret & 1);
    int t = bit && (a > b);           // && can lower to a conditional jump
    int m = -t;
    return (a & m) | (b & ~m);
}
