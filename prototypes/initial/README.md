# aisec-invariants-mlir

An MLIR compile-time non-interference verifier for ML model weights, built on
top of [google/heir](https://github.com/google/heir)'s `secret` dialect.

## What this is

HEIR ships a `secret` dialect designed for fully homomorphic encryption:
`!secret.secret<T>` wraps any MLIR type, `secret.conceal` lifts plaintext to
secret, `secret.reveal` releases a secret back to plaintext, and `secret.generic`
is a regional op that lifts cleartext computation to operate on secrets.

HEIR assumes everything marked secret will be encrypted downstream, so it does
not enforce that secrets can't leak to public sinks. **We do.**

This repo contributes an `--aisec-verify-non-interference` MLIR pass that:

1. Collects function arguments tagged with `{aisec.protected}`.
2. Propagates "taint" forward through SSA uses (and through `secret.generic`
   regions).
3. Errors if any `secret.reveal` op in the function consumes a tainted value
   without being explicitly tagged with `{aisec.declassify}`.

The result is a compile-time guarantee that model weights (marked protected at
the function boundary) cannot reach a public sink except through sanctioned
declassification points. Non-interference modulo explicit declassification —
the standard IFC theorem, phrased at the MLIR level.

## Why MLIR

At LLVM IR a tensor has been shattered into `i64` GEPs and scalar loads;
tracking "this dereference came from a secret weight" is a whole-program
pointer-analysis problem. At MLIR's `linalg`-on-tensors altitude,
`tensor<256x768xf32>` is a first-class SSA value with structured dataflow, and
"secret weight" is a type attribute that propagates by construction. The same
analysis that would take a heavyweight pass at LLVM is a ~50-line verifier walk
at MLIR.

## Building

### Prerequisites

- **bazelisk** (reads `.bazelversion`, fetches Bazel 8.4.0)
- **clang** (any recent version; HEIR's code is C++20)
- **lld** on Linux

On Arch: `pacman -S bazelisk clang lld`

Alternatively, a reproducible devshell is provided via Nix flakes:

```sh
nix develop
```

This pins `bazelisk` and `uv`; everything else is resolved by Bazel and uv on
first run. See `flake.nix`.

### First build

```sh
bazelisk build //...
bazelisk test  //...
```

**Day-1 risk**: HEIR is not in the Bazel Central Registry. Before the first
build, pin a real HEIR commit in `MODULE.bazel`:

```sh
git ls-remote https://github.com/google/heir.git HEAD
# paste the SHA into the `git_override` block in MODULE.bazel
```

### Running the verifier

```sh
bazelisk build //tools/aisec-opt
./bazel-bin/tools/aisec-opt/aisec-opt \
    --aisec-verify-non-interference \
    test/Transforms/VerifyNonInterference/leak-via-reveal.mlir
```

## Repository layout

```
aisec-invariants-mlir/
├── MODULE.bazel, .bazelrc, .bazelversion, BUILD.bazel
├── flake.nix                       # dev tooling (bazelisk + uv)
├── include/AISec/Transforms/       # pass headers and tablegen
├── lib/Transforms/                 # verifier pass implementation
├── tools/aisec-opt/                # mlir-opt-style driver
└── test/                           # lit + FileCheck tests (hand-written .mlir inputs)
```

## Scope and non-goals

**In scope (MVP):**
- The non-interference verifier pass described above.
- A worked example: a hand-written MobileNetV2-block-shaped MLIR file with
  conv weights marked `aisec.protected`, demonstrating both the sanctioned-
  declassify path and the leak-rejection path.

**Out of scope (for MVP):**
- Affine/linear use-count enforcement for weight tensors.
- Bandwidth-bounded egress certificates (compile-time information-theoretic
  bounds on function output size).
- Translation validation across lowering passes.
- Formal mechanization of the verifier in Lean 4.
- Any runtime component.

## Related work

- [google/heir](https://github.com/google/heir) — Homomorphic Encryption
  Intermediate Representation; source of the `secret` dialect we build on.
- [opencompl/lean-mlir](https://github.com/opencompl/lean-mlir) — SSA-theory
  formalization in Lean 4 (target for future mechanization of this verifier).
- [aqjune/mlir-tv](https://github.com/aqjune/mlir-tv) — Alive2-style SMT
  translation validation for MLIR.
- Regehr et al., *First-Class Verification Dialects for MLIR*, PLDI 2025.
- Chen et al., *Your Compiler is Backdooring Your Model*, IEEE S&P 2026
  (arXiv:2509.11173).

## License

Licensed under the Apache License, Version 2.0. See [`LICENSE`](LICENSE) and
[`NOTICE`](NOTICE).

Portions of this work were originally developed by Quinn Dougherty for Lucid
Computing Inc. and are released under the Apache License, Version 2.0.
