// The classic table lookup on a secret index: `t[s & 3]`. The values are correct, the
// address is not -- this is the cache/address channel, obligation 2 of the plan.
func.func @secret_index(%table: memref<8xi8>, %secret: index {fcvdct.secret}) -> i8 {
  %c3 = arith.constant 3 : index
  %index = arith.andi %secret, %c3 : index
  %value = memref.load %table[%index] : memref<8xi8>
  func.return %value : i8
}
