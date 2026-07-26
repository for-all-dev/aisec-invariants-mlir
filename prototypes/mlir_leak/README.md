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

### Fixed: `run_mlir.py` was unrunnable since 2026-07-16

`run_mlir.py` imported `_disjoint` from `../leak_check/noninterference.py` and
compared counts sampled at a **fixed** secret path. Commit `d0d3232` in
`leak_check` ("the count channel is confounded by measurement context")
replaced that criterion with a context-varying floor+stability guard and
removed `_disjoint` in the process; this file was never updated, so every run
since raised `ImportError`. Fixed by reusing `noninterference.py`'s
context-varying method directly (via `leak_check/differential.py`, which
factors that method out for reuse instead of re-deriving a weaker one) — see
`analyze()`'s docstring.

**Re-validated under the fixed engine.** Every row of **Results** below was
re-measured and reproduces exactly — `dIr`/`dBc`/`dDw` byte-for-byte, all
verdicts unchanged: the core `kernel × P0..P5 @ -O0` sweep, `P0 @ -O2`, the
`P4` bufferized variants, and all four `dynshape`/`dynshape_t` rows
(`@ -O0`, `@ -O2`, `@ -O3`). The `sparse/` finding is now re-measured too,
by its own runner (see below). Not re-measured: nothing.

Both axes now sweep in one run (`--opt` takes several levels), and each cell
gets a **computed** verdict relative to a baseline cell
(`leak-present-in-baseline` / `introduced-relative-to-baseline` /
`removed-relative-to-baseline` / `oblivious`, from
`differential.verdict_relative_to_baseline` — the N-build generalization of
`noninterference.py`'s authored/compiler-introduced/compiler-removed/
oblivious quadrant). Previously the verdict spanned MLIR pipelines only, so
findings 1/2/4 below — which are `-O0`-vs-`-O2` results — still had to be
inferred by eye across two separate invocations. They are now computed:

```
$ python3 run_mlir.py --kernels cond_reduce mask_select idx_gather --pipelines P0 --opt O0 O2
  cond_reduce    P0@O0  LEAK   baseline-cell                    taint:cf ...
  cond_reduce    P0@O2  obliv  removed-relative-to-baseline     clean
  mask_select    P0@O2  obliv  removed-relative-to-baseline     clean
  idx_gather     P0@O2  LEAK   leak-present-in-baseline         taint:addr
```

### Note: the taint parser is broadened, in the shared instrument
`instruments.memcheck_taint` matches only the control-flow message
(`"... depends on uninitialised value"`). An **address** leak (gather) prints
`"Use of uninitialised value of size N"`, which that regex misses. Without the
broadened match, the gather leak is invisible on *every* channel (its
instruction count is identical — `dIr=0` — only the address differs).

This used to be a private copy of the instrument here, which duplicated
`memcheck_taint_cmd`'s whole valgrind/subprocess body just to change the
regex. It is now a **parameter of the standard instrument** —
`instruments.memcheck_taint_cmd(..., classify=True)` returns `kind`
(`cf`/`addr`/`""`) and `kinds` (the full set, since a build can fire on
both and a single label hides one behind the other). It is opt-in because
enabling it by default would silently change what `leak_check`'s own
recorded corpus results mean.

Caveat that matters when comparing two builds: memcheck's cf message covers
a conditional jump **or move**, so *any* comparison on a secret trips `cf`,
even a fully branchless masked one. `cf` is therefore a weak discriminator
between two builds that both touch the secret at all — see `sparse/`, where
the verdict is taken on the address channel specifically.

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
8. **An *optimizing* pass that DOES introduce a leak: `sparse_tensor` + `--sparsification`**
   (see `sparse/`). The sparsifier lowers a `linalg.generic` over a sparse tensor into iteration
   over *stored coordinates*, so the loop trip count and the `x[coordinates[k]]` load address
   depend on the sparsity **pattern** -- while the dense lowering of the same op is oblivious.
   Measured on a scatter kernel (`out[crd[i]] = vals[i]`, secret = coordinates, identical vals/
   nnz across classes): **taint fires (address leak)**, count is blind (`dIr=dBc=dDw=0`, trip
   count public). This is the "compiler-introduced" quadrant firing via an optimization -- the
   known sparsity/pruning-pattern side channel -- and the one case in this study where an
   optimizing pass (not the `-O0` selector) manufactures the channel.
   **Now a computed verdict, not a claim**: `sparse/run_sparse.py` measures the sparsified
   build against an oblivious dense reference (`sparse/scatter_dense.mlir`) on the same
   engine as everything else, and reports `introduced-relative-to-baseline` on the
   **address channel**. The verdict has to be per-channel: both builds compare the secret,
   and memcheck's cf message covers a conditional jump *or move*, so the oblivious
   reference trips `cf` too — only the address channel separates them (dense: no address
   channel; sparse: `taint:addr`). Previously this finding had no runner at all — a
   copy-paste shell recipe in `sparse/README.md` — so it was the only result here that
   never went through the shared instruments or the floor/stability guard.

## Gaps / honest caveats

- All builds are **AVX2-capped** (`-mno-avx512f`) so valgrind 3.22 can decode them; native
  AVX-512 codegen is a different config point (valgrind can't measure it here).
- Within the CORE-dialect sweep, no *optimizing* pass introduced a leak into oblivious code
  (the one introduced leak, `mask_select` @ `-O0`, is the unoptimized instruction selector's,
  removed by optimization); `idx_gather`/`dynshape` are **authored**. The exception is outside
  core dialects: `sparse_tensor` + `--sparsification` (finding 8, `sparse/`) is an optimizing
  pass that DOES introduce an address channel. "Not detected" ≠ "proven absent" (PRINCIPLES §1).
- **P3 super-vectorize** lowered every kernel but its verdicts equal P0's; whether it actually
  vectorized (vs no-op'd) is not confirmed at the IR level.
