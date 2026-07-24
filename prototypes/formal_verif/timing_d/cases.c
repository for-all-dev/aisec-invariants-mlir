/*
 * Layer C/D corpus — the wall-clock timing channel, measured on real silicon.
 *
 * Same idea as the A/B corpora (timing_a/cases.c, contract_b/cases.c): a small
 * set of kernels with KNOWN ground truth, so the measurement harness can be
 * calibrated (a control that must stay silent, a positive that must fire) before
 * any verdict is trusted. Here the observable is wall-clock cycles, not a solver
 * verdict, so the corpus is chosen to exercise the three regimes that matter for
 * the A+B+C+D story:
 *
 *   d_ct_baseline    NEGATIVE CONTROL. Identical integer work regardless of the
 *                    secret bytes. Formally secure (A/B) AND should measure
 *                    ~0 leaked bits (D). If D reports a leak here, the harness
 *                    is miscalibrated — do not trust its other verdicts.
 *
 *   d_branch_earlyexit  POSITIVE CONTROL. memcmp-style early return: run time
 *                    depends on how many bytes match. A/binsec catch this too
 *                    (control-flow leak) — so for layer C it is the
 *                    "contract already says INSECURE, silicon confirms" case.
 *                    D must report clearly > 0 bits or the harness is deaf.
 *
 *   d_denormal       THE HEADLINE. A plain floating-point multiply-accumulate.
 *                    No secret-dependent branch, address, or integer mul/div.
 *                    binsec does NOT model FP latency — worse, it does not even
 *                    DECODE SSE/x87 (it cuts the path as "uninterpreted" and
 *                    returns `unknown`, not `secure`). So on FP code the formal
 *                    layer is not "clean", it is SILENT. Yet when the secret
 *                    operands are SUBNORMAL floats the FPU takes a microcode
 *                    assist (~40x on this Xeon), so the time leaks the secret.
 *                    This is the ~25x denormal channel the leak_check prototype
 *                    measured (Andrysco et al., IEEE S&P 2015). Only D sees it —
 *                    the concrete reason layers C/D exist.
 *
 *                    The FORMAL fix for denormals is not a solver proof (timing
 *                    is unprovable) but a CONFIG proof: build the driver with
 *                    -DINFOLEAK_FTZ so the process runs under flush-to-zero, which
 *                    turns subnormals into 0 in hardware and erases the channel.
 *                    `infoleak ftz` verifies that config statically; running the
 *                    SAME d_denormal kernel in the FTZ build confirms it is gone.
 *
 *   d_idiv_secret    The clean "binsec says SECURE, D says LEAK" case. Integer
 *                    division by a SECRET divisor: no branch, no secret address,
 *                    so binsec's DEFAULT constant-time check DECODES it and
 *                    proves `secure`. But `idiv` latency depends on the operand,
 *                    so D measures a channel. (binsec's layer-A `divisor` feature
 *                    would also catch it — this kernel shows that "formal secure"
 *                    is only as wide as the feature set you enabled.)
 *
 * Two secret classes (0/1) per kernel differ ONLY in the protected bytes; both
 * are pre-populated at init() and set_class() just swaps the active pointer, so
 * selecting a class costs the same for either and never enters the timed region.
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "kernel_abi.h"

#define VEC_N 2048  /* elements per measured call: big enough to clear the
                     * rdtsc/overhead floor, small enough to stay in L1/L2. */

/* ------------------------------------------------------------------ *
 * d_ct_baseline — negative control (integer, value-independent work)  *
 * ------------------------------------------------------------------ */
static uint32_t base_buf[INFOLEAK_N_CLASSES][VEC_N];
static const uint32_t *base_active;

static void base_init(void) {
    /* Both classes are random, distinct, same length — identical work either
     * way. (Integer, so no subnormal surprise; that channel is d_denormal.) */
    unsigned s = 0x1234567u;
    for (int c = 0; c < INFOLEAK_N_CLASSES; c++)
        for (int i = 0; i < VEC_N; i++) {
            s = s * 1103515245u + 12345u;
            base_buf[c][i] = s;
        }
    base_active = base_buf[0];
}
static void base_set_class(int cls) { base_active = base_buf[cls]; }
static uint64_t base_run(void) {
    uint64_t acc = 0;
    for (int i = 0; i < VEC_N; i++)
        acc += (uint64_t)base_active[i] * 2654435761u; /* fixed multiplier */
    return acc;
}

