# SPS Rev-4 executable reference slice

This directory contains a deliberately small, executable reference slice for
the highest-risk SPS Rev-4 confidentiality rules. It is not a conforming SPS
implementation and cannot emit `ModelStatus: Proved`.

The reference slice exists to make specification drift observable while the
full LLVM normalizer, `ExpandV2`, PONF builder, replay engine, proof
mechanization, and deployment-evidence profile are implemented. Its artifact
identifiers contain `Reference` so that no output can be confused with a
normative `SPS-PONF-v2` artifact.

Implemented:

- canonical JSON and SHA-256 identity for reference artifacts;
- strict duplicate-free schemas and canonical program snapshots that reject
  post-compilation mutation;
- a typed finite bitvector expression language;
- a structured, bounded reference IR with public and High inputs;
- bounded exhaustive terminal-closure validation, terminal return/explicit
  bound-exhaustion behavior, and ABI-root `Output` events;
- `Transfer.valueBytes` and location-visible `Release.valueBytes`;
- audience-authorized release retirement without location-based retirement;
- fixed-bound structured expansion with explicit remainder events;
- a canonical `SPS-Reference-PONF-v2` query object bound to canonical program,
  coalition descriptor, expanded-CFG, and exact-SMT digests;
- deterministic QF_BV SMT-LIB lowering and complete extraction of every
  declared lane input, including formula-irrelevant High inputs;
- strict reparsing and lowering of the serialized PONF, checked byte-for-byte
  against lowering from the independently built product;
- field-by-field PONF auditing that does not call the PONF serializer under
  test;
- Z3 execution plus an independent exhaustive finite-domain backend;
- an independently interpreted exhaustive product for both SAT and UNSAT
  cases, plus concrete replay of every reported confidentiality witness;
- exact replay checks for same-program identity, complete witness domain,
  widths, Low equality, and the shared product support profile;
- an exact fixture catalog that makes deletion, addition, or header drift a
  test failure;
- explicit fail-closed status for unsupported profiles and unavailable tools.
- normalized solver timeout/launch/model-retrieval failures that cannot become
  a successful proof result.
- reproducibility, canonical-byte, schema, raw-negative, semantic-negative,
  and aggregation checks for the Rev4.1 machine interface package.

Not implemented and never implied by a passing reference run:

- parsing or normalizing LLVM bitcode;
- the patched `llvm.sps.release` intrinsic or its `SPS_RELEASE` MIR lowering;
- the complete normative `ExpandedCFGTableV2` or `SPS-PONF-v2` schemas;
- the full LLVM instruction, memory, contract, error, timing, and query
  surfaces;
- an inductive proof of the complete written metatheory;
- a concrete deployment/P4 refinement proof;
- arbitrary physical, microarchitectural, debugger, kernel, or DMA compromise.

Run all executable checks from the workspace root:

```sh
python3 SPS/reference/run_reference_checks.py
```

The command exits nonzero on a fixture failure, a disagreement between the
SMT, symbolic exhaustive, and independently interpreted concrete backends, a
rejected replay, specification/fixture drift, or a falsely closed unsupported
assurance claim. Z3 is required for this slice; CVC5 is cross-checked when
installed and otherwise remains explicitly open in the run output and
assurance manifest.

Set `Z3=/absolute/path/to/solver` to select an exact Z3 executable. The
reference runner honors that path directly; it does not silently substitute a
different ambient `z3` binary.
