/*
 * Cycle-accurate timing primitives for the layer C/D measurement driver.
 *
 * We time the measured region with the CPU timestamp counter (rdtsc). The
 * begin/end pair follows Intel's "How to Benchmark Code Execution Times"
 * (Paoloni, 2010): serialize *before* the start read with `lfence` so earlier
 * instructions have retired, and use `rdtscp` at the end so the measured region
 * has finished before the counter is sampled. This bounds out-of-order slop that
 * would otherwise smear a small per-call difference into the noise floor.
 *
 * rdtsc counts *reference* cycles (invariant TSC on this class of Intel part),
 * not core cycles, so absolute values are wall-clock-proportional and stable
 * across frequency scaling — which is what a timing attacker actually observes.
 */
#ifndef INFOLEAK_TIMER_H
#define INFOLEAK_TIMER_H

#include <stdint.h>

static inline uint64_t timer_begin(void) {
    unsigned hi, lo;
    __asm__ __volatile__(
        "lfence\n\t"
        "rdtsc\n\t"
        "lfence"
        : "=a"(lo), "=d"(hi)::"memory");
    return ((uint64_t)hi << 32) | lo;
}

static inline uint64_t timer_end(void) {
    unsigned hi, lo, aux;
    __asm__ __volatile__(
        "rdtscp\n\t"
        "lfence"
        : "=a"(lo), "=d"(hi), "=c"(aux)::"memory");
    return ((uint64_t)hi << 32) | lo;
}

#endif /* INFOLEAK_TIMER_H */
