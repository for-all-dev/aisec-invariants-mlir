#!/usr/bin/env bash
# Regenerate every row of the paper's measured-cells table in one run, and record the
# machine and toolchain beside the numbers so a table can always be traced to its run.
# Meant to run inside the Dockerfile's image; see the Dockerfile header.
set -euo pipefail

cd "$(dirname "$0")"
OUT="results/$(date +%Y%m%d)-$(hostname)"
mkdir -p "$OUT"

{
  echo "date:     $(date -Iseconds)"
  echo "cpu:      $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | sed 's/^ //')"
  echo "kernel:   $(uname -r)"
  echo "glibc:    $(ldd --version | head -1)"
  echo "mlir-opt: $(mlir-opt-18 --version | grep -m1 -i version)"
  echo "clang:    $(clang-18 --version | head -1)"
  echo "valgrind: $(valgrind --version)"
  echo "python:   $(python3 --version)"
} | tee "$OUT/environment.txt"

# The MLIR axis: every scalar kernel through P0..P3,P5 at -O0.
python3 run_mlir.py --kernels matvec cond_reduce mask_select idx_gather dynshape \
  --pipelines P0 P1 P2 P3 P5 --opt O0 | tee "$OUT/mlir_axis.O0.out"

# The LLVM axis, on the baseline pipeline only.
python3 run_mlir.py --kernels matvec cond_reduce mask_select idx_gather dynshape \
  --pipelines P0 --opt O0 O2 O3 | tee "$OUT/llvm_axis.P0.out"

# One-shot bufferization applies to the tensor kernels only.
python3 run_mlir.py --kernels matvec_t mask_select_t dynshape_t \
  --pipelines P4 --opt O0 O2 | tee "$OUT/bufferization.P4.out"

# The sparsifier against its hand-written dense reference.
python3 sparse/run_sparse.py | tee "$OUT/sparse.out"

echo "wrote $OUT"
