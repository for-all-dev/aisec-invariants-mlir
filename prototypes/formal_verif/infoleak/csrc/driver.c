/*
 * dudect-style measurement driver — the data source for layers C and D.
 *
 *   driver <kernel> <n_samples> <warmup> <seed>
 *
 * Emits CSV `class,cycles` to stdout, one measured kernel call per line. The
 * Python `infoleak` engine reads this stream and computes the leakage estimate
 * (mutual information in bits + the dudect/TVLA t-test).
 *
 * Discipline baked in here, learned the hard way by the `leak_check` prototype
 * (see docs/research/leak_check.lessons.agents.md):
 *
 *   - RANDOMLY INTERLEAVED classes. The class for each measurement is drawn from
 *     a PRNG, not measured in two blocks. Thermal / frequency drift over the run
 *     is then uncorrelated with the class label and cannot masquerade as a
 *     value-dependent signal (the "measure both at matched contexts" rule).
 *   - set_class() is O(1) (pointer swap), so it adds no class-dependent cost
 *     outside the timed region.
 *   - A volatile sink consumes run()'s result so the optimizer keeps the work.
 *   - Warmup samples (caches/branch-predictor/frequency ramp) are discarded.
 *
 * This is dudect's methodology (Reparaz-Balasch-Verbauwhede, DATE 2017): time a
 * kernel across two secret classes and test statistically. It is DETECTION on
 * real silicon, never a proof of constant-time (a null = "below this harness's
 * floor", not "provably oblivious").
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "kernel_abi.h"
#include "timer.h"

/* Optional: measure the whole process under flush-to-zero / denormals-are-zero.
 * Build with -DINFOLEAK_FTZ (see timing_d/run.sh). FTZ is a per-thread CPU state,
 * not a per-binary property, so it belongs here in the driver (set once, before
 * any measurement) rather than inside one kernel — it then closes the denormal
 * channel for every FP kernel, exactly as an -ffast-math build would in the field.
 * `infoleak ftz` detects the resulting ldmxcsr statically. */
#ifdef INFOLEAK_FTZ
#include <pmmintrin.h>
#include <xmmintrin.h>
#endif

/* Volatile sink: prevents dead-code elimination of the kernel result. */
volatile uint64_t infoleak_sink;

/* SplitMix64 — a tiny, self-contained PRNG so the class sequence is
 * reproducible from the seed without pulling in libc rand() quirks. */
static uint64_t sm_state;
static inline uint64_t sm_next(void) {
    uint64_t z = (sm_state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static const struct kernel *find_kernel(const char *name) {
    for (const struct kernel *const *k = infoleak_kernels; *k; k++)
        if (strcmp((*k)->name, name) == 0)
            return *k;
    return NULL;
}

int main(int argc, char **argv) {
    if (argc != 5) {
        fprintf(stderr, "usage: %s <kernel> <n_samples> <warmup> <seed>\n", argv[0]);
        fprintf(stderr, "kernels:");
        for (const struct kernel *const *k = infoleak_kernels; *k; k++)
            fprintf(stderr, " %s", (*k)->name);
        fprintf(stderr, "\n");
        return 2;
    }

    const char *name = argv[1];
    long n = strtol(argv[2], NULL, 10);
    long warmup = strtol(argv[3], NULL, 10);
    sm_state = (uint64_t)strtoull(argv[4], NULL, 10);

    const struct kernel *k = find_kernel(name);
    if (!k) {
        fprintf(stderr, "unknown kernel: %s\n", name);
        return 2;
    }

#ifdef INFOLEAK_FTZ
    _MM_SET_FLUSH_ZERO_MODE(_MM_FLUSH_ZERO_ON);
    _MM_SET_DENORMALS_ZERO_MODE(_MM_DENORMALS_ZERO_ON);
#endif

    k->init();

    /* Warm caches / predictor / frequency; touch both classes so neither is
     * cold when the measured run starts. Results discarded. */
    for (long i = 0; i < warmup; i++) {
        k->set_class((int)(sm_next() & 1));
        infoleak_sink += k->run();
    }

    printf("class,cycles\n");
    for (long i = 0; i < n; i++) {
        int cls = (int)(sm_next() % INFOLEAK_N_CLASSES);
        k->set_class(cls);
        uint64_t t0 = timer_begin();
        uint64_t r = k->run();
        uint64_t t1 = timer_end();
        infoleak_sink += r;
        printf("%d,%llu\n", cls, (unsigned long long)(t1 - t0));
    }
    return 0;
}
