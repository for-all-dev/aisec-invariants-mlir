#!/bin/sh
set -eu

# Generate the two readable Clangover MLIR fixtures from checked compiler
# evidence.  This script does not decompile x86 into LLVM.  It:
#
#   1. compiles the vulnerable and fixed C reductions to LLVM IR and x86 asm;
#   2. imports the real LLVM IR into LLVM-dialect MLIR;
#   3. checks the decisive vulnerable/fixed assembly patterns; and
#   4. emits small, explicitly labeled semantic models for SPS tests.

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
HARNESS_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

LLVM_BIN=${LLVM_BIN:-/opt/homebrew/opt/llvm/bin}
CLANG=${CLANG:-$LLVM_BIN/clang}
MLIR_TRANSLATE=${MLIR_TRANSLATE:-$LLVM_BIN/mlir-translate}
MLIR_OPT=${MLIR_OPT:-$LLVM_BIN/mlir-opt}

OUTPUT_DIR=${1:-$HARNESS_DIR/build/clangover-generated}
EVIDENCE_DIR=$HARNESS_DIR/build/clangover-evidence

for tool in "$CLANG" "$MLIR_TRANSLATE" "$MLIR_OPT"; do
  if test ! -x "$tool"; then
    echo "error: required tool is not executable: $tool" >&2
    exit 1
  fi
done

mkdir -p "$OUTPUT_DIR" "$EVIDENCE_DIR"

COMMON_FLAGS="-std=c11 -Wall -Wextra -Wpedantic -fno-builtin"
TARGET_FLAGS="--target=x86_64-unknown-linux-gnu"
OPT_FLAGS="-Os -fno-vectorize -fno-slp-vectorize"

"$CLANG" $COMMON_FLAGS $TARGET_FLAGS $OPT_FLAGS -S -emit-llvm \
  "$SCRIPT_DIR/clangover_poly_frommsg_vulnerable.c" \
  -o "$EVIDENCE_DIR/vulnerable.ll"

"$CLANG" $COMMON_FLAGS $TARGET_FLAGS $OPT_FLAGS -S \
  "$SCRIPT_DIR/clangover_poly_frommsg_vulnerable.c" \
  -o "$EVIDENCE_DIR/vulnerable.s"

"$CLANG" $COMMON_FLAGS $TARGET_FLAGS $OPT_FLAGS -S -emit-llvm \
  "$SCRIPT_DIR/clangover_poly_frommsg_fixed.c" \
  -o "$EVIDENCE_DIR/fixed.ll"

"$CLANG" $COMMON_FLAGS $TARGET_FLAGS $OPT_FLAGS -S \
  "$SCRIPT_DIR/clangover_poly_frommsg_fixed.c" \
  -o "$EVIDENCE_DIR/fixed.s"

"$CLANG" $COMMON_FLAGS $TARGET_FLAGS $OPT_FLAGS -S \
  "$SCRIPT_DIR/clangover_ct_cmov.c" \
  -o "$EVIDENCE_DIR/ct_cmov.s"

"$MLIR_TRANSLATE" --import-llvm "$EVIDENCE_DIR/vulnerable.ll" \
  -o "$EVIDENCE_DIR/vulnerable.imported.mlir"

"$MLIR_TRANSLATE" --import-llvm "$EVIDENCE_DIR/fixed.ll" \
  -o "$EVIDENCE_DIR/fixed.imported.mlir"

"$MLIR_OPT" --verify-each "$EVIDENCE_DIR/vulnerable.imported.mlir" \
  -o /dev/null
"$MLIR_OPT" --verify-each "$EVIDENCE_DIR/fixed.imported.mlir" \
  -o /dev/null

# Vulnerable evidence: BT copies the selected message bit into CF, and JAE
# branches when CF is zero.
grep -Eq '^[[:space:]]*btl[[:space:]]' "$EVIDENCE_DIR/vulnerable.s"
grep -Eq '^[[:space:]]*jae[[:space:]]' "$EVIDENCE_DIR/vulnerable.s"
grep -q 'llvm.select' "$EVIDENCE_DIR/vulnerable.imported.mlir"

