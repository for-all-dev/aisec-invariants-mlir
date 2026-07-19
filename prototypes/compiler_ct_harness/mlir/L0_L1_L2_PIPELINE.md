# Catching the harness cases at L0, L1, and L2

This document explains what the current C/MLIR fixtures can demonstrate before
the SPS verifier exists. The checked-in MLIR comments are documentation only;
later they can become sidecar annotations, attributes, or lit expectations.

## Level meanings

| Level | Role in this harness |
| --- | --- |
| L0 | Declares secrets, public inputs, observable effects, target timing facts, helper summaries, host authority, and allowed release policies. |
| L1 | Propagates secret dependence and rejects direct observable effects such as branches, addresses, variable-latency operations, public sinks, and known unsafe helpers. |
| L2 | Builds a relational witness: two runs with equal public inputs and different secrets that produce different observations. |
| L3 | Attributes a violation to a compiler lowering, backend choice, or translation boundary. This is needed for compiler-regression claims. |
| L4 | Supplies facts outside MLIR semantics, such as actual helper timing, compressor internals, GPU isolation, or numerical-noise proof obligations. |

## Security property

Let `P` be the artifact under analysis, `p` public inputs, `s0` and `s1` two
secret inputs, and `Obs_Theta` the observation projection selected by target
profile `Theta`.

```text
for every p, s0, s1:
  Obs_Theta(Trace(P, p, s0)) == Obs_Theta(Trace(P, p, s1))
```

Returned private data may depend on the secret. The violation is an additional
observer-visible dependency, such as branch direction, address, latency,
allocation count, response length, public sink value, or unauthorized host
placement.

## Case table

| Case | L0 role | L1 | L2 | Honest L0-L2 result |
| --- | --- | ---: | ---: | --- |
| Clangover | Mark message bit secret; branch direction observable | yes on lowered branch | yes, `bit=0/1` | Catches unsafe target; L3 needed to call it a compiler regression |
| wolfSSL 3580 | Secret table index; RV32I branch profile | yes if `bnez` is imported or modeled | yes, index pair | Requires machine-level artifact; L3 stores backend evidence |
| wolfSSL 3579 | Secret operands; `__muldi3` helper summary | partial known-helper sink | partial with latency semantics | Helper timing fact remains L4 |
| KyberSlash1 | Secret coefficient; division variable-time | yes | optional | Strong direct L1 case |
| KyberSlash2 | Secret coefficient; division variable-time | yes | optional | Strong direct L1 case |
| Wrong-party plaintext | Owners, hosts, audiences, public/unauthorized sinks | yes | usually unnecessary | Direct L1 placement/output violation |
| redis-py analogue | Actors and public response channel | yes for sequential model | optional | Analogue only; exact concurrent incident needs future runtime semantics |
| Secret logging/checkpoint | Declare public log and artifact sinks | yes with call/sink summaries | usually unnecessary | Direct L1 sink violation |
| Explicit error oracle | Error/status/length observable; allowed validity release | yes | yes for residual leakage | L1 rejects direct secret status; L2 can justify witnesses |
| BREACH analogue | Transfer size observable; compressor summary | partial size taint | yes if compressor semantics exist | Modeled compressor only; compressor fact is L4 |
| Secret embedding index | Secret index; address granularity observable | yes | optional | Direct L1 address-effect violation |
| Dynamic tensor/KV length | Shape/length secret; allocation and loop counts visible | planned but v1 incomplete | partial with dynamic-shape semantics | Needs dynamic-shape support beyond current tiny model |
| Wrong-host FHE reveal | Host authority and reveal/release policy | yes | usually unnecessary | Direct L1 host-policy violation |
| CKKS unsafe release | Sanitizer prerequisite and certificate slot | yes for ordering/host/policy | partial for release correctness | Noise sufficiency remains L4 |
| LeftoverLocals analogue | Scratch ownership and tenant boundary | yes for sequential scratch model | optional | Analogue only; exact GPU persistence/isolation is L4 |

