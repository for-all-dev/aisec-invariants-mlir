SHELL := /bin/sh

HARNESS_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
LLVM_BIN ?= /opt/homebrew/opt/llvm/bin
PYTHON ?= python3
HOST_CC ?= cc
LIT ?= $(HARNESS_DIR)/.venv/bin/lit
LIT_FLAGS ?= -sv
LIT_BUILD_ROOT ?= $(HARNESS_DIR)/build/lit
RISCV_GCC ?=

.PHONY: check check-mlir check-integration list-tests bootstrap-lit require-lit

check: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  "$(LIT)" $(LIT_FLAGS) "$(HARNESS_DIR)"

check-mlir: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  "$(LIT)" $(LIT_FLAGS) "$(HARNESS_DIR)/mlir"

check-integration: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  "$(LIT)" $(LIT_FLAGS) "$(HARNESS_DIR)/integration"

list-tests: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  "$(LIT)" --show-tests "$(HARNESS_DIR)"

bootstrap-lit:
	$(PYTHON) -m venv "$(HARNESS_DIR)/.venv"
	"$(HARNESS_DIR)/.venv/bin/python" -m pip install \
	  --requirement "$(HARNESS_DIR)/requirements-test.txt"

require-lit:
	@if ! command -v "$(LIT)" >/dev/null 2>&1; then \
	  echo "error: LLVM lit not found at $(LIT)" >&2; \
	  echo "run 'make bootstrap-lit' or set LIT=/path/to/lit" >&2; \
	  exit 1; \
	fi