# Fixed evidence: the caller materializes the bit and calls the separately
# compiled helper.  The helper itself must contain no jump instruction.
grep -Eq '^[[:space:]]*setb[[:space:]]' "$EVIDENCE_DIR/fixed.s"
grep -Eq 'callq?[[:space:]].*clangover_ct_cmov' "$EVIDENCE_DIR/fixed.s"
grep -q 'llvm.call @clangover_ct_cmov' "$EVIDENCE_DIR/fixed.imported.mlir"
if grep -Eq '^[[:space:]]*j[a-z]+[[:space:]]' "$EVIDENCE_DIR/ct_cmov.s"; then
  echo "error: clangover_ct_cmov contains a jump instruction" >&2
  exit 1
fi

BAD_OUT=$OUTPUT_DIR/clangover_poly_frommsg.lowered_bad.mlir
FIXED_OUT=$OUTPUT_DIR/clangover_poly_frommsg.lowered_fixed.mlir

cat >"$BAD_OUT" <<'MLIR'
// case: clangover/poly_frommsg
// classification: modeled-from-verified-assembly
// c source: ../c/clangover_poly_frommsg_vulnerable.c
// upstream GitHub source: https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c#L141-L159
// upstream revision: b628ba78711bc28327dc7d2d5c074a00f061884e
// secret: %bit, one bit selected from the message byte
// public: coefficient constant 1665
// expected verdict: reject
// exact incident boundary: L1 target check; L2 bit witness; L3 compiler evidence
module {
  // observed x86: btl %ecx, %r8d; jae .Lclear; movl $1665, %edx
  llvm.func @poly_frommsg_x86_bad_model(%bit: i1) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    // CONFIDENTIALITY ERROR: secret-dependent branch
    // secret source: %bit is derived from the secret message
    // observable effect: branch direction and execution timing
    // reason: inputs differing only in %bit select different successors
    // detection boundary: L1 here; L2 reports bit=0/1; L3 attributes compiler introduction
    llvm.cond_br %bit, ^set, ^clear
  ^set:
    llvm.return %constant : i16
  ^clear:
    llvm.return %zero : i16
  }
}
MLIR

cat >"$FIXED_OUT" <<'MLIR'
// case: clangover/poly_frommsg
// classification: modeled-fixed-target
// c source: ../c/clangover_poly_frommsg_fixed.c
// upstream GitHub source: https://github.com/antoonpurnal/clangover/tree/7f4d5dc162b77c362a34a0d52949f7a3e1b16d81
// upstream revision: 7f4d5dc162b77c362a34a0d52949f7a3e1b16d81
// secret: %bit, one bit selected from the message byte
// public: coefficient constant 1665 and helper arguments
// expected verdict: pass with helper reviewed or inlined
// exact incident boundary: L1 checks no secret branch in this fixture
module {
  llvm.func @clangover_ct_cmov(%zero: i16, %one: i16, %bit: i16) -> i16

  llvm.func @poly_frommsg_x86_fixed_model(%bit: i16) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    // CONFIDENTIALITY REPAIR: helper call preserves dataflow boundary
    // secret source: %bit is passed as data to a separately compiled helper
    // safe effect: the caller has no secret-dependent control-flow operation
    // reason: no successor, address, or variable-time operation is selected by %bit here
    // detection boundary: L1 caller check passes; the helper remains an explicit obligation
    %result = llvm.call @clangover_ct_cmov(%zero, %constant, %bit)
        : (i16, i16, i16) -> i16
    llvm.return %result : i16
  }
}
MLIR

"$MLIR_OPT" --verify-each "$BAD_OUT" -o /dev/null
"$MLIR_OPT" --verify-each "$FIXED_OUT" -o /dev/null

echo "generated models:"
echo "  $BAD_OUT"
echo "  $FIXED_OUT"
echo "compiler evidence:"
echo "  $EVIDENCE_DIR"
