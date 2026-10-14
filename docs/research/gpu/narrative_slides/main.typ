// GPU attack/defense pair — team deck.
// Source of truth: docs/research/gpu/narrative.agents.md
// Build: typst compile docs/research/gpu/narrative_slides/main.typ

#import "@preview/typslides:1.3.2": *
#import "@preview/cetz:0.4.2"

#show: typslides.with(
  ratio: "16-9",
  theme: "dusky",
  font: "DejaVu Sans",
  font-size: 19pt,
  link-style: "color",
  show-progress: true,
)

// ---------------------------------------------------------------- helpers

#let c-secret = rgb("#c0392b")
#let c-public = rgb("#2e6f9e")
#let c-ok = rgb("#2e8b57")
#let c-muted = luma(225)
#let c-gpu = rgb("#76b900")

#let measured = box(fill: c-ok.lighten(75%), inset: (x: 4pt, y: 2pt), radius: 3pt)[#text(size: 0.7em)[measured]]
#let hyp = box(fill: rgb("#f0c040").lighten(55%), inset: (x: 4pt, y: 2pt), radius: 3pt)[#text(size: 0.7em)[hypothesized]]
#let lead = box(fill: c-muted, inset: (x: 4pt, y: 2pt), radius: 3pt)[#text(size: 0.7em)[unverified lead]]

// A labelled rounded box centred at `pos`.
#let node(pos, name, body, w: 2.6, h: 1, fill: rgb("#ffffff"), stroke: 0.8pt + rgb("#000000")) = {
  import cetz.draw: rect, content, line
  rect(
    (pos.at(0) - w / 2, pos.at(1) - h / 2),
    (rel: (w, h)),
    name: name,
    radius: 0.12,
    fill: fill,
    stroke: stroke,
  )
  content(name, align(center, text(size: 13pt, body)))
}

#let arrow(a, b, label: none, stroke: 0.8pt + rgb("#000000"), anchor: "north") = {
  import cetz.draw: rect, content, line
  line(a, b, mark: (end: ">", fill: rgb("#000000")), stroke: stroke, name: "ln")
  if label != none {
    content("ln.mid", text(size: 11pt, label), anchor: "south", padding: 0.12)
  }
}

// ---------------------------------------------------------------- slides

#front-slide(
  title: "Secret-derived constants on the GPU path",
  subtitle: [One attack/defense pair that ties the prototypes together],
  authors: "Confidential compiling stream — SPS Fellowship",
  info: [Plan, not a result · `docs/research/gpu/narrative.agents.md`],
)

#table-of-contents()

// ================================================================
#title-slide[Why GPU]

#slide(title: "The asset is on a GPU; our evidence is on a CPU")[
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    let rows = (
      ("Silicon timing", "ebpf-tracing", "CUPTI / Nsight (stretch)"),
      ("Dynamic taint", "mlir_leak, leak_check", "—"),
      ("Codegen / artifact diff", "leak_check (freezing, exfil)", "this plan"),
      ("Per-pass SMT", "fcvd_ct", "unchanged"),
      ("2-safety BMC", "proofs_l2_seabmc", "+1 job"),
      ("Static IFC", "Staging_NI, initial", "+1 rule"),
    )
    content((0, 0.9), text(weight: "bold", size: 13pt)[layer])
    content((6, 0.9), text(weight: "bold", size: 13pt)[CPU (today)])
    content((12, 0.9), text(weight: "bold", size: 13pt, fill: c-gpu.darken(30%))[GPU])
    for (i, r) in rows.enumerate() {
      let y = -i * 1.05
      node((0, y), "l" + str(i), r.at(0), w: 4.6, h: 0.85, fill: c-muted)
      node((6, y), "c" + str(i), r.at(1), w: 5.6, h: 0.85, fill: c-public.lighten(80%))
      let gf = if r.at(2) == "—" { rgb("#ffffff") } else { c-gpu.lighten(75%) }
      node((12, y), "g" + str(i), r.at(2), w: 5, h: 0.85, fill: gf)
    }
  }))
  #v(0.3em)
  Both compiler-introduced findings in `leak_check` are explicitly scoped *away*
  from Triton/GPU. The pair below fills the codegen row on GPU and pulls the
  static, proof and regression rows along with it.
]

