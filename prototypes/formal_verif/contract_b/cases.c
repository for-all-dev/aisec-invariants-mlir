// Layer B corpus — the leakage-contract question at cache-line granularity.
//
// binsec `-checkct` (memory-access) proves whether a load ADDRESS depends on the
// secret at BYTE granularity — the `[ct]` contract, deliberately conservative.
// A real cache attacker observes only which 64-byte LINE is touched. Layer B
// re-expresses the verdict as "program |= contract" for a chosen observation
// granularity, so a byte-level leak that never crosses a line boundary is
// SECURE under the `[cache-line]` contract even though it is insecure under `[ct]`.
//
// Same harness signature (secret, a, b); `secret` is the confidential index /
// token, the table CONTENTS are public. The tables are cache-line aligned so the
// contract analysis (contract.py, using the layout in layout.tsv) can reason
// about line spanning from the element size and index range alone.
//
// Expected:
//   kernel              [ct]       [cache-line]   why
//   b_dense             secure     secure         no secret-dependent address
//   b_codebook_small    insecure   SECURE         8*4 = 32 B span, fits one line
//   b_codebook_wide     insecure   insecure       64*4 = 256 B span, crosses lines
//   b_embedding_row     insecure   insecure       rows 128 B apart, cross lines
#include <stdint.h>

#define ALIGNED __attribute__((aligned(64)))

// Public dequant codebooks / weights (contents public; only the INDEX is secret).
ALIGNED int codebook_small[8] = {3, 1, 4, 1, 5, 9, 2, 6};
ALIGNED int codebook_wide[64] = {
    3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3,
    2, 3, 8, 4, 6, 2, 6, 4, 3, 3, 8, 3, 2, 7, 9, 5,
    0, 2, 8, 8, 4, 1, 9, 7, 1, 6, 9, 3, 9, 9, 3, 7,
    5, 1, 0, 5, 8, 2, 0, 9, 7, 4, 9, 4, 4, 5, 9, 2,
};
ALIGNED int emb[32][32];  // 32 rows x 128 B; a secret token selects a whole row

// ---- control: weights -> arithmetic only, no secret address ---------------
int b_dense(int secret, int a, int b) {
    (void)b;
    int s = 0;
    for (int i = 0; i < 8; i++) s += codebook_small[i] * a;
    return s + (secret & 0);  // secret never reaches an address
}

// ---- secret index into a small (one-line) table ---------------------------
int b_codebook_small(int secret, int a, int b) {
    (void)a; (void)b;
    return codebook_small[secret & 7];   // span 8*4 = 32 B
}

// ---- secret index into a wide (multi-line) table --------------------------
int b_codebook_wide(int secret, int a, int b) {
    (void)a; (void)b;
    return codebook_wide[secret & 63];   // span 64*4 = 256 B
}

// ---- secret token selects a whole embedding row (rows cross lines) --------
int b_embedding_row(int secret, int a, int b) {
    (void)b;
    int *row = emb[secret & 31];         // row base is secret-dependent, 128 B apart
    int s = 0;
    for (int i = 0; i < 32; i++) s += row[i] * a;
    return s;
}
