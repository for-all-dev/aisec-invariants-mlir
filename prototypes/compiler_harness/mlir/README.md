# Checked-in MLIR regression fixtures

These 35 files are standard LLVM-dialect MLIR modules annotated as standalone
lit tests. They intentionally require no AISec dialect or SPS pass. Generic
discardable `sps.*` attributes record selected release, sanitizer, integrity,
and target-helper contracts without pretending that MLIR currently validates
those contracts.

Each fixture has two current checks:

1. `mlir-opt` parses and verifies the complete module.
2. `FileCheck` matches the minimum decisive IR shape and metadata.

That catches malformed IR and accidental fixture drift. It does not prove the
fixture's stated SPS outcome. See
[`L0_L1_L2_PIPELINE.md`](L0_L1_L2_PIPELINE.md) for the security model and the
future verifier interface.

## Required metadata

Every fixture begins with exactly one occurrence of each field:

```mlir
// case: <human-readable case name>
// classification: compiler-generated-minimized | modeled-from-verified-assembly | modeled-fixed-target | modeled-helper-call-without-contract | modeled-test-profile | seeded-semantic-harness | reduced-runtime-model
// c source: ../c/<existing-source-file>.c
// upstream GitHub source: <immutable source, stable report/issue, or motivating project URL>
// upstream revision: <full revision or none with an explanation>
// secret: <secret values>
// public: <public values and observer-visible state>
// expected outcome: verified | unsafe | unknown | conditional
// observer/model: <lower-kebab-case identifier>
// reason id: <lower-kebab-case identifier>
// outstanding obligations: none | <comma-separated lower-kebab-case identifiers>
// evidence boundary: <text naming at least one of L0 through L4>
```

The outcome field is one token, not a sentence and not a pair of possible
results. Scope belongs in `observer/model`; the explanation belongs in
`reason id`; uncertainty belongs in `outstanding obligations` and
`evidence boundary`.

The consistency rules are:

- `verified` and `unsafe` must use `outstanding obligations: none`.
- `unknown` and `conditional` must name at least one outstanding obligation.
- A bad filename must have outcome `unsafe`, cite bad/vulnerable C provenance,
  and contain an adjacent `CONFIDENTIALITY ERROR` block.
- A fixed filename must have outcome `verified` or `conditional`, cite fixed C
  provenance, and contain an adjacent `CONFIDENTIALITY REPAIR` block.
- Legacy `expected verdict`, `pass`, `reject`, compound outcomes, and legacy
  `exact incident boundary` metadata are rejected.

`../c/check_harness.py annotations` also pins the complete 35-file scenario
inventory, so adding or removing a fixture requires an explicit outcome-map
update.

## Lit/FileCheck convention

Every file carries a `RUN:` line equivalent to:

```mlir
// RUN: %mlir-opt %s | %FileCheck %s
```

Checks should identify the function with `CHECK-LABEL`, capture values with
variables such as `%[[SECRET:.*]]`, and assert only the essential dataflow or
operation. Fixed fixtures scope `CHECK-NOT` between labels or other positive
checks and also require the concrete replacement. Avoid matching SSA numbering,
printer whitespace, or an entire module snapshot.

Examples of decisive shapes include:

- a secret-derived value stored to the named public sink;
- `llvm.cond_br` fed by a secret-derived condition;
- `llvm.getelementptr` indexed by secret data;
- `llvm.udiv` or a helper call whose named profile has operand-dependent
  latency;
- a fixed scan, mask sequence, zero/redacted store, sanctioned release, or
  constant-latency helper contract replacing that effect.

Confidentiality-bad files are nevertheless valid MLIR. Their first RUN verifies
and checks the unsafe shape. A second, active `--verify-diagnostics` RUN requires
one localized `expected-error` per `CONFIDENTIALITY ERROR`, using the fixture's
stable reason ID. No final-LLVM SPS pass emits those diagnostics yet, so these
15 bring-up tests intentionally fail rather than being hidden behind `XFAIL`.
Once the pass exists, its invocation must be added to that second RUN.

## Generation boundary

```sh
make -C ../c regen-mlir
```

This runs Clang to emit LLVM IR and `mlir-translate --import-llvm`. Complete
imports are written beneath `../build/mlir/`; checked-in fixtures remain
minimal and reviewable.

For backend-modeled Clangover and wolfSSL cases, generated vulnerable imports
are `.source.mlir` and repaired imports are `.fixed_source.mlir`. The generator
never calls pre-backend imported IR `target_bad` or `target_fixed`. Checked-in
target files are hand-minimized models tied to separate assembly evidence.

The wolfSSL 3579 call scenarios are deliberately separate:

- `wolfssl_3579_mul.target_unknown.mlir` has no helper timing summary.
- `wolfssl_3579_mul.target_bad.mlir` selects the affected operand-dependent
  helper profile.
- `wolfssl_3579_mul.target_constant_latency.mlir` selects a constant-latency
  test profile.

No single file therefore means both `unknown` and `unsafe`.
