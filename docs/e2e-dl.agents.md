# "The life of one token": an end-to-end deep learning story for the SaTML draft

A candidate narrative for the "end-to-end walk of one program" bullet in
`comms/satml-typst/sections/05-case-studies.typ`. Every beat below cites a measured or proved
result that already exists in the repo — the story is a re-narration of existing evidence, not a
new experiment (with one bounded exception, flagged at the end).

## The story

Follow a single autoregressive decode step of a tiny GPT (the nanoGPT slice profiled in
`prototypes/nanoGPT-analysis.claude`) from source to binary, and report the paper's four
coordinates (observer, evidence kind, level, attribution) at each stage. The step decomposes into
exactly the kernel classes the prototypes measured:

- an embedding **gather** (`wte[token_id]`),
- a **matvec** against the weights,
- an **activation** (`exp` inside softmax/GELU),
- a **dynamic-length** loop over the growing KV cache,
- and — if the model is pruned — a **sparse** weight multiply.

One inference step is the union of the five measured kernel classes. That is what makes the story
end-to-end without inventing evidence.

### Stage 1 — source semantics

Two channels are *authored*: the embedding gather's load address depends on the token identity,
and eager libm `expf` branches on magnitude (dIr ≈ +35M, taint fires — `prototypes/leak_check`).
The matvec is oblivious. The four-coordinate vocabulary lets the paper say precisely who is at
fault before any compiler runs.

### Stage 2 — the DL compiler compiles it (Inductor, measure side)

Three verdicts, one per quadrant, all from `prototypes/leak_check`:

- The `exp` channel is **COMPILER-REMOVED** — Inductor's branchless vectorized polynomial erases
  the CSI-NN channel. The headline stays the headline, but as a beat in a narrative instead of an
  isolated table row.
- Freezing constant-folds the weights, and the instruction-level taint proof shows the weight-fold
  leak (**compiler-introduced**, weights asset; PR #55 lineage).
- Max-autotune's GEMM kernel *selection* is value-dependent (**compiler-introduced**, one level up
  from the emitted code itself).

### Stage 3 — the same computation through the MLIR lowering axis (`prototypes/mlir_leak`)

- The gather's address channel survives *every* pipeline and every `-O` level (`idx_gather`:
  `dIr=0`, invisible to counts; only the broadened taint parser sees it).
- The KV-cache dynamic extent is the `dynshape` channel — irreducible because the trip count is
  runtime; optimization narrows it (dIr 73872 → 5117) but cannot remove it, and the secret-sized
  memory footprint survives `-O2` iff the buffer is live (`dynshape_t`).
- If the model is pruned, `--sparsification` *manufactures* an address channel from the sparsity
  pattern that the dense lowering of the same op does not have (`mlir_leak/sparse/`) — the one
  measured case where an *optimizing* pass, not the `-O0` selector, fires the compiler-introduced
  quadrant. This connects pruning — a real DL deployment axis — to the structure asset in the
  threat model.

### Stage 4 — the verify side answers the story (`prototypes/fcvd_ct`)

The kernels in stages 1–3 lower to exactly the shared dialects (affine/scf/memref/arith) that
Polygeist's eight checked steps speak, and `affine.load`/`affine.store` with identity maps — the
matvec and gather's bread and butter — are the cheapest-and-most-used verified translations. The
two-property check is what would have caught stage 3's surprises ahead of time: `mask_select` at
`-O0` (a source-branchless `arith.select` lowered to a `jne`) is a lowering that is congruent but
*not* non-interference-preserving — the precise failure mode "safe = congruent + non-interfering"
was built to reject.

### Ending — what remains, and why the four coordinates matter

After a verified compile, the residual channels are exactly the authored/structural ones:

| residual channel | asset axis | character |
|---|---|---|
| token identity via gather address | activations | one-shot per query |
| sequence length via dynamic shape | structure | irreducible trip count |
| sparsity pattern | structure / weights | leaked by control structure, not values |

The compiler neither adds to them (verified steps) nor is blamed for them (attribution). That is
the paper's thesis paid off in one program: measurement attributes, verification excludes, and the
leftover is a precise statement of what the *model architecture* owes you, not the compiler.

## Why this story and not an attention-head story

Every beat above is already measured or proved. A full attention-head walk would be more glamorous
but mostly unmeasured, and softmax specifically is the retired probe — which still earns a place
in-story as "and here is a probe we refused to trust" (the retirement discipline as a worked
example).

## The one piece of real glue missing

The verify side (fcvd_ct on Polygeist's steps) and the measure side (mlir_leak kernels) currently
touch *different programs*. To close the loop literally: write the story's matvec+gather as the C
source, push it through cgeist's eight steps, and report the per-step two-property verdicts
alongside the mlir_leak measurements. That instantiates the "end-to-end walk of one program"
bullet already in `05-case-studies.typ`. Bounded: one C file, the existing harness, the existing
checked specifications.

## Honest caveat to carry into the draft

The story spans two toolchains — Inductor for stage 2, MLIR/Polygeist for stages 3–4 — so it is
"one computation, two compilations," not one binary. State that plainly rather than blur it; the
2×2 attribution is per-compiler anyway.
