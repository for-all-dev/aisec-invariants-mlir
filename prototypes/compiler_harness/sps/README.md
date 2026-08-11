# Rev4.1 V2 verifier contracts

The active SPS boundary in this harness is Rev4.1 only. It consumes
`SPS-LLVM-NF-v2`, `SPSRunReportV2`, and the digest-locked V2 package under
`contracts/vendor/sps-rev4.1/`. No alternate report or configuration format is
part of this boundary.

`rev41-exact-verifier-contract.test` is feature-gated until both inputs exist:

- `SPS_VERIFIER capabilities --format=json` advertises spec `4.1`, profile
  `SPS-LLVM-NF-v2`, and every capability probed by `lit.cfg.py`; and
- `SPS_REV41_MATERIALIZED` names the operator-supplied V2 bundles used by the
  test.

The contract covers mandatory diagnostic health, complete observation and
latency schedules, the non-voting `RelationalRequired` diagnostic, accepted
replay over an unrelated proof-completion timeout, and rejection of accepted
replay with a replay-invalidating blocker. Stock LLVM and the current
unimplemented verifier therefore report the test as `UNSUPPORTED`; they never
fabricate success.

Before an exact-verifier report is interpreted, the harness validates its
materialized identity, evidence, NF manifest, proof configuration, aggregation
input, artifact bytes, and report with `tools/check_sps_v2_bundle.py`. That is a
cross-file boundary check, not a verifier: it does not establish `WFInputs` or
`NFConforms`, solve a product, or authenticate restricted evidence by itself.

Always-runnable V2 schema, canonical-byte, semantic-rule, aggregation,
required-module, and bundle-boundary tests live under `contracts/`. NFv2
intrinsic preservation and code-generation contracts live under
`integration/` and are independently capability-gated.

## V2 removal

The former V2 report checker and its teaching/report tests have been removed.
There is no archive or alternate-version execution path. Rev4.1 materialized
inputs and reports must validate directly against the V2 package.
