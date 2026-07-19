# Minimal C/MLIR confidentiality harness

This is a standalone regression corpus for compiler-security and information
flow examples. It intentionally does not use the AISec dialect or SPS passes
yet. The checked-in files are small C reductions plus review-sized MLIR
fixtures with comments at the operation where confidentiality is broken or
repaired.

There is no key-recovery code and no full crypto implementation here.

## Layout

```text
prototypes/compiler_ct_harness/
├── README.md
├── c/
│   ├── Makefile
│   ├── toolchains.mk
│   ├── check_harness.py
│   ├── equivalence_driver.c
│   └── *_bad.c / *_fixed.c / *_vulnerable.c
└── mlir/
    ├── README.md
    ├── L0_L1_L2_PIPELINE.md
    └── *.mlir
```

The `c/` directory has 30 paired fixture files plus the Clangover helper and
the local smoke-test driver. The `mlir/` directory has 33 fixtures: 13 for the
crypto/compiler cases and 20 for the semantic/runtime analogues.

## How to run

```sh
make -C c verify
make -C c check-provenance
make -C c check-annotations
make -C c check-equivalence
make -C c check-codegen
make -C c regen-mlir
```

`make -C c verify` currently passes on this machine. The RISC-V GCC-specific
wolfSSL 3580 reproduction is skipped unless `RISCV_GCC` is supplied:

```sh
make -C c check-codegen RISCV_GCC=/path/to/riscv32-gcc
```

The default LLVM tools come from `/opt/homebrew/opt/llvm/bin`. Override
`LLVM_BIN` if needed. Host-only compilation and the equivalence driver use
`HOST_CC ?= cc`, while cross-target LLVM generation continues to use
`$(LLVM_BIN)/clang`.

## What the comments mean

Bad MLIR fixtures mark the decisive operation like this:

```mlir
// CONFIDENTIALITY ERROR: secret-dependent branch
// secret source: %bit is derived from the secret message
// observable effect: branch direction and execution timing
// reason: inputs differing only in %bit select different successors
// detection boundary: L1 here; L2 reports bit=0/1; L3 attributes compiler introduction
llvm.cond_br %bit, ^taken, ^not_taken
```

Fixed MLIR fixtures use `CONFIDENTIALITY REPAIR` above the corresponding safe
operation. These are plain comments for now; later SPS integration can turn
them into lit expectations.

## Mathematical contract

Each pair is meant to document:

```text
Functional behavior:
    F_bad(secret, public) = F_fixed(secret, public)

Confidentiality requirement:
    Obs(secret_0, public) = Obs(secret_1, public)

Violation:
    secret_0 != secret_1
    Obs_bad(secret_0, public) != Obs_bad(secret_1, public)
```

For semantic/runtime harnesses, the fixed version may intentionally redact a
public sink. In those cases the local smoke test checks the authorized result
and a concrete bad-observation witness rather than claiming every public store
is functionally identical.

## Source map

| Case | Local C fixture | Upstream or motivating source | Classification | Boundary |
| --- | --- | --- | --- | --- |
| Clangover / `poly_frommsg` | `clangover_poly_frommsg_*` | `pq-crystals/kyber` `poly_frommsg`, Clangover repo | faithful minimal reduction plus target model | L1 target, L2 witness, L3 compiler regression |
| wolfSSL CVE-2026-3580 | `wolfssl_3580_mask_*` | wolfSSL PR 9855 and vulnerable 5.8.4 source tree | independently written equivalent reduction | L1/L2 target model, L3 backend evidence |
| wolfSSL CVE-2026-3579 | `wolfssl_3579_mul_*` | wolfSSL PR 9855 and vulnerable 5.8.4 source tree | independently written equivalent reduction | L1 known-helper sink, L4 helper timing fact |
| KyberSlash1 | `kyberslash1_poly_tomsg_*` | Kyber `poly_tomsg`, fix `dda29cc...` | faithful minimal reduction | L1 |
| KyberSlash2 | `kyberslash2_compress_*` | Kyber `poly_compress`, fix `11d00ff...` | faithful minimal reduction | L1 |
| Wrong-party plaintext | `wrong_party_plaintext_*` | hosted-system disclosure class | seeded semantic harness | L1 |
| redis-py analogue | `redis_pool_reuse_*` | redis-py cancellation/pool incident class | reduced runtime model | analogue L1; exact race needs runtime semantics |
| Secret logging/checkpoint | `secret_logging_checkpoint_*` | logging/checkpoint sink class | seeded semantic harness | L1 |
| Explicit error oracle | `explicit_error_oracle_*` | OpenSSL-style oracle class | seeded semantic harness | L1, optional L2 |
| BREACH analogue | `breach_compressed_length_*` | compression-length leak class | seeded semantic harness | L2 model, compressor fact at L4 |
| Secret embedding index | `secret_embedding_index_*` | tensor embedding lookup class | seeded semantic harness | L1 |
| Dynamic tensor/KV length | `dynamic_kv_length_*` | vLLM-style dynamic-cache privacy class | seeded semantic harness | planned L1/L2 dynamic-shape support |
| Wrong-host FHE reveal | `wrong_host_fhe_reveal_*` | FHE host/reveal policy class | seeded semantic harness | L1 |
| CKKS unsafe release | `ckks_unsafe_release_*` | approximate-release policy class | seeded semantic harness | L1/L2 structure; noise proof at L4 |
| LeftoverLocals analogue | `leftoverlocals_scratch_*` | Trail of Bits LeftoverLocals report | reduced runtime model | analogue L1; exact GPU issue at L4 |

Every C file has a structured provenance header. Where original C exists, the
header links to immutable GitHub commits or PRs. Where the motivating incident
was not C, the header says so and labels the file as a model.

## Generated evidence

`make -C c regen-mlir` emits raw imported MLIR under `build/mlir/`. The
checked-in MLIR remains hand-minimized and annotated for review. Backend-only
effects, such as GCC RV32I `bnez` and legalization to `__muldi3`, are labeled
as target models derived from compiler evidence; they are not represented as
literal GCC-generated MLIR.

Future SPS tests can consume these comments as:

```text
not aisec-opt --aisec-verify-ct --target-profile=<profile> bad.mlir
aisec-opt --aisec-verify-ct --target-profile=<profile> fixed.mlir
```
