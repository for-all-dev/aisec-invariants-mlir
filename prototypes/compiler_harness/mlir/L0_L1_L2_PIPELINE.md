# Confidentiality evidence pipeline and result contract

This document separates what the current LLVM/MLIR regression suite checks
from what a future SPS information-flow verifier must establish. Today,
`mlir-opt` verification, `FileCheck`, the C witness driver, and backend
code-generation tests preserve evidence. They do not compute or prove the
four-valued outcomes recorded in fixture metadata.

Run the layers from the harness root:

```sh
make check                 # all lit tests
make check-mlir            # MLIR verification and decisive IR shape
make check-integration     # metadata, C witness, import, and backend evidence
make list-tests            # discovery audit
make -C c verify           # compatibility entry point
```

## Evidence levels

| Level | Role in this harness |
| --- | --- |
| L0 | Declares secrets, public inputs, observer projections, authorized release policies, helper summaries, host/audience authority, integrity requirements, and target timing facts. |
| L1 | Propagates dependence and analyzes effects such as branches, addresses, variable-latency operations, public sinks, and summarized helpers. |
| L2 | Produces a relational witness: equal public inputs and authorized releases, different secrets, and different observations. |
| L3 | Relates source, imported IR, and target artifacts to attribute a violation or repair to a compiler boundary. |
| L4 | Supplies facts outside the modeled MLIR semantics, including real helper latency, compressor behavior, GPU isolation, sanitizer sufficiency, certificate soundness, and backend trace preservation. |

An `evidence boundary` says where the fixture's conclusion is established and
where its real-world applicability stops. It is not an assurance score.

## Four-valued outcome contract

| Outcome | Meaning for the named observer/model | Obligations |
| --- | --- | --- |
| `verified` | The modeled artifact has no residual forbidden dependence at the claimed boundary. | Must be `none`. |
| `unsafe` | The modeled artifact contains a forbidden dependence or a concrete relational counterexample. | Must be `none`; applicability limitations belong in the model/boundary. |
| `unknown` | Required semantics or a contract are absent, so neither safety nor unsafety follows. | Must name the missing facts. |
| `conditional` | The modeled repair is acceptable only if named external assumptions are discharged. | Must name every outstanding assumption used by the conclusion. |

This is why the affected wolfSSL 3579 helper model is `unsafe` while the same
call with no timing summary is `unknown`: they are separate scenarios with
different L0 knowledge, not two outcomes attached to one file.

## Exact fixture map

The following 35 outcomes are enforced by `c/check_harness.py`. Reason IDs and
obligation IDs are stable machine-facing identifiers; explanatory scope stays
in the observer/model and evidence-boundary fields.

| Fixture | Outcome | Reason ID | Outstanding obligations |
| --- | --- | --- | --- |
| `breach_compressed_length.bad.mlir` | `unsafe` | `secret-to-public-sink` | `none` |
| `breach_compressed_length.fixed.mlir` | `verified` | `public-sink-isolation` | `none` |
| `ckks_unsafe_release.bad.mlir` | `unsafe` | `unauthorized-release` | `none` |
| `ckks_unsafe_release.fixed.mlir` | `conditional` | `sanitized-release-requires-evidence` | `sanitizer-sufficiency,certificate-soundness,release-policy-integrity` |
| `clangover_poly_frommsg.lowered_bad.mlir` | `unsafe` | `secret-dependent-branch` | `none` |
| `clangover_poly_frommsg.lowered_fixed.mlir` | `verified` | `branchless-selection` | `none` |
| `clangover_poly_frommsg.source.mlir` | `verified` | `source-branchless-dataflow` | `none` |
| `dynamic_kv_length.bad.mlir` | `unsafe` | `secret-to-public-sink` | `none` |
| `dynamic_kv_length.fixed.mlir` | `verified` | `public-sink-isolation` | `none` |
| `explicit_error_oracle.bad.mlir` | `unsafe` | `residual-leak-beyond-release` | `none` |
| `explicit_error_oracle.fixed.mlir` | `verified` | `authorized-release-only` | `none` |
| `kyberslash1_poly_tomsg.bad.mlir` | `unsafe` | `secret-dependent-variable-latency-op` | `none` |
| `kyberslash1_poly_tomsg.fixed.mlir` | `verified` | `variable-latency-op-removed` | `none` |
| `kyberslash2_compress.bad.mlir` | `unsafe` | `secret-dependent-variable-latency-op` | `none` |
| `kyberslash2_compress.fixed.mlir` | `verified` | `variable-latency-op-removed` | `none` |
| `leftoverlocals_scratch.bad.mlir` | `unsafe` | `cross-domain-stale-state` | `none` |
| `leftoverlocals_scratch.fixed.mlir` | `verified` | `cross-domain-state-reinitialized` | `none` |
| `redis_pool_reuse.bad.mlir` | `unsafe` | `cross-domain-stale-state` | `none` |
| `redis_pool_reuse.fixed.mlir` | `verified` | `cross-domain-state-reinitialized` | `none` |
| `secret_embedding_index.bad.mlir` | `unsafe` | `secret-dependent-address` | `none` |
| `secret_embedding_index.fixed.mlir` | `verified` | `secret-independent-address-scan` | `none` |
| `secret_logging_checkpoint.bad.mlir` | `unsafe` | `secret-to-public-sink` | `none` |
| `secret_logging_checkpoint.fixed.mlir` | `verified` | `public-sink-isolation` | `none` |
| `wolfssl_3579_mul.source.mlir` | `unknown` | `missing-target-timing` | `target-lowering-semantics,helper-latency-contract` |
| `wolfssl_3579_mul.target_unknown.mlir` | `unknown` | `missing-helper-contract` | `helper-latency-contract` |
| `wolfssl_3579_mul.target_bad.mlir` | `unsafe` | `secret-dependent-variable-latency-call` | `none` |
| `wolfssl_3579_mul.target_constant_latency.mlir` | `verified` | `constant-latency-helper-contract` | `none` |
| `wolfssl_3579_mul.target_fixed.mlir` | `conditional` | `fixed-loop-requires-target-evidence` | `base-operation-latency,backend-trace-preservation` |
| `wolfssl_3580_mask.source.mlir` | `verified` | `source-branchless-dataflow` | `none` |
| `wolfssl_3580_mask.target_bad.mlir` | `unsafe` | `secret-dependent-branch` | `none` |
| `wolfssl_3580_mask.target_fixed.mlir` | `verified` | `branchless-selection` | `none` |
| `wrong_host_fhe_reveal.bad.mlir` | `unsafe` | `wrong-audience-or-host` | `none` |
| `wrong_host_fhe_reveal.fixed.mlir` | `verified` | `authorized-sink-isolation` | `none` |
| `wrong_party_plaintext.bad.mlir` | `unsafe` | `wrong-audience-or-host` | `none` |
| `wrong_party_plaintext.fixed.mlir` | `verified` | `authorized-sink-isolation` | `none` |