#slide(title: "Why this pair and not another")[
  #cols(columns: (1fr, 1fr), gutter: 1.5em)[
    #framed(title: "Chosen: freezing on CUDA/Triton")[
      - Probe exists and is calibrated (3 guards)
      - Constant folding runs on the FX graph *before* the C++/Triton split → sharp hypothesis
      - `Staging_NI` already names the leak class
    ]
  ][
    #framed(title: "Deferred")[
      - *LeftoverLocals on silicon*: NVIDIA was not affected; needs AMD/Apple
      - *MLIR→NVVM control-flow leaks*: Valgrind can't see device code; rebuild the instrument
    ]
  ]
]

// ================================================================
#title-slide[The attack]

#slide(title: [Freezing turns a weight into code (CPU)])[
  #measured
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    // non-frozen lane
    content((-0.4, 2.5), text(size: 12pt, weight: "bold")[non-frozen], anchor: "west")
    node((2, 1.6), "w0", [$w$ (runtime buffer)], w: 3.4, h: 0.8, fill: c-secret.lighten(80%))
    node((7, 1.6), "k0", [kernel computes \ `max|w|/127` at run time], w: 4.6, h: 1.1)
    node((12.5, 1.6), "o0", [codegen A = B], w: 3.4, h: 0.8, fill: c-ok.lighten(75%))
    arrow("w0.east", "k0.west")
    arrow("k0.east", "o0.west")
    // frozen lane
    content((-0.4, 0.1), text(size: 12pt, weight: "bold")[frozen `freezing=True`], anchor: "west")
    node((2, -0.8), "w1", [$w$ (constant)], w: 3.4, h: 0.8, fill: c-secret.lighten(80%))
    node((7, -0.8), "k1", [constant folding \ evaluates `max|w|/127`], w: 4.6, h: 1.1)
    node((12.5, -0.8), "o1", [codegen A ≠ B], w: 3.4, h: 0.8, fill: c-secret.lighten(70%))
    arrow("w1.east", "k1.west")
    arrow("k1.east", "o1.west")
  }))
  #v(0.2em)
  #grayed[
    ```diff
    -  auto tmp1 = static_cast<float>(0.007874015718698502); // A
    +  auto tmp1 = static_cast<float>(0.787401556968689);    // B
    ```
  ]
  #text(size: 14pt)[Fires on `quant_scale`, `wmax`, `wnorm`; `wsum` inconclusive. torch 2.13.0+cu130, Inductor CPU, x86-64. `probe_freezing.py`]
]

#slide(title: [Where the literal could go on GPU])[
  #hyp
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    let ys = 0
    node((0, 0), "fx", [FX graph \ (frozen)], w: 2.6, h: 1.1, fill: c-muted)
    node((3.6, 0), "cf", [constant \ folding], w: 2.4, h: 1.1, fill: c-secret.lighten(80%))
    node((7.2, 0), "tr", [Triton `.py` \ *H1*], w: 2.6, h: 1.1, fill: c-gpu.lighten(70%))
    node((10.6, 0), "ptx", [`.ttir` → `.ptx` \ *H2*], w: 2.6, h: 1.1, fill: c-gpu.lighten(70%))
    node((14, 0), "cu", [`.cubin` \ *H2*], w: 2.2, h: 1.1, fill: c-gpu.lighten(70%))
    arrow("fx.east", "cf.west")
    arrow("cf.east", "tr.west", label: [literal])
    arrow("tr.east", "ptx.west")
    arrow("ptx.east", "cu.west")
    // disk
    node((10.6, -2.6), "disk", [Inductor + Triton caches on disk \ mode under default umask? *H3*], w: 8.6, h: 1.1, fill: c-secret.lighten(85%), stroke: (dash: "dashed", paint: c-secret))
    line("tr.south", (7.2, -2.05), mark: (end: ">"), stroke: (dash: "dotted"))
    line("ptx.south", (10.6, -2.05), mark: (end: ">"), stroke: (dash: "dotted"))
    line("cu.south", (14, -2.05), mark: (end: ">"), stroke: (dash: "dotted"))
    // aoti
    node((2, -2.6), "aoti", [AOTI CUDA `.so` \ raw weights? *H4*], w: 4, h: 1.1, fill: c-secret.lighten(85%))
  }))
  #text(size: 15pt)[
    *H3* is the composition: the freezing leak *and* the exfil leak in one artifact —
    a weight statistic on a shared filesystem, attacker never runs the model.
    *H5* #lead: IREE `const-eval` is the MLIR-native analogue.
  ]
]

