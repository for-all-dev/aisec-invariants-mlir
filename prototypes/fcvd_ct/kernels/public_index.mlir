// The table index comes from the public argument: the address is the same in both
// runs, so `address` holds even though a secret is present in the kernel.
func.func @public_index(%table: memref<8xi8>, %secret: i8 {fcvdct.secret}, %public: index) -> i8 {
  %value = memref.load %table[%public] : memref<8xi8>
  %sum = arith.addi %value, %secret : i8
  func.return %sum : i8
}
