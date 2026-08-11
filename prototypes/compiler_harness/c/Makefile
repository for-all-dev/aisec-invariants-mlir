SHELL := /bin/sh

include toolchains.mk

.PHONY: all verify compile-host regen-mlir check-codegen check-equivalence \
	check-provenance check-snapshots check-c-source-layout \
	check-runtime-source-groups check-runtime-link-symbols clean \
	clangover clangover-models \
	wolfssl-3580 wolfssl-3579 kyberslash

PYTHON ?= ../.venv/bin/python

SOURCE_LAYOUT := $(PYTHON) ../tools/fixture_layout.py --root ..
RUNTIME_INVENTORY := $(PYTHON) runtime_inventory.py --root ..
ALL_SOURCES := $(shell $(SOURCE_LAYOUT) --relative-to . --list-provenance-c-sources)
UNSUPPORTED_RUNTIME_SOURCES := $(filter %.cc %.cpp %.cxx,$(ALL_SOURCES))
ifneq ($(strip $(UNSUPPORTED_RUNTIME_SOURCES)),)
$(error C++ fixture sources need an explicit C++ runtime driver before Make can compile/link them: $(UNSUPPORTED_RUNTIME_SOURCES))
endif
RUNTIME_SOURCES := $(shell $(RUNTIME_INVENTORY) --relative-to . --list-link-c-sources)
HOST_OBJECTS := $(patsubst ../%.c,$(BUILD)/host/%.o,$(ALL_SOURCES))
RUNTIME_OBJECTS := $(patsubst ../%.c,$(BUILD)/host/%.o,$(RUNTIME_SOURCES))
EQUIV_DRIVER := $(BUILD)/host/equivalence_driver.o
EQUIV_BIN := $(BUILD)/host/equivalence_driver
LLVM_NM ?= $(LLVM_BIN)/llvm-nm

CLANGOVER_BAD_SOURCE := $(FIXTURES_DIR)/clangover-poly-frommsg/lowered-bad/clangover_poly_frommsg_vulnerable.c
CLANGOVER_FIXED_SOURCE := $(FIXTURES_DIR)/clangover-poly-frommsg/lowered-fixed/clangover_poly_frommsg_fixed.c
CLANGOVER_HELPER_SOURCE := $(FIXTURES_DIR)/clangover-poly-frommsg/lowered-fixed/clangover_ct_cmov.c
WOLFSSL_3580_BAD_SOURCE := $(FIXTURES_DIR)/wolfssl-3580-mask/target-bad/wolfssl_3580_mask_vulnerable.c
WOLFSSL_3580_FIXED_SOURCE := $(FIXTURES_DIR)/wolfssl-3580-mask/target-fixed/wolfssl_3580_mask_fixed.c
WOLFSSL_3579_BAD_SOURCE := $(FIXTURES_DIR)/wolfssl-3579-mul/target-bad/wolfssl_3579_mul_vulnerable.c
WOLFSSL_3579_FIXED_SOURCE := $(FIXTURES_DIR)/wolfssl-3579-mul/target-fixed/wolfssl_3579_mul_fixed.c
KYBERSLASH1_BAD_SOURCE := $(FIXTURES_DIR)/kyberslash1-poly-tomsg/bad/kyberslash1_poly_tomsg_vulnerable.c
KYBERSLASH1_FIXED_SOURCE := $(FIXTURES_DIR)/kyberslash1-poly-tomsg/fixed/kyberslash1_poly_tomsg_fixed.c
KYBERSLASH2_BAD_SOURCE := $(FIXTURES_DIR)/kyberslash2-compress/bad/kyberslash2_compress_vulnerable.c
KYBERSLASH2_FIXED_SOURCE := $(FIXTURES_DIR)/kyberslash2-compress/fixed/kyberslash2_compress_fixed.c

all: verify

clangover: \
	$(BUILD)/x86/clangover_poly_frommsg_vulnerable.s \
	$(BUILD)/x86/clangover_poly_frommsg_fixed.s \
	$(BUILD)/mlir/clangover_poly_frommsg.source.mlir \
	$(BUILD)/mlir/clangover_poly_frommsg.fixed_source.mlir
	@echo "Clangover C, assembly, LLVM IR, and source-level MLIR imports are ready"

