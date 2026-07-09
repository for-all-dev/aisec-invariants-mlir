/*
 * Driver for one MLIR-compiled kernel invocation under a Valgrind instrument.
 *
 *   mlir_driver <kernel> <secret_file> <count|taint>
 *
 * Same protocol as leak_check/ctbench/harness.c (so instruments.py parses it
 * unchanged), but the kernels are MLIR-lowered objects called via the
 * bare-pointer memref calling convention (each memref arg = one aligned ptr).
 *
 * Kernel symbols are declared __weak__: a given pipeline may fail to lower a
 * given kernel, so its object is simply not linked into that pipeline's binary.
 * A weak-undefined symbol resolves to NULL; the runner only invokes (kernel,
 * pipeline) cells it lowered, and we null-check anyway (rc=3 = not linked).
 *
 * Public inputs are fixed constants (never secret-derived). The sink reads
 * output[0] only AFTER the gated region.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <valgrind/callgrind.h>
#include <valgrind/memcheck.h>

/* MLIR kernels, bare-pointer memref calling convention, weak (may be unlinked). */
__attribute__((weak)) void matvec(float *W, float *x, float *y);
__attribute__((weak)) void cond_reduce(float *w, float *out);
__attribute__((weak)) void mask_select(uint8_t *mask, float *a, float *b, float *out);
__attribute__((weak)) void idx_gather(int32_t *idx, float *table, float *out);
/* tensor-source variants for the bufferization pipeline P4 (out-param ABI). */
__attribute__((weak)) void matvec_t(float *W, float *x, float *out);
__attribute__((weak)) void mask_select_t(uint8_t *mask, float *a, float *b, float *out);
/* dynamic-shape: the secret is an extent k (secret-sized alloc + trip count). */
__attribute__((weak)) void dynshape(int32_t *k, float *out);
__attribute__((weak)) void dynshape_t(int32_t *k, float *out);   /* tensor-source, for P4 */

#define MM_N 256      /* matvec dimension */
#define EL_N 4096     /* elementwise / gather length */
#define TBL_N 256     /* gather table length */

volatile uint64_t g_sink;   /* prevent dead-code elimination of outputs */

static uint8_t *read_file(const char *path, size_t *out_sz) {
    FILE *f = fopen(path, "rb");
    if (!f) { perror("fopen"); exit(2); }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *buf = malloc(sz);
    if (fread(buf, 1, sz, f) != (size_t)sz) { fprintf(stderr, "short read\n"); exit(2); }
    fclose(f);
    *out_sz = (size_t)sz;
    return buf;
}

static void expect(size_t got, size_t want) {
    if (got != want) { fprintf(stderr, "secret size %zu != expected %zu\n", got, want); exit(2); }
}

