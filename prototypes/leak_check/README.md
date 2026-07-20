# leak_check: Detecting Compiler-Introduced Information Leaks

A general, compiler-agnostic harness for deciding whether a *compiler*, rather than the source program, violates the confidentiality of a secret (here, the model weights).

This prototype started by asking whether a compiler (e.g., `torch.compile`/Inductor) transforms data-oblivious code into a secret-dependent *execution path*. That question is largely answered "no, the compiler tends to *remove* such paths" (see the lessons note). But the search since found two leaks of a different shape, where the compiler is the threat:

- **Constant-folding under freezing** bakes a secret-derived statistic (a quantization scale `max|w|/127`) into the generated code as a numeric literal — the compiled artifact discloses that statistic of the secret weights exactly. ([finding](../../docs/research/leak_check.freezing.agents.md), [instruction-level escalation](../../docs/research/leak_check.freezing-taint.agents.md))
- **Artifact exfiltration**: AOTInductor persists the raw weight bytes into a content-addressed `.so`/`.pt2` under the world-traversable `/tmp/torchinductor_<user>/`, whose mode follows the process umask (so other-readable under the common default). ([finding](../../docs/research/leak_check.exfil.agents.md))

Each is scoped to one config point (PRINCIPLES §2) and stated no more strongly than its evidence. A third surface — value-specialized `max-autotune` kernel selection — was probed and came back a clean negative *by construction* (the tuner benchmarks on random tensors, so weight values never reach it). ([note](../../docs/research/leak_check.autotune-select.agents.md))

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

Start with the methodology document: [`../../docs/research/leak_check.methodology.siddharth.md`](../../docs/research/leak_check.methodology.siddharth.md)

Reference materials:
- **Empirical results**: [`../../docs/research/leak_check.results.siddharth.md`](../../docs/research/leak_check.results.siddharth.md)
- **Environment setup**: [`../../docs/research/leak_check.environment.siddharth.md`](../../docs/research/leak_check.environment.siddharth.md)
- **Lessons / synthesis**: [`../../docs/research/leak_check.lessons.agents.md`](../../docs/research/leak_check.lessons.agents.md)
- **CSI-NN paper reference**: [`../../docs/priorlit/csi_nn_paper.siddharth.md`](../../docs/priorlit/csi_nn_paper.siddharth.md)
- **Journal**: [`../../docs/research/journal/`](../../docs/research/journal/)

Findings from the confidentiality hunt (each scoped to its config point):
- **Freezing constant-fold** (a compiler-introduced leak): [`../../docs/research/leak_check.freezing.agents.md`](../../docs/research/leak_check.freezing.agents.md) and its taint escalation [`../../docs/research/leak_check.freezing-taint.agents.md`](../../docs/research/leak_check.freezing-taint.agents.md)
- **AOTInductor artifact exfiltration**: [`../../docs/research/leak_check.exfil.agents.md`](../../docs/research/leak_check.exfil.agents.md)
- **max-autotune selection is value-independent** (clean negative): [`../../docs/research/leak_check.autotune-select.agents.md`](../../docs/research/leak_check.autotune-select.agents.md)
- **The count channel's context confound** (a methodology correction): [`../../docs/research/leak_check.count-confound.agents.md`](../../docs/research/leak_check.count-confound.agents.md)

### Core Modules

- **`instruments.py`**: Observation channels (taint tracking, instruction counts, timing)
- **`noninterference.py`**: Differential non-interference criterion. Measures each secret class over several *contexts* and pairs them, because the callgrind count channel is confounded by measurement context (e.g. the secret's filename length) at the ~100s-of-instructions scale — a single run per class manufactures false positives. ([why](../../docs/research/leak_check.count-confound.agents.md))
- **`corpus.py`** / **`corpus_activations.py`**: Test input generation (extreme values for sensitivity)
- **`measured_run.py`**: Orchestrate a measurement across different configurations
- **`attacks/`**: Model-specific attacks for extracting model information through side channels
- **`ctbench/`**: Constant-time benchmarking utilities

### Probes (each prints a verdict and writes a cited `.out`)

- **`probe_freezing.py`** / **`probe_freezing_taint.py`**: the freezing constant-fold leak — codegen-diff 2×2, then an instruction-level taint + functional-dependence escalation.
- **`probe_exfil.py`**: searches the inductor cache / AOTInductor artifacts for the secret weight bytes and reports file mode + directory traversability.
- **`probe_autotune_select.py`**: whether `max-autotune` kernel choice depends on weight values (with the same-class control that catches the earlier normalizer-bug false positive).
- **`probe_softmax.py`**, **`probe_autotune.py`**, **`probe_fastmath.py`**, **`denormal_probe.py`**, **`honest_timing.py`**: codegen-inspection and timing/cycle-count probes (the timing tier catches leaks the deterministic channels are blind to).
- **`sweep_overnight.py`**: runs the whole probe set cheapest-first, serialized, with a streaming heartbeat log and a rolling `SWEEP_REPORT.md`. `--dry-run` prints the plan.

### Principles

See [`PRINCIPLES.md`](PRINCIPLES.md) for the constitution governing this work:

- **Evidence discipline**: Every claim names the script and exact command that produced it
- **Scope verdicts**: Results hold for one config point `(source, compiler, backend, version, flags, target ISA)`
- **Sober tone**: State what was measured and what it means; let evidence carry weight
- **Reproducibility**: Include runnable commands; pin determinism (fixed seed, single-thread BLAS/OMP, warm caches)
- **Code quality**: SOLID design; new attacks/targets should slot into existing interfaces
