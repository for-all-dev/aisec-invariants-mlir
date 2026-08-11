= Measuring: Compiler-Introduced and Compiler-Removed Channels

// OUTLINE ONLY. Source of truth: prototypes/leak_check,
// docs/research/leak_check.{methodology,results,environment}.siddharth.md,
// leak_check.count-confound.agents.md, leak_check.lessons.agents.md.

== Methodology
- Differential eager-vs-Inductor on deterministic channels: instruction
  counts (Ir), branch counts (Bc), instruction-level taint; baited input
  classes probe value-regime branches.
- The 2×2 attribution: whose fault — source or compiler; four-valued verdicts
  (OBLIVIOUS / DISTINGUISHABLE / COMPILER-INTRODUCED / COMPILER-REMOVED).
- Instrument honesty: the Zen5 count-channel confound; verdicts resting on
  small |dIr| without taint corroboration were retired
  (softmax), criterion updated in `noninterference.py`.

== Results
- Activation corpus (CSI-NN mechanism 2):
  - relu: OBLIVIOUS both builds — PyTorch's eager kernel is already a
    vectorized max; library kernels can be constant-time where hand code is
    not.
  - *exp: COMPILER-REMOVED (headline).* Eager libm `expf` branches on
    magnitude (dIr ≈ +35M, taint fires); Inductor lowers to a branchless
    vectorized polynomial — compilation erased the CSI-NN channel.
  - softmax: RETIRED — degenerate probe (uniform rows cancel under
    max-subtraction); shown as a worked example of the retirement discipline.
- Freezing / constant-folding: instruction-level taint proof of the
  weight-fold leak (`probe` branch work, PR #55 lineage).
- Autotune: max-autotune GEMM kernel *selection* as a value-dependent channel.
- Overnight-sweep coverage numbers.