clangover-models:
	./generate_clangover_mlir.sh

wolfssl-3580: \
	$(BUILD)/rv32/wolfssl_3580_mask_vulnerable.s \
	$(BUILD)/rv32/wolfssl_3580_mask_fixed.s \
	$(BUILD)/mlir/wolfssl_3580_mask.source.mlir \
	$(BUILD)/mlir/wolfssl_3580_mask.fixed_source.mlir
	@echo "wolfSSL 3580 C, RV32I assembly, LLVM IR, and source-level MLIR imports are ready"

wolfssl-3579: \
	$(BUILD)/rv32/wolfssl_3579_mul_vulnerable.s \
	$(BUILD)/rv32/wolfssl_3579_mul_fixed.s \
	$(BUILD)/mlir/wolfssl_3579_mul.source.mlir \
	$(BUILD)/mlir/wolfssl_3579_mul.fixed_source.mlir
	@echo "wolfSSL 3579 C, RV32I assembly, LLVM IR, and source-level MLIR imports are ready"

kyberslash: \
	$(BUILD)/mlir/kyberslash1_poly_tomsg.bad.mlir \
	$(BUILD)/mlir/kyberslash1_poly_tomsg.fixed.mlir \
	$(BUILD)/mlir/kyberslash2_compress.bad.mlir \
	$(BUILD)/mlir/kyberslash2_compress.fixed.mlir
	@echo "KyberSlash C, LLVM IR, and imported MLIR are ready"

compile-host: check-c-source-layout $(HOST_OBJECTS)

$(BUILD)/host/%.o: ../%.c
	@mkdir -p $(dir $@)
	$(HOST_CC) $(COMMON_CFLAGS) -c $< -o $@

$(EQUIV_DRIVER): equivalence_driver.c
	@mkdir -p $(dir $@)
	$(HOST_CC) $(COMMON_CFLAGS) -c $< -o $@

$(EQUIV_BIN): $(RUNTIME_OBJECTS) $(EQUIV_DRIVER) | check-c-source-layout check-runtime-link-symbols
	$(HOST_CC) $(COMMON_CFLAGS) $^ -o $@

