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
SPS_REV41_MATERIALIZED ?=
SPS_INTERFACE_ROOT ?=
SPS_SOURCE_ANNOTATIONS_ROOT ?=
SPS_REFERENCE_ROOT ?=
Z3 ?=
export SPS_SOURCE_ANNOTATIONS_ROOT

.PHONY: check check-shape check-mlir check-integration check-diagnostic \
	check-sps check-candidates check-artifacts check-p4-risk check-contracts \
	check-interfaces check-source-annotations check-checkpoints list-tests \
	check-sps-reference \
	list-fixture-status list-fixture-results \
	bootstrap-lit require-lit

check: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  SPS_SCAN="$(SPS_SCAN)" SPS_VERIFIER="$(SPS_VERIFIER)" \
	  SPS_REV41_MATERIALIZED="$(SPS_REV41_MATERIALIZED)" \
	  SPS_REFERENCE_ROOT="$(SPS_REFERENCE_ROOT)" Z3="$(Z3)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)"
	@if [ -z "$(SPS_VERIFIER)" ] || [ -z "$(SPS_REV41_MATERIALIZED)" ]; then \
	  echo "SKIPPED: no exact Rev4.1 V2 verifier/materialized bundle; no ModelStatus was computed"; \
	fi

check-shape: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  SPS_SCAN="$(SPS_SCAN)" SPS_VERIFIER="$(SPS_VERIFIER)" \
	  SPS_REFERENCE_ROOT="$(SPS_REFERENCE_ROOT)" Z3="$(Z3)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/fixtures"

check-mlir: check-shape

check-integration: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  SPS_SCAN="$(SPS_SCAN)" SPS_VERIFIER="$(SPS_VERIFIER)" \
	  SPS_REFERENCE_ROOT="$(SPS_REFERENCE_ROOT)" Z3="$(Z3)" \
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
	  SPS_REV41_MATERIALIZED="$(SPS_REV41_MATERIALIZED)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/sps"
	@if [ -z "$(SPS_VERIFIER)" ] || [ -z "$(SPS_REV41_MATERIALIZED)" ]; then \
	  echo "SKIPPED: no exact Rev4.1 V2 verifier/materialized bundle; no ModelStatus was computed"; \
	fi

check-candidates: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/integration/candidate-bundles"

check-artifacts: check-candidates

check-contracts: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" SPS_REFERENCE_ROOT="$(SPS_REFERENCE_ROOT)" \
	  Z3="$(Z3)" LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/contracts"

check-sps-reference: require-lit
	@if [ -n "$(Z3)" ]; then \
	  command -v "$(Z3)" >/dev/null 2>&1 || { \
	    echo "error: configured Z3 is not executable: $(Z3)" >&2; exit 1; \
	  }; \
	else \
	  command -v z3 >/dev/null 2>&1 || { \
	    echo "error: z3 is required by check-sps-reference; set Z3=/path/to/z3" >&2; exit 1; \
	  }; \
	fi
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" SPS_REFERENCE_ROOT="$(SPS_REFERENCE_ROOT)" \
	  Z3="$(Z3)" LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) \
	    "$(HARNESS_DIR)/contracts/sps-reference-lock.test" \
	    "$(HARNESS_DIR)/integration/sps-reference-suite.test"

check-interfaces: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" SPS_INTERFACE_ROOT="$(SPS_INTERFACE_ROOT)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/contracts/sps-interface-drift.test"

check-source-annotations: require-lit
	@if [ -z "$(SPS_SOURCE_ANNOTATIONS_ROOT)" ]; then \
	  echo "error: set SPS_SOURCE_ANNOTATIONS_ROOT to SPS/source-annotations" >&2; \
	  exit 1; \
	fi
	@if [ ! -d "$(SPS_SOURCE_ANNOTATIONS_ROOT)" ]; then \
	  echo "error: SPS_SOURCE_ANNOTATIONS_ROOT is not a directory: $(SPS_SOURCE_ANNOTATIONS_ROOT)" >&2; \
	  exit 1; \
	fi
	@for relative in include/sps/annotations.h schemas/policy.schema.json \
	  schemas/abi.schema.json tests/check.py; do \
	  if [ ! -f "$(SPS_SOURCE_ANNOTATIONS_ROOT)/$$relative" ]; then \
	    echo "error: SPS source-annotation contract file is missing: $$relative" >&2; \
	    exit 1; \
	  fi; \
	done
	@mkdir -p "$(LIT_BUILD_ROOT)"
	SPS_SOURCE_ANNOTATIONS_ROOT="$(SPS_SOURCE_ANNOTATIONS_ROOT)" \
	  LLVM_BIN="$(LLVM_BIN)" LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) \
	    "$(HARNESS_DIR)/contracts/source-annotations-vendor.test" \
	    "$(HARNESS_DIR)/contracts/source-annotations-upstream.test" \
	    "$(HARNESS_DIR)/contracts/source-boundary.test"

check-checkpoints: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  SPS_SCAN="$(SPS_SCAN)" SPS_VERIFIER="$(SPS_VERIFIER)" \
	  SPS_REV41_MATERIALIZED="$(SPS_REV41_MATERIALIZED)" \
	  SPS_REFERENCE_ROOT="$(SPS_REFERENCE_ROOT)" Z3="$(Z3)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) \
	    "$(HARNESS_DIR)/fixtures/metadata.test" \
	    "$(HARNESS_DIR)/fixtures/metadata-negative.test" \
	    "$(HARNESS_DIR)/contracts/checkpoint-runner.test" \
	    "$(HARNESS_DIR)/contracts/checkpoint-results.test"

check-p4-risk: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) $(LIT_FLAGS) "$(HARNESS_DIR)/p4-risk"

list-tests: require-lit
	@mkdir -p "$(LIT_BUILD_ROOT)"
	LLVM_BIN="$(LLVM_BIN)" HOST_CC="$(HOST_CC)" RISCV_GCC="$(RISCV_GCC)" \
	  SPS_SCAN="$(SPS_SCAN)" SPS_VERIFIER="$(SPS_VERIFIER)" \
	  SPS_REV41_MATERIALIZED="$(SPS_REV41_MATERIALIZED)" \
	  SPS_REFERENCE_ROOT="$(SPS_REFERENCE_ROOT)" Z3="$(Z3)" \
	  LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  $(LIT) --show-tests "$(HARNESS_DIR)"

list-fixture-status: require-lit
	@"$(HARNESS_DIR)/.venv/bin/python" \
	  "$(HARNESS_DIR)/c/check_harness.py" list-fixtures

list-fixture-results: require-lit
	@LIT_BUILD_ROOT="$(LIT_BUILD_ROOT)" \
	  "$(HARNESS_DIR)/.venv/bin/python" \
	  "$(HARNESS_DIR)/tools/checkpoint_runner.py" results --root "$(HARNESS_DIR)"

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
