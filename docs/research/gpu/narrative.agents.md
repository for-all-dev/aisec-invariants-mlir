# GPU attack/defense pair: secret-derived constants on the CUDA/Triton path

Plan, not a result. Proposes one GPU experiment that turns the existing
prototypes into a single attack/defense story. Every claim below is labelled
**measured**, **hypothesized**, or **unverified lead** (`prototypes/leak_check/PRINCIPLES.md` §1).
Slides: `narrative_slides/main.typ` (full), `simple_slides/main.typ` (leak_check vs Staging_NI only).

## 0. Why GPU, and why this pair

The asset this project protects is model weights, and weights are deployed on
GPUs. Every result currently in `prototypes/` is on CPU: Valgrind taint
(`mlir_leak`, `leak_check`), PMU counters (`ebpf-tracing`), SMT over MLIR/LLVM
(`fcvd_ct`), bounded model checking over C (`proofs_l2_seabmc`). The two
compiler-introduced findings in `leak_check` are explicitly scoped away from the
GPU path:

- `leak_check.freezing.agents.md` §5: "Not established: that this reproduces on
  any other ... backend (Triton/GPU)".
- `leak_check.exfil.agents.md`: "`cu130` present but CPU path exercised".

The freezing leak is chosen over other GPU candidates because (a) the probe code
exists and is calibrated, (b) Inductor's constant folding runs on the FX graph
before the backend splits into C++ vs Triton, so the port is cheap and the
hypothesis is sharp, and (c) `Staging_NI` already formalizes the leak class —
protected runtime data becoming compile-time data — so the defense half connects
to existing work instead of starting a new line.

Rejected alternatives, briefly:

- **LeftoverLocals on silicon.** Fixture and SeaBMC proof exist
  (`compiler_harness/fixtures/leftoverlocals-scratch`). NVIDIA hardware was not
  affected by CVE-2023-4969; a real reproduction needs an AMD/Apple/Qualcomm
  GPU. Deferred.
- **Secret-dependent control flow in MLIR→NVVM lowering.** Natural `mlir_leak`
  port, but Valgrind does not see device code, so the measurement layer must be
  rebuilt. Deferred.

## 1. The attack

### 1.1 What is already measured (CPU)

**Measured** (`prototypes/leak_check/probe_freezing.py` → `probe_freezing.out`;
torch 2.13.0+cu130, Inductor CPU backend, x86-64):

With `torch._inductor.config.freezing = True`, Inductor constant-folds
weight-derived scalars and emits them as literals in the generated C++:

| surface | folded scalar | non-frozen A vs B | frozen A vs B |
|---|---|---|---|
| `quant_scale` | `w.abs().max()/127` | identical | differs (`0.0078740…` vs `0.7874015…`) |
| `wmax` | `w.max()` | identical | differs (`3.0` vs `100.0`) |
| `wnorm` | `1/w.norm()` | identical | differs (`0.5` vs `0.01`) |

Same-class control holds for these three; `wsum` is inconclusive. Separately,
**measured** (`probe_exfil.py`): AOTInductor writes the raw weight bytes into a
`.wrapper.so` under `/tmp/torchinductor_<user>/` at mode `0o755` under umask 0022.

### 1.2 GPU hypotheses

Config point to pin: torch 2.13.0+cu130 (same wheel as CPU runs), Triton version
bundled with it, one named GPU SKU, driver version, `TORCHINDUCTOR_CACHE_DIR` and
`TRITON_CACHE_DIR` private per compile, `force_disable_caches=True`.

- **H1 (hypothesized).** With `device="cuda"`, the same folds appear as literals
  in the generated Triton kernel source (`output_code`), A≠B, same-class A=A′,
  non-frozen A=B. Rationale: `torch._inductor.constant_folding` operates on the
  FX graph before backend selection.
- **H2 (hypothesized).** The literal survives Triton compilation into PTX and the
  cubin (as an immediate or in a constant bank), and those files land in the
  Triton cache on disk.
- **H3 (hypothesized).** H2's cache files are readable by other local users under
  default umask, i.e. the freezing leak and the exfil leak compose on GPU: a
  weight statistic is written to a shared filesystem location without the
  attacker ever running the model.
- **H4 (hypothesized).** AOTInductor on CUDA persists raw weights like the CPU
  path (`exfil` on GPU).
- **H5 (unverified lead).** MLIR-native analogue: IREE's compile-time
  const-eval of globals derived from parameters (`iree-opt-const-eval`) would
  produce the same class of leak on an MLIR GPU pipeline. Worth one look, since
  it would let `Staging_NI` run on the real compiler IR rather than a model of it.

Each hypothesis is falsifiable by the existing detector
(`probe_autotune.normalize` + `probe_softmax.kernel_body`), extended to read
Triton source, `.ptx` and `.cubin` (via `cuobjdump -sass`).

### 1.3 Observer

Ring per `docs/research/threat-models.agents.md`: an observer who reads compiled
artifacts — a co-tenant on the build host, anyone the compiled package is shipped
to, or anyone with read access to a shared cache volume. No timing, no execution
of the victim model.

## 2. The defense

The defense is a layered stack over one property: **the generated artifact must
not depend on protected weights**, beyond explicitly declassified values. Each
layer is an existing prototype extended, not a new one.

### 2.1 Static: freezing is a runtime→staging conversion (`Staging_NI`)

`Staging_NI` today seeds runtime taint from `{stagingni.protected}` arguments
and converts it to staging taint at `tensor.dim`; staging-tainted values
reaching loop bounds are violations. Freezing is a second conversion rule of the
same kind: it moves a protected value from runtime to compile time wholesale.

