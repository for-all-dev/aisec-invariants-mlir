// ctprobe.bpf.c — BATCHED PMU constant-time probe (BPF side).
//
// Corrected from the per-call version: a tiny kernel (idx_gather ~tens of ns)
// is swamped by the ~microsecond uprobe/uretprobe trap cost, so we measure a
// BATCH of identical-class calls per probe pair and let the fixed trap cost
// amortize over `iters` calls. The harness runs the loop; we bracket the whole
// loop with one uprobe/uretprobe pair.
//
// Harness contract (CHANGED — now takes iters):
//     void mw_run(unsigned long class_id, unsigned long iters) {
//         volatile long sink = 0;
//         for (unsigned long i = 0; i < iters; i++)
//             sink ^= idx_gather(table, secret_idx);  // same secret within a batch
//     }
//   class_id 0/1 = the two secret classes; iters = batch size (KEEP CONSTANT,
//   e.g. 1000). Each batch is ONE sample; the t-test compares batch durations.
//   The t-statistic is scale-invariant, so per-call vs per-batch scaling cancels
//   in t — iters is used only to print friendly per-call figures. Keep sink
//   volatile / idx_gather non-inlinable so the loop isn't optimized away.
//
// Counters (delta = end - start, per batch):
//     cycles                 timing / control-flow channel (cond_reduce)
//     L1-dcache-load-misses  cache-PRESSURE address channel
//     dTLB-load-misses       page-granularity PRESSURE channel (controlled-chan. model)
//
// HONEST SCOPE: the cache/TLB counters move only when the access pattern changes
// MISS behaviour. A small, cache-resident table leaks via which LINE is touched
// (line identity) with NO miss-count change — invisible here; that channel is
// Microwalk's job (deterministic address trace), with Flush+Reload for
// exploitability. ctprobe owns timing + pressure + the real-silicon view.

#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

char LICENSE[] SEC("license") = "GPL";

struct start_t { __u64 cyc, l1d, dtlb, cls, iters; };
struct stats_t {
    __u64 n, iters;
    __u64 cyc_sum,  cyc_sq;
    __u64 l1d_sum,  l1d_sq;
    __u64 dtlb_sum, dtlb_sq;
};

#define PEA(name) \
  struct { __uint(type, BPF_MAP_TYPE_PERF_EVENT_ARRAY); \
           __uint(key_size, sizeof(__u32)); __uint(value_size, sizeof(__u32)); \
  } name SEC(".maps")
PEA(cycles_pea);
PEA(l1d_pea);
PEA(dtlb_pea);

struct { __uint(type, BPF_MAP_TYPE_HASH); __uint(max_entries, 4096);
         __type(key, __u32); __type(value, struct start_t); } start SEC(".maps");

struct { __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY); __uint(max_entries, 2);
         __type(key, __u32); __type(value, struct stats_t); } stats SEC(".maps");

static __always_inline int rd(void *pea, __u64 *out) {
    struct bpf_perf_event_value v = {};
    if (bpf_perf_event_read_value(pea, BPF_F_CURRENT_CPU, &v, sizeof(v)))
        return -1;
    *out = v.counter;   // dedicated core + <=4 events => no multiplexing, no scaling
    return 0;
}

SEC("uprobe")
int BPF_KPROBE(mw_enter, unsigned long cls, unsigned long iters) {
    __u32 tid = (__u32)bpf_get_current_pid_tgid();
    struct start_t s = {};
    s.cls = cls; s.iters = iters ? iters : 1;
    if (rd(&cycles_pea, &s.cyc)) return 0;   // required
    if (rd(&l1d_pea,    &s.l1d)) return 0;    // required
    if (rd(&dtlb_pea,   &s.dtlb)) s.dtlb = 0; // optional: 0 if counter unavailable
    bpf_map_update_elem(&start, &tid, &s, BPF_ANY);
    return 0;
}

SEC("uretprobe")
int BPF_KRETPROBE(mw_exit) {
    __u32 tid = (__u32)bpf_get_current_pid_tgid();
    struct start_t *s = bpf_map_lookup_elem(&start, &tid);
    if (!s) return 0;

    __u64 c, l, d;
    if (rd(&cycles_pea, &c)) goto done;
    if (rd(&l1d_pea,    &l)) goto done;
    if (rd(&dtlb_pea,   &d)) d = s->dtlb;    // optional -> delta 0

    //__u64 dc = c - s->cyc, dl = l - s->l1d, dd = d - s->dtlb;
    __u64 it = s->iters ? s->iters : 1;
    __u64 dc = (c - s->cyc) / it;      // per-call cycles, not per-batch
    __u64 dl = l - s->l1d, dd = d - s->dtlb;   // cache deltas are tiny, leave as-is
    __u32 key = s->cls > 1 ? 1 : (__u32)s->cls;
    struct stats_t *st = bpf_map_lookup_elem(&stats, &key);
    if (st) {
        st->n += 1;
        st->iters = s->iters;                 // constant across batches
        st->cyc_sum  += dc; st->cyc_sq  += dc*dc;
        st->l1d_sum  += dl; st->l1d_sq  += dl*dl;
        st->dtlb_sum += dd; st->dtlb_sq += dd*dd;
    }
done:
    bpf_map_delete_elem(&start, &tid);
    return 0;
}