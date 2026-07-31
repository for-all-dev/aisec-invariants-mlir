# Rev4 semantic suite

This directory contains the seven future semantic tests corresponding to the
hand-authored SPS lecture artifacts. Every test requires all three capabilities:

```text
sps-verifier
llvm-22.1.8
sps-teaching-materialized
```

None is `XFAIL`. Missing implementation or canonical input is an absent
capability, so the current result is `UNSUPPORTED`. The executable integration
counterparts live at `../integration/sps-lecture-*.test`; they validate fixture
inventory and LLVM shape but never assert a `ModelStatus`.

Set `SPS_VERIFIER` and `SPS_TEACHING_MATERIALIZED` only after the exact
LLVM 22.1.8 packages exist. The materialized root must contain one directory
per case. The future CLI contract used here is:

```text
sps-verifier verify --bundle <materialized-root>/<case-id>
```

The verifier must consume `artifact.bc` plus its identity-bound canonical
policy, ABI, contracts, placement, timing, observation, and release data;
freshly parse and audit the bitcode; construct every derived coalition product;
and independently replay each counterexample. The fixture expectations remain
nonclaimable until those steps succeed.
