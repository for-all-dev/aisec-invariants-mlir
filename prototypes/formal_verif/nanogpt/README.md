# nanoGPT weight-confidentiality (per-program, on the binary)

A nanoGPT-*shaped* corpus that ports the `formal_verif` methodology from crypto
constant-time to **model-weight confidentiality**. Same tool (`binsec -checkct`,
relational SE), same before/after (`-O0` vs `-O2`), same per-program verdict —
new asset: the **weights**.

## Threat model

The weights are the confidential asset (a proprietary model served for
inference). Adversary observes microarchitectural side channels during
inference — **branch timing** and **cache / memory-access addresses**. A kernel
is **secure** iff the weight *values* never influence a branch condition or a
memory address; they may only flow into arithmetic. Formally: non-interference
of the leakage trace (PC + addresses) w.r.t. the secret weights.

For the full adversary analysis — capability bundle, concrete attacker profiles
(cloud co-tenant, malicious TEE host, on-device, physical), and the formal-vs-
cache-line-resolution caveat — see
[`docs/research/formal_verif.threat-model.agents.md`](../../../docs/research/formal_verif.threat-model.agents.md).

- **Secret** = `W[]` (weights) — `secret global W` in `w.cfg`
- **Public** = `x[]` (activations) — `public global x`
- **Concrete** = `codebook[]` — a fixed public dequant table (not an input, so
  not in the cfg); only a *secret index* into it can leak.

## Why this is faithful to nanoGPT (and its limits)

Every kernel is one row of `y = W . x`, the atom of every linear and attention
projection in a transformer. The leaks are **structural, not size-dependent** —
a secret-indexed gather leaks at `N=4` exactly as at `N=768` — so a toy miniature
reproduces the phenomenon a real layer would exhibit.

**We do not verify nanoGPT.** BINSEC eats x86-32 binaries and symbolic execution
is bounded, so:
- dimensions are tiny (`N=4`, `|codebook|=8`) to stay decidable — a real matmul's
  formula is astronomically large and would time out;
- the target is CPU x86-32 (`-m32 -static`), not the GPU/Triton path nanoGPT
  actually runs.

The claim is: *the methodology transfers to nanoGPT's characteristic operation*
at a scale where formal proof is possible. This is the intended next step after
the crypto beachhead — "the codebook gather is the transformer's S-box."

## The corpus (`cases.c`)

| kernel | weight leaks via | expected |
|---|---|---|
| `mm_dense` | — (weights → arithmetic only) | **secure** (baseline / false-positive guard) |
| `mm_sparse` | **branch** (skip-zero → leaks sparsity mask) | insecure |
| `mm_codebook` | **memory address** (quantized dequant → the S-box analog) | insecure, no branch |
| `mm_codebook_ct` | oblivious dequant (read-all + mask-select) | secure at `-O0`; **clang `-O1` reintroduces the leak** (see below) |

The headline candidate is `mm_codebook`: the leak is a secret-dependent **load
address** with **no conditional jump**, so branch-counting / eyeballing the
disassembly sees nothing — only the relational memory-address check catches it.
`mm_codebook_ct` is the compiler-*introduced* experiment (parallels
`quadrants/q_oblivious`); the result is below.

## A compiler-introduced leak (`mm_codebook_ct`)

`mm_codebook_ct` is written to be constant-time: it reads **all** codebook
entries at public addresses and mask-selects the one at the secret index, so
there is no secret-dependent branch or address in the source. It verifies
`secure` at `-O0`. Sweeping `binsec -checkct` across compilers and optimisation
levels (`bash compiler_introduced.sh`, which drives the `ctverify` package):

| | `-O0` | `-O1` | `-O2` | `-O3` |
|---|---|---|---|---|
| **gcc** | secure | secure | secure | secure |
| **clang** | secure | **insecure** | secure | secure |

**clang `-O1` lowers the branchless mask-select back into a secret-dependent
branch** (`control flow` leak at `0x80499dc`): a leak the *compiler* introduces,
not the source. The disassembly shows it directly —

```asm
cmp    ebp, ecx        ; ebp = W[i] & 7  (secret index) vs ecx = j
jne    ...             ; secret-dependent conditional jump
mov    esi, [edx+ecx*4] ; codebook[j] now loaded only when j == secret index
```

This is a real compiler-introduced constant-time regression on a transformer's
weight-dequant kernel — the same class as the documented Clangover ML-KEM case
(branchless constant-time source → secret-dependent branch after lowering). It
is `secure → insecure` across the *same source*, differing only in the compiler
pass, which is exactly the compiler-introduced quadrant (`../README.md`); gcc and
clang `-O2/-O3` keep the kernel oblivious.

## Run

Inside the Docker image (`../Dockerfile`), or any host with binsec + `-m32`:

```sh
bash run.sh              # gcc
CC=clang bash run.sh     # clang — the interesting arm
```

Prints a per-kernel `-O0 | -O2 | verdict` table. Quadrant labels mirror the
parent prototype: `NN` oblivious, `YY` authored-and-kept, `YN` compiler-removed,
`NY` **compiler-introduced**.

## Status / assumptions to verify on first run

- [ ] `secret global W` marks the whole `W[N]` array region. If binsec only
  flags `W[0]`, switch `w.cfg` to a sized range or per-element secrets.
- [ ] `mm_codebook` fires as a **memory** leak (address-dependent load), not a
  branch — confirm via the counterexample localizing a `mov (reg)`, not a `jcc`.
- [ ] `mm_dense` verifies **secure** (false-positive guard) before trusting any
  insecure verdict — same discipline as the parent calibration controls.

## Real nanoGPT (`realgpt_probe.py`, CPU-only)

`nanoGPT/` is a vendored clone of Karpathy's repo (upstream
`3adf61e154c3fe3fca428ad6bc3818b27a3b8291`, MIT). `realgpt_probe.py` is a
[PEP 723](https://peps.python.org/pep-0723/) single-file `uv` script (inline
`# /// script` deps, **CPU torch** pinned via `download.pytorch.org/whl/cpu` — no
GPU needed) that:

1. builds a tiny GPT from the **real** `model.py` and runs a real forward pass;
2. pulls a genuine weight matrix (`transformer.h[0].mlp.c_fc.weight`);
3. expresses `y = W·x` two ways — dense vs on-the-fly codebook dequant — and
   lowers each to an **aten-level IR graph** (`make_fx`), localizing the leak:
   dense → `addmm` (oblivious); codebook → `index`/`embedding` gather (the
   secret-dependent address = weight leak), on real nanoGPT weights.

```sh
uv run realgpt_probe.py          # first run downloads the CPU torch wheel
```

This is the ML-compiler-IR view; `binsec -checkct` on `cases.c::mm_codebook` is
the binary-level *proof* of the same gather. The bridge still open: lower that
IR the rest of the way (→ MLIR/LLVM → x86-32 object) and run `-checkct` on the
compiler's *own* output, testing whether the tensor compiler introduces the leak.

## Next steps

1. Functional-equivalence (`../equiv/`) on `mm_codebook` vs `mm_codebook_ct`:
   same output, one leaks — the orthogonality result in weight terms.
2. **[in progress]** ML compiler: `realgpt_probe.py` reaches the aten IR; extend
   to lower toy dims → MLIR/LLVM → x86-32 object and run `-checkct` on the
   *lowered* binary — the `aisec-invariants-mlir` target proper.
3. Real dimensions are out of SE reach → hand off to the A/B/C/D roadmap
   (leakage contracts + Revizor + dudect).
