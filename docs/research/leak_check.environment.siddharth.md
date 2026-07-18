# Reference: environment & tooling

Pointers and versions. Changes when the machine or toolchain changes.

## Platform (current — re-provisioned 2026-07; see migration note)
- Python env: repo-relative `prototypes/leak_check/.venv` (uv-managed, `uv sync`);
  Python 3.12.3, uv 0.11.28.
- CPU: **AMD Ryzen 9 9955HX**, 16 cores / 32 threads, **Zen5**, has AVX-512 (`avx512f`).
  Harness still pins to 1 thread for determinism.
- GPU: none usable for compute — only the AMD display iGPU (`01:00.0`, device `13c0`);
  no CUDA/ROCm. All measurement is CPU-side by design.

### Migration note: this is NOT the original 8-core host
The "historical" block below is the *original* machine (8-core, torch 2.12, a standalone
non-uv venv). This is a different box; two consequences surfaced while
re-confirming the harness end to end, both recorded as config-point facts:

- **Valgrind cannot decode Inductor's AVX-512 → SIGILL.** On Zen5, Inductor emits EVEX
  kernels (e.g. `vpternlog`); Valgrind 3.22's VEX decoder rejects them, so the compiled
  callgrind/memcheck legs die. `measured_run.py` reads `LEAKCHECK_SIMDLEN=8` to cap
  Inductor at 256-bit AVX2 the decoder can handle. **A Valgrind upgrade does not lift
  this** — 3.25.1 (latest release) SIGILLs on the identical bytes; mainline Valgrind has
  no EVEX/AVX-512 decoder (nothing in `VEX/priv/guest_amd64_toIR.c`). So `SIMDLEN=8` is a
  *standing* requirement, and it moves the measured **ISA config point** to AVX2 — note it
  in any verdict, since the shipped AVX-512 build is not what is measured here. Measuring
  native AVX-512 would need the unmerged out-of-tree Intel VEX branch.
- **The callgrind count channel is confounded across processes.** The zero-vs-random
  baseline drifts by tens–hundreds of instructions between processes even for identical
  data, so the old "a single run per class is decisive" rule (methodology doc,
  "Observation channels" 2) does not hold at this config point. The root cause and the fix
  are not mine: `noninterference.py` now measures both classes at **matched contexts** with
  floor + stability guards — see `leak_check.count-confound.agents.md` (root-caused to
  path length / ASLR-off deterministic layout, on a 24-core Ryzen AI 9 HX 370) and upstream
  `d0d3232`. The **taint channel is immune** to this and reproduced every documented verdict
  on this box. (The confound is *established* on that other box; here I observed the same
  cross-process drift symptom but did not re-run the full path-length isolation.)
- torch is installed here as the **CPU-only wheel** (`torch==2.13.0+cpu`,
  `torch.cuda.is_available() == False`) as a *local* choice on this GPU-less box; the
  committed `pyproject.toml` keeps the full CUDA stack for CI/contributor parity, so this
  is a local override, not a committed pin.

## Key library versions (current)
- `torch` 2.13.0+cpu (`device = cpu`); `numpy` 2.5.1; `scipy` 1.18.0; `scikit-learn` 1.9.0
- `gcc` 13.3.0, `clang` 18.1.3 (the ctbench flag-sweep compilers)
- `valgrind` 3.22.0 (see the AVX-512 gotcha above)
- AOTInductor: `torch._inductor.aoti_compile_and_package` present.
- Inductor code dump: `TORCH_LOGS=output_code` (env, always available).

---
## (historical) Original 8-core host
- Python venv: a standalone (non-uv) venv, Python 3.12.
- CPU: 8 cores (`nproc` = 8); harness pins to 1 thread for determinism.
- `torch` 2.12.1+cu130 (CPU path used; `device = cpu`); `numpy` 2.5.0; `scipy` (for the
  Mann-Whitney AUC tier). The count channel was bit-exact here — the confound above was
  not observed on this host.

