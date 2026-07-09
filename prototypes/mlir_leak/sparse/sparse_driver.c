/*
 * Driver for the sparsifier-generated scatter kernel, under a Valgrind instrument.
 *
 *   sparse_driver <secret_crd_file> <count|taint>
 *
 * scatter.mlir = sparse_tensor.assemble(vals,pos,crd) -> convert-to-dense.
 * --sparsification lowers the convert to: for i in pos[0]..pos[1]: out[crd[i]] = vals[i].
 * The store ADDRESS is crd[i] = the secret sparsity pattern (nonzero locations).
 * vals/pos are public and identical across classes (same nnz=8); only crd differs,
 * so any secret-dependence is the PATTERN leaking through the store address --
 * a channel the sparsifier INTRODUCED (the equivalent dense write is oblivious).
 *
 * ABI (mlir-18, standard memref calling convention, struct return):
 *   {alloc,aligned,offset,size,stride} scatter(vals-desc, pos-desc, crd-desc)
 * each descriptor unpacked to (alloc*, aligned*, offset, size, stride).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <valgrind/callgrind.h>
#include <valgrind/memcheck.h>

#define NNZ 8
#define DENSE 256

typedef struct { float *alloc, *aligned; int64_t offset, sizes[1], strides[1]; } RetMR;

extern RetMR scatter(
    float   *v_a, float   *v_al, int64_t v_o, int64_t v_s, int64_t v_st,
    int64_t *p_a, int64_t *p_al, int64_t p_o, int64_t p_s, int64_t p_st,
    int64_t *c_a, int64_t *c_al, int64_t c_o, int64_t c_s, int64_t c_st);

volatile uint64_t g_sink;

static uint8_t *read_file(const char *path, size_t *out_sz) {
    FILE *f = fopen(path, "rb");
    if (!f) { perror("fopen"); exit(2); }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t *buf = malloc(sz);
    if (fread(buf, 1, sz, f) != (size_t)sz) { fprintf(stderr, "short read\n"); exit(2); }
    fclose(f); *out_sz = (size_t)sz; return buf;
}

int main(int argc, char **argv) {
    if (argc != 3) { fprintf(stderr, "usage: %s <secret_crd_file> <count|taint>\n", argv[0]); return 2; }
    size_t sz;
    int64_t *crd = (int64_t *)read_file(argv[1], &sz);   /* SECRET: NNZ coordinates */
    if (sz != (size_t)NNZ * sizeof(int64_t)) { fprintf(stderr, "bad crd size %zu\n", sz); return 2; }
    int taint = (strcmp(argv[2], "taint") == 0);

    float   vals[NNZ]; for (int i = 0; i < NNZ; i++) vals[i] = (float)(i + 1);  /* public */
    int64_t pos[2] = {0, NNZ};                                                   /* public */

    #define BEGIN() do { if (taint) { VALGRIND_PRINTF("taint region begin\n"); \
                          VALGRIND_MAKE_MEM_UNDEFINED(crd, sz); } \
                         else CALLGRIND_START_INSTRUMENTATION; } while (0)

    BEGIN();
    RetMR r = scatter(vals, vals, 0, NNZ, 1,
                      pos, pos, 0, 2, 1,
                      crd, crd, 0, NNZ, 1);
    if (taint) {
        VALGRIND_MAKE_MEM_DEFINED(r.aligned, DENSE * sizeof(float));
        VALGRIND_MAKE_MEM_DEFINED(crd, sz);
        VALGRIND_PRINTF("taint region end\n");
    } else {
        CALLGRIND_STOP_INSTRUMENTATION;
    }
    g_sink += (uint64_t)r.aligned[r.offset];   /* read AFTER the region */
    return 0;
}
