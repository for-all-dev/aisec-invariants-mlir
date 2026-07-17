# leak_check: lessons, slide points, and related work

Synthesis note. Distills what the `leak_check` experiments (torch/Inductor differential
non-interference, the `ctbench` gcc/clang toolchain sweep, the timing/denormal probes, and the
Zen5 re-run) taught, plus which published results the work reproduces vs. extends. AI-drafted;
owner reviews. Tone/discipline per `../../prototypes/leak_check/PRINCIPLES.md` — claims are
**[measured]** here unless marked otherwise. Companion detail: `leak_check.results.siddharth.md`,
`leak_check.methodology.siddharth.md`.

## Top three (for a slide / an outside audience)

1. **The compiler was the protector, not the threat.** The worry going in: optimizing a program
   might secretly create a way to leak private data (like proprietary model weights). We probed
   this 5+ ways — the optimizer almost always *removed* those leaks (rewriting risky "if" logic
   into safe branch-free math) and **never once created one** (for this toolchain). The real
   culprits were leaks already in the source, or the physical hardware — not the compiler.
2. **"Is this code safe?" is unanswerable without naming the exact toolchain.** The *identical*
   source came out secure with one compiler and leaky with another **at the same settings**
   (GCC vs. Clang disagreed). Security is a property of the specific compiler + version + flags +
   chip you ship, not of the source. Test the exact build you deploy.
3. **No single test catches every leak — you need several lenses.** The biggest real leak (certain
   weight values ran **~25× slower**, exposing them via timing alone) was **invisible** to the
   checks that inspect the program's instructions — they reported "perfectly safe." Only a
   stopwatch-style test caught it.

## Full learnings

### Headline findings
- **Compilers remove side channels more than they add them.** Across the corpus, `torch.compile`/
  Inductor introduced **zero** leaks and *erased* several. Every leak observed was authored
  (already in eager) or hardware (denormals).
- **The "compiler-introduced" quadrant never fired for Inductor** across 5+ adversarial probes.
  (It *does* fire elsewhere — Clang `-O0` `select`→branch; `sparse_tensor --sparsification` — just
  not for Inductor.)
- **Inductor erased a real side channel (`where_select`):** eager runs a per-element conditional
  on a secret mask (taint fires); compiled, it lowers to a branchless vectorized blend →
  taint-clean, `dIr=0`.
- **Inductor erased the exact channel CSI-NN exploits (`exp`):** eager scalar `libm expf` branches
  on magnitude (35M-instruction difference); compiled, a branchless vectorized polynomial makes it
  instruction-identical across inputs.

### Leakage is a config-point property, not "compilation"
- **Same source flips across `-O` levels:** `relu` (branch on sign) leaks at `-O0`, oblivious once
  vectorized to a branchless `max` (gcc `-O3`, clang `-O2`).
- **GCC and Clang disagree at identical flags:** `select_branch` at `-O3 -march=native` — gcc keeps
  a secret-dependent branch, clang lowers to a blend. Same source + flags → opposite security.
- A "no leak" verdict holds for one `(source, compiler, backend, version, flags, ISA, libs)` tuple
  only; it does not generalize.

### The channels are complementary, not a hierarchy
- **The 25× denormal (subnormal-float) timing leak** (AUC = 1.000) is *byte-identical* in the
  instruction stream — `dIr=0`, taint-clean. Deterministic channels call it "oblivious" and are
  wrong; timing is the only instrument that sees it.
- **The denormal leak is hardware, not the compiler** — present *identically* in eager and compiled
  (neither sets flush-to-zero), symmetric across builds.
- A clean digital result bounds only *digital* obliviousness; it says nothing about *analog*
  (timing) leakage. Run the timing tier even when counts/taint are clean.

### Authored vs. compiler-introduced
- **A leak present before compilation cannot be the compiler's fault:** `torch.cond` skip leaks in
  *both* eager (AUC 0.80) and compiled (0.998) → authored.
- **"Delta got bigger after compiling" ≠ a new channel — it's denoising:** Inductor cut `torch.cond`
  overhead ~13× (94 ms → 7 ms), which stripped noise and made the *authored* channel easier to see
  (AUC 0.90 → 0.999).
