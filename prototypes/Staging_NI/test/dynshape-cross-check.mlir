// RUN: %staging-ni-opt --verify-staging-ni --verify-diagnostics --split-input-file %s
//
// Drift guard. The function below is a hand-adapted COPY of
// ../../mlir_leak/dynshape.mlir, and the whole point of the copy is that it
// still represents what mlir_leak actually measures. Nothing enforced that,
// so an edit upstream would silently leave this file asserting agreement
// with a kernel that no longer exists in that shape. These RUN lines fail
// the test if the upstream pattern this one mirrors -- a secret extent
// index_cast into an scf.for bound and a secret-sized alloc -- is gone.
// RUN: grep -q "arith.index_cast" %S/../../mlir_leak/dynshape.mlir
// RUN: grep -q "memref.alloc(%%k)" %S/../../mlir_leak/dynshape.mlir
// RUN: grep -q "scf.for .* to %%k step" %S/../../mlir_leak/dynshape.mlir

// Cross-check against ../mlir_leak/dynshape.mlir: the secret there is a
// buffer extent `k`, loaded from a protected memref and cast to `index`,
// used as both the memref.alloc size and the scf.for trip count. mlir_leak
// MEASURED this leaking on every MLIR lowering pipeline and every LLVM -O
// level (see mlir_leak/README.md, "Dynamic-shape channel": "irreducible on
// the control channel"). This is the same pattern expressed as a
// stagingni.protected input, and this STATIC pass must predict the same
// violation mlir_leak's dynamic measurement already confirmed -- the
// static-predicts/dynamic-confirms pattern the project's own
// formal_verif/infoleak FTZ layer uses for denormal handling.
//
// Before the arith.index_cast Runtime->Staging conversion (this project's
// only prior conversion point was tensor.dim), this case was silently
// missed: runtime taint from %kbuf propagated generically through
// memref.load and the cast, but nothing ever promoted it to staging taint,
// so the loop-bound check saw an untainted value.

func.func @dynshape(
    %kbuf : memref<1xi32> {stagingni.protected},
    %out : memref<1xf32>
) {
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %z = arith.constant 0.0 : f32
  %one = arith.constant 1.0 : f32
  %k32 = memref.load %kbuf[%c0] : memref<1xi32>
  %k = arith.index_cast %k32 : i32 to index
  %buf = memref.alloc(%k) : memref<?xf32>
  // expected-error @+1 {{loop upper bound depends on protected runtime data}}
  %s = scf.for %j = %c0 to %k step %c1 iter_args(%acc = %z) -> (f32) {
    memref.store %one, %buf[%j] : memref<?xf32>
    %a = arith.addf %acc, %one : f32
    scf.yield %a : f32
  }
  memref.store %s, %out[%c0] : memref<1xf32>
  memref.dealloc %buf : memref<?xf32>
  return
}
