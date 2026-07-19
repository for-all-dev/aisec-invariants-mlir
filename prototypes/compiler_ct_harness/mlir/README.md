# Plain MLIR fixtures

These files intentionally use no AISec dialect, pass, or custom attribute.
They are standard MLIR/LLVM-dialect snapshots annotated with comments.

See [`L0_L1_L2_PIPELINE.md`](L0_L1_L2_PIPELINE.md) for the planned detection
levels and the expected result for every harness case.

## Generation path

```sh
make -C ../c regen-mlir
```

That command runs Clang to emit LLVM IR and then runs
`mlir-translate --import-llvm`. The imported form is LLVM dialect
(`llvm.func`, `llvm.mul`, `llvm.udiv`, and so on). For RISC-V backend
phenomena, LLVM dialect cannot see a later GCC decision; those checked-in files
are explicitly labeled as target models.

The checked-in files keep only the decisive operations so that a reviewer can
read them quickly. Complete importer output is available under `../build/mlir/`
after regeneration.

## Required header

Each fixture starts with:

```mlir
// case: ...
// classification: compiler-generated-minimized | modeled-from-verified-assembly | seeded-semantic-harness | reduced-runtime-model
// c source: ../c/<file>.c
// upstream GitHub source: ...
// upstream revision: ...
// secret: ...
// public: ...
// expected verdict: reject | pass | target obligation
// exact incident boundary: L1 | L2 | L3 | L4 | unsupported-currently
```

## Comment vocabulary

Bad fixtures use:

```mlir
// CONFIDENTIALITY ERROR: ...
// secret source: ...
// observable effect: ...
// reason: ...
// detection boundary: ...
<decisive bad operation>
```

Fixed fixtures use:

```mlir
// CONFIDENTIALITY REPAIR: ...
// secret source: ...
// safe effect: ...
// reason: ...
// detection boundary: ...
<decisive safe operation>
```

The checker in `../c/check_harness.py` verifies these headers and adjacent
comment blocks. It does not prove confidentiality; it keeps the harness shape
ready for a future SPS pass.