- **Dynamo refuses the naive premise outright:** `torch.compile(fullgraph=True)` rejects a plain
  `if weight==0` on tensor values ("Data-dependent branching Unsupported").

### Methodology lessons (the ones that bit)
- **Decide timing on effect size, not p-value:** at large N, Mann-Whitney `p = 1.3e-3`
  ("significant") while AUC ≈ 0.5 (negligible). Use AUC.
- **Look at the raw artifact before trusting a summary statistic:** the `max-autotune`
  "compiler-introduced leak" was a false positive — the code-diff normalizer failed to strip
  `TORCH_LOGS` timestamp/PID prefixes, so identical code looked different.
- **Never read a secret-derived value inside the measured region:** the counting sink
  `float(out[0])` injected ~194 instructions of *harness* data-dependence on the Zen5 re-run; fixed
  with a value-independent sink.
- **The callgrind count channel is confounded across processes, and the confound is not what
  it first looks like:** on the Zen5 box the zero-vs-random baseline drifts by hundreds–
  thousands of instructions, so a single-run `!= 0` test fires on noise. The first reading
  (measurement *order* / warmup transient, "fix" by interleaving) treated a symptom; the
  root cause is deeper — with ASLR disabled, layout is a deterministic function of argv/env,
  and the two classes load from **different-length file paths** (`zero.npy` vs `random.npy`),
  so the path length itself moves the count (~495 instructions for md5-identical data). The
  robust criterion measures both classes at **matched contexts** (floor + cross-context
  stability), not interleaved fixed paths — see `leak_check.count-confound.agents.md` and
  `noninterference.py` (upstream `d0d3232`). Taint is immune to all of it and reproduced
  every verdict.
- **Calibrate every run:** positive control (authored branch) must fire; negative control
  (branchless) must stay silent.

### The one genuinely new positive (Zen5 re-run)
- **Same source, new toolchain, different obliviousness:** torch 2.13 / oneDNN has a small
  all-zeros special-value path in the "branchless" matmul (eager +109, compiled −1801 instructions;
  taint-clean; `random ≡ random2` so it is zero-specific) — **absent** on the old box. Authored
  (library special-casing), not compiler-introduced — a live demonstration that obliviousness is
  per-config.

## Related work: what we reproduce vs. extend

| Published result | What we did | Strength |
|---|---|---|
| **Simon, Chisnall & Anderson, "What you get is what you C" (EuroS&P 2018)**; Kaufmann et al. (2016); Reparaz "Compilers and constant-time code"; ToB `__builtin_ct_select`; LLVM CT RFC | `mask_select` (`select`→branch @ `-O0`) and ctbench `select_branch` (gcc keeps branch, clang blends); `formal_verif` shows the `(m&a)\|(~m&b)` idiom broken by clang `-O2` | **Reproduced the finding** |
| **Andrysco et al., "On Subnormal Floating Point and Abnormal Timing" (IEEE S&P 2015)** | denormal probe: subnormal weights → ~25× slowdown, timing AUC = 1.000, invisible to instruction-level checks | **Reproduced the finding** |
| **Batina et al., "CSI NN" (USENIX Security 2019)** | activation corpus reproduced the mechanism-2 premise (scalar `expf` value-dependent timing), then showed Inductor *erases* it | **Reproduced the mechanism** (+ our extension) |
| **Yan et al., "Cache Telepathy" (USENIX 2020); Hu et al., "DeepSniffer" (ASPLOS 2020)** | `idx_gather` / sparse `out[crd[i]]` / `formal_verif` `mm_codebook` — secret-dependent gather address reveals model info | **Reproduced the leak class** (not the full extraction attack) |
| **ctgrind (Langley, 2010)** | our taint channel *is* ctgrind (mark secret bytes undefined; memcheck flags secret-dependent branch/address) applied to ML kernels | **Reused the technique** |
| **dudect (Reparaz, Balasch, Verbauwhede, DATE 2017) / TVLA** | the statistical timing tier (Mann-Whitney AUC variant) | **Reused the technique** |

**Novel contributions on top:** the differential *per-config-point* framing; the empirical finding
that Inductor tends to *remove* these channels rather than add them; the MLIR-lowering sweep
(`prototypes/mlir_leak/`) including the `sparse_tensor --sparsification` measured leak — an
*optimizing* pass that does introduce an address channel.