#slide(title: "Who observes")[
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    node((0, 0), "own", [model owner \ compiles with `freezing=True`], w: 4.6, h: 1.2, fill: c-secret.lighten(80%))
    node((6.5, 0), "art", [compiled artifact \ (cache dir / package)], w: 4.4, h: 1.2, fill: c-muted)
    arrow("own.east", "art.west", label: [writes])
    node((13, 1.4), "a1", [co-tenant on build host], w: 4.4, h: 0.8)
    node((13, 0), "a2", [recipient of the package], w: 4.4, h: 0.8)
    node((13, -1.4), "a3", [reader of shared cache volume], w: 5.2, h: 0.8)
    for a in ("a1", "a2", "a3") {
      line(a + ".west", "art.east", mark: (end: ">"), stroke: c-secret + 0.9pt)
    }
  }))
  #v(0.4em)
  - No timing, no execution of the victim model, no physical access.
  - Ring from `threat-models.agents.md`: artifact reader.
  - Property violated: *artifact non-interference* — codegen must not depend on protected weights.
]

// ================================================================
#title-slide[The defense]

#slide(title: "One property, four layers")[
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    node((7, 2.2), "prop", [$forall w_1, w_2.$ #h(0.3em) $"pub"(w_1) = "pub"(w_2) => "codegen"(P, w_1) = "codegen"(P, w_2)$], w: 13, h: 1, fill: c-public.lighten(80%))
    let layers = (
      ("st", [*Static* \ Staging_NI rule \ before compile]),
      ("en", [*Enforce* \ selective freezing \ during compile]),
      ("pr", [*Prove* \ SeaBMC job \ model of the fold]),
      ("de", [*Detect* \ artifact diff \ after compile]),
    )
    for (i, (n, b)) in layers.enumerate() {
      let x = i * 4.6 + 0.1
      node((x, 0), n, b, w: 4, h: 1.7, fill: c-muted)
      line(n + ".north", "prop.south", mark: (end: ">"), stroke: 0.6pt)
    }
  }))
  #v(0.3em)
  #text(size: 15pt)[Each layer extends an existing prototype; none is new infrastructure.]
]

#slide(title: [Static: freezing is runtime → staging])[
  #hyp
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    node((0, 0), "rt", [runtime taint \ `{protected}` args], w: 3.8, h: 1.2, fill: c-secret.lighten(80%))
    node((5.2, 1.1), "dim", [`tensor.dim`], w: 2.8, h: 0.8, fill: c-muted)
    node((5.2, -1.1), "frz", [*freeze + fold*], w: 2.8, h: 0.8, fill: c-gpu.lighten(70%), stroke: 1.4pt + c-gpu.darken(20%))
    node((10, 0), "stg", [staging taint], w: 3, h: 1.2, fill: rgb("#f0c040").lighten(50%))
    node((15, 1.1), "lb", [loop bound], w: 3, h: 0.8)
    node((15, -1.1), "lit", [*constant / literal*], w: 3.6, h: 0.8, stroke: 1.4pt + c-gpu.darken(20%))
    arrow("rt.east", "dim.west")
    arrow("rt.east", "frz.west")
    arrow("dim.east", "stg.west")
    arrow("frz.east", "stg.west")
    arrow("stg.east", "lb.west", label: [violation])
    arrow("stg.east", "lit.west")
    content((15, -2.1), text(size: 11pt)[unless `{aisec.declassify}`])
  }))
  #v(0.3em)
  #text(size: 15pt)[
    Grey = existing `Staging_NI` rule. Green = proposed. Apply at FX level first (the real
    Inductor path), then in Staging_NI on torch-mlir / IREE output. Calibrate: fires on the
    three measured surfaces, silent on non-frozen and declassified folds.
  ]
]

