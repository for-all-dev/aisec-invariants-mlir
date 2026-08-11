// ctprobe.c — userspace loader for the BATCHED PMU constant-time probe.
// (Makefile unchanged.)
//
// HYBRID-CPU aware: on Alder/Raptor Lake the P-cores (cpu_core) and E-cores
// (cpu_atom) are SEPARATE PMUs, and a generic PERF_TYPE_HARDWARE event is
// ambiguous across them -> perf_event_open returns ENOENT. So we open events
// against the cpu_core PMU by its dynamic type, using RAW Intel encodings, and
// we arm the counter ONLY on the measurement core (auto-detected from the
// taskset affinity), so E-cores are never touched.
//
// Run pinned on the isolated rig:
//   sudo measurement-rig.sh setup 7
//   sudo taskset -c 7 ./ctprobe ./ct/libmask.so mw_run
//   # then, pinned to 7, drive mw_run(class, iters) interleaved (ctprobe_driver).

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <signal.h>
#include <sched.h>
#include <math.h>
#include <linux/perf_event.h>
#include <sys/syscall.h>
#include <bpf/libbpf.h>
#include <bpf/bpf.h>
#include "ctprobe.skel.h"

static volatile sig_atomic_t stop;
static void on_sigint(int _) { (void)_; stop = 1; }

static int g_core = -1;   // measurement core; arm counters only here

static long perf_event_open(struct perf_event_attr *a, pid_t pid, int cpu,
                            int grp, unsigned long flags) {
    return syscall(__NR_perf_event_open, a, pid, cpu, grp, flags);
}

// Read the dynamic perf type of a named PMU (e.g. "cpu_core" -> 4 on this box).
static __u32 pmu_type(const char *pmu) {
    char path[128]; snprintf(path, sizeof path, "/sys/bus/event_source/devices/%s/type", pmu);
    FILE *f = fopen(path, "r"); if (!f) return PERF_TYPE_HARDWARE;
    unsigned t; if (fscanf(f, "%u", &t) != 1) t = PERF_TYPE_HARDWARE; fclose(f);
    return t;
}

// If the process is pinned to a single CPU (via taskset), that's our measurement
// core. Returns the cpu index, or -1 if not pinned to exactly one.
static int detect_pinned_core(void) {
    cpu_set_t set; CPU_ZERO(&set);
    if (sched_getaffinity(0, sizeof set, &set) != 0) return -1;
    if (CPU_COUNT(&set) != 1) return -1;
    for (int c = 0; c < CPU_SETSIZE; c++) if (CPU_ISSET(c, &set)) return c;
    return -1;
}

// Arm one (type,config) event on the measurement core into perf-event-array map_fd.
// required=1 -> failure is fatal; required=0 -> warn and skip that counter.
static int arm(int map_fd, __u32 type, __u64 config, int ncpu, int *fds, int required) {
    struct perf_event_attr attr = {
        .type = type, .size = sizeof(attr), .config = config,
        .disabled = 0, .exclude_kernel = 0, .exclude_hv = 1,
    };
    for (int cpu = 0; cpu < ncpu; cpu++) {
        fds[cpu] = -1;
        // Only the measurement core (auto-detected). If unknown, fall back to all.
        if (g_core >= 0 && cpu != g_core) continue;
        int fd = perf_event_open(&attr, -1, cpu, -1, 0);
        if (fd < 0) {
            if (required) { fprintf(stderr, "perf_event_open(type=%u cfg=0x%llx cpu=%d) failed: %s\n",
                                    type, (unsigned long long)config, cpu, strerror(errno)); return -1; }
            fprintf(stderr, "warn: optional counter (cfg=0x%llx) unavailable on cpu %d (%s) — continuing\n",
                    (unsigned long long)config, cpu, strerror(errno));
            continue;
        }
        fds[cpu] = fd;
        __u32 key = cpu;
        if (bpf_map_update_elem(map_fd, &key, &fd, BPF_ANY)) {
            if (required) { fprintf(stderr, "map_update(cpu=%d) failed\n", cpu); return -1; }
        }
    }
    return 0;
}

struct agg { double n, sum, sq; unsigned long iters; };

static void read_class(int stats_fd, __u32 cls, int ncpu,
                       struct agg *cyc, struct agg *l1d, struct agg *dtlb) {
    struct stats_t {
        __u64 n, iters, cyc_sum, cyc_sq, l1d_sum, l1d_sq, dtlb_sum, dtlb_sq;
    } vals[ncpu];
    memset(vals, 0, sizeof(vals));
    if (bpf_map_lookup_elem(stats_fd, &cls, vals)) return;
    for (int i = 0; i < ncpu; i++) {
        if (vals[i].iters) { cyc->iters = l1d->iters = dtlb->iters = vals[i].iters; }
        cyc->n  += vals[i].n; cyc->sum  += vals[i].cyc_sum;  cyc->sq  += vals[i].cyc_sq;
        l1d->n  += vals[i].n; l1d->sum  += vals[i].l1d_sum;  l1d->sq  += vals[i].l1d_sq;
        dtlb->n += vals[i].n; dtlb->sum += vals[i].dtlb_sum; dtlb->sq += vals[i].dtlb_sq;
    }
}

