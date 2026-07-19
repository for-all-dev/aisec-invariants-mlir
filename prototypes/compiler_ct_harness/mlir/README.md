# Plain MLIR fixtures

These files intentionally use no AISec dialect or SPS pass. They are standard
MLIR/LLVM-dialect snapshots annotated with comments. Target and release models
may use generic discardable `sps.*` attributes for machine-readable contract
facts. The wolfSSL 3579 target model carries a helper summary; the explicit
oracle and CKKS fixed model carry release/sanitizer policy identifiers.

See [`L0_L1_L2_PIPELINE.md`](L0_L1_L2_PIPELINE.md) for the planned detection
levels and the expected result for every harness case.

## Generation path

```sh
make -C ../c regen-mlir
```

That command runs Clang to emit LLVM IR and then runs
`mlir-translate --import-llvm`. For the backend-modeled Clangover/wolf
families, it emits `.source.mlir` and `.fixed_source.mlir` imports, never
generated `target_bad`/`target_fixed` files. KyberSlash retains accurate
source-level `.bad`/`.fixed` import names. The imported form is LLVM dialect
(`llvm.func`, `llvm.mul`, `llvm.udiv`, and so on). For backend phenomena, LLVM
dialect cannot see a later codegen decision; the corresponding checked-in
files are explicitly labeled as hand-written target models.

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
// expected verdict: <outcome and any scope/assumptions>
// exact incident boundary: L1 | L2 | L3 | L4 | unsupported-currently
```

New and migrated fixtures use the SPS outcome vocabulary `unsafe`, `unknown`,
`conditional`, and `verified`. Some older fixtures still use the legacy
`reject`, `target obligation`, and `pass` spellings until they are migrated.

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

The checker in `../c/check_harness.py` verifies these headers, adjacent comment
blocks, and a few contract-defining snippets/orderings for the migrated
fixtures. It does not prove confidentiality or validate an assumed target
fact; it keeps the harness shape ready for a future SPS pass.
