/* spill.c -- adversarial reproduction attempt for the claimed break:
 * "Register allocator creates secret memory observations that exist in no IR"
 *
 * Shape of the claim:
 *   - source declares a secret region; the source scrubs every name it owns
 *   - LLVM IR at -O2 has 0 allocas and 0 stores for the region (nothing to see)
 *   - the register allocator (greedy) invents stack slots BELOW any machine-IR
 *     freeze point that a policy could plausibly bind to
 *   - the spill address is $sp+const, i.e. PUBLIC, so an address-based
 *     extractor at post-PEI reports clean
 *   - the real channel is VALUE RESIDENCY AFTER REGION END
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define SECRET 0xC0FFEE0DDBADF00DULL

/* opaque, defined in spill_opaque.c so nothing inlines / interprocedurally
 * propagates. Forces a call in the middle of the secret's live range. */
extern uint64_t opaque(uint64_t x);
extern void sink(uint64_t x);

/* ---- the "secret region" ------------------------------------------------
 * key must be live ACROSS the opaque call, together with many other live
 * values, so the allocator runs out of callee-saved registers and spills.
 * At the end the source scrubs every variable it can name.
 */
__attribute__((noinline, aligned(64)))
uint64_t crypt_region(uint64_t key, const uint64_t *in, unsigned n)
{
    uint64_t a = in[0], b = in[1], c = in[2], d = in[3];
    uint64_t e = in[4], f = in[5], g = in[6], h = in[7];
    uint64_t i = in[8], j = in[9], k = in[10], l = in[11];
    uint64_t m = in[12], o = in[13], p = in[14], q = in[15];

    for (unsigned t = 0; t < n; t++) {
        a = opaque(a ^ t);
        b = opaque(b + a);
        c = opaque(c ^ b);
        d = opaque(d + c);
        e = opaque(e ^ d);
        f = opaque(f + e);
        g = opaque(g ^ f);
        h = opaque(h + g);
        i = opaque(i ^ h);
        j = opaque(j + i);
        k = opaque(k ^ j);
        l = opaque(l + k);
        m = opaque(m ^ l);
        o = opaque(o + m);
        p = opaque(p ^ o);
        q = opaque(q + p);
    }

    /* key is used only HERE, at the very end: its live range spans the whole
     * loop and every call in it. */
    uint64_t acc = a ^ b ^ c ^ d ^ e ^ f ^ g ^ h
                 ^ i ^ j ^ k ^ l ^ m ^ o ^ p ^ q;
    uint64_t res = acc + (key >> 60);   /* only 4 bits of key ever escape */

    /* SOURCE-LEVEL SCRUB: every name the source owns is cleared. */
    key = 0; a = b = c = d = e = f = g = h = 0;
    i = j = k = l = m = o = p = q = 0;
    acc = 0;
    __asm__ __volatile__("" :: "r"(key), "r"(acc) : "memory");

    return res;
}

/* ---- probe: read the freed frame ---------------------------------------- */
__attribute__((noinline, aligned(64)))
static unsigned probe_residue(uint64_t pattern, unsigned words)
{
    volatile uint64_t buf[512];      /* deliberately UNINITIALISED */
    unsigned hits = 0;
    for (unsigned x = 0; x < words && x < 512; x++)
        if (buf[x] == pattern) hits++;
    return hits;
}

int main(void)
{
    uint64_t in[16];
    for (unsigned x = 0; x < 16; x++) in[x] = 0x1000ULL + x;

    uint64_t r = crypt_region(SECRET, in, 3);
    sink(r);

    unsigned hits = probe_residue(SECRET, 512);
    printf("result=%llu  SECRET residue in freed frame = %u occurrence(s)\n",
           (unsigned long long)r, hits);
    return 0;
}