// Welch t on raw batch deltas (scale-invariant); per-call mean = batch mean / iters.
// static void report(const char *label, struct agg a, struct agg b) {
//     if (a.n < 2 || b.n < 2) { printf("  %-8s no data (this counter didn't arm, or one class missing)\n", label); return; }
//     double ma = a.sum/a.n, mb = b.sum/b.n;
//     double va = a.sq/a.n - ma*ma, vb = b.sq/b.n - mb*mb;
//     double denom = sqrt(va/a.n + vb/b.n);
//     double t = denom > 0 ? (ma - mb) / denom : 0.0;
//     unsigned long it = a.iters ? a.iters : 1;
//     printf("  %-8s per-call: A=%.2f  B=%.2f  |  batches: nA=%.0f nB=%.0f  t=%.2f%s\n",
//            label, ma/it, mb/it, a.n, b.n, t, fabs(t) > 4.5 ? "   <-- LEAK" : "");
// }
// cyc is already per-call (divided in BPF); l1d/dtlb are per-batch (divide here)
static void report(const char *label, struct agg a, struct agg b, int already_percall) {
    if (a.n < 2 || b.n < 2) { printf("  %-8s no data\n", label); return; }
    long double ma = (long double)a.sum/a.n, mb = (long double)b.sum/b.n;
    long double va = fmaxl(0.0L, (long double)a.sq/a.n - ma*ma);
    long double vb = fmaxl(0.0L, (long double)b.sq/b.n - mb*mb);
    long double denom = sqrtl(va/a.n + vb/b.n);
    double t = denom > 1e-9L ? (double)((ma-mb)/denom) : (ma==mb ? 0.0 : 1e9);
    unsigned long it = a.iters ? a.iters : 1;
    long double div = already_percall ? 1.0L : it;
    printf("  %-8s per-call: A=%.2f  B=%.2f  |  batches: nA=%.0f nB=%.0f  t=%.2f%s\n",
           label, (double)(ma/div), (double)(mb/div), a.n, b.n, t,
           fabs(t) > 4.5 ? "   <-- LEAK" : "");
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s <library.so> [symbol=mw_run]\n", argv[0]); return 1; }
    const char *lib = argv[1];
    const char *sym = argc > 2 ? argv[2] : "mw_run";

    int ncpu = libbpf_num_possible_cpus();
    int cyc_fds[ncpu], l1d_fds[ncpu], dtlb_fds[ncpu];

    g_core = detect_pinned_core();
    if (g_core >= 0) fprintf(stderr, "measurement core (from affinity): cpu%d\n", g_core);
    else fprintf(stderr, "warn: not pinned to one core — arming all CPUs (may fail on hybrid). "
                         "run under: taskset -c <core> %s ...\n", argv[0]);

    struct ctprobe_bpf *skel = ctprobe_bpf__open_and_load();
    if (!skel) { fprintf(stderr, "open/load BPF failed\n"); return 1; }

    __u32 cp = pmu_type("cpu_core");   // P-core PMU (type 4 on this box)
    fprintf(stderr, "cpu_core PMU type = %u\n", cp);

    // cycles: CPU_CLK_UNHALTED.THREAD  event=0x3c umask=0x00 -> 0x003c  (required)
    if (arm(bpf_map__fd(skel->maps.cycles_pea), cp, 0x3c, ncpu, cyc_fds, 1)) goto out;
    // L1D miss: MEM_LOAD_RETIRED.L1_MISS  event=0xd1 umask=0x08 -> 0x08d1  (optional)
    arm(bpf_map__fd(skel->maps.l1d_pea),  cp, 0x08d1, ncpu, l1d_fds, 0);
    // dTLB miss: DTLB_LOAD_MISSES.WALK_COMPLETED  event=0x12 umask=0x0e -> 0x0e12  (optional)
    arm(bpf_map__fd(skel->maps.dtlb_pea), cp, 0x0e12, ncpu, dtlb_fds, 0);

    LIBBPF_OPTS(bpf_uprobe_opts, eo, .func_name = sym, .retprobe = false);
    LIBBPF_OPTS(bpf_uprobe_opts, ro, .func_name = sym, .retprobe = true);
    struct bpf_link *le = bpf_program__attach_uprobe_opts(skel->progs.mw_enter, -1, lib, 0, &eo);
    struct bpf_link *lr = bpf_program__attach_uprobe_opts(skel->progs.mw_exit,  -1, lib, 0, &ro);
    if (!le || !lr) { fprintf(stderr, "attach to %s:%s failed: %s\n", lib, sym, strerror(errno)); goto out; }

    signal(SIGINT, on_sigint);
    printf("ctprobe: attached to %s:%s (cpu_core PMU). Ctrl-C to report.\n", lib, sym);
    printf("         drive mw_run(class, iters), class in {0,1}, pinned to the same core.\n");
    while (!stop) pause();

    struct agg ca={0}, cb={0}, la={0}, lb={0}, da={0}, db={0};
    int sfd = bpf_map__fd(skel->maps.stats);
    read_class(sfd, 0, ncpu, &ca, &la, &da);
    read_class(sfd, 1, ncpu, &cb, &lb, &db);

    printf("\n=== batched constant-time report (|t| > 4.5 => secret-dependent) ===\n");
    report("cycles",  ca, cb, 1);   // timing / control-flow  <-- the one that matters here
    report("l1dmiss", la, lb, 0);   // cache-pressure address channel (if armed)
    report("dtlbmiss",da, db, 0);   // page-granularity pressure channel (if armed)
    printf("note: l1d/dtlb move only on cache/TLB PRESSURE changes; a resident-table\n"
           "      line-identity leak (idx_gather) is Microwalk's job, not this counter.\n");

    bpf_link__destroy(le); bpf_link__destroy(lr);
out:
    for (int i = 0; i < ncpu; i++) {
        if (cyc_fds[i] > 0) close(cyc_fds[i]);
        if (l1d_fds[i] > 0) close(l1d_fds[i]);
        if (dtlb_fds[i] > 0) close(dtlb_fds[i]);
    }
    ctprobe_bpf__destroy(skel);
    return 0;
}