# leak_check: Detecting Compiler-Introduced Information Leaks

A general, compiler-agnostic harness for deciding whether a *compiler*, rather than the source program, introduces a secret-dependent execution path.

This prototype measures whether a compiler (e.g., `torch.compile`/Inductor) transforms data-oblivious code into secret-dependent machine code.

## Quick Start

### Installation

This project uses `uv` for dependency management:

```bash
uv sync --dev
```

### Documentation

Start with the methodology document: [`../../docs/research/leak_check.methodology.siddarth.md`](../../docs/research/leak_check.methodology.siddarth.md)

Reference materials:
- **Empirical results**: [`../../docs/research/leak_check.results.siddarth.md`](../../docs/research/leak_check.results.siddarth.md)
- **Environment setup**: [`../../docs/research/leak_check.environment.siddarth.md`](../../docs/research/leak_check.environment.siddarth.md)
- **CSI-NN paper reference**: [`../../docs/research/leak_check.csi_nn_paper.siddarth.md`](../../docs/research/leak_check.csi_nn_paper.siddarth.md)

### Core Modules

- **`instruments.py`**: Observation channels (taint tracking, instruction counts, timing)
- **`noninterference.py`**: Differential testing framework
- **`corpus.py`** / **`corpus_activations.py`**: Test input generation (extreme values for sensitivity)
- **`measured_run.py`**: Orchestrate a measurement across different configurations
- **`attacks/`**: Model-specific attacks for extracting model information through side channels
- **`ctbench/`**: Constant-time benchmarking utilities

### Principles

See [`PRINCIPLES.md`](PRINCIPLES.md) for the constitution governing this work:

- **Evidence discipline**: Every claim names the script and exact command that produced it
- **Scope verdicts**: Results hold for one config point `(source, compiler, backend, version, flags, target ISA)`
- **Sober tone**: State what was measured and what it means; let evidence carry weight
- **Reproducibility**: Include runnable commands; pin determinism (fixed seed, single-thread BLAS/OMP, warm caches)
- **Code quality**: SOLID design; new attacks/targets should slot into existing interfaces