#slide(title: [Enforce: freeze all but the protected subgraph])[
  #hyp
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    // shaded protected region
    rect((-1.6, -2.0), (7.6, 1.0), fill: c-secret.lighten(90%), stroke: (dash: "dashed", paint: c-secret), radius: 0.2)
    content((3, -1.65), text(size: 11pt, fill: c-secret)[protected-derived: stays a runtime computation])
    node((0, 0), "w", [$w$], w: 1.4, h: 0.8, fill: c-secret.lighten(70%))
    node((2.2, 0), "abs", [`abs`], w: 1.4, h: 0.8)
    node((4.4, 0), "mx", [`max`], w: 1.4, h: 0.8)
    node((6.6, 0), "dv", [`/127`], w: 1.4, h: 0.8)
    arrow("w.east", "abs.west")
    arrow("abs.east", "mx.west")
    arrow("mx.east", "dv.west")
    node((9.6, 0), "mul", [`mul`], w: 1.6, h: 0.8)
    node((9.6, 2.0), "x", [$x$ (input)], w: 2, h: 0.8, fill: c-public.lighten(80%))
    arrow("dv.east", "mul.west")
    arrow("x.south", "mul.north")
    // other params: frozen fine
    rect((11.6, -2.0), (16.6, 1.6), fill: c-ok.lighten(88%), stroke: (dash: "dashed", paint: c-ok), radius: 0.2)
    content((14.1, -1.65), text(size: 11pt, fill: c-ok.darken(20%))[public consts: fold as usual])
    node((14.1, 0.5), "bn", [shape consts, \ eps, ...], w: 3.6, h: 1.1)
    arrow("mul.east", "bn.west")
  }))
  #v(0.3em)
  - Hook to exclude nodes from Inductor constant folding at 2.13: #lead. Fallback: pre-freeze FX rewrite that hides protected params behind an opaque op.
  - Report latency: frozen vs selective vs non-frozen, same GPU.
]

#slide(title: [Prove: the artifact is the observation])[
  #hyp
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    node((0, 1.2), "w1", [$w_1$], w: 1.4, h: 0.8, fill: c-secret.lighten(80%))
    node((0, -1.2), "w2", [$w_2$], w: 1.4, h: 0.8, fill: c-secret.lighten(80%))
    node((4.2, 1.2), "c1", [model of fold], w: 3.2, h: 0.9)
    node((4.2, -1.2), "c2", [model of fold], w: 3.2, h: 0.9)
    node((8.6, 1.2), "o1", [$"code"_1$], w: 2, h: 0.8, fill: c-muted)
    node((8.6, -1.2), "o2", [$"code"_2$], w: 2, h: 0.8, fill: c-muted)
    node((12, 0), "eq", [$"code"_1 = "code"_2$ ?], w: 3.2, h: 0.9, fill: c-public.lighten(80%))
    arrow("w1.east", "c1.west")
    arrow("w2.east", "c2.west")
    arrow("c1.east", "o1.west")
    arrow("c2.east", "o2.west")
    arrow("o1.east", "eq.north-west")
    arrow("o2.east", "eq.south-west")
    content((0, 0), text(size: 11pt)[$"pub"(w_1) = "pub"(w_2)$])
    node((16.4, 1), "bad", [bad (fold): *sat*], w: 3.9, h: 0.8, fill: c-secret.lighten(75%))
    node((16.4, -1), "fix", [fixed (runtime): *unsat*], w: 3.9, h: 0.8, fill: c-ok.lighten(75%))
    line("eq.east", "bad.west", mark: (end: ">"))
    line("eq.east", "fix.west", mark: (end: ">"))
  }))
  #v(0.3em)
  - One `add_l2_job` in `proofs_l2_seabmc`, same calibration rule as the seven existing pairs.
  - A proof about a *model* of the fold, not about Inductor — stated that way.
]

#slide(title: "Detect: artifact differential, as a regression fixture")[
  #cols(columns: (3fr, 2fr), gutter: 1.2em)[
    - Existing detector (`probe_autotune.normalize` + `kernel_body`), widened to every file a GPU compile writes:
      `.py` · `.ttir` · `.ttgir` · `.llir` · `.ptx` · `.cubin` (via `cuobjdump -sass`) · AOTI `.so`
    - Plus a permission audit of every cache directory up to `/`.
    - Same three guards: caches disabled per compile, same-class control A = A′, non-frozen A = B.
  ][
    #framed(title: [`compiler_harness` fixture])[
      #text(size: 14pt)[
        `snapshot.yaml` \
        `bad/` freezing on \
        `fixed/` selective freezing \
        expected: bad A≠B, fixed A=B
      ]
    ]
  ]
]

