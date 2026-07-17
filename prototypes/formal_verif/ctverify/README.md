# ctverify — reusable constant-time / leakage-contract verdicts for binaries

The reusable engine behind the formal_verif timing layers **A** and **B**. It
wraps `binsec -checkct` so you can point it at *any* `-m32` binary plus an SSE
script that declares the secret/public globals, and get a structured, JSON-ready
verdict — instead of re-implementing the invocation and stdout-scraping per
corpus. Pure standard library at runtime (binsec is a subprocess), so it installs
light and imports anywhere.

## Install

```sh
uv sync                       # dev tools; the package itself is importable
```

## Python API

```python
from ctverify import run_checkct, LAYER_A, DEFAULT_CT, AccessLayout, cacheline_verdict

# Layer A: run the constant-time check with the variable-latency channels on.
res = run_checkct("bin/a_div_divisor_O0", "a.cfg", features=LAYER_A)
res.verdict          # "insecure"
res.leaks            # [Leak(instruction="0x8049934", kind="divisor")]
res.to_dict()        # JSON-ready dict

# Layer B: compute the cache-line contract verdict from the [ct] result + layout.
ct = run_checkct("bin/b_codebook_small_O0", "b.cfg", features=DEFAULT_CT)
cacheline_verdict(ct.verdict, AccessLayout(elem_size=4, index_count=8))
# ContractResult(ct_verdict="insecure", contract_verdict="secure", distinct_lines=1, ...)
```

`features` is any subset of binsec's channels; two presets are provided:
`DEFAULT_CT = (control-flow, memory-access)` and
`LAYER_A = DEFAULT_CT + (multiplication, dividend, divisor)`.

## CLI

```sh
# Layer A — constant-time check at chosen channels (ct | layerA | comma-list):
uv run ctverify checkct BINARY --cfg a.cfg --features layerA [--json]

# Layer B — cache-line leakage contract; --elem/--count declare the access layout:
uv run ctverify contract BINARY --cfg b.cfg --elem 4 --count 8 [--line 64] [--json]
```

Exit code is non-zero on an insecure verdict, so it drops into shell pipelines
and CI. `--json` emits the full structured result.

Requires binsec on PATH (`eval $(opam env)`); `run_checkct` raises
`BinsecNotFound` otherwise.

## Development

```sh
uv run ruff format --check .   # formatting
uv run ruff check .            # lint
uv run ty check .              # type-check
uv run pytest                  # tests (parser + contract logic; no binsec needed)
```

The tests exercise the output parser (on captured binsec samples) and the
cache-line contract math, so they run without binsec or a `-m32` toolchain. The
corpora in [`../timing_a/`](../timing_a/) and [`../contract_b/`](../contract_b/)
are worked examples that drive this package end-to-end against real binaries.
