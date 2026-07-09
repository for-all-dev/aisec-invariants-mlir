# mlir_leak: do MLIR lowering / optimization passes introduce information leaks?

The `leak_check` differential non-interference experiment with the "compiler axis"
swapped from (gcc/clang × flags) to **(MLIR lowering-pipeline × LLVM -O level)**. Tests
the project proposal's thesis: *lowering passes can introduce information channels
(data-dependent control flow, memory aliasing) that leak protected weights even when the
source program is non-interferent.* Uses core MLIR dialects + prebuilt MLIR-18 (no HEIR,
no Bazel), and reuses `../leak_check`'s Valgrind instruments unchanged.

## How it works

- 4 core-MLIR kernels (`*.mlir`), lowered by `mlir-opt-18` through several pipelines,
  `mlir-translate-18 → clang-18 -c`, linked into `mlir_driver.c` (bare-pointer memref ABI).
- The driver speaks `../leak_check/ctbench/harness.c`'s protocol, so
  `instruments.callgrind_count_cmd` / `memcheck_taint_cmd` apply unchanged.
- **Leakage is shown by memcheck shadow memory (taint):** the driver marks the secret bytes
  `VALGRIND_MAKE_MEM_UNDEFINED`; memcheck reports any secret byte reaching a conditional
  branch/move (`taint:cf`) or a load/store address (`taint:addr`). Callgrind `Ir/Bc/Dw`
  differential (class A vs B) corroborates. Taint is primary.
- Run: `python3 run_mlir.py` (MLIR axis) / `--pipelines P0 --opt O2` (LLVM -O axis).

### Note: the taint parser was broadened here
`instruments.memcheck_taint` matches only the control-flow message
(`"... depends on uninitialised value"`). An **address** leak (gather) prints
`"Use of uninitialised value of size N"`, which that regex misses. `run_mlir.py.taint_check`
matches both and classifies `cf` vs `addr`. Without this, the gather leak is invisible on
*every* channel (its instruction count is identical — `dIr=0` — only the address differs).

## Results (config point: mlir-opt-18 1:18.1.3, clang-18, `-mavx2 -mno-avx512f`, Zen5, valgrind 3.22)

**MLIR-pipeline axis** (backend fixed `clang -O0`), P0=scf-loops, P1=affine, P2=canonicalize+cse,
P3=affine-super-vectorize, P5=generalize-named-ops:

```
kernel        P0  P1  P2  P3  P5      taint / mechanism
matvec         .   .   .   .   .      oblivious (dense fixed-bound loops)
cond_reduce    L   L   L   L   L      taint:cf  (authored scf.if on sum(secret))
mask_select    L   L   L   L   L      taint:cf  (see below)
idx_gather     L   L   L   L   L      taint:addr (secret-dependent load address)
```

MLIR pipeline choice is **verdict-invariant** at the -O0 backend: canonicalize/cse and
super-vectorize neither introduced nor removed any leak here. The determining factor is the
LLVM backend -O level (below).

**P4 one-shot-bufferization** (tensor-source kernels `matvec_t`, `select_t`; the proposal's
top-flagged suspect for aliasing/copy divergence). Verdicts are **byte-identical** to the
memref versions:

```
kernel           P4@O0   P4@O2      vs memref P0
matvec_t          .       .         same as matvec  (oblivious)
mask_select_t     L       .         same as mask_select (taint:cf dIr=-8192 @O0; removed @O2)
```

Bufferization inserts a `malloc`/copy but it is **secret-independent** (in-place-vs-copy is a
compile-time aliasing decision on IR structure, not runtime values), so it introduces no
channel at static shapes.

**Dynamic-shape channel** (`dynshape`: the secret *is* a buffer extent `k`; class A `k=1`,
B `k=4096`). A `memref.alloc(%k)` + `scf.for 0..k` whose size/trip-count are secret-derived.

```
build                              verdict  channels (dIr / dBc / dDw)
dynshape  P0..P5 @ -O0              L        +73872 / +4124 / +20493   taint:cf
dynshape  P0 @ -O2 / -O3           L         +5117 /  +511 / (Dw gone) taint:cf
dynshape_t (bufferized) P4 @ -O0   L        +106703 / +8233 / +24595  taint:cf
dynshape_t (bufferized) P4 @ -O2   L         +12391 / +1194 / +4631   taint:cf
```

