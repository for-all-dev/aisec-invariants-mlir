# leak_check: Detecting Compiler-Introduced Information Leaks

A general, compiler-agnostic harness for deciding whether a *compiler*, rather than the source program, introduces a secret-dependent execution path.

This prototype measures whether a compiler (e.g., `torch.compile`/Inductor) transforms data-oblivious code into secret-dependent machine code.

## Quick Start

### Installation

This project uses `uv` for dependency management. One command gives every
contributor the same environment — the full runtime stack (torch + CUDA,
scikit-learn) plus the dev tools — resolved from the committed `uv.lock`:

```bash
uv sync
```

### Development / CI

The same four checks run in GitHub Actions ([`.github/workflows/leak-check-ci.yml`](../../.github/workflows/leak-check-ci.yml)) and should pass locally before pushing:

```bash
uv run ruff format --check .   # formatting (ruff is the single formatting authority)
uv run ruff check .            # lint
uv run ty check .              # type-check
uv run pytest                  # tests
```

`ruff format` normalises the whole package; run `uv run ruff format .` to apply
it. Notebooks (`*.ipynb`) are analysis artifacts and are never linted or
formatted. `ty` skips the pure torch-nn model files, where it only
false-positives on torch's dynamic attribute typing (see `[tool.ty.src]` in
`pyproject.toml`).

### Documentation

Start with the methodology document: [`../../docs/research/leak_check.methodology.siddarth.md`](../../docs/research/leak_check.methodology.siddarth.md)

Reference materials:
- **Empirical results**: [`../../docs/research/leak_check.results.siddarth.md`](../../docs/research/leak_check.results.siddarth.md)
- **Environment setup**: [`../../docs/research/leak_check.environment.siddarth.md`](../../docs/research/leak_check.environment.siddarth.md)
- **CSI-NN paper reference**: [`../../docs/priorlit/csi_nn_paper.siddarth.md`](../../docs/priorlit/csi_nn_paper.siddarth.md)
- **Journal**: [`../../docs/research/journal/`](../../docs/research/journal/)

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