Interpretation boundaries remain important:

- BREACH and Dynamic KV already inline a public length/count fact; they do not
  model a compressor, allocation, shape, loop, or scheduler.
- Redis and LeftoverLocals are reduced sequential cross-domain models; the
  original cancellation/concurrency and GPU isolation facts are L4.
- CKKS fixed models release ordering and masks but leaves production sanitizer,
  certificate, and policy integrity as named L4 obligations.
- Clangover and wolfSSL target files are hand-minimized models. L3 evidence is
  required to relate them to actual compiler output.

## Release-relative security property

Let `P` be the artifact, `p` public inputs, `s0` and `s1` two secret inputs,
`R` the releases authorized for the named observer, and `Obs_Theta` the
observation projection selected by target/profile `Theta`:

```text
for every p, s0, s1:
  R(p, s0) == R(p, s1)
    implies Obs_Theta(Trace(P, p, s0)) == Obs_Theta(Trace(P, p, s1))
```

Returned private data may depend on a secret. A violation is an additional
observer-visible dependency, such as branch direction, address, operation
latency/count, allocation size, transfer length, public sink value, or delivery
to an unauthorized host/audience.

The explicit oracle illustrates the release condition: L2 holds the sanctioned
validity result equal while varying error detail. CKKS uses the declared masked
release function in the equality premise. A raw private return is outside the
public observer projection in those reduced models.

## L0 and L1 model sketch

An L0 profile supplies facts such as:

```yaml
observer: local-timing-or-public-output-attacker
observes: [branch-direction, memory-address, operation-latency, public-sink-value]
operations:
  llvm.udiv: variable-latency
  llvm.mul: target-parameterized
helpers:
  __muldi3:
    latency: operand-dependent
    relevant-operands: [0, 1]
release-policies:
  padding_validity_v1: not(padding_is_valid)
  ckks_masked_release_v1: raw & public_mask & certificate_mask
unknown-call: unknown
```

L0 is a contract, not proof of the contract. If no `__muldi3` summary is
available, the result is `unknown`. Selecting a named operand-dependent test
profile allows L1 to classify the call as `unsafe` under that profile; L4 is
still needed to claim that a real deployed helper matches it.

Conceptually, L1 propagates an SSA dependence label and a program-counter
label through ordinary operations. It checks timing-relevant operands for
variable-latency operations/helpers, conditions for branches, index operands
for addresses, and stored values for public sinks. A sanctioned release removes
only the dependence authorized by the named release function.

## Future IFC report interface

A production SPS pass should emit a deterministic structured result containing
at least:

```text
outcome: verified | unsafe | unknown | conditional
observer_model: <stable identifier>
reason_id: <stable identifier>
obligations: [<stable identifier>, ...]
evidence_boundary: <L0-L4 provenance>
locations: [<source/IR locations for decisive effects>]
```

The `expected-error` comments are active bring-up oracles for that future
interface. Until the final-LLVM SPS pass is added to their diagnostic RUN, bad
fixtures deliberately fail because the expected stable reason IDs are not
emitted. Once implemented, the pass must produce localized diagnostics while
avoiding prose snapshots. Missing semantics,
unsupported operations, or solver timeout must report `unknown`, never
`verified`. Certification tooling may impose its own policy over these four
results, but the analysis must not collapse them into shell success/failure.

## L2 witness examples

| Case | Relational witness |
| --- | --- |
| Clangover | `bit=0` and `bit=1` select different successors in the lowered bad model. |
| wolfSSL 3580 | Equal public scan inputs and different secret table indices change the modeled target branch. |
| KyberSlash | Equal public constants and different coefficients reach a variable-latency `llvm.udiv`. |
| Explicit oracle | Equal `padding_is_valid` values and different error detail keep the authorized release equal but change the bad public detail output. |
| BREACH analogue | Equality versus inequality of secret byte and public guess produces public lengths 31 versus 32. |
| CKKS | Raw values 55 and 23 with public mask 12 and certificate 1 have the same declared release 4, while the bad sink exposes different raw values. |
| Secret embedding index | Different secret indices produce different `llvm.getelementptr` addresses. |

These finite witnesses strengthen the regression corpus but do not replace a
proof over all inputs.
