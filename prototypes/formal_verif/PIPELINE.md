## Idea

1. What can be verified
A — Binsec compares traces pairwise, differing only in the secret, and proves the absence of leaks.
B — reads the compiled code through Binsec and builds byte-by-byte SMT solvers.
2. What can be detected
C — fixes the contract and runs the binary on the CPU, estimating the leakage in bits.
D — measures the same leakage, but over time.