Proposed rule: an op whose operands are all compile-time constants after
freezing (i.e. is foldable) and any of whose operands is runtime-tainted makes
its result staging-tainted, and any staging-tainted value materialized as a
constant (`arith.constant`, a constant global, a literal in a kernel) is a
violation unless tagged `{aisec.declassify}` — reusing `initial`'s
declassification attribute.

Two places to apply it, both **hypothesized** to be sufficient:

- **FX level (the actual Inductor path).** Run the taint over the frozen FX
  graph with parameters marked protected; flag every node constant folding would
  evaluate whose inputs are protected-derived. Small Python pass beside
  `probe_freezing.py`.
- **MLIR level (Staging_NI proper).** On torch-mlir/IREE output where frozen
  params become constant globals; the new rule is an addition to Phase 2.

### 2.2 Enforcement: selective freezing

The repair is to freeze everything except protected-derived subgraphs: those
stay runtime computations on runtime buffers, so codegen is identical across
secret classes. Whether Inductor exposes a supported hook to exclude nodes from
constant folding at 2.13 is an **unverified lead**; if not, the fallback repair
is a pre-freezing FX rewrite that hides the protected parameters behind an
opaque op. Measure the cost: latency of frozen vs selectively-frozen vs
non-frozen on the same GPU.

### 2.3 Proof: self-composition with the artifact as the observation

`fcvd_ct` and `proofs_l2_seabmc` already prove bad/fixed pairs where the
observation is control flow, addresses, or released values. Here the observation
is the generated code itself. The 2-safety statement:

    ∀ w₁ w₂. public(w₁) = public(w₂) ⇒ codegen(P, w₁) = codegen(P, w₂)

Modelled as a SeaBMC job (`add_l2_job`) where the "compiler" is a C model of the
fold: bad = emit `f(w)` as a literal into the observation buffer; fixed = emit
the code template and compute `f(w)` at run time. Expect bad **sat**, fixed
**unsat**, same calibration rule as the seven existing jobs. This is a proof
about the model of the fold, not about Inductor; state it that way.

### 2.4 Detection after the fact: artifact differential

The existing codegen-diff detector, generalized to every artifact a GPU compile
writes (Triton `.py`, `.ttir`, `.ttgir`, `.llir`, `.ptx`, `.cubin`, AOTI `.so`),
plus a permission audit of the cache directories. Runs as a `compiler_harness`
regression fixture (`snapshot.yaml` + bad/fixed).

### 2.5 What the silicon layer does not cover

`ebpf-tracing` measures CPU PMU timing; this leak is not a timing leak, so it is
out of scope for the pair. GPU timing via CUPTI/Nsight counters is a stretch goal
and not part of this plan.

## 3. How the prototypes map onto the story

| Role | Prototype | Work in this plan |
|---|---|---|
| Theory of the leak class | `Staging_NI`, `initial` | new conversion rule; reuse `aisec.declassify` |
| Attack, CPU (done) | `leak_check` | none |
| Attack, GPU | `leak_check` | `device="cuda"` port; artifact scanner |
| Enforcement | new, beside `leak_check` | selective-freezing FX pass + overhead numbers |
| Proof | `proofs_l2_seabmc` (and/or `fcvd_ct`) | one bad/fixed job, artifact-as-observation |
| Regression | `compiler_harness` | one fixture family |
| Static per-pass checks | `fcvd_ct` | unchanged; cited as the pass-level analogue |
| Silicon timing | `ebpf-tracing`, `mlir_leak` | unchanged; out of scope for this pair |

## 4. Work items

Ordered; E1–E3 are the minimum publishable unit.

- **E1. Pin a GPU config point.** One cloud GPU, one SKU, record
  `nvidia-smi`, driver, CUDA, torch, Triton versions in
  `leak_check.environment.*`. Re-run `probe_freezing.py` unchanged on CPU on that
  box first to confirm the CPU finding reproduces there.
- **E2. Port `probe_freezing.py` to `device="cuda"`** (H1). Same four surfaces,
  same three guards. Output `probe_freezing_cuda.out`.
- **E3. Artifact scanner** (H2, H3). Walk inductor + Triton cache dirs, diff A vs
  B per artifact type, recover literals from PTX/SASS, record file modes.
- **E4. AOTI on CUDA** (H4). Port `probe_exfil.py`.
- **E5. Static detector.** FX-level pass first (it runs on the real path),
  Staging_NI rule second. Calibrate: fires on the three measured surfaces, silent
  on non-frozen compiles and on a declassified fold.
- **E6. Selective freezing + overhead.** Repair, re-run E2/E3 to show A=B, report
  latency.
- **E7. SeaBMC job** for the artifact-as-observation property.
- **E8. `compiler_harness` fixture** wrapping E2/E6 as bad/fixed.
- **E9 (optional). IREE const-eval lead** (H5).

Ownership is for the fellows to decide; E2–E4 are a natural unit for whoever
owns `leak_check`, E5 for `Staging_NI`, E7 for `proofs_l2_seabmc`.

## 5. What would falsify the plan

- H1 false (Triton path does not fold, or folds into a runtime buffer instead of
  a literal): still reportable, scoped to the config point; the story shifts to
  buffer-valued folding (freezing note §4), which needs a different detector.
- Literal appears in Triton source but not on disk (H3 false under private cache
  dirs at default settings): the leak is to whoever receives the compiled
  package, not to local co-tenants. Narrower observer, still a finding.
- Selective freezing removes the performance benefit of freezing entirely:
  report it; the defense is then "don't freeze protected models", which is a
  policy, not a pass.

## 6. Timing relative to SaTML

The SaTML submission deadline was 2026-09-29 (`comms/satml-typst/main.typ`).
This work fits a rebuttal, camera-ready, or follow-up venue as a "realistic
deployment target" section: §3 of the paper (attack) gains a GPU column, §4
(defense) gains a non-pass-level property (artifact non-interference).
