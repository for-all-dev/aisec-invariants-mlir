# The toolchain the paper's measurement tables are stated against: Ubuntu 24.04's
# MLIR/Clang 18.1.3 and Valgrind 3.22.0 (glibc 2.39). The rig hardcodes the -18
# binaries, and Valgrind 3.22 does not decode AVX-512, hence -mno-avx512f in run_mlir.py.
#
#   docker build -t mlir-leak prototypes/mlir_leak
#   docker run --rm --hostname "$(hostname)" --user "$(id -u):$(id -g)" \
#       -v "$PWD/prototypes:/work/prototypes" mlir-leak prototypes/mlir_leak/regen_table.sh
#
# --hostname names the results/<date>-<host>/ dir after the machine rather than the
# container; --user keeps the written results owned by you rather than root.
FROM ubuntu:24.04

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      mlir-18-tools llvm-18 clang-18 valgrind python3 libc6-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /work
