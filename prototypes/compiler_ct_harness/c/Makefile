SHELL := /bin/sh

include toolchains.mk

.PHONY: all verify compile-host regen-mlir check-codegen clean \
	clangover wolfssl-3580 wolfssl-3579 kyberslash

SOURCES := $(wildcard *.c)
HOST_OBJECTS := $(patsubst %.c,$(BUILD)/host/%.o,$(SOURCES))

all: verify

clangover: \
	$(BUILD)/x86/clangover_poly_frommsg_vulnerable.s \
	$(BUILD)/x86/clangover_poly_frommsg_fixed.s \
	$(BUILD)/mlir/clangover_poly_frommsg.source.mlir \
	$(BUILD)/mlir/clangover_poly_frommsg.lowered_bad.mlir \
	$(BUILD)/mlir/clangover_poly_frommsg.lowered_fixed.mlir
	@echo "Clangover C, assembly, LLVM IR, and imported MLIR are ready"

wolfssl-3580: \
	$(BUILD)/rv32/wolfssl_3580_mask_vulnerable.s \
	$(BUILD)/rv32/wolfssl_3580_mask_fixed.s \
	$(BUILD)/mlir/wolfssl_3580_mask.source.mlir \
	$(BUILD)/mlir/wolfssl_3580_mask.target_bad.mlir \
	$(BUILD)/mlir/wolfssl_3580_mask.target_fixed.mlir
	@echo "wolfSSL 3580 C, RV32I assembly, LLVM IR, and MLIR model are ready"

wolfssl-3579: \
	$(BUILD)/rv32/wolfssl_3579_mul_vulnerable.s \
	$(BUILD)/rv32/wolfssl_3579_mul_fixed.s \
	$(BUILD)/mlir/wolfssl_3579_mul.source.mlir \
	$(BUILD)/mlir/wolfssl_3579_mul.target_bad.mlir \
	$(BUILD)/mlir/wolfssl_3579_mul.target_fixed.mlir
	@echo "wolfSSL 3579 C, RV32I assembly, LLVM IR, and MLIR model are ready"

kyberslash: \
	$(BUILD)/mlir/kyberslash1_poly_tomsg.bad.mlir \
	$(BUILD)/mlir/kyberslash1_poly_tomsg.fixed.mlir \
	$(BUILD)/mlir/kyberslash2_compress.bad.mlir \
	$(BUILD)/mlir/kyberslash2_compress.fixed.mlir
	@echo "KyberSlash C, LLVM IR, and imported MLIR are ready"

compile-host: $(HOST_OBJECTS)

$(BUILD)/host/%.o: %.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) -c $< -o $@

$(BUILD)/x86/clangover_poly_frommsg_vulnerable.ll: clangover_poly_frommsg_vulnerable.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(X86_FLAGS) -Os -fno-vectorize -fno-slp-vectorize -S -emit-llvm $< -o $@

$(BUILD)/x86/clangover_poly_frommsg_fixed.ll: clangover_poly_frommsg_fixed.c clangover_ct_cmov.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(X86_FLAGS) -Os -fno-vectorize -fno-slp-vectorize -S -emit-llvm $< -o $@

$(BUILD)/x86/clangover_poly_frommsg_vulnerable.s: clangover_poly_frommsg_vulnerable.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(X86_FLAGS) -Os -fno-vectorize -fno-slp-vectorize -S $< -o $@

$(BUILD)/x86/clangover_poly_frommsg_fixed.s: clangover_poly_frommsg_fixed.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(X86_FLAGS) -Os -fno-vectorize -fno-slp-vectorize -S $< -o $@

$(BUILD)/rv32/wolfssl_3580_mask_vulnerable.ll: wolfssl_3580_mask_vulnerable.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S -emit-llvm $< -o $@

$(BUILD)/rv32/wolfssl_3580_mask_fixed.ll: wolfssl_3580_mask_fixed.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S -emit-llvm $< -o $@

$(BUILD)/rv32/wolfssl_3580_mask_vulnerable.s: wolfssl_3580_mask_vulnerable.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S $< -o $@

$(BUILD)/rv32/wolfssl_3580_mask_fixed.s: wolfssl_3580_mask_fixed.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S $< -o $@

$(BUILD)/rv32/wolfssl_3579_mul_vulnerable.ll: wolfssl_3579_mul_vulnerable.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S -emit-llvm $< -o $@

$(BUILD)/rv32/wolfssl_3579_mul_fixed.ll: wolfssl_3579_mul_fixed.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S -emit-llvm $< -o $@

$(BUILD)/rv32/wolfssl_3579_mul_vulnerable.s: wolfssl_3579_mul_vulnerable.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S $< -o $@

$(BUILD)/rv32/wolfssl_3579_mul_fixed.s: wolfssl_3579_mul_fixed.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(RV32_FLAGS) -O3 -S $< -o $@

