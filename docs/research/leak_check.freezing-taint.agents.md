# Escalating the freezing weight-fold leak: instruction-level taint and a
# measured secret -> literal map

Companion to `leak_check.freezing.agents.md`, which established at the
codegen-diff level that `torch._inductor.config.freezing = True` folds the
quantization scale `max|w|/127` into a `static_cast<float>` literal in the
generated C++. This note escalates that finding from "the two frozen kernels
differ by a literal" to (a) a **measured, exact secret -> literal map** and
(b) an **instruction-level taint signal** showing the tainted value being
serialized into the generated code, isolated to freezing.

Code: `prototypes/leak_check/probe_freezing_taint.py`, `_freezing_taint_worker.py`,
`tests/test_freezing_taint.py` (reuses `corpus_freezing.py`, `probe_freezing.py`,
the `vgshim.c` taint primitives).
Raw evidence: `prototypes/leak_check/probe_freezing_taint.out`.

    cd prototypes/leak_check && uv run python probe_freezing_taint.py   # -> .out

## Config point (PRINCIPLES §2)

**torch 2.13.0+cu130, Inductor CPU backend, Python 3.14, x86-64, Valgrind 3.25.1,
OMP/MKL pinned to 1 thread, `PYTHONHASHSEED=0`.** For the compile-time-taint arm:
`TORCHINDUCTOR_COMPILE_THREADS=1` (compile in-process so the fold and the log share
one process), `force_disable_caches=True`, a private `TORCHINDUCTOR_CACHE_DIR` per
compile, memcheck `--track-origins=yes --num-callers=40 --trace-children=no`.
Nothing here generalizes to other torch versions, backends, or ISAs. The finding is
specifically about the `freezing` constant-fold pass.

## Summary

The critical design constraint (and the reason a naive taint reads clean): **the
fold happens at COMPILE time.** In the frozen model the executed kernel reads the
folded *literal*, not the weight buffer, so the classic runtime taint — mark the
weights UNDEFINED, run the forward under memcheck — sees nothing; the secret was
already baked into the code during compilation. So the taint is applied to the
**compile step**: mark the weight bytes UNDEFINED, then run `torch.compile(...,
freezing=True)` under memcheck.

Two proof paths, reported independently:

| path | what it shows | verdict at this config point |
|---|---|---|
| **[2] functional dependence** | perturb one weight element to `v` (the new max), recompile frozen, recover the emitted literal | **PROVEN**: literal `== v/127` exactly (float32) across the sweep; slope `d(literal)/d(v) = 1/127` |
| **[1] compile-time taint (memcheck)** | mark weights UNDEFINED, compile frozen under `--track-origins`; look for a report at the literal-emit site | **INSTRUCTION-LEVEL SIGNAL, isolated to freezing** — but the origin is *not* traced to the weight buffer |

The headline is deliberately split: the functional-dependence path is the clean,
exact escalation (a measured map, not a "they differ"); the taint path lands on a
**partial** result that is itself the interesting methodological point — memcheck
fires at exactly the right instruction, yet `--track-origins` cannot name the
weight buffer as the source.

## 1. Functional dependence: the emitted literal is an exact function of the secret (measured)

`probe_freezing_taint.functional_dependence` fixes a base weight with all
`|w_ij| <= 0.9`, then sets a single element `w[0,0] = v` so that `max|w| = v`
exactly, recompiles **frozen**, and recovers the `static_cast<float>` literal from
the generated kernel body (`probe_freezing.recover_literal`). The recovered literal
equals `v/127` to full float32 precision at every point in the sweep, and the map
`v -> literal` is exactly affine with slope `1/127`:

| `v` (= `max|w|`) | expected `v/127` | recovered literal | match |
|---|---|---|---|
| 1 | 0.0078740157187 | 0.0078740157187 | yes |
| 1.00097656 | 0.0078817056492 | 0.0078817056492 | yes |
| 1.5 | 0.011811023578 | 0.011811023578 | yes |
| 2 | 0.0157480314374 | 0.0157480314374 | yes |
| 5 | 0.0393700785935 | 0.0393700785935 | yes |
| 42 | 0.330708652735 | 0.330708652735 | yes |
| 100 | 0.787401556969 | 0.787401556969 | yes |

Fitted slope `d(literal)/d(v) = 0.007874015562` vs `1/127 = 0.007874015748`
(agreement to float32 rounding of the fold). Every recovered literal equals `v/127`
to full float32 precision (`abs err = 0`).

This is stronger than the codegen-diff finding. It is not "class A and class B
differ"; it is a **calibrated channel**: perturbing one secret weight element by
`dv` moves the constant baked into the generated C++ by exactly `dv/127`. An
attacker reading the generated code recovers `max|w|` of the compiled weights
exactly (and, for symmetric quantization, the quantization scale is `max|w|`
itself). The map is deterministic and needs no valgrind — it is the data-level
proof of the secret -> literal causal flow.

## 2. Compile-time taint: memcheck fires at the literal emission, isolated to freezing (measured)

`_freezing_taint_worker.py` marks the weight bytes UNDEFINED (`vg_make_undefined`,
bracketed by `vg_marker` taint-region markers) and then triggers a frozen compile,
all under memcheck. The negative control is the identical worker with `freezing`
off. Parsed strictly inside the taint region (`probe_freezing_taint.out`):

|  | in-region reports | at the literal-**emit** site (float formatter) | origin = weight buffer (client request) |
|---|---|---|---|
| **frozen** | 1000 | **184** | 0 |
| **non-frozen** (control) | 4 | **0** | 0 |

Two things are established and one is not.

