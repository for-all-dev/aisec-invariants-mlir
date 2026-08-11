#!/usr/bin/env bash
# run_ctprobe.sh — wire ctprobe (eBPF PMU probe) to mlir_leak's kernels and run it.
#
# Does NOT modify mlir_leak. It borrows the kernel objects run_mlir.py produced,
# wraps each in the mw_run shim, builds the eBPF probe + driver, and runs the
# attach/drive/report sequence on the isolated rig for the two control-flow
# kernels (cond_reduce, mask_select) — the only ones where PMU cycles add
# something over mlir_leak's Valgrind taint verdict.
#
# Expects, in the current dir: ctprobe.bpf.c ctprobe.c Makefile ctprobe_shim.c
#   ctprobe_driver.c measurement-rig.sh
# and mlir_leak at ../  (adjust MLIR_LEAK below).
#
# Usage:  sudo ./run_ctprobe.sh <rig-core>   [rounds=20000] [iters=1000]

set -euo pipefail
CORE="${1:?usage: sudo ./run_ctprobe.sh <rig-core> [rounds] [iters]}"
ROUNDS="${2:-20000}"
ITERS="${3:-1000}"
MLIR_LEAK="${MLIR_LEAK:-$PWD/../}"        # where run_mlir.py / build/ live
CLANG="${CLANG:-clang}"                    # use your LLVM-24 clang for consistency
LLC="${LLC:-llc}"

say(){ printf '\n=== %s ===\n' "$*"; }
die(){ printf 'FAIL: %s\n' "$*" >&2; exit 1; }

# ---- 0. preflight: every file and tool this needs, fail loudly & early --------
say "preflight"
for f in ctprobe.bpf.c ctprobe.c Makefile ctprobe_shim.c ctprobe_driver.c measurement-rig.sh; do
  [ -f "$f" ] || die "missing $f (written earlier in the thread — put it here)"
done
for t in "$CLANG" bpftool gcc make; do command -v "$t" >/dev/null || die "missing tool: $t (need clang llvm libbpf-dev bpftool linux-headers)"; done
[ -d "$MLIR_LEAK/build" ] || die "no $MLIR_LEAK/build — run 'python3 run_mlir.py' first (it produces the .o objects)"

# ---- 1. rescue the kernel objects (run_mlir.py wipes build/ each run) ---------
say "copying kernel objects out of build/ (before the next run_mlir.py wipes them)"
mkdir -p ct
for k in cond_reduce mask_select; do
  o="$MLIR_LEAK/build/${k}.P0_O0.o"
  ll="$MLIR_LEAK/build/${k}.P0_O0.ll"
  if [ -f "$o" ]; then cp "$o" "ct/${k}.o"
  elif [ -f "$ll" ]; then
    echo "  ${k}: only .ll present -> re-emitting PIC object with llc"
    "$LLC" -relocation-model=pic -filetype=obj "$ll" -o "ct/${k}.o"
  else die "no ${k}.P0_O0.{o,ll} in $MLIR_LEAK/build — rerun run_mlir.py"; fi
done

# ---- 2. build the two shim .so's (PIC; -DMW_COND selects the kernel) ----------
say "building shim libraries"
build_so(){ # kernel  define  outlib
  local k="$1" def="$2" out="$3"
  if ! "$CLANG" -O2 -g -fPIC -shared $def ctprobe_shim.c "ct/${k}.o" -o "ct/${out}" 2>ct/link.err; then
    grep -q "recompile with -fPIC" ct/link.err && die "ct/${k}.o is non-PIC; re-lower ${k}.P0_O0.ll with: $LLC -relocation-model=pic -filetype=obj (see cat ct/link.err)"
    cat ct/link.err; die "link of ${out} failed"
  fi
  echo "  built ct/${out}"
}
build_so cond_reduce "-DMW_COND" libcond.so
build_so mask_select ""          libmask.so

# ---- 3. build the eBPF probe and the driver ----------------------------------
say "building ctprobe (eBPF) + driver"
make >/dev/null || die "make failed (ctprobe.bpf.c / ctprobe.c) — check libbpf/bpftool"
gcc -O2 -o ctprobe_driver ctprobe_driver.c -ldl || die "driver build failed"
[ -x ./ctprobe ] || die "ctprobe binary not produced by make"

# ---- 4. isolate the core -----------------------------------------------------
say "isolating core $CORE"
./measurement-rig.sh setup "$CORE"
trap './measurement-rig.sh restore || true' EXIT   # always restore the machine

# ---- 5. attach + drive + report, per kernel ----------------------------------
run_one(){ # lib  label
  local lib="$1" label="$2"
  say "measuring $label ($lib)"
  taskset -c "$CORE" ./ctprobe "./ct/$lib" mw_run & local probe=$!
  sleep 1
  taskset -c "$CORE" ./ctprobe_driver "./ct/$lib" "$ROUNDS" "$ITERS" || true
  sleep 1
  kill -INT "$probe" 2>/dev/null || true          # triggers ctprobe's per-class report
  wait "$probe" 2>/dev/null || true
}
run_one libcond.so "cond_reduce (dIr=-3 in the matrix -> expect a SMALL/borderline t)"
run_one libmask.so "mask_select (dIr=-8192 -> expect a LARGE, clear t)"

say "done — rig will be restored on exit"