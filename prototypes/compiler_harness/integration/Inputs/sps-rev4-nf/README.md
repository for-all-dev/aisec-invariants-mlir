# Rev4 normal-form preflight inputs

These textual LLVM modules are review-sized inputs for the harness's
`CandidateOnly` normal-form tests. They are not normalized SPS artifacts and
they are not a substitute for canonical LLVM 22.1.8 bitcode.

Each test assembles its input into temporary `%t` bitcode, verifies it, and
uses LLVM 17.0.6 transformations only as structural or contrast oracles. Stock
`scalarizer`, `scalarize-masked-mem-intrin`, inlining, loop inspection,
`simplifycfg`, and `dce` are not aliases for the versioned SPS normalizer or
relational engine. In particular, a stock transformation may mutate the input,
erase too much, preserve residue, or use target-dependent behavior.

`tools/check_rev4_nf_seeds.py` is deliberately a narrow harness-owned checker
for these named inputs and JSON case tables. Its `SPS-Harness-Expectation`
lines describe the result a future conforming SPS run should produce; they are
not `NFConforms`, `ModelStatus`, replay, or deployment evidence. Successful
output always ends with:

```text
tier=CandidateOnly
nf_conforms=NotEvaluated
model_status=NotComputed
deployment_status=NotComputed
```

No `.bc` file belongs in this directory. Checked-in bitcode becomes meaningful
only when a complete Rev4.1 materialization freezes its artifact identity,
normalizer trace, audit inventory, policy/ABI bindings, relational query
schedule, and expected authenticated run report.
