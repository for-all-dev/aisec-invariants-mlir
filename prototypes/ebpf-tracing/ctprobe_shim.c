// ctprobe_shim.c — mw_run(class, iters) harness for ctprobe, reusing mlir_leak's kernels.
// Links against the SAME build/*.o objects run_mlir.py produces (bare-pointer ABI).
//
// class 0 = fixed secret, class 1 = random secret. Interleave batches from the caller.
// Built as a shared object so ctprobe's uprobe can attach to mw_run by symbol.
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define EL_N 4096

// same weak decls / ABI as mlir_driver.c
__attribute__((weak)) void cond_reduce(float *w, float *out);
__attribute__((weak)) void mask_select(uint8_t *mask, float *a, float *b, float *out);

// public inputs, fixed exactly as the driver sets them
static float   a_buf[EL_N], b_buf[EL_N];
static float   cr_secret[EL_N], cr_out;
static uint8_t ms_secret[EL_N];
static float   ms_out[EL_N];
static float   fixed_cr[EL_N];
static uint8_t fixed_ms[EL_N];
volatile uint64_t g_sink;

__attribute__((constructor))
static void init(void) {
    for (int i = 0; i < EL_N; i++) { a_buf[i] = 2.0f; b_buf[i] = 3.0f; }
    for (int i = 0; i < EL_N; i++) { fixed_cr[i] = 1.0f; fixed_ms[i] = 0; } // class-0 fixed secret
    srand(1234);
}

// fill the secret buffers for this batch's class (0 = fixed, 1 = random)
static void set_class(unsigned long cls) {
    if (cls == 0) {
        memcpy(cr_secret, fixed_cr, sizeof cr_secret);
        memcpy(ms_secret, fixed_ms, sizeof ms_secret);
    } else {
        for (int i = 0; i < EL_N; i++) cr_secret[i] = (float)(rand() & 0xff);
        for (int i = 0; i < EL_N; i++) ms_secret[i] = rand() & 1;
    }
}

// THE PROBED SYMBOL. ctprobe brackets this whole call; the loop amortizes trap cost.
// Set MW_KERNEL at build time: -DMW_KERNEL=cond_reduce  or  -DMW_KERNEL=mask_select
void mw_run(unsigned long cls, unsigned long iters) {
    set_class(cls);
    for (unsigned long i = 0; i < iters; i++) {
#if defined(MW_COND)
        cond_reduce(cr_secret, &cr_out);
        g_sink += (uint64_t)cr_out;
#else
        mask_select(ms_secret, a_buf, b_buf, ms_out);
        g_sink += (uint64_t)ms_out[0];
#endif
    }
}