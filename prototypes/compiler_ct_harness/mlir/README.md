# Plain MLIR snapshots

These files intentionally use no AISec dialect, pass, or custom attribute.
They are standard MLIR/LLVM-dialect snapshots annotated with comments.

The authoritative generation path is:

```sh
make -C ../c regen-mlir
```

That command runs Clang to emit LLVM IR and then runs
`mlir-translate --import-llvm`.  The imported form is LLVM dialect (`llvm.func`,
`llvm.mul`, `llvm.udiv`, and so on); it is not a hand-claimed `func`/`arith`
lowering.  For RISC-V backend phenomena, LLVM dialect cannot see a later GCC
decision.  Such files say `MODELED FROM ASSEMBLY` directly above the modeled
operation and include the expected target instruction in the comment.

The checked-in files keep only the decisive operations so that a reviewer can
read them quickly.  The complete importer output is available in
`../build/mlir/` after regeneration.

Comments use the following vocabulary:

* `SECRET`: the input whose value must not affect the observation.
* `PUBLIC`: loop bounds, table contents, and constants.
* `CONFIDENTIALITY BREAK`: a secret-dependent branch, address, variable-time
  division, or target helper.
* `PATCHED`: the same functional operation without that observation.
