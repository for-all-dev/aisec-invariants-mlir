# Verifying three MLIR compilers: CIRCT, HEIR, onnx-mlir

Companion to `fcvd-selfcomposition.agents.md`, which builds the method. This note applies it to the
three compilers that were picked as the starting set, and answers the question that picked them:
*which compiler has the fewest translations that are not proved?*

Claim discipline as in the plan note: **[source]** = read from the compiler's own code at the commit
named below, **[measured]** = a run on this box (2026-07-29, Xeon 8168, z3 4.15.1), **[inference]** =
our reasoning.

Checkouts: circt `2803829`, heir `de797a2`, onnx-mlir `de23de7`, all shallow clones in
`~/third_party`. Everything below is reproducible with `prototypes/fcvd_ct/run_all.sh`.

## 1. The answer, in numbers

`fcvd-ct-coverage` reads the operations that occur in each compiler's **own test corpus** and sorts
them into the plan's three forms — 0: has SMT semantics (or is control flow our flattener handles),
1: covered by a macro-template that still proves, 2: neither. [measured]

| compiler | test files | distinct ops | form 0 | form 2 (unproved) | share of mentions translatable | steps with a checked specification |
|---|---|---|---|---|---|---|
| **heir** | 453 | 117 | 34 | **83** | **53.4 %** | 2 / 11 |
| **circt** | 280 | 237 | 49 | 188 | 40.1 % | 2 / 12 |
| **onnx-mlir** | 248 | 302 | 14 | 288 | 33.6 % | 1 / 6 |

So the ordering is **HEIR, then CIRCT, then onnx-mlir**, and the three are blocked by quite different
things:

- **HEIR** — 83 unproved operations, and the top of the list is its own abstraction: `secret.generic`
  and `secret.yield` (849 mentions between them), then the layout and tensor-shape operations
  (`tensor_ext.layout`, `tensor.empty`, `tensor.extract_slice`). Its *arithmetic* is largely
  `arith` already, which is why the share is the highest of the three.
- **CIRCT** — 188 unproved operations, but the mass is structural rather than computational:
  `hw.module`, `hw.output`, `hw.instance`, and the `sv`/`seq` register-and-wire vocabulary. The
  combinational core, `comb`, has full semantics upstream, which is why the one pipeline step we
  checked went through with no new translations except `hw.constant`.
- **onnx-mlir** — 288 unproved operations, and 236 of them feed a single step,
  `--convert-onnx-to-krnl` [source: `src/Compiler/CompilerPasses.cpp:298`]. This is the ONNX
  operation zoo, and there is no way around it: each operation is a separate translation.

A caveat worth keeping: these are *usage-weighted counts over test corpora*, not a measure of
difficulty. `hw.module` is one translation and a mechanical one; `onnx.Conv` is one translation and a
week of it. The number says how many, not how hard.

## 2. What was actually proved, per compiler

Every row below is a template or kernel in `prototypes/fcvd_ct/`, transcribed from the compiler's own
source at the cited line, and re-run by `uv run pytest`. [measured]

### CIRCT — the division channel opens and closes

| what | verdict | source |
|---|---|---|
| `--map-arith-to-comb`, the one-to-one table | ct-preserving (0 → 0) | `lib/Transforms/MapArithToComb.cpp:255` |
| `--map-arith-to-comb`, div/rem | ct-preserving (4 → 0) | same, :258–261 |
| `--map-arith-to-comb`, min/max | ct-preserving (0 → 0) | same, :174 |
| `--convert-comb-to-arith`, unsigned division | **ct-breaking (0 → 2)** | `lib/Conversion/CombToArith/CombToArith.cpp:196` |

The finding is the last row, and it is about a path people use: arcilator simulates a circuit by
running `--lower-arc-to-llvm`, which pulls in the same CombToArith patterns [source:
`lib/Tools/arcilator/pipelines.cpp:170` → `lib/Conversion/ArcToLLVM/LowerArcToLLVM.cpp:1910`]. A
divider that was fixed-delay in hardware becomes an x86 `div`, and the zero-guard the pattern inserts
(`isZero = b == 0; divisor = isZero ? 1 : b`) does not change that — it swaps one data-dependent
divisor for another. Per-program: `hw_divide.mlir` is SECURE and `hw_divide_simulated.mlir` is
INSECURE on `latency`, secrets `0x80000001` vs `0xfffffffe`.

This rests on one modelling choice — combinational arithmetic takes the same time on all operands,
x86 `div` does not — pinned by `test_comb_arithmetic_is_deliberately_not_observed`. It is a choice,
not a fact about every synthesis flow: a *sequential* divider that early-exits on small operands
would break it, and then `comb.divu` would need a rule of its own.

### HEIR — the hardening is complete only at the last pass