## L0 profile sketch

```yaml
observer: local_timing_or_public_output_attacker

observes:
  - branch_direction
  - memory_address
  - operation_latency
  - operation_count
  - allocation_size
  - transfer_length
  - public_sink_value
  - unauthorized_host_value

operations:
  llvm.udiv: variable_latency
  llvm.sdiv: variable_latency
  llvm.mul: target_parameterized
  llvm.add: fixed_latency
  llvm.and: fixed_latency
  llvm.or: fixed_latency
  llvm.xor: fixed_latency
  llvm.shl: fixed_latency
  llvm.lshr: fixed_latency

helpers:
  __muldi3:
    latency: operand_dependent
    relevant_operands: [0, 1]

unknown_call: reject_or_obligation
```

L0 is a contract, not a proof. If it says `__muldi3` is operand-dependent, L1
may reject the call. If the helper body and timing summary are absent, the
checker should return `unknown` or a target obligation, not silently pass.

## L1 rules

L1 assigns SSA values a label:

```text
Public <= Secret
```

For ordinary dataflow:

```text
label(result) = pc OR label(operand_0) OR ... OR label(operand_n)
```

For observable effects:

```text
branch:
  dependency = pc OR label(condition)

variable latency:
  dependency = pc OR labels(timing-relevant operands)

address:
  dependency = pc OR labels(address operands)

public sink:
  dependency = pc OR label(stored value)

known helper:
  dependency = pc OR labels(profile.relevant_operands)
```

If the dependency is secret and the policy does not permit that release, L1
rejects.

## L2 witness shape

For a suspicious effect `e`, L2 solves:

```text
StateWF(run0)
AND StateWF(run1)
AND PublicInputs(run0) == PublicInputs(run1)
AND SecretInputs(run0) != SecretInputs(run1)
AND Semantics(P, run0, trace0)
AND Semantics(P, run1, trace1)
AND ObservableEffect(trace0, e) != ObservableEffect(trace1, e)
```

Example witnesses:

| Case | Witness |
| --- | --- |
| Clangover | `bit=0` goes to `^not_taken`; `bit=1` goes to `^taken`. |
| wolfSSL 3580 | Same public scan index, two secret table indices make the modeled `bnez` differ. |
| KyberSlash | Same public constants, two coefficients reach variable-time `llvm.udiv`. |
| Explicit error oracle | `padding_is_valid=0` and `1` produce different public status values. |
| BREACH analogue | `secret_byte == public_guess` shortens the public wire length. |
| Secret embedding index | Two secret indices produce different `llvm.getelementptr` addresses. |

Unsupported semantics or timeout should produce `unknown`, not `pass`.

## Per-family notes

Clangover: the source fixture is branchless and can pass L1. The bad fixture is
a target-level model of observed x86 `btl`/`jae`; L1 rejects the branch and L2
can produce `bit=0/1`. L3 is required to claim the compiler introduced the
unsafe branch.

wolfSSL 3580: the source scan is fixed-count and mask-based. The bad fixture
models the reported RV32I `bnez`/`bne` backend shape. L1/L2 can reject the
modeled target artifact, while L3 records the GCC backend evidence.

wolfSSL 3579: source `llvm.mul i64` is not enough by itself. The RV32I target
profile matters because legalization may call `__muldi3`. L1 can reject a
known unsafe helper summary, but the helper timing evidence is L4.

KyberSlash1 and KyberSlash2: the vulnerable fixtures contain direct
secret-derived `llvm.udiv`. They are the cleanest L1 cases. The fixed fixtures
replace division with multiply/add/shift and retain the final bit or nibble
mask.

Semantic/runtime models: these are not claims about compiler bugs. They give
the same SPS machinery non-crypto examples: wrong sink, public error bit,
compressed length, secret address, dynamic length, host authority, release
ordering, and tenant scratch state.
