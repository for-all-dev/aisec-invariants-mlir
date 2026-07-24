# Layer C — validate the leakage contract against real silicon

Layer C of the timing roadmap in [`../README.md`](../README.md). Layers A and B
prove a program satisfies a **contract** (`[ct]`, `[cache-line]`) — but only in
a *model* of the machine. The model is an assumption about the hardware: that
non-selected instructions run in fixed time, that only the cache line (not
sub-line timing) is observable, that no microcode assist depends on operand
values. **Layer C tests that assumption on the actual chip.**

This is the job the roadmap assigns to Revizor / Scam-V — *does the CPU leak
beyond the contract?* — expressed through the same **information estimate** as
layer D: measure the kernel on this silicon, estimate the bits its timing leaks
(`I(secret; timing)`), and compare to what the contract **allows**.

- A contract verdict of **`secure`** claims the observable carries **0 bits**.
  Any measured `I(S;T)` above the harness floor **refutes** the contract on this
  CPU — the model promised a guarantee the hardware does not keep.
- A contract verdict of **`insecure`** already predicts leakage; the measurement
  either **confirms** it or shows it is **not exploitable at this config point**
  (the contract was conservative).

The engine is the reusable [`../infoleak/`](../infoleak/) package
(`infoleak silicon`); this directory reuses layer D's corpus
([`../timing_d/cases.c`](../timing_d/cases.c)) — one corpus, two lenses, the same
way layers A and B both run over `ctverify`.

## The four outcomes

| contract verdict (A/B) | silicon measures a leak? | status | meaning |
|---|---|---|---|
| `secure` | no | **consistent** | model holds on this CPU |
| `secure` | **yes** | **contract-violated** | **silicon leaks beyond the model** |
| `insecure` | yes | **confirmed** | silicon leaks as A/B predicted |
| `insecure` | no | **not-exploitable-here** | contract was conservative at this config |

## Run

```sh
bash run.sh            # gcc
N=40000 bash run.sh    # more samples
```

Needs a C compiler and `uv`; **no binsec, no -m32** (C tests silicon, not a model).

## Result (gcc `-O2 -march=native`, Intel Xeon 8168, N=20000)

| kernel | A/B verdict (`[ct]`) | measured bits | status |
|---|---|---|---|
| `d_ct_baseline` | secure | 0.000 | **consistent** |
| `d_denormal` | secure | 0.991 | **contract-violated** |
| `d_branch_earlyexit` | insecure | 0.999 | **confirmed** |

**The headline is `d_denormal`.** binsec (`-checkct`, including layer-A's
variable-latency features) proves it `secure`: the kernel is a plain FP
multiply-accumulate with no secret-dependent branch, address, or integer mul/div
— nothing in binsec's instruction semantics leaks. Yet on this Xeon the timing
leaks **~1 bit/query** because subnormal secret operands trigger a ~39× microcode
assist the model never sees. Layer C names this precisely: **the `[ct]` contract
claims 0 bits but the silicon leaks ~0.99 — MODEL REFUTED on this CPU.** That is
the `[ct]`-vs-silicon trust gap layer B explicitly puts out of its own scope,
now measured and quantified.

The other two are the calibration poles: `d_ct_baseline` shows C does not cry
wolf on a genuinely oblivious kernel (`consistent`), and `d_branch_earlyexit`
shows C correctly reports `confirmed` when A/binsec already flagged the leak and
the chip agrees.

## What C does and does not buy you

- **Closes B's trust gap in the exploitable direction.** A `secure`-contract →
  `contract-violated` result is a genuine, load-bearing finding: your formal
  proof does not transfer to this hardware/config, and you can see how many bits
  escape.
- **It is silicon- and config-specific.** The violation depends on this CPU and
  this build. `-ffast-math` (FTZ/DAZ) or an FPU without a subnormal assist would
  make `d_denormal` `consistent` again — which is the correct, honest answer:
  whether the contract holds *is* a deployment property.
- **Still detection, not proof** (it inherits layer D's floor). A `consistent`
  verdict means "no violation observed at this N on this CPU", not "the contract
  provably holds on all silicon". Proving a contract holds on hardware is the
  RTL/formal job (LeaVe, layer B's hardware half) — out of scope here.

## References

- Oleksenko et al., *Revizor: Testing Black-Box CPUs against Speculation Contracts* (ASPLOS 2022) — relational testing of a CPU against a leakage contract.
- Nemati et al., *Scam-V* — validating observational models against hardware.
- Guarnieri, Köpf, Reineke, Vila, *Hardware-Software Contracts for Secure Speculation* (IEEE S&P 2021) — the contract framework C validates.
