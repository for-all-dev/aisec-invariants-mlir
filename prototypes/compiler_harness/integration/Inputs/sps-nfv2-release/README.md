# SPS-LLVM-NF-v2 release inputs

This directory separates two kinds of evidence:

- `contract-shapes.ll.in` and `cases.json` are harness-owned textual cases.
  They include malformed and legacy carriers, so they are intentionally not
  assembled. `check_nfv2_release_contract.py` validates their structural
  disposition on stock LLVM without computing `NFConforms` or `ModelStatus`.
- `nfv2-release.ll.in` is valid only as the intended patched-LLVM contract.
  Lit runs its optimization and code-generation tests only after semantic
  capability probes enable `sps-nfv2-intrinsic` and
  `sps-nfv2-codegen`.

The only current carrier spelling is `llvm.sps.release`. Its variadic integer
operands are flattened release payload leaves. Release identity is external:
`ReleaseImplementationBindingV2.emitMarkerInstructionId` names the stable
intrinsic instruction; no `ReleaseId` operand is permitted.