int main(int argc, char **argv) {
    if (argc != 4) { fprintf(stderr, "usage: %s <kernel> <secret_file> <count|taint>\n", argv[0]); return 2; }
    const char *kern = argv[1];
    size_t sz;
    uint8_t *secret = read_file(argv[2], &sz);
    int taint = (strcmp(argv[3], "taint") == 0);

    #define BEGIN() do { if (taint) { VALGRIND_PRINTF("taint region begin\n"); \
                          VALGRIND_MAKE_MEM_UNDEFINED(secret, sz); } \
                         else CALLGRIND_START_INSTRUMENTATION; } while (0)
    #define END(outp, outn) do { if (taint) { VALGRIND_MAKE_MEM_DEFINED(outp, outn); \
                          VALGRIND_MAKE_MEM_DEFINED(secret, sz); VALGRIND_PRINTF("taint region end\n"); } \
                         else CALLGRIND_STOP_INSTRUMENTATION; } while (0)

    if (!strcmp(kern, "matvec")) {
        if (!matvec) { fprintf(stderr, "kernel not linked\n"); return 3; }
        expect(sz, (size_t)MM_N * MM_N * sizeof(float));
        float *W = (float *)secret;
        float *x = malloc(MM_N * sizeof(float)), *y = malloc(MM_N * sizeof(float));
        for (int i = 0; i < MM_N; i++) x[i] = 1.0f;
        memset(y, 0, MM_N * sizeof(float));   /* linalg.matvec accumulates into y */
        BEGIN();
        matvec(W, x, y);
        END(y, MM_N * sizeof(float));
        g_sink += (uint64_t)y[0];
    } else if (!strcmp(kern, "cond_reduce")) {
        if (!cond_reduce) { fprintf(stderr, "kernel not linked\n"); return 3; }
        expect(sz, (size_t)EL_N * sizeof(float));
        float *w = (float *)secret;
        float *out = malloc(sizeof(float));
        BEGIN();
        cond_reduce(w, out);
        END(out, sizeof(float));
        g_sink += (uint64_t)out[0];
    } else if (!strcmp(kern, "mask_select")) {
        if (!mask_select) { fprintf(stderr, "kernel not linked\n"); return 3; }
        expect(sz, (size_t)EL_N);                      /* uint8 mask */
        uint8_t *mask = secret;
        float *a = malloc(EL_N * sizeof(float)), *b = malloc(EL_N * sizeof(float)),
              *out = malloc(EL_N * sizeof(float));
        for (int i = 0; i < EL_N; i++) { a[i] = 2.0f; b[i] = 3.0f; }
        BEGIN();
        mask_select(mask, a, b, out);
        END(out, EL_N * sizeof(float));
        g_sink += (uint64_t)out[0];
    } else if (!strcmp(kern, "idx_gather")) {
        if (!idx_gather) { fprintf(stderr, "kernel not linked\n"); return 3; }
        expect(sz, (size_t)EL_N * sizeof(int32_t));    /* int32 indices */
        int32_t *idx = (int32_t *)secret;
        float *table = malloc(TBL_N * sizeof(float)), *out = malloc(EL_N * sizeof(float));
        for (int i = 0; i < TBL_N; i++) table[i] = (float)i;
        BEGIN();
        idx_gather(idx, table, out);
        END(out, EL_N * sizeof(float));
        g_sink += (uint64_t)out[0];
    } else if (!strcmp(kern, "matvec_t")) {
        if (!matvec_t) { fprintf(stderr, "kernel not linked\n"); return 3; }
        expect(sz, (size_t)MM_N * MM_N * sizeof(float));
        float *W = (float *)secret;
        float *x = malloc(MM_N * sizeof(float)), *out = malloc(MM_N * sizeof(float));
        for (int i = 0; i < MM_N; i++) x[i] = 1.0f;   /* fill() inits out inside kernel */
        BEGIN();
        matvec_t(W, x, out);
        END(out, MM_N * sizeof(float));
        g_sink += (uint64_t)out[0];
    } else if (!strcmp(kern, "mask_select_t")) {
        if (!mask_select_t) { fprintf(stderr, "kernel not linked\n"); return 3; }
        expect(sz, (size_t)EL_N);
        uint8_t *mask = secret;
        float *a = malloc(EL_N * sizeof(float)), *b = malloc(EL_N * sizeof(float)),
              *out = malloc(EL_N * sizeof(float));
        for (int i = 0; i < EL_N; i++) { a[i] = 2.0f; b[i] = 3.0f; }
        BEGIN();
        mask_select_t(mask, a, b, out);
        END(out, EL_N * sizeof(float));
        g_sink += (uint64_t)out[0];
    } else if (!strcmp(kern, "dynshape")) {
        if (!dynshape) { fprintf(stderr, "kernel not linked\n"); return 3; }
        expect(sz, sizeof(int32_t));               /* single int32 extent k */
        int32_t *k = (int32_t *)secret;
        float *out = malloc(sizeof(float));
        BEGIN();
        dynshape(k, out);
        END(out, sizeof(float));
        g_sink += (uint64_t)out[0];
    } else if (!strcmp(kern, "dynshape_t")) {
        if (!dynshape_t) { fprintf(stderr, "kernel not linked\n"); return 3; }
        expect(sz, sizeof(int32_t));
        int32_t *k = (int32_t *)secret;
        float *out = malloc(sizeof(float));
        BEGIN();
        dynshape_t(k, out);
        END(out, sizeof(float));
        g_sink += (uint64_t)out[0];
    } else {
        fprintf(stderr, "unknown kernel %s\n", kern);
        return 2;
    }
    return 0;
}
