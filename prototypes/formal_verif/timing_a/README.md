# Layer A — variable-latency (mul/div) constant-time, formal & software-only

Layer A of the timing roadmap in [`../README.md`](../README.md). Standard
constant-time forbids the secret from steering a **branch** or a memory
**address**. Layer A adds the third software channel: variable-latency
**arithmetic** — integer division (latency depends on operand magnitude) and,
on some microarchitectures, multiplication. It needs **no external library**:
`binsec -checkct` already exposes these as check points.

```
-checkct-features control-flow,memory-access,multiplication,dividend,divisor
```

(`multiplication`, `dividend`, `divisor` are marked experimental upstream.)

The check itself lives in the reusable [`../ctverify/`](../ctverify/) package
(`ctverify checkct --features layerA`); this directory is a worked example whose
`run.sh` just compiles the corpus and drives that CLI.

## Run

```sh
bash run.sh            # gcc
CC=clang bash run.sh   # clang
```

Requires binsec (`eval $(opam env)`), a `-m32` toolchain, and `uv` (the driver
calls the `ctverify` CLI). Result (gcc, at `-O0`):

| kernel | defaultCT | layerA |
|---|---|---|
| `a_ct_baseline` | secure | secure |
| `a_div_public` | secure | secure |
| `a_div_divisor` | secure | **insecure** |
| `a_div_dividend` | secure | **insecure** |
| `a_mul_operand` | secure | **insecure** |

The headline is the **delta**: `a_div_*` and `a_mul_operand` have no
secret-dependent branch or address, so default constant-time verifies them
`secure`; only once layer A's features are enabled does binsec prove the
secret reaches a variable-latency instruction. The controls (`a_ct_baseline`,
`a_div_public` — division by a *public* divisor) stay `secure` under gcc, so the
added check is not just flagging every `imul`/`idiv`.

> Note (clang): under `CC=clang` the branchless `a_ct_baseline` flips to
> `insecure` at `-O2` — the same "clang breaks `(m&a)|(~m&b)`" result the parent
> prototype documents (`../README.md`, quadrant `q_oblivious`). That is a
> control-flow / memory-access leak the compiler *introduced*, orthogonal to the
> mul/div point of this layer but caught because the layer-A feature set is a
> superset of default CT. `a_div_public` stays `secure` under both compilers and
> is the clean control here.

## Trust anchor and scope limit (honest)

- **DOIT/DIT assumption.** Layer A proves the secret does not reach a
  *variable-latency* instruction; it assumes the remaining instructions run in
  fixed time. On modern x86/ARM that is exactly the guarantee of the hardware
  **DOIT/DIT** modes (Data-Operand-Independent-Timing) — enable them, and A's
  software proof composes into a real timing guarantee. Without DOIT/DIT, even
  "safe" instructions may vary and A is necessary-but-not-sufficient.
- **Denormals are out of scope for A.** The ~25× floating-point denormal
  slowdown (see the `leak_check/` prototype) is a microarchitectural effect
  *not present in binsec's instruction semantics* — no solver sees it. It is a
  **layer D** concern (dudect/ct-fuzz measurement). The formal software move
  available here is to forbid FP-on-secret as a taint property; proving the
  timing itself is not possible at this layer.

## References

- Intel, *Data Operand Independent Timing (DOIT)* / Arm, *DIT* — fixed-latency
  execution modes that are the hardware backing for this layer.
- Oscar Reparaz, "Compilers and constant-time code" — https://www.reparaz.net/oscar/misc/cmov