## Instrument availability (the constraint that shaped the design)
| Tool | Status | Role |
|------|--------|------|
| `g++` | present (`/usr/bin/g++`) | build `vgshim.so`; Inductor CPU codegen |
| `objdump` | present | inspect generated `.so` |
| `valgrind` (memcheck/cachegrind/callgrind) | **INSTALLED — 3.22.0** | deterministic count + taint channels |
| `perf` | MISSING | optional hardware-counter cross-check only |

### Valgrind (installed)
`valgrind-3.22.0` installed by the user; headers present at
`/usr/include/valgrind/{valgrind,memcheck,callgrind}.h`. Build + run:

    g++ -shared -fPIC -O0 leak_check/vgshim.c -o leak_check/vgshim.so
    python leak_check/run_all.py   # run_all rebuilds the shim automatically

`perf` is intentionally not required — callgrind gives the same signal
deterministically in userspace without elevated privileges.

### Gotchas discovered while wiring it up
- `vgshim.c` must wrap its API in `extern "C"` — `run_all.py` builds it with
  `g++`, which otherwise mangles the symbols and `ctypes` can't find them.
- callgrind is gated with `--instr-atstart=no` + `CALLGRIND_START/STOP_INSTRUMENTATION`,
  so the counted region is the **`totals:`** line of the callgrind output, NOT
  `summary:` (which tracks *collection*, left off, and reads 0).
- memcheck cost is dominated by importing torch under instrumentation:
  **~8 min per run** at DIM=512. On the original 8-core host callgrind legs were ~70 s;
  on the Zen5 box they are ~15 s. A full corpus sweep is ~50-70 min — longer now that the
  count criterion takes `REPEATS` runs per class per build (it multiplies only the fast
  callgrind legs, not memcheck).
- **Zen5 AVX-512 SIGILL:** compiled legs require `LEAKCHECK_SIMDLEN=8` (AVX2 cap); a
  Valgrind upgrade does not lift it (3.25.1 tested, still SIGILLs). Standing requirement,
  see the migration note above.

## File map
- `leak_check/timing_leak.py` — the original (flawed) demo, kept for continuity.
- `leak_check/honest_timing.py` — the corrected timing-channel harness.
- `leak_check/honest_timing.run.out` — its recorded output (source of `empirical/results.md`).
- `leak_check/vgshim.c` — Valgrind client-request bridge (taint + callgrind gating).
- `leak_check/corpus.py` — models + secret classes + expected verdicts.
- `leak_check/measured_run.py` — one fixed-code-path forward pass under an instrument
  (`LEAKCHECK_SIMDLEN` AVX2 cap; `LEAKCHECK_SINK=none` value-independent sink — see the
  migration note and `results` §recalibration).
- `leak_check/instruments.py` — callgrind counter + memcheck taint runner/parsers.
- `leak_check/noninterference.py` — the differential criterion + verdict. Now measures both
  classes at **matched contexts** with floor + stability guards (was: single run per class);
  rationale in `leak_check.count-confound.agents.md`.
- `leak_check/run_all.py` — driver; builds shim, generates secrets, prints table.
- `leak_check/secrets/{zero,random}.npy` — the two secret-class buffers.
- `leak_check/secrets/_ctx/` — per-run context copies the count criterion makes and removes
  (gitignored).
- `docs/research/leak_check.count-confound.agents.md` — why the count channel needs a floor +
  stability check across contexts (the criterion change above).
- `leak_check/run_all.out` / `.err` — latest deterministic-channel run output.
- `leak_check/denormal_probe.py` — timing probe: subnormal-float leak (blind spot).
- `leak_check/probe_fastmath.py` + `_denorm_worker.py` — Probe 2 (FTZ / fast-math).
- `leak_check/probe_autotune.py` + `_autotune_worker.py` — Probe 1 (max-autotune codegen).
- `leak_check/probe_{fastmath,autotune}.out` — their outputs.
- `leak_check/ctbench/{kernels,harness}.c` — toolchain C testbed (gcc/clang flag sweep).
- `leak_check/ctbench/run_ct.py` — sweep driver + leak matrix; output `run_ct.out`.
- `leak_check/instruments.py` `*_cmd` runners — instrument an arbitrary binary (adds Dw).