Irreducible on the control channel (loop bound `j<k` depends on the secret -> `taint:cf` at
every level; trip count can't be optimized away, `k` is runtime). Optimization *narrows* it
(vectorizes the loop: `dIr` 73872->5117). The **memory** channel's survival depends on buffer
**liveness**: `dynshape`'s write-only buffer is DCE'd at `-O2` (`Dw` gone), but `dynshape_t`'s
buffer is *reduced* (live) so its secret-sized `Dw` footprint **survives -O2** (`dDw=+4631`).
Bufferizing the dynamic tensor inserts the *intrinsic* secret-sized `memref.alloc(%k)` plus a
*fixed-size* result `memref.copy` -- i.e. it does **not** add a secret-sized copy (no
amplification beyond the source's own dynamic shape).

**LLVM -O axis** (pipeline fixed P0):

```
kernel        O0   O2   O3     mechanism
matvec         .    .    .     oblivious throughout
cond_reduce    L    .    .     authored branch -> -O2 makes it branchless arithmetic -> REMOVED
mask_select    L    .    .     source arith.select is branchless, but -O0 lowers it to a
                               conditional BRANCH (jne, dIr=-8192); -O2/-O3 emit a branchless
                               blend (andps/andnps/orps) -> REMOVED
idx_gather     L    L    L     table[secret_idx]: secret-dependent load address; NO -O removes it
```

## Findings

1. **A lowering *did* introduce a control-flow leak — `mask_select` at `-O0`.** A source-level
   *branchless* `arith.select` on a secret mask was lowered by the `-O0` backend into a
   data-dependent conditional branch (confirmed in the disassembly: `jne` on the mask, 0
   cmov/blend; `dIr=-8192`, `taint:cf`). This is the proposal's thesis realized — lowering
   introducing data-dependent control flow on a secret. It is the `-O0` instruction selector's
   doing, and optimization removes it.
2. **Optimization *removes* the control-flow channels (compiler-removed).** Both `cond_reduce`
   (authored `if/else`) and `mask_select` (the `-O0`-introduced branch) become oblivious at
   `-O2/-O3` — branchless arithmetic / `andps` blend. Mirrors leak_check's Inductor
   `where_select` and C `select_branch` results: optimizers tend to *remove* value-dependent
   control flow, not add it.
3. **The one irreducible leak is the address channel (`idx_gather`), and it is the one both
   other channels miss.** `table[secret_idx]` leaks through the load address at every -O level.
   It is invisible to the count channel (`dIr=0` — identical instructions, different addresses)
   AND to the original harness's taint regex (prints "Use of uninitialised value", not
   "depends on") — only the broadened parser catches it. This is the memory/addressing channel
   the proposal flagged as known-tricky, and the experiment shows it is the durable one.
4. **The "compiler-introduced" quadrant fired only at `-O0` (mask_select), and optimization
   removed it.** The stronger claim — that an *optimizing* pass introduces a leak into oblivious
   code — did **not** fire at these config points. `idx_gather`'s address dependence is inherent
   to a gather (authored), not compiler-introduced. "Not detected" ≠ "proven absent" (PRINCIPLES §1).
5. **Bufferization (P4) introduced no leak.** The proposal's top suspect is oblivious at static
   shapes: tensor kernels through one-shot-bufferize give verdicts and count-deltas identical to
   their memref versions. The inserted copy is secret-independent.
6. **The dynamic-shape channel is real and irreducible on the control channel.** A secret-derived
   extent (`dynshape`) leaks at every pipeline and every `-O` (the loop bound depends on the
   secret; `taint:cf`). Optimization *narrows* it (vectorization) but cannot remove a runtime
   trip count. This is a third irreducible class alongside `idx_gather`'s address dependence.
7. **The dynamic-shape *memory* channel survives optimization iff the secret-sized buffer is
   live.** `dynshape` (write-only buffer) loses its `Dw` channel to DCE at `-O2`; the bufferized
   `dynshape_t` (buffer reduced/read) keeps a secret-sized `Dw` footprint at `-O2`. Bufferization
   supplies the intrinsic secret-sized alloc but no *extra* secret-sized copy -- no amplification.

## Gaps / honest caveats

- All builds are **AVX2-capped** (`-mno-avx512f`) so valgrind 3.22 can decode them; native
  AVX-512 codegen is a different config point (valgrind can't measure it here).
- The irreducible leaks (`idx_gather` address, `dynshape` extent) are **authored** — the secret
  drives the address/shape in the source. No *optimizing* pass was observed to introduce a leak
  into genuinely oblivious code (the one introduced leak, `mask_select` @ `-O0`, is the
  unoptimized instruction selector's, and optimization removes it). "Not detected" ≠ "proven
  absent" (PRINCIPLES §1).
- **P3 super-vectorize** lowered every kernel but its verdicts equal P0's; whether it actually
  vectorized (vs no-op'd) is not confirmed at the IR level.