/* ------------------------------------------------------------------ *
 * d_branch_earlyexit — positive control (authored control-flow leak)  *
 * ------------------------------------------------------------------ */
static uint8_t ee_secret[INFOLEAK_N_CLASSES][VEC_N];
static uint8_t ee_guess[VEC_N];
static const uint8_t *ee_active;

static void ee_init(void) {
    memset(ee_guess, 0xAA, VEC_N);
    /* class 0: mismatches at byte 0  -> exits immediately (fast).
     * class 1: matches until the last byte -> full scan (slow). */
    memset(ee_secret[0], 0x00, VEC_N);
    memset(ee_secret[1], 0xAA, VEC_N);
    ee_secret[1][VEC_N - 1] = 0x00;
    ee_active = ee_secret[0];
}
static void ee_set_class(int cls) { ee_active = ee_secret[cls]; }
static uint64_t ee_run(void) {
    for (int i = 0; i < VEC_N; i++)
        if (ee_active[i] != ee_guess[i]) /* early exit: time ~ match length */
            return (uint64_t)i;
    return (uint64_t)VEC_N;
}

/* ------------------------------------------------------------------ *
 * d_denormal — the channel A/B cannot see (subnormal-float latency)    *
 * ------------------------------------------------------------------ */
static float dn_buf[INFOLEAK_N_CLASSES][VEC_N];
static const float *dn_active;

static void dn_init(void) {
    /* class 0: normal floats near 1.0 -> fast FPU path.
     * class 1: subnormal floats (< 2^-126) -> microcode assist, ~10-100x. */
    for (int i = 0; i < VEC_N; i++) {
        dn_buf[0][i] = 1.0f + (float)(i & 7) * 0.01f;
        dn_buf[1][i] = 3.0e-40f + (float)(i & 7) * 1.0e-45f; /* subnormal */
    }
    dn_active = dn_buf[0];
}
static void dn_set_class(int cls) { dn_active = dn_buf[cls]; }
static uint64_t dn_run(void) {
    /* Multiply-accumulate that keeps the running value in the same regime as the
     * operands, so subnormal inputs drive subnormal intermediates (each op pays
     * the assist). Same instruction stream for both classes. */
    float acc = 1.0f;
    for (int i = 0; i < VEC_N; i++)
        acc = acc * 0.5f + dn_active[i];
    /* reinterpret the float bits as the sink value (value-independent read). */
    uint32_t bits;
    memcpy(&bits, &acc, sizeof bits);
    return bits;
}

/* ------------------------------------------------------------------ *
 * d_idiv_secret — binsec (default CT) proves SECURE, but idiv leaks    *
 * ------------------------------------------------------------------ */
static uint32_t id_div[INFOLEAK_N_CLASSES];  /* the SECRET divisor (per class) */
static uint32_t id_active;

static void id_init(void) {
    /* Divisor magnitude drives idiv latency. class 0: large divisor -> tiny
     * quotient (fast). class 1: divisor 1 -> full-width quotient (slow). No
     * branch, no secret address -> binsec default CT decodes it and says secure. */
    id_div[0] = 0x7fffffffu;
    id_div[1] = 1u;
    id_active = id_div[0];
}
static void id_set_class(int cls) { id_active = id_div[cls]; }
static uint64_t id_run(void) {
    uint64_t acc = 0;
    uint32_t d = id_active | 1u;  /* avoid div-by-zero; still secret-dependent */
    for (int i = 0; i < VEC_N; i++)
        acc += (uint32_t)(0xdeadbeefu + (unsigned)i) / d;  /* idiv on secret divisor */
    return acc;
}

/* ------------------------------------------------------------------ *
 * registry                                                            *
 * ------------------------------------------------------------------ */
static const struct kernel K_base = {"d_ct_baseline", base_init, base_set_class, base_run};
static const struct kernel K_ee = {"d_branch_earlyexit", ee_init, ee_set_class, ee_run};
static const struct kernel K_dn = {"d_denormal", dn_init, dn_set_class, dn_run};
static const struct kernel K_id = {"d_idiv_secret", id_init, id_set_class, id_run};

const struct kernel *const infoleak_kernels[] = {
    &K_base, &K_ee, &K_dn, &K_id, NULL,
};
