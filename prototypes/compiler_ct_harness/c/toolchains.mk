LLVM_BIN ?= /opt/homebrew/opt/llvm/bin
CLANG ?= $(LLVM_BIN)/clang
MLIR_TRANSLATE ?= $(LLVM_BIN)/mlir-translate
MLIR_OPT ?= $(LLVM_BIN)/mlir-opt
OPT ?= $(LLVM_BIN)/opt
LLC ?= $(LLVM_BIN)/llc
RISCV_GCC ?=

COMMON_CFLAGS := -std=c11 -Wall -Wextra -Wpedantic -fno-builtin
X86_FLAGS := --target=x86_64-unknown-linux-gnu
RV32_FLAGS := --target=riscv32-unknown-elf -march=rv32i -mabi=ilp32
AARCH64_FLAGS := --target=aarch64-unknown-linux-gnu

BUILD := ../build
MLIR_DIR := ../mlir