$(BUILD)/x86/clangover_poly_frommsg_vulnerable.ll: $(CLANGOVER_BAD_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(X86_FLAGS) -Os -fno-vectorize -fno-slp-vectorize -S -emit-llvm $< -o $@

$(BUILD)/x86/clangover_poly_frommsg_fixed.ll: $(CLANGOVER_FIXED_SOURCE) $(CLANGOVER_HELPER_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(X86_FLAGS) -Os -fno-vectorize -fno-slp-vectorize -S -emit-llvm $< -o $@

$(BUILD)/x86/clangover_poly_frommsg_vulnerable.s: $(CLANGOVER_BAD_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(X86_FLAGS) -Os -fno-vectorize -fno-slp-vectorize -S $< -o $@

$(BUILD)/x86/clangover_poly_frommsg_fixed.s: $(CLANGOVER_FIXED_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(X86_FLAGS) -Os -fno-vectorize -fno-slp-vectorize -S $< -o $@

$(BUILD)/rv32/wolfssl_3580_mask_vulnerable.ll: $(WOLFSSL_3580_BAD_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S -emit-llvm $< -o $@

$(BUILD)/rv32/wolfssl_3580_mask_fixed.ll: $(WOLFSSL_3580_FIXED_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S -emit-llvm $< -o $@

$(BUILD)/rv32/wolfssl_3580_mask_vulnerable.s: $(WOLFSSL_3580_BAD_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S $< -o $@

$(BUILD)/rv32/wolfssl_3580_mask_fixed.s: $(WOLFSSL_3580_FIXED_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S $< -o $@

$(BUILD)/rv32/wolfssl_3579_mul_vulnerable.ll: $(WOLFSSL_3579_BAD_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S -emit-llvm $< -o $@

$(BUILD)/rv32/wolfssl_3579_mul_fixed.ll: $(WOLFSSL_3579_FIXED_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S -emit-llvm $< -o $@

$(BUILD)/rv32/wolfssl_3579_mul_vulnerable.s: $(WOLFSSL_3579_BAD_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S $< -o $@

$(BUILD)/rv32/wolfssl_3579_mul_fixed.s: $(WOLFSSL_3579_FIXED_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S $< -o $@

$(BUILD)/aarch64/kyberslash1_poly_tomsg_vulnerable.ll: $(KYBERSLASH1_BAD_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(AARCH64_FLAGS) -O0 -Xclang -disable-O0-optnone -S -emit-llvm $< -o $@

$(BUILD)/aarch64/kyberslash1_poly_tomsg_fixed.ll: $(KYBERSLASH1_FIXED_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(AARCH64_FLAGS) -O0 -Xclang -disable-O0-optnone -S -emit-llvm $< -o $@

$(BUILD)/aarch64/kyberslash2_compress_vulnerable.ll: $(KYBERSLASH2_BAD_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(AARCH64_FLAGS) -O0 -Xclang -disable-O0-optnone -S -emit-llvm $< -o $@

$(BUILD)/aarch64/kyberslash2_compress_fixed.ll: $(KYBERSLASH2_FIXED_SOURCE)
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(AARCH64_FLAGS) -O0 -Xclang -disable-O0-optnone -S -emit-llvm $< -o $@

define IMPORT_MLIR
	@mkdir -p $(dir $@)
	$(MLIR_TRANSLATE) --import-llvm $< -o $@
	$(MLIR_OPT) --verify-each $@ -o /dev/null
endef

regen-mlir: \
	$(BUILD)/mlir/clangover_poly_frommsg.source.mlir \
	$(BUILD)/mlir/clangover_poly_frommsg.fixed_source.mlir \
	$(BUILD)/mlir/wolfssl_3580_mask.source.mlir \
	$(BUILD)/mlir/wolfssl_3580_mask.fixed_source.mlir \
	$(BUILD)/mlir/wolfssl_3579_mul.source.mlir \
	$(BUILD)/mlir/wolfssl_3579_mul.fixed_source.mlir \
	$(BUILD)/mlir/kyberslash1_poly_tomsg.bad.mlir \
	$(BUILD)/mlir/kyberslash1_poly_tomsg.fixed.mlir \
	$(BUILD)/mlir/kyberslash2_compress.bad.mlir \
	$(BUILD)/mlir/kyberslash2_compress.fixed.mlir
	@echo "Generated source-level standard MLIR imports under $(BUILD)/mlir"

$(BUILD)/mlir/clangover_poly_frommsg.source.mlir: $(BUILD)/x86/clangover_poly_frommsg_vulnerable.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/clangover_poly_frommsg.fixed_source.mlir: $(BUILD)/x86/clangover_poly_frommsg_fixed.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/wolfssl_3580_mask.source.mlir: $(BUILD)/rv32/wolfssl_3580_mask_vulnerable.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/wolfssl_3580_mask.fixed_source.mlir: $(BUILD)/rv32/wolfssl_3580_mask_fixed.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/wolfssl_3579_mul.source.mlir: $(BUILD)/rv32/wolfssl_3579_mul_vulnerable.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/wolfssl_3579_mul.fixed_source.mlir: $(BUILD)/rv32/wolfssl_3579_mul_fixed.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/kyberslash1_poly_tomsg.bad.mlir: $(BUILD)/aarch64/kyberslash1_poly_tomsg_vulnerable.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/kyberslash1_poly_tomsg.fixed.mlir: $(BUILD)/aarch64/kyberslash1_poly_tomsg_fixed.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/kyberslash2_compress.bad.mlir: $(BUILD)/aarch64/kyberslash2_compress_vulnerable.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/kyberslash2_compress.fixed.mlir: $(BUILD)/aarch64/kyberslash2_compress_fixed.ll
	$(IMPORT_MLIR)

check-codegen: compile-host \
	$(BUILD)/x86/clangover_poly_frommsg_vulnerable.s \
	$(BUILD)/x86/clangover_poly_frommsg_fixed.s \
	$(BUILD)/rv32/wolfssl_3580_mask_vulnerable.s \
	$(BUILD)/rv32/wolfssl_3580_mask_fixed.s \
	$(BUILD)/rv32/wolfssl_3579_mul_vulnerable.s \
	$(BUILD)/rv32/wolfssl_3579_mul_fixed.s \
	$(BUILD)/aarch64/kyberslash1_poly_tomsg_vulnerable.ll \
	$(BUILD)/aarch64/kyberslash1_poly_tomsg_fixed.ll \
	$(BUILD)/aarch64/kyberslash2_compress_vulnerable.ll \
	$(BUILD)/aarch64/kyberslash2_compress_fixed.ll
	@grep -q 'udiv' $(BUILD)/aarch64/kyberslash1_poly_tomsg_vulnerable.ll
	@grep -q 'udiv' $(BUILD)/aarch64/kyberslash2_compress_vulnerable.ll
	@! grep -q 'udiv' $(BUILD)/aarch64/kyberslash1_poly_tomsg_fixed.ll
	@! grep -q 'udiv' $(BUILD)/aarch64/kyberslash2_compress_fixed.ll
	@grep -q 'btl' $(BUILD)/x86/clangover_poly_frommsg_vulnerable.s
	@grep -q 'jae' $(BUILD)/x86/clangover_poly_frommsg_vulnerable.s
	@! grep -q 'jae' $(BUILD)/x86/clangover_poly_frommsg_fixed.s
	@grep -q '__muldi3' $(BUILD)/rv32/wolfssl_3579_mul_vulnerable.s
	@! grep -q '__muldi3' $(BUILD)/rv32/wolfssl_3579_mul_fixed.s
	@echo "Clangover assembly and RV32I table-selection assembly are in $(BUILD)/x86 and $(BUILD)/rv32"
	@if test -n "$(RISCV_GCC)"; then \
	  $(RISCV_GCC) -O3 -march=rv32i -mabi=ilp32 -S $(WOLFSSL_3580_BAD_SOURCE) -o $(BUILD)/rv32/wolfssl_3580_gcc_vulnerable.s; \
	  $(RISCV_GCC) -O3 -march=rv32i -mabi=ilp32 -S $(WOLFSSL_3580_FIXED_SOURCE) -o $(BUILD)/rv32/wolfssl_3580_gcc_fixed.s; \
	  grep -q 'bnez\|bne' $(BUILD)/rv32/wolfssl_3580_gcc_vulnerable.s; \
	  ! grep -q 'bnez\|bne' $(BUILD)/rv32/wolfssl_3580_gcc_fixed.s; \
	else \
	  echo "SKIP: set RISCV_GCC to test the historical GCC CVE-2026-3580 lowering"; \
	fi

check-equivalence: check-c-source-layout check-runtime-source-groups $(EQUIV_BIN)
	$(EQUIV_BIN)
	@echo "Equivalence and witness smoke checks passed"

check-c-source-layout:
	$(SOURCE_LAYOUT) --check-c-source-layout

check-runtime-source-groups: check-c-source-layout
	$(RUNTIME_INVENTORY) --check-normal-llvm --clang $(CLANG) --include ../include

check-runtime-link-symbols: $(HOST_OBJECTS)
	$(RUNTIME_INVENTORY) --check-objects --object-root $(BUILD)/host --llvm-nm $(LLVM_NM)

check-provenance: check-c-source-layout
	$(PYTHON) check_harness.py provenance

check-snapshots: check-c-source-layout
	$(PYTHON) check_harness.py snapshots

verify: compile-host check-provenance check-snapshots check-equivalence check-codegen regen-mlir
	@find ../fixtures -name '*.mlir' -type f -exec $(MLIR_OPT) --verify-each '{}' -o /dev/null \;
	@echo "C compilation, code-generation checks, and checked-in MLIR parsing succeeded"

clean:
	rm -rf $(BUILD)