`--convert-to-data-oblivious` [source: `tools/heir-opt.cpp:613`,
`lib/Pipelines/PipelineRegistration.cpp:153–164`] is a sequence, and running the property at each
stage says which obligation each pass discharges: [measured]

| stage | kernel | verdict |
|---|---|---|
| input | `tensor.extract %t[%secret]` | INSECURE — `address` |
| after `--convert-secret-extract-to-static-extract` | scan, keep the match with `scf.if` | INSECURE — `control` |
| after `--convert-if-to-select` | the same with `arith.select` | SECURE (9 address observations proved equal) |

The middle row is the result worth keeping: the pass closes the address channel and **opens a control
one**, because the `scf.if` it emits branches on `j == secret` [source:
`ConvertSecretExtractToStaticExtract.cpp:113`]. HEIR runs `--convert-if-to-select` last, so the
pipeline as a whole is fine; a user running the extract pass alone would not be.

Two more, both transcribed from HEIR:

- `--convert-if-to-select` on a *speculatable* body: ct-preserving. On the body its own negative test
  rejects (a `divui` in an arm): **ct-breaking**. HEIR refuses that case because of undefined
  behaviour; this shows the same side condition is needed for constant-time, since hoisting the
  divider makes it run on every input. [inference, machine-checked]
- `--mod-arith-to-arith`, addition: `mod_arith.add` → `arith.addi` + `arith.remui`
  [source: `ModArithToArith.cpp:350–364`] — **ct-breaking (0 → 2)**. A modular addition, which has no
  timing meaning at the `mod_arith` level, becomes a variable-latency instruction on secret data.
  **Scope:** this is a statement about the MLIR. The modulus is a constant, and LLVM turns division
  by a constant into multiply-shift, so the channel may well be closed further down — that question
  belongs to layers A/B (binsec, on the binary), and nothing in HEIR's pipeline requires the backend
  to do it.

### onnx-mlir — the ordinary lowering, and a missing pass

`--convert-onnx-to-krnl` lowers `onnx.Gather` to a loop that loads an index out of `indices` and then
loads `data` at that index [source: `src/Conversion/ONNXToKrnl/Tensor/Gather.cpp:104–144`]:
**ct-breaking (0 → 3)**. Per-program, after `--convert-krnl-to-affine` as well,
`gather_secret_index.mlir` is INSECURE on `address` (4 observations) and the hand-written oblivious
version is SECURE (18 observations proved equal). [measured]

Nothing here is a compiler bug — this is what a gather *is*. The finding is the asymmetry: private
token ids in an embedding lookup are an ordinary situation, HEIR has a pass that rewrites exactly
this shape, and onnx-mlir has no data-oblivious mode anywhere in its pipeline [source:
`src/Compiler/CompilerPasses.cpp`]. The oblivious form has to be written by hand.

## 3. What had to be built, and what it says about the method

Four translations were written for this note, and they are the evidence for the plan's claim that
translations are written once and then reused: [measured]

| translation | why it was needed | reused by |
|---|---|---|
| `hw.constant` (syntax + semantics) | `--map-arith-to-comb` sends every integer constant to it | CIRCT |
| `tensor.extract` / `tensor.insert` + the tensor type, on the SMT theory of arrays | HEIR's hardenings are written on tensors | HEIR, and anything post-`--elementwise-to-affine` |
| `affine.for` / `affine.yield` syntax, and **exact** unrolling for constant bounds | both HEIR and onnx-mlir emit it | HEIR, onnx-mlir |
| `{secret.secret}` as a secret label | HEIR's `--secretize` writes it | HEIR |

The affine one is the interesting entry. A constant-bound loop has a *public* trip count, so unlike
`scf.for` it costs no control observation and needs no unrolling budget: the verdict is exact rather
than bounded. That is precisely the property the hardening passes are engineered to produce, and the
checker gets to see it.

## 4. Honest limits

- **`secret.generic` is not modelled.** HEIR kernels here are transcribed with the wrapper dropped,
  since the data-oblivious passes rewrite the body and not the wrapper — but that means 849 mentions
  of the two most common `secret` operations stay in form 2, and a whole-module HEIR check is not
  possible yet.
- **The compilers were not run.** None of circt-opt, heir-opt or onnx-mlir is built on this box;
  every before/after pair is transcribed by hand from the pass source or its own lit test, with the
  file and line cited. That is a real trusted assumption: it makes these proofs statements about the
  *specification* of each step. Discharging it needs the compilers built and the IR taken from them,
  which is the obvious next task.
- **Every verdict is relative to the leakage model** in `prototypes/fcvd_ct/src/fcvdct/leakage.py`,
  and the hardware verdicts additionally to the "combinational arithmetic is fixed-delay" choice.
- **MLIR-level only.** A green verdict here says nothing about the binary; that is what layers A/B
  and C/D in `prototypes/formal_verif` are for, and the `--mod-arith-to-arith` row above is a live
  example of a finding that may or may not survive the backend.
