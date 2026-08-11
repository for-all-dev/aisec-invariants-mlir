// ctprobe_driver.c — the caller that makes ctprobe fire.
//
// ctprobe attaches a uprobe/uretprobe to mw_run() and reads PMU counters per
// invocation — but something has to actually CALL mw_run in an interleaved
// loop, pinned to the measured core, or the probe never triggers. That's this.
//
// It links against the same libcond.so / libmask.so the shim builds (mw_run +
// the mlir_leak kernel object), and calls mw_run(class, iters) alternating
// class 0 (fixed secret) and class 1 (random secret) batch-by-batch. Interleaving
// — not "all A then all B" — is what stops slow drift (thermal, DVFS residue)
// from aligning with one class and faking a signal.
//
// Usage:
//   sudo ./measurement-rig.sh setup 3
//   sudo taskset -c 3 ./ctprobe ./libcond.so mw_run &   # attach the eBPF probe
//   sleep 1
//   taskset -c 3 ./ctprobe_driver ./libcond.so 20000 1000   # drive mw_run
//   # then Ctrl-C ctprobe to print the per-class report
//
// args: <kernel.so> [rounds=20000] [iters=1000]
//   rounds = how many (class0 batch + class1 batch) pairs to run
//   iters  = calls per batch (must match what you want amortized; ctprobe divides by it)

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <sched.h>

typedef void (*mw_run_fn)(unsigned long cls, unsigned long iters);

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s <kernel.so> [rounds=20000] [iters=1000]\n", argv[0]); return 2; }
    const char   *lib    = argv[1];
    unsigned long rounds = argc > 2 ? strtoul(argv[2], 0, 10) : 20000;
    unsigned long iters  = argc > 3 ? strtoul(argv[3], 0, 10) : 1000;

    // Load the shim lib and resolve mw_run — the exact symbol ctprobe's uprobe is on,
    // so we and the probe agree on the same function instance.
    void *h = dlopen(lib, RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen(%s): %s\n", lib, dlerror()); return 2; }
    mw_run_fn mw_run = (mw_run_fn)dlsym(h, "mw_run");
    if (!mw_run) { fprintf(stderr, "dlsym(mw_run): %s\n", dlerror()); return 2; }

    // Confirm we're pinned (the caller should taskset us; warn if not).
    cpu_set_t set; CPU_ZERO(&set);
    if (sched_getaffinity(0, sizeof set, &set) == 0) {
        int ncpu = CPU_COUNT(&set);
        if (ncpu != 1)
            fprintf(stderr, "warn: not pinned to a single core (%d cpus in affinity mask).\n"
                            "      run me under: taskset -c <rig-core> %s ...\n", ncpu, argv[0]);
    }

    fprintf(stderr, "driving mw_run: %lu rounds x (class0 + class1), iters=%lu each. "
                    "Ctrl-C ctprobe when done to see the report.\n", rounds, iters);

    // Interleave: one class-0 batch, then one class-1 batch, repeated.
    // Each mw_run call is one ctprobe sample (one uprobe/uretprobe bracket).
    for (unsigned long r = 0; r < rounds; r++) {
        mw_run(0, iters);   // fixed-secret batch
        mw_run(1, iters);   // random-secret batch
    }

    fprintf(stderr, "done: %lu samples per class.\n", rounds);
    dlclose(h);
    return 0;
}