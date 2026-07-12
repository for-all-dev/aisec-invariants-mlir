// Weight-confidentiality harness for `binsec -checkct`.
//
// Threat model: the model WEIGHTS are the confidential asset (a proprietary
// model served for inference). An adversary who can observe microarchitectural
// side channels during inference -- branch timing, and cache/memory-access
// ADDRESSES -- must not be able to recover the weights. "Secure" here = the
// weight values never influence a branch condition or a memory address (the
// standard constant-time leakage model), only arithmetic.
//
//   Secret   = W[]         (the weights)      -> `secret global W` in w.cfg
//   Public   = x[]         (activations)      -> `public global x`
//   Concrete = codebook[]  (public dequant table; like q_kept_mem's pub_table,
//                           NOT declared in the cfg -- it is fixed data, not an
//                           input; only a secret INDEX into it can leak)
//
// One harness fits every kernel; pick it at compile time:
//   gcc -m32 -DFUNC=mm_dense ...   /   -DFUNC=mm_codebook ...
#include <stdlib.h>
#define N 4

extern int FUNC(void);            // the kernel under test (reads the globals)

int W[N];                         // SECRET model weights
int x[N];                         // public activations / input
int codebook[8] = {2,3,5,7,11,13,17,19};   // public, concrete dequant table

int main(void) {
    int y = FUNC();
    exit(y & 1);                  // observable public output
}
