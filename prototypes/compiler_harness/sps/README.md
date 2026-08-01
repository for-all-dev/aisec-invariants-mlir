# Rev4 semantic and machine-contract suite

lit discovers eleven tests here. Seven are the future semantic tests
(`teaching-01`-`teaching-07`) corresponding to the hand-authored SPS lecture
artifacts; each of those requires all three capabilities:

```text
sps-verifier
llvm-22.1.8
sps-teaching-materialized
```

None is `XFAIL`. Missing implementation or canonical input is an absent
capability, so the current result for those seven is `UNSUPPORTED`. The
executable integration counterparts live at `../integration/sps-lecture-*.test`;
they validate fixture inventory and LLVM shape but never assert a
`ModelStatus`.

Three report tests are ungated and run today, because they exercise the
report checker against checked-in synthetic JSON rather than a verifier:

| Test | What it pins |
| --- | --- |
| `report-schema.test` | the top-level `CompletedV1` envelope and the three `ModelStatus` shapes |
| `report-nested-canonicality.test` | every section-19 nested record, the query scope matrix, `CanonicalPublicQueryScheduleDigestV1`, one result row per schedule ordinal, and the exact `ReleasePolicyLintV1` list |
| `report-nonclaim-arms.test` | the `ConfigurationRejectedV1` and `ReportingFailedV1` refusal arms and their `disposition: "NoModelStatus"` boundary |

The error-event work adds two more tests without changing the authority
boundary:

| Test | What it pins |
| --- | --- |
| `../integration/sps-error-events-contract.test` | ungated `SPS-Harness-*`, nonclaimable future-conformance intent plus missing/dangling/malformed binding and event-order negatives |
| `error-events-conformance.test` | future exact-verifier report/status smoke arm for an operator-supplied `ConformanceV1` directory, gated on `sps-verifier`, LLVM 22.1.8, and `SPS_ERROR_MATERIALIZED` |

Their fixtures under `Inputs/` are deliberately synthetic (`aaaa...`/`cccc...`
digests). A passing arm says the bytes are a well-formed report of the
requested arm; it never says `NFConforms`, and it never turns a matcher into a
computed `ModelStatus`. `Inputs/lecture-policy-release.json` is a
`SPS-Harness-Lecture-Policy-Release-v1` transcription of the *declared*
lecture policy visibility bases and release audiences; the checker applies the
normative section-12 lint predicates to it rather than mirroring a lecture
`expected.logical.yaml`, which self-declares `normativeInterface: false`.

Set `SPS_VERIFIER` and `SPS_TEACHING_MATERIALIZED` only after the exact
LLVM 22.1.8 packages exist. The materialized root must contain one directory
per case. The future CLI contract used here is:

```text
sps-verifier verify --bundle <materialized-root>/<case-id>
```

The independent error-event case uses `SPS_ERROR_MATERIALIZED` pointing
directly at its materialized `ConformanceV1` directory. Until then, only the
namespaced contract and its negative mutations execute; they print
`ModelStatus=NotComputed`.

The exact verifier, not the smoke arm, owns identity binding, fresh parsing,
`NFConforms`, query construction, and replay. The arm checks the required tier
file inventory and the verifier's canonical report shape/status against the
checked-in future contract; it does not independently certify the supplied
directory as conformant.

Standard output is the compact canonical `SPSRunReportV1` JSON byte sequence,
not a human rendering. Each test passes it to
`tools/check_sps_run_report.py`, which rejects duplicate, unknown, or reordered
fields *recursively*, at the top level and inside every schema'd nested record;
re-serializes from a declared per-record field-order table rather than from
parse order; dispatches on the requested `SPSRunReportV1` arm (`--expect-arm`,
default `CompletedV1`); checks the independent result domains; and requires
`Counterexample` to carry only a fresh 256-bit `receiptId`. Human-readable
output is intentionally outside these wire-format tests.

Two derivations are recomputed rather than trusted: `queryScheduleDigest` must
equal `SHA256(CanonInterfaceJSONV1(querySchedule))`, and
`releasePolicyReview.lints` must be the exact ordered set the four
`ReleasePolicyLintClass` predicates produce from the declared policy, release,
and review rows. The checker still executes no relational semantics, parses no
bitcode, and resolves no receipt against a restricted store.

Two positions are deliberately outside the recursive key check: a value that
the schema types as a scalar but that arrives as an object (its diagnostic
belongs to the later semantic pass, for example a `Counterexample` argument
that is a witness object rather than a receipt string), and the two positions
still typed opaque here, `OptionV1.value` and the argument of
`DeploymentStatus: Closed`. The base profile never emits the latter.

The verifier must consume `artifact.bc` plus its identity-bound canonical
policy, ABI, contracts, placement, timing, observation, and release data;
freshly parse and audit the bitcode; construct every derived coalition product;
and independently replay each counterexample. The fixture expectations remain
nonclaimable until those steps succeed.
