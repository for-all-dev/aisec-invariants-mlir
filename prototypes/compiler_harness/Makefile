SHELL := /bin/sh

HARNESS_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
LLVM_BIN ?= /opt/homebrew/opt/llvm/bin
PYTHON ?= python3
HOST_CC ?= cc
LIT ?= "$(HARNESS_DIR)/.venv/bin/python" -c 'from lit.main import main; main()'
LIT_FLAGS ?= -sv
LIT_BUILD_ROOT ?= $(HARNESS_DIR)/build/lit
RISCV_GCC ?=
SPS_SCAN ?=
SPS_VERIFIER ?=
SPS_TEACHING_MATERIALIZED ?=
SPS_ERROR_MATERIALIZED ?=

.PHONY: check check-shape check-mlir check-integration check-diagnostic \
	check-sps check-artifacts check-p4-risk check-contracts list-tests \
	list-fixture-status \
	bootstrap-lit require-lit

check: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  SPS_SCAN="$(SPS_SCAN)" SPS_VERIFIER="$(SPS_VERIFIER)" \
	  SPS_TEACHING_MATERIALIZED="$(SPS_TEACHING_MATERIALIZED)" \
	  SPS_ERROR_MATERIALIZED="$(SPS_ERROR_MATERIALIZED)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)"
	@if [ -z "$(SPS_VERIFIER)" ] || { [ -z "$(SPS_TEACHING_MATERIALIZED)" ] && [ -z "$(SPS_ERROR_MATERIALIZED)" ]; }; then \
	  echo "SKIPPED: no executable Rev4 verifier/materialized conformance bundle; no ModelStatus was computed"; \
	fi

check-shape: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  SPS_SCAN="$(SPS_SCAN)" SPS_VERIFIER="$(SPS_VERIFIER)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/mlir"

check-mlir: check-shape

check-integration: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  SPS_SCAN="$(SPS_SCAN)" SPS_VERIFIER="$(SPS_VERIFIER)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/integration"

check-diagnostic: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" SPS_SCAN="$(SPS_SCAN)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/diagnostic"

check-sps: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" SPS_VERIFIER="$(SPS_VERIFIER)" \
	  SPS_TEACHING_MATERIALIZED="$(SPS_TEACHING_MATERIALIZED)" \
	  SPS_ERROR_MATERIALIZED="$(SPS_ERROR_MATERIALIZED)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/sps"
	@if [ -z "$(SPS_VERIFIER)" ] || { [ -z "$(SPS_TEACHING_MATERIALIZED)" ] && [ -z "$(SPS_ERROR_MATERIALIZED)" ]; }; then \
	  echo "SKIPPED: no executable Rev4 verifier/materialized conformance bundle; no ModelStatus was computed"; \
	fi

check-artifacts: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/artifacts"

check-contracts: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/contracts"

check-p4-risk: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/p4-risk"

list-tests: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  SPS_SCAN="$(SPS_SCAN)" SPS_VERIFIER="$(SPS_VERIFIER)" \
	  SPS_TEACHING_MATERIALIZED="$(SPS_TEACHING_MATERIALIZED)" \
	  SPS_ERROR_MATERIALIZED="$(SPS_ERROR_MATERIALIZED)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) --show-tests "$(HARNESS_DIR)"

list-fixture-status:
	@$(PYTHON) "$(HARNESS_DIR)/c/check_harness.py" list-fixtures

bootstrap-lit:
	$(PYTHON) -m venv "$(HARNESS_DIR)/.venv"
	"$(HARNESS_DIR)/.venv/bin/python" -m pip install \
	  --requirement "$(HARNESS_DIR)/requirements-test.txt"

require-lit:
	@if ! $(LIT) --version >/dev/null 2>&1; then \
	  echo "error: LLVM lit is not runnable through: $(LIT)" >&2; \
	  echo "run 'make bootstrap-lit' or set LIT=/path/to/lit" >&2; \
	  exit 1; \
	fi
