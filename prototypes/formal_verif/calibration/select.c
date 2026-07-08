// Calibration pair for the constant-time / semantic-side-channel verifier.
// The harness MUST verify select_ct as PASS and select_leaky as FAIL before
// any real verdict is trusted (positive + negative control).
//
// `secret` is the protected input; `a`, `b` are public.
// Both compute the same function: secret ? a : b.

// NEGATIVE CONTROL: secret-dependent branch -> constant-time VIOLATED.
// Expected: FAIL, with counterexample localizing the branch.
int select_leaky(int secret, int a, int b) {
    if (secret)
        return a;
    return b;
}

// POSITIVE CONTROL: branchless mask -> constant-time PRESERVED (at source).
// Expected: PASS at -O0. Interesting case is -O2: if the backend lowers the
// mask/select back into a branch, this flips to FAIL = compiler-introduced leak.
int select_ct(int secret, int a, int b) {
    int mask = -(!!secret);            // 0x00000000 or 0xFFFFFFFF
    return (mask & a) | (~mask & b);
}