// ================================================================
#title-slide[How it fits, and the plan]

#slide(title: "The prototypes, as one story")[
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    node((0, 2.2), "sn", [Staging_NI \ + initial], w: 3, h: 1.1, fill: c-muted)
    node((0, 0), "lc", [leak_check \ CPU #sym.checkmark → GPU], w: 3.4, h: 1.1, fill: c-gpu.lighten(70%))
    node((0, -2.2), "fv", [fcvd_ct \ per-pass], w: 3, h: 1.1, fill: c-muted)
    node((7, 0), "story", [*artifact non-interference* \ for weights on the GPU path], w: 5, h: 1.6, fill: c-public.lighten(80%))
    node((14, 2.2), "en", [selective \ freezing (new)], w: 3, h: 1.1, fill: c-gpu.lighten(70%))
    node((14, 0), "sb", [proofs_l2_seabmc \ +1 job], w: 3.4, h: 1.1, fill: c-muted)
    node((14, -2.2), "ch", [compiler_harness \ +1 fixture], w: 3.4, h: 1.1, fill: c-muted)
    arrow("sn.east", "story.north-west", label: [predicts])
    arrow("lc.east", "story.west", label: [demonstrates])
    arrow("fv.east", "story.south-west", label: [pass-level analogue])
    arrow("en.west", "story.north-east", label: [repairs])
    arrow("sb.west", "story.east", label: [proves fix])
    arrow("ch.west", "story.south-east", label: [guards])
  }))
  #v(0.2em)
  #text(size: 14pt)[Out of scope for this pair: `ebpf-tracing`, `mlir_leak` (timing / control-flow channels; this leak is neither).]
]

#slide(title: "Work items")[
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    let items = (
      ("E1", [pin GPU \ config], 0, 0),
      ("E2", [CUDA port \ (H1)], 3.3, 0),
      ("E3", [artifact \ scanner (H2,H3)], 6.6, 0),
      ("E4", [AOTI CUDA \ (H4)], 6.6, -2),
      ("E5", [static \ detector], 3.3, 2),
      ("E6", [selective \ freezing], 9.9, 0),
      ("E7", [SeaBMC \ job], 9.9, 2),
      ("E8", [harness \ fixture], 13.2, 0),
      ("E9", [IREE lead \ (H5)], 13.2, -2),
    )
    for (n, b, x, y) in items {
      let f = if n in ("E1", "E2", "E3") { c-gpu.lighten(65%) } else if n == "E9" { rgb("#ffffff") } else { c-muted }
      node((x, y), n, [*#n* \ #b], w: 2.8, h: 1.4, fill: f)
    }
    arrow("E1.east", "E2.west")
    arrow("E2.east", "E3.west")
    arrow("E1.south", "E4.west")
    arrow("E3.east", "E6.west")
    arrow("E5.east", "E6.north-west")
    arrow("E6.east", "E8.west")
    arrow("E3.south", "E9.west")
  }))
  #v(0.2em)
  #text(size: 15pt)[Green = minimum publishable unit. Natural owners: E2–E4 `leak_check`, E5 `Staging_NI`, E7 `proofs_l2_seabmc`. Hardware: one cloud GPU, one pinned SKU.]
]

#slide(title: "What would change the story")[
  #table(
    columns: (1fr, 1.4fr),
    stroke: none,
    inset: 7pt,
    fill: (_, y) => if calc.odd(y) { c-muted.lighten(50%) },
    table.header[*if*][*then*],
    [H1 false: Triton folds into a runtime buffer, not a literal],
    [still reportable at the config point; switch to buffer-valued folding (freezing note §4), new detector],
    [H3 false: literal in source, not on shared disk],
    [observer narrows to package recipients; still a finding],
    [selective freezing erases freezing's speedup],
    [defense becomes a policy ("don't freeze protected models"), not a pass — report the numbers],
  )
  #v(0.4em)
  #text(size: 15pt)[SaTML deadline (2026-09-29) has passed: this is rebuttal / camera-ready / follow-up material — a GPU column for §3, artifact non-interference for §4.]
]

#focus-slide[
  Freezing turns a weight into code. \
  We predict it, show it on the GPU path, repair it, and prove the repair.
]
