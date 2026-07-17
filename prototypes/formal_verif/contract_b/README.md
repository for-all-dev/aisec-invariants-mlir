# Layer B — leakage contract at cache-line granularity, on top of binsec

Layer B of the timing roadmap in [`../README.md`](../README.md). `binsec
-checkct` (memory-access) decides the **`[ct]`** contract: does a load address
depend on the secret at *byte* granularity? That is deliberately conservative.
A real cache attacker observes only which **64-byte line** is touched. Layer B
re-expresses the verdict as **`program ⊨ contract`** for a chosen observation
granularity, so a byte-level leak whose reachable addresses all fall in one
cache line is **secure under `[cache-line]`** even though it is insecure under
`[ct]`.

This is the **software** half of layer B and needs no external library: binsec
supplies the formal byte-level leak (and the leaking instruction address); the
reusable [`../ctverify/`](../ctverify/) package (`ctverify contract`) computes
the cache-line verdict from the access layout. This directory is a worked
example whose `run.sh` compiles the corpus and drives that CLI. The **hardware**
half (verify RTL ⊨ contract with *LeaVe*) is a separate tool on an RTL core and
is out of scope here.

## How the cache-line verdict is computed (not asserted)

For a secret-dependent access `base + i·elem`, `i ∈ [0, index_count)`, with a
cache-line-aligned `base` (the corpus enforces `__attribute__((aligned(64)))`):

```
distinct_lines = |{ (i·elem) // 64 : i ∈ [0, index_count) }|
distinct_lines == 1  ⟹  secure   under [cache-line]   (all secrets share a line)
distinct_lines  > 1  ⟹  insecure under [cache-line]   (secret moves the line)
```

`elem` and `index_count` are the source ground truth (passed as `--elem`/`--count`
to `ctverify contract`, listed per kernel in `run.sh`); the verdict is derived
from them plus binsec's `[ct]` result. If `[ct]` is `secure`, `[cache-line]` is
secure too (a coarser observer sees no more than the byte observer).

## Run

```sh
bash run.sh            # gcc
CC=clang bash run.sh   # clang
```

Result (gcc):

| kernel | `[ct]` | `[cache-line]` | reason |
|---|---|---|---|
| `b_dense` | secure | secure | no secret-dependent address |
| `b_codebook_small` | insecure | **secure** | span 32 B fits 1 cache line |
| `b_codebook_wide` | insecure | insecure | reaches 4 cache lines (span 256 B) |
| `b_embedding_row` | insecure | insecure | reaches 32 cache lines (span 4096 B) |

The split is the point: all three gathers leak an address under `[ct]`, but
under a realistic cache-line observer only the ones whose secret-dependent
address crosses a line boundary remain exploitable. `b_codebook_small`
reproduces the threat-model note ([`../../../docs/research/formal_verif.threat-model.agents.md`](../../../docs/research/formal_verif.threat-model.agents.md)):
the toy 32-byte codebook is formally insecure yet a pure cache attack learns
almost nothing at that size. `b_embedding_row` is the `wte[token]` case — rows
span many lines, so it leaks under both contracts.

## Assumptions (honest)

- **Alignment.** The one-line "secure" claim holds because the tables are
  cache-line aligned; an unaligned base could straddle a boundary, and
  `ctverify` stays conservative (`insecure`) when alignment is unknown
  (`--unaligned`).
- **Contract, not silicon.** `[cache-line]` is a *model* of the observer.
  Whether a given CPU actually leaks exactly at line granularity is layer **C**
  (Revizor / Scam-V), and the analog wall-clock residue is layer **D**
  (dudect / ct-fuzz). B proves the software satisfies the contract; it does not
  prove the hardware honours it.

## References

- Yarom & Falkner, *Flush+Reload* (USENIX Security 2014) — the cache-line-resolution channel this contract models.
- Guarnieri, Köpf, Reineke, Vila, *Hardware-Software Contracts for Secure Speculation* (IEEE S&P 2021) — leakage-contract framework.
- Wang et al., *LeaVe* — verifying hardware (RTL) against a leakage contract (the hardware half, out of scope here).