$(BUILD)/aarch64/kyberslash1_poly_tomsg_vulnerable.ll: kyberslash1_poly_tomsg_vulnerable.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(AARCH64_FLAGS) -O0 -Xclang -disable-O0-optnone -S -emit-llvm $< -o $@

$(BUILD)/aarch64/kyberslash1_poly_tomsg_fixed.ll: kyberslash1_poly_tomsg_fixed.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(AARCH64_FLAGS) -O0 -Xclang -disable-O0-optnone -S -emit-llvm $< -o $@

$(BUILD)/aarch64/kyberslash2_compress_vulnerable.ll: kyberslash2_compress_vulnerable.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(AARCH64_FLAGS) -O0 -Xclang -disable-O0-optnone -S -emit-llvm $< -o $@

$(BUILD)/aarch64/kyberslash2_compress_fixed.ll: kyberslash2_compress_fixed.c
	@mkdir -p $(dir $@)
	$(CLANG) $(COMMON_CFLAGS) $(AARCH64_FLAGS) -O0 -Xclang -disable-O0-optnone -S -emit-llvm $< -o $@

define IMPORT_MLIR
	@mkdir -p $(dir $@)
	$(MLIR_TRANSLATE) --import-llvm $< -o $@
	$(MLIR_OPT) --verify-each $@ -o /dev/null
endef

regen-mlir: \
	$(BUILD)/mlir/clangover_poly_frommsg.source.mlir \
	$(BUILD)/mlir/clangover_poly_frommsg.lowered_bad.mlir \
	$(BUILD)/mlir/clangover_poly_frommsg.lowered_fixed.mlir \
	$(BUILD)/mlir/wolfssl_3580_mask.source.mlir \
	$(BUILD)/mlir/wolfssl_3580_mask.target_bad.mlir \
	$(BUILD)/mlir/wolfssl_3580_mask.target_fixed.mlir \
	$(BUILD)/mlir/wolfssl_3579_mul.source.mlir \
	$(BUILD)/mlir/wolfssl_3579_mul.target_bad.mlir \
	$(BUILD)/mlir/wolfssl_3579_mul.target_fixed.mlir \
	$(BUILD)/mlir/kyberslash1_poly_tomsg.bad.mlir \
	$(BUILD)/mlir/kyberslash1_poly_tomsg.fixed.mlir \
	$(BUILD)/mlir/kyberslash2_compress.bad.mlir \
	$(BUILD)/mlir/kyberslash2_compress.fixed.mlir
	@echo "Generated standard MLIR snapshots under $(BUILD)/mlir"

$(BUILD)/mlir/clangover_poly_frommsg.source.mlir: $(BUILD)/x86/clangover_poly_frommsg_vulnerable.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/clangover_poly_frommsg.lowered_bad.mlir: $(BUILD)/x86/clangover_poly_frommsg_vulnerable.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/clangover_poly_frommsg.lowered_fixed.mlir: $(BUILD)/x86/clangover_poly_frommsg_fixed.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/wolfssl_3580_mask.source.mlir: $(BUILD)/rv32/wolfssl_3580_mask_vulnerable.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/wolfssl_3580_mask.target_bad.mlir: $(BUILD)/rv32/wolfssl_3580_mask_vulnerable.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/wolfssl_3580_mask.target_fixed.mlir: $(BUILD)/rv32/wolfssl_3580_mask_fixed.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/wolfssl_3579_mul.source.mlir: $(BUILD)/rv32/wolfssl_3579_mul_vulnerable.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/wolfssl_3579_mul.target_bad.mlir: $(BUILD)/rv32/wolfssl_3579_mul_vulnerable.ll
	$(IMPORT_MLIR)
$(BUILD)/mlir/wolfssl_3579_mul.target_fixed.mlir: $(BUILD)/rv32/wolfssl_3579_mul_fixed.ll
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
	  $(RISCV_GCC) -O3 -march=rv32i -mabi=ilp32 -S wolfssl_3580_mask_vulnerable.c -o $(BUILD)/rv32/wolfssl_3580_gcc_vulnerable.s; \
	  $(RISCV_GCC) -O3 -march=rv32i -mabi=ilp32 -S wolfssl_3580_mask_fixed.c -o $(BUILD)/rv32/wolfssl_3580_gcc_fixed.s; \
	  grep -q 'bnez\|bne' $(BUILD)/rv32/wolfssl_3580_gcc_vulnerable.s; \
	  ! grep -q 'bnez\|bne' $(BUILD)/rv32/wolfssl_3580_gcc_fixed.s; \
	else \
	  echo "SKIP: set RISCV_GCC to test the historical GCC CVE-2026-3580 lowering"; \
	fi

verify: compile-host check-codegen regen-mlir
	@for f in ../mlir/*.mlir; do $(MLIR_OPT) --verify-each "$$f" -o /dev/null; done
	@echo "C compilation, code-generation checks, and checked-in MLIR parsing succeeded"

clean:
	rm -rf $(BUILD)
