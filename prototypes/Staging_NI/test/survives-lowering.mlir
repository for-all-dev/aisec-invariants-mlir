// RUN: mlir-opt-18 %s --convert-scf-to-cf -o %t.cf.mlir
// RUN: not %staging-ni-opt --verify-staging-ni %t.cf.mlir 2>&1 | %FileCheck %s
//
// (FileCheck rather than --verify-diagnostics: mlir-opt does not preserve
// comments, so an expected-error marker would not survive into %t.cf.mlir.
// `not` because a confirmed violation makes the pass signal failure.)
//
// The checker must be equally capable BEFORE and AFTER a lowering step, or
// a before/after comparison is worthless: if it simply goes blind on the
// lowered form, the diff reads "the leak disappeared" and reports a
// lowering-removed verdict that is really just the analysis failing.
//
// scf.if becomes cf.cond_br under --convert-scf-to-cf. Only the scf form
// used to be checked, so this exact program flipped from VIOLATION to
// silent after one standard pass. This test lowers first, then checks, and
// requires the violation to still be reported -- on the cf form, at the
// cf.cond_br the lowering produced.
//
// staging_ni_diff.py depends on this property holding; see its header.

// The violation must be reported on the LOWERED form, at a cf.cond_br.
// CHECK: error: Staging Non-Interference violation: branch condition depends on protected runtime data
// CHECK: cf.cond_br

func.func @branch_survives_scf_to_cf(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  %cond = arith.cmpi eq, %dim, %c0 : index
  scf.if %cond {
    scf.yield
  }
  return
}
