/*
 * Kernel ABI for the layer C/D measurement driver.
 *
 * The driver (driver.c) is corpus-agnostic: it links against a corpus TU that
 * provides a NULL-terminated table of `struct kernel`. This mirrors how layers
 * A/B keep the reusable engine (`ctverify`) separate from the worked-example
 * corpora (`timing_a/cases.c`, `contract_b/cases.c`). Here the reusable engine
 * is driver.c + the Python `infoleak` package; the corpus is `timing_d/cases.c`.
 *
 * Contract for a kernel:
 *   init()          one-time buffer allocation/population for BOTH secret
 *                   classes. Called once before any measurement.
 *   set_class(cls)  select which pre-populated secret drives the next run().
 *                   MUST be O(1) (e.g. swap a pointer) so it adds no
 *                   class-dependent cost *outside* the timed region and cannot
 *                   itself become a confound.
 *   run()           the measured region. Reads the currently selected secret,
 *                   returns a value the driver folds into a volatile sink so the
 *                   optimizer cannot delete the work.
 *
 * The two classes must differ ONLY in the protected (secret) values — same
 * sizes, same code path at the source level — so any timing difference is
 * attributable to the secret, not to the harness.
 */
#ifndef INFOLEAK_KERNEL_ABI_H
#define INFOLEAK_KERNEL_ABI_H

#include <stdint.h>

#define INFOLEAK_N_CLASSES 2

struct kernel {
    const char *name;
    void (*init)(void);
    void (*set_class)(int cls);
    uint64_t (*run)(void);
};

/* Provided by the corpus TU (e.g. timing_d/cases.c): NULL-terminated. */
extern const struct kernel *const infoleak_kernels[];

#endif /* INFOLEAK_KERNEL_ABI_H */
