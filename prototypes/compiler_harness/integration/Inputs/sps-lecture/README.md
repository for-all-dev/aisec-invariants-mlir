# SPS lecture fixture inputs

These files mirror the hand-authored capture shapes in
`SPS/SPS_Lecture_Notes/artifacts/`. They are checked-in textual LLVM inputs for
the compiler harness, not canonical Rev. 4 bitcode.

The integration tests establish only:

- the seven-case inventory and exact three-coalition expectation rows;
- `claimable: false` and `current_status: Pending`;
- LLVM assembly/disassembly viability;
- absence of mutable globals and obsolete value/ordinal release carriers;
- presence of the reserved `llvm.sps.release` call inside each release wrapper; and
- the decisive branch/release prefix order.

LLVM 17 may assemble these inputs during harness testing. That candidate
round-trip is neither a V2 artifact identity nor a PONF/SMT proof, replay, or
`SPSRunReportV2`; stock-LLVM parsing of the intrinsic spelling does not establish
its required preservation or lowering semantics.
