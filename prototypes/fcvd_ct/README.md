# fcvd_ct — constant-time verification inside MLIR, on top of FCVD

Static, SMT-backed counterpart to `mlir_leak` (dynamic) and to `formal_verif`'s binary-level layers
A/B (binsec). Built on **FCVD** = *First-Class Verification Dialects for MLIR* (PLDI'25), whose
implementation is [`opencompl/xdsl-smt`](https://github.com/opencompl/xdsl-smt).

The idea: FCVD supplies formal SMT semantics for MLIR ops (values, UB/poison, memory); we add the
two things it lacks for a security property — an explicit **leakage model** (which observations an
attacker sees) and **self-composition** (two traces agreeing on public inputs, differing on secrets).
Constant-time then becomes one SMT query: UNSAT = proved, SAT = counterexample.

Plan, findings and honest scope limits: `../../docs/research/fcvd-selfcomposition.agents.md`.

## Setup

```bash
./setup.sh                                  # clones + installs xdsl-smt at ~/third_party/xdsl-smt
source ~/third_party/xdsl-smt/.venv/bin/activate
```

xdsl-smt ships no LICENSE file, so it is deliberately **not** vendored here — it stays an external
checkout referenced as a dependency.

## Status

- **P0 (done)** — `poc/run.sh`: shows that the stock refinement checker cannot be used as-is for
  constant-time (poison from function arguments makes even a CT kernel come back `sat`), which is why
  the driver needs its own predicate.
- P1+ — see the plan note.
