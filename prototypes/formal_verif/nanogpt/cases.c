// nanoGPT-derived weight-confidentiality corpus (toy dimensions).
//
// Each kernel is one row of a matrix-vector product y = W . x -- the atom of
// every linear/attention layer in a transformer -- specialized to expose (or
// avoid) a way the SECRET weights W leak through the constant-time leakage
// model (branches + memory addresses). Pick one with -DFUNC=<name>.
//
// Dimensions are deliberately tiny (N=4, |codebook|=8) so bounded symbolic
// execution stays decidable. The leaks are STRUCTURAL, not size-dependent: a
// secret-indexed gather leaks at N=4 exactly as it does at N=768.
#include <stdint.h>
#define N 4

extern int W[N];           // secret weights
extern int x[N];           // public activations
extern int codebook[8];    // public, concrete dequant table

// (control) DENSE -- weights flow ONLY into arithmetic. No secret-dependent
// branch, no secret-dependent address. Oblivious at every -O. This is the
// reassuring baseline: plain dense inference does not leak weights under the
// CT model. It also guards against false positives from the checker.
int mm_dense(void) {
    int acc = 0;
    for (int i = 0; i < N; i++) acc += W[i] * x[i];
    return acc;
}

// SPARSE (skip-zero) -- the classic inference optimization. The branch tests
// the weight VALUE, so its taken/not-taken trace leaks the pruning/sparsity
// mask (which weights are zero) -- often most of the model's structure.
// Authored control-flow leak. Expect: insecure.
int mm_sparse(void) {
    int acc = 0;
    for (int i = 0; i < N; i++)
        if (W[i] != 0) acc += W[i] * x[i];
    return acc;
}

// CODEBOOK (quantized) -- GPTQ/AWQ-style: each weight is a small index into a
// public dequant table. The load ADDRESS codebook[W[i]] depends on the secret
// weight -> a memory-access leak with NO branch. This is the transformer
// analog of the AES S-box: branch-counting sees nothing; only the relational
// memory-address check catches it. The strongest weight-confidentiality
// result. Expect: insecure (memory), gcc and clang alike.
int mm_codebook(void) {
    int acc = 0;
    for (int i = 0; i < N; i++) acc += codebook[W[i] & 7] * x[i];
    return acc;
}

// CODEBOOK-CT -- a constant-time dequant: read ALL codebook entries at public
// addresses and mask-select the one at the secret index. Oblivious at -O0.
// This is the compiler-INTRODUCED test (parallels q_oblivious): does -O2,
// especially clang, collapse the scan back into a direct secret-indexed load,
// or lower `j == idx` into a conditional jump -- re-introducing the weight
// leak the source was written to avoid? Run the O0-vs-O2 x gcc-vs-clang matrix
// and see. Either outcome is a result.
int mm_codebook_ct(void) {
    int acc = 0;
    for (int i = 0; i < N; i++) {
        int idx = W[i] & 7;
        int dq = 0;
        for (int j = 0; j < 8; j++) {
            int m = -(j == idx);       // all-ones iff j is the secret index
            dq |= codebook[j] & m;     // every entry read at a PUBLIC address
        }
        acc += dq * x[i];
    }
    return acc;
}
