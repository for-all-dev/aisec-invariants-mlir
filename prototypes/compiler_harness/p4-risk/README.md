# P4 risk evidence

These tests pin target assembly shapes that can falsify or keep open a paired
LLVM-to-deployment refinement claim. They are deliberately named `p4-risk`:
assembly `FileCheck` is not a `DeploymentStatus: Closed` proof, does not validate
final linked bytes, and never changes the independent LLVM `ModelStatus`.

Fixture-linked tests bind their risk and control arms to capability-gated
Snapshot V3 pipelines. Typed assembly facts are recorded only below the lit
build root. The register-allocation spill experiment remains an independent
P4 regression because it has no fixture snapshot.

A `PassedV1` backend-risk checkpoint means that the expected risky assembly
shape was observed; a passing backend-control checkpoint means only that the
declared control shape was observed. Neither is a security verdict. In
particular, a conditional jump alone does not prove that its condition is
secret-derived or that it changes a declared public observation. The final
classification must come from the fixture's validated actual
`SPSRunReportV2`; all current terminal pipelines remain unmaterialized.
