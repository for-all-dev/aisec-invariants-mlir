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
mlir-opt-18 scatter.mlir "--sparsifier=enable-runtime-library=false" -o scatter.lld.mlir
mlir-translate-18 --mlir-to-llvmir scatter.lld.mlir -o scatter.ll
clang-18 -O0 -c scatter.ll -o scatter.o
clang-18 -O0 -I/usr/include -o scatter_bin sparse_driver.c scatter.o
python3 -c "import array; array.array('q',[0,1,2,3,4,5,6,7]).tofile(open('crd_A.bin','wb')); \
            array.array('q',[3,29,61,97,130,168,201,240]).tofile(open('crd_B.bin','wb'))"
valgrind --tool=memcheck --track-origins=yes ./scatter_bin crd_B.bin taint   # -> Use of uninitialised value (addr)
```

## Caveats

- ABI: mlir-18 lacks `--sparse-assembler` (mlir-19+), so `sparse_driver.c` calls the sparse
  kernel via its standard memref ABI (unpacked descriptors + struct return) directly.
- The sparse *encoding* is a source annotation; the *choice* to iterate over stored
  coordinates (skip zeros) is the optimization, and that is what creates the address channel.
  A dense lowering of the same values-at-(public)-positions is oblivious.
- Config point: mlir-opt-18 1:18.1.3, clang-18 -O0, Zen5, valgrind 3.22.
