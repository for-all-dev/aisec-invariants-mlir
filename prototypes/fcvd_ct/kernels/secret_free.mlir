// Which of two buffers is released depends on a secret, chosen without a branch, so
// control flow is clean and the *resource* obligation is the one that fails: the sets
// of still-allocated memory differ between the two runs.
func.func @secret_free(%secret: i1 {fcvdct.secret}) {
  %first = memref.alloc() : memref<4xi8>
  %second = memref.alloc() : memref<4xi8>
  %chosen = arith.select %secret, %first, %second : memref<4xi8>
  memref.dealloc %chosen : memref<4xi8>
  func.return
}
