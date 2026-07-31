# P4 risk evidence

These tests pin target assembly shapes that can falsify or keep open a paired
LLVM-to-deployment refinement claim. They are deliberately named `p4-risk`:
assembly `FileCheck` is not a `DeploymentStatus: Closed` proof, does not validate
final linked bytes, and never changes the independent LLVM `ModelStatus`.