**Established — the fold reaches the emitted code, at the instruction level.** In
the frozen arm, 184 in-region "conditional jump / use of uninitialised value"
reports fire inside Python's float-formatting routine — `format_float_internal` ->
`_PyFloat_FormatAdvancedWriter` -> `float___format__` — which is the code that
writes the numeric literal into the generated C++ source string. A "depends on
uninitialised value" there means the number being serialized into the generated
code is UNDEFINED, i.e. secret-derived. This is the fold's output flowing into the
kernel source, caught at the formatting instruction.

**Established — freezing is the cause.** The non-frozen compile of the same source
produces **zero** emit-site reports (its 4 in-region reports are torch's own
uninitialised-stack hygiene noise: `at::detail::empty_generic`, a GC
`mark_stacks`, and an `at::native::to`, all with stack/heap origins, none in the
formatting path). No literal is emitted because the weight stays a runtime input,
so nothing secret-derived is ever formatted at compile time. Flipping only the
`freezing` flag turns 0 emit-site taint reports into 184.

**Not established — the byte-exact origin.** `--track-origins` does **not** trace
any of the 184 reports back to the weight buffer: the client-request origin count
is 0. The origin memcheck reports instead points one hop upstream of the formatter,
to a `c10::Scalar` created by the reduction that extracts the folded scalar from
the tensor:

    Uninitialised value was created by a stack allocation
       at ... c10::Scalar ... _local_scalar_dense ... (libtorch_cpu.so)

That is exactly the `aten` op that materializes `max|w|/127` from the folded
constant tensor into a scalar for formatting — corroborating that the formatted
value came from a tensor reduction over the weight — but the origin tag stops
there. `--track-origins` keeps the *most recent* creation point of an
uninitialised value; the tensor -> scalar reduction writes the result into a fresh
stack `c10::Scalar`, whose allocation origin overwrites the client-request tag on
the weight bytes. So the chain "weight buffer -> ... -> literal" is observed at its
downstream end (the formatting) but not attributed at its upstream end (the weight).

The consequence for the strongest possible claim: memcheck at this config point can
show *that* freezing serializes an undefined, secret-derived value into the
generated code (an instruction-level, freezing-isolated signal), but it **cannot,
via origin tracking, name the weight buffer as the source**. The byte-exact
"origin = weight buffer" proof the escalation aimed for is not reached through the
taint channel; the functional-dependence map (§1) supplies the secret -> literal
link that the origin tag drops.

## 3. Why the taint channel is only partially informative here (hypothesized)

The taint channel is a **runtime** channel: it observes loads, stores, branches,
and syscall arguments as instructions execute. The constant fold *does* execute (as
`aten` kernels, in-process, at compile time — the run shows in-region reports in
`abs_stub` and `copy_kernel`, the fold's `w.abs()` and the weight clone), so the
channel is not blind to the fold the way it would be to a purely static analysis.
What it loses is **attribution**, for two structural reasons (both hypothesized,
not separately measured here):

1. **Branchless SIMD arithmetic carries no report.** `abs`, the `max`-reduction
   (AVX `max_ps`, branchless), and the `/127` are pure data transforms; memcheck
   only *reports* when an undefined value reaches a branch, an address, or a
   syscall. So the tainted value flows silently through the arithmetic and only
   surfaces a report at the first branch on its bits — inside the float formatter.
2. **Origin is severed at the tensor -> scalar boundary.** The reduction result is
   written into a freshly allocated `c10::Scalar`; `--track-origins` records that
   allocation as the origin, dropping the client-request tag that marked the weight
   bytes.

The methodological takeaway, consistent with the corpus's other channel results
(`leak_check.count-confound.agents.md`): the taint channel confirms an undefined
value is being written into the generated code and pins the *cause* (freezing) via
the control, but it does not, by itself, prove the *source* is the weight. For a
compile-time fold, the data-level functional-dependence map is the load-bearing
proof; the taint channel corroborates the mechanism (fold output -> emitted code)
at the instruction level.

## 4. Claim labels (PRINCIPLES §1)

- **Measured:** the recovered frozen literal equals `v/127` to float32 precision as
  a single weight element `v` is swept (§1), with fitted slope `1/127`; under
  freezing, 184 in-region memcheck reports fire at the Python float-formatting site
  and 0 in the non-frozen control; the frozen emit-site reports' origin is a
  `c10::Scalar` from `_local_scalar_dense` (the fold's reduction), not the weight
  buffer; 0 client-request (weight-buffer) origins in either arm; the taint-region
  markers bracket both compiles (2 markers each).
- **Measured (negative):** `--track-origins` does not attribute any emit-site report
  to the weight buffer — the strongest "origin = weight buffer" form of the taint
  proof is not achieved at this config point.
- **Hypothesized:** that the attribution loss is due to (1) branchless SIMD
  arithmetic emitting no report and (2) origin severance at the tensor -> scalar
  reduction. Neither micro-mechanism was isolated with a dedicated probe.
- **Not established:** that a different valgrind configuration (e.g. a hand-written
  scalar fold that branches on the tainted bytes, or expression-level DFSan
  instrumentation of the compiler) could recover the weight-buffer origin; that any
  of this reproduces on another torch version, backend, or ISA.

## 5. One sentence for a security reviewer

With `torch._inductor.config.freezing = True`, the quantization scale `max|w|/127`
is constant-folded into a numeric literal in the generated CPU kernel that is an
exact, measured function of the secret weights (perturbing one weight element by
`dv` moves the literal by `dv/127`); compiling the identical source under memcheck
shows an undefined, secret-derived value being serialized into that code at the
float-formatting instruction only when freezing is on — an instruction-level
confirmation that the fold reaches the emitted code, though the runtime taint
channel cannot trace the literal's origin byte-for-byte back to the weight buffer.
