# LLVM/MLIR confidentiality regression harness

This directory is a standalone LLVM-style regression suite for compiler
security and information-flow examples. It combines small C reductions with
review-sized LLVM-dialect MLIR fixtures. `llvm-lit` supplies test discovery and
isolation, `mlir-opt` verifies the checked-in IR, and `FileCheck` pins each
fixture's decisive operation or repair.

These checks are regression evidence, not a confidentiality proof. In
particular, verifier-valid IR and a matching `FileCheck` pattern establish
neither semantic equivalence nor noninterference for every input. The C
execution and code-generation tests add concrete evidence at the boundaries
they name; assumptions about helper timing, compression, GPU state, and
sanitizer sufficiency remain explicit obligations.

There is no key-recovery code and no full cryptographic implementation here.

## Layout

```text
prototypes/compiler_ct_harness/
├── Makefile                 # public test entry points
├── lit.cfg.py               # standalone llvm-lit configuration
├── README.md
├── c/
│   ├── Makefile             # compatibility and fixture-generation targets
│   ├── check_harness.py     # provenance and metadata contract checks
│   ├── equivalence_driver.c
│   └── *_bad.c / *_fixed.c / *_vulnerable.c
├── mlir/
│   ├── README.md
│   ├── L0_L1_L2_PIPELINE.md
│   └── *.mlir               # 35 checked-in regression fixtures
└── integration/             # integration .test files
```

Generated artifacts and per-test temporary files live below `build/`; a local
lit virtual environment lives below `.venv/`. Neither directory is test input.

## Commands

Run these from this directory:

```sh
make check                 # all MLIR and integration tests
make check-mlir            # verifier and focused IR-shape tests
make check-integration     # metadata, C execution/import, and codegen tests
make list-tests            # show exactly what llvm-lit discovered
```

The suite never installs a dependency as a side effect of `check`. If
`llvm-lit` is unavailable, explicitly create the pinned local runner once:

```sh
make bootstrap-lit         # installs lit==17.0.6 in .venv/
```

LLVM 17.0.6 is the initial code-generation baseline. Tools default to
`/opt/homebrew/opt/llvm/bin`; override the tool directory or lit executable
when necessary:

```sh
make check LLVM_BIN=/path/to/llvm/bin
make check LIT=/path/to/llvm-lit
```

The existing C entry point remains supported:

```sh
make -C c verify
```

An optional historical wolfSSL 3580 reproduction needs a RISC-V GCC. Its lit
test is `UNSUPPORTED` when no compiler is configured; this is an unavailable
test environment, not an expected failure:

```sh
make check-integration RISCV_GCC=/path/to/riscv32-gcc
```

The lit configuration detects Clang's X86, AArch64, and RISC-V targets and the
ability to execute host binaries. Tests that depend on a missing optional
feature are skipped with `UNSUPPORTED`; portable MLIR verification remains
runnable.

## What each layer establishes

| Layer | Mechanism | Evidence provided |
| --- | --- | --- |
| MLIR syntax/invariants | `mlir-opt` | Every checked-in module parses and satisfies registered operation invariants. |
| Fixture shape | `FileCheck` | The decisive store, branch, address, division, helper contract, or repair remains present and connected as expected. |
| Diagnostic oracle | `--verify-diagnostics` | Every bad fixture names the stable reason ID that a future SPS pass must emit at each decisive operation. |
| Metadata | `check_harness.py` | Each fixture has one four-valued outcome, one observer/model, a reason ID, valid obligations, an evidence boundary, and existing C provenance. |
| C behavior | two-run driver | Selected bad cases have a concrete differing-observation witness and repairs retain their intended functional result. |
| Translation | Clang, `mlir-translate`, `mlir-opt` | C can be emitted as LLVM IR, imported into LLVM-dialect MLIR, and verified. |
| Backend shape | Clang and optional GCC | Selected target-specific branch, division, or helper-call shapes are reproducible for the named toolchain/profile. |

Bad confidentiality fixtures remain valid compiler input. Each now has both a
successful verifier/shape RUN and an active `--verify-diagnostics` RUN with an
`expected-error` at every decisive operation. Because no final-LLVM SPS pass
emits those diagnostics yet, the 15 bad fixtures intentionally fail. They are
bring-up gates, not `XFAIL` tests: implementing the pass and adding it to the
diagnostic RUN is what turns them green.

## Scenario contract

The metadata outcome is exact: `verified`, `unsafe`, `unknown`, or
`conditional`. It describes the named observer/model only. `verified` and
`unsafe` have no outstanding obligations; `unknown` and `conditional` must
name the facts still needed.

| Family | Checked scenarios |
| --- | --- |
| Explicit oracle | Bad is `unsafe` because error detail remains beyond `padding_validity_v1`; fixed is `verified` for that authorized-validity release model. |
| Dynamic KV, BREACH, logging | Bad is `unsafe` through a reduced public sink; fixed is `verified` for the named reduced model. Real allocation/compression/runtime behavior is outside the reduced fixture. |
| Wrong party and wrong host | Bad is `unsafe` for the named audience/host policy; fixed is `verified`. |
| Redis and LeftoverLocals | Bad is `unsafe` for the explicit sequential cross-domain model; fixed is `verified` for that model. Relating it to the concurrent/GPU incident remains L4 evidence. |
| Secret embedding index | Bad is `unsafe` due to a secret-dependent address; fixed is `verified` at the source boundary. |
| CKKS | Bad is `unsafe` because it performs an unauthorized release; fixed is `conditional` on sanitizer sufficiency, certificate soundness, and release-policy integrity. |
| KyberSlash 1 and 2 | Bad is `unsafe` due to secret-dependent variable-latency division; fixed is `verified` under the source-operation timing model. |
| Clangover | Source is `verified`; lowered bad is `unsafe` due to a secret-dependent branch; lowered fixed is `verified` for its in-module model. L3 is required for the compiler-regression attribution. |
| wolfSSL 3580 | Source is `verified`; target bad is `unsafe` due to a secret-dependent branch; target fixed is `verified` for the modeled target. |
| wolfSSL 3579 | Source is `unknown` without target timing; a target call with no summary is `unknown`; the affected helper profile is `unsafe`; a constant-latency test profile is `verified`; the fixed-loop target model is `conditional` on base-operation latency and backend-trace preservation. |

The complete file-by-file mapping and L0-L4 interpretation are in
[`mlir/L0_L1_L2_PIPELINE.md`](mlir/L0_L1_L2_PIPELINE.md).

## Generated evidence

`make -C c regen-mlir` emits source-level imports under `build/mlir/`. For the
backend-modeled Clangover and wolfSSL families, vulnerable imports use
`.source.mlir` and repaired imports use `.fixed_source.mlir`. It deliberately
never generates a `target_bad` or `target_fixed` file: LLVM-dialect import
occurs before backend effects. KyberSlash keeps accurate source-level
`.bad.mlir` and `.fixed.mlir` generated names.

Checked-in target MLIR is hand-minimized and labeled as a target model.
Backend-only effects such as an RV32I branch or legalization to `__muldi3` are
supported by separate compiler evidence; they are not represented as literal
GCC-generated MLIR.
