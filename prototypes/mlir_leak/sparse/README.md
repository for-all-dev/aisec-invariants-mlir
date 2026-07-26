# sparse: an MLIR *optimizing* pass that introduces a leak (`--sparsification`)

The core-dialect sweep (`../README.md`) found that optimizers *remove* control-flow
channels -- no optimizing pass introduced a leak into oblivious code. This subdir finds the
exception: the **`sparse_tensor` dialect + `--sparsification`** pass manufactures a
secret-dependent memory-address channel from a computation whose dense lowering is oblivious.
This reproduces the known **sparsity / pruning-pattern side-channel** class (a proprietary
sparse/pruned model's structure leaking through data-dependent execution).

## Mechanism (IR-level, from the actual pass)

`--sparsification` lowers a `linalg.generic` over a sparse tensor into iteration over
*stored* (nonzero) coordinates. For a sparse matvec `y = A.x` it emits:

```
for i in 0..M:
  for k in positions[i] .. positions[i+1]:      # trip count = nnz in row i  (pattern)
    y[i] += values[k] * x[ coordinates[k] ]      # x address = coordinate     (pattern)
```

Both the inner trip count and the `x[coordinates[k]]` load address depend on the sparsity
**pattern**. The dense lowering of the same op visits all elements identically -> oblivious.
So the sparsification optimization is what introduces the channel.

## Measured (scatter kernel, `scatter.mlir`)

`sparse_tensor.assemble(vals,pos,crd) -> convert-to-dense` sparsifies to
`for i in pos[0]..pos[1]: out[crd[i]] = vals[i]`. The store address is the secret
coordinate. Two secret classes: **identical** `vals` and `pos` (same nnz=8), only the
coordinate positions differ, so any dependence is purely the pattern.

```
channel   class A (coords 0..7)   class B (coords spread)   verdict
taint     Use of uninitialised    Use of uninitialised      LEAK (addr): crd -> store address
count     Ir=3377 Bc=332 Dw=875   Ir=3377 Bc=332 Dw=875     oblivious (dIr=dBc=dDw=0)
```

The count channel is **blind** (trip count is public here; instructions identical) -- the
leak is caught **only** by memcheck shadow-memory taint on the address, exactly like the
core sweep's `idx_gather`. This is the definitional "compiler-introduced" quadrant firing via
an *optimizing* pass.

## Reproduce

```sh
python3 run_sparse.py
```

Builds both lowerings, measures each against the same two secret classes on
the shared engine (`../../leak_check`: `instruments.py` for both valgrind
channels, `differential.py` for the context-varying floor+stability guard),
and prints a computed verdict:

```
  LOWERING   ADDR   VERDICT (addr channel)             CHANNELS
  dense      no     baseline-cell                      taint:cf
  sparse     yes    introduced-relative-to-baseline    taint:addr
```

### Why the verdict is per-channel, and what the baseline is

The claim is that *the pass* introduces the channel, so the sparsified build
needs an oblivious reference to be judged against. That reference cannot be
another pipeline over the same file: mlir-18 will not legalize
`sparse_tensor.convert` off the sparsification path (`--sparse-tensor-conversion`
rejects it), so "the same IR lowered densely" does not exist. `scatter_dense.mlir`
is that reference instead — same signature and same result, computed by
visiting every dense position, with the secret never used as an address. It
deliberately avoids `arith.select`, because this study's own core sweep found
`-O0` lowers a select on a secret into a conditional *branch* (`mask_select`),
which would make the baseline leak for a reason unrelated to sparsity.

Even so, the dense reference reports `taint:cf`: memcheck's control-flow
message covers a conditional jump **or move**, so merely *comparing* the
secret coordinate against each position trips it, however branchlessly it
compiles. A leak/no-leak bit therefore cannot separate the two builds — but
the **address** channel does, and that is exactly what `--sparsification`
adds. Hence the verdict is taken on `addr`.

This ran as a hand-copied shell recipe until now, which made the strongest
finding in this prototype the only one that never went through the shared
instruments, never got the floor/stability guard, and could not be
re-validated by running anything.

## Caveats

- ABI: mlir-18 lacks `--sparse-assembler` (mlir-19+), so `sparse_driver.c` calls the sparse
  kernel via its standard memref ABI (unpacked descriptors + struct return) directly.
- The sparse *encoding* is a source annotation; the *choice* to iterate over stored
  coordinates (skip zeros) is the optimization, and that is what creates the address channel.
  A dense lowering of the same values-at-(public)-positions is oblivious.
- Config point: mlir-opt-18 1:18.1.3, clang-18 -O0, Zen5, valgrind 3.22.
