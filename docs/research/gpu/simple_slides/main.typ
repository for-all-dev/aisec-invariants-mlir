// GPU attack/defense pair — short deck: leak_check attacks, Staging_NI defends.
// Full version: ../narrative_slides/main.typ. Source of truth: ../narrative.agents.md
// Build: typst compile docs/research/gpu/simple_slides/main.typ

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
#let c-stage = rgb("#f0c040")
#let c-new = rgb("#76b900")
#let c-ink = rgb("#000000")
#let c-paper = rgb("#ffffff")

#let badge(label, color) = box(fill: color.lighten(60%), inset: (x: 4pt, y: 2pt), radius: 3pt)[#text(size: 0.7em)[#label]]
#let measured = badge("measured", c-ok)
#let hyp = badge("hypothesized", c-stage)

// A labelled rounded box centred at `pos`.
#let node(pos, name, body, w: 2.6, h: 1, fill: c-paper, stroke: 0.8pt + c-ink) = {
  import cetz.draw: rect, content
  rect((pos.at(0) - w / 2, pos.at(1) - h / 2), (rel: (w, h)), name: name, radius: 0.12, fill: fill, stroke: stroke)
  content(name, align(center, text(size: 13pt, body)))
}

#let arrow(a, b, label: none, stroke: 0.8pt + c-ink) = {
  import cetz.draw: content, line
  line(a, b, mark: (end: ">", fill: c-ink), stroke: stroke, name: "ln")
  if label != none {
    content("ln.mid", text(size: 11pt, label), anchor: "south", padding: 0.12)
  }
}

// ---------------------------------------------------------------- slides

#front-slide(
  title: "Freezing turns a weight into code",
  subtitle: [`leak_check` attacks, `Staging_NI` defends — on the GPU path],
  authors: "Confidential compiling stream — SPS Fellowship",
  info: [Plan, not a result · `docs/research/gpu/narrative.agents.md`],
)

#slide(title: "The pair")[
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    node((0, 0), "src", [model source \ oblivious in eager], w: 3.6, h: 1.3, fill: c-muted)
    node((6, 0), "cc", [Inductor \ `freezing=True`], w: 3.4, h: 1.3, fill: c-muted)
    node((12, 0), "art", [compiled artifact \ carries `f(w)`], w: 3.8, h: 1.3, fill: c-secret.lighten(75%))
    arrow("src.east", "cc.west")
    arrow("cc.east", "art.west")
    node((12, -2.6), "lc", [*leak_check* \ attack: show it], w: 3.8, h: 1.3, fill: c-secret.lighten(88%))
    node((0, -2.6), "sn", [*Staging_NI* \ defense: predict it], w: 3.8, h: 1.3, fill: c-ok.lighten(80%))
    line("lc.north", "art.south", mark: (end: ">"), stroke: c-secret + 1pt)
    line("sn.north", "src.south", mark: (end: ">"), stroke: c-ok + 1pt)
    content((6, -2.6), text(size: 12pt)[same property, \ two directions])
  }))
  #v(0.3em)
  Property: *the generated artifact must not depend on protected weights*,
  except through explicit declassification.
]

// ================================================================
#title-slide[Attack: `leak_check`]

#slide(title: "Measured on CPU")[
  #measured
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    content((-0.4, 2.5), text(size: 12pt, weight: "bold")[non-frozen], anchor: "west")
    node((2, 1.6), "w0", [$w$ (runtime buffer)], w: 3.4, h: 0.8, fill: c-secret.lighten(80%))
    node((7, 1.6), "k0", [kernel computes \ `max|w|/127` at run time], w: 4.6, h: 1.1)
    node((12.5, 1.6), "o0", [codegen A = B], w: 3.4, h: 0.8, fill: c-ok.lighten(75%))
    arrow("w0.east", "k0.west")
    arrow("k0.east", "o0.west")
    content((-0.4, 0.1), text(size: 12pt, weight: "bold")[frozen], anchor: "west")
    node((2, -0.8), "w1", [$w$ (constant)], w: 3.4, h: 0.8, fill: c-secret.lighten(80%))
    node((7, -0.8), "k1", [constant folding \ evaluates `max|w|/127`], w: 4.6, h: 1.1)
    node((12.5, -0.8), "o1", [codegen A ≠ B], w: 3.4, h: 0.8, fill: c-secret.lighten(70%))
    arrow("w1.east", "k1.west")
    arrow("k1.east", "o1.west")
  }))
  #grayed[
    ```diff
    -  auto tmp1 = static_cast<float>(0.007874015718698502); // A
    +  auto tmp1 = static_cast<float>(0.787401556968689);    // B
    ```
  ]
  #text(size: 14pt)[A: max|w| = 1, B: max|w| = 100. `quant_scale`, `wmax`, `wnorm` fire; `wsum` inconclusive. torch 2.13.0+cu130, Inductor CPU. `probe_freezing.py`]
]

#slide(title: "The GPU question")[
  #hyp
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    node((0, 0), "fx", [FX graph \ (frozen)], w: 2.8, h: 1.1, fill: c-muted)
    node((4, 0), "cf", [constant \ folding], w: 2.6, h: 1.1, fill: c-secret.lighten(80%))
    node((8, 0), "tr", [Triton `.py` \ *H1*], w: 2.8, h: 1.1, fill: c-new.lighten(70%))
    node((12, 0), "pt", [`.ptx` / `.cubin` \ *H2*], w: 3, h: 1.1, fill: c-new.lighten(70%))
    arrow("fx.east", "cf.west")
    arrow("cf.east", "tr.west", label: [literal])
    arrow("tr.east", "pt.west")
    node((10, -2.4), "disk", [on-disk caches, other-readable? *H3*], w: 6.6, h: 1, fill: c-secret.lighten(88%), stroke: (dash: "dashed", paint: c-secret))
    line("tr.south", (8, -1.9), mark: (end: ">"), stroke: (dash: "dotted"))
    line("pt.south", (12, -1.9), mark: (end: ">"), stroke: (dash: "dotted"))
  }))
  #v(0.3em)
  - Folding runs on the FX graph, *before* the C++ / Triton split → expect H1.
  - Port: `probe_freezing.py` with `device="cuda"`, same three guards
    (caches off, same-class A = A′, non-frozen A = B).
]

// ================================================================
#title-slide[Defense: `Staging_NI`]

#slide(title: "Staging_NI today")[
  #measured
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    node((0, 0), "rt", [runtime taint \ `{stagingni.protected}`], w: 4, h: 1.2, fill: c-secret.lighten(80%))
    node((5.2, 0), "dim", [`tensor.dim`], w: 2.6, h: 0.9, fill: c-muted)
    node((9.6, 0), "stg", [staging taint], w: 3, h: 1.2, fill: c-stage.lighten(50%))
    node((14.2, 0), "lb", [`scf.for` / `affine.for` \ bound], w: 3.6, h: 1.2)
    arrow("rt.east", "dim.west")
    arrow("dim.east", "stg.west")
    arrow("stg.east", "lb.west", label: [violation])
  }))
  #v(0.3em)
  - Protected *runtime* data must not decide *compile-time* structure.
  - Propagation is sound over-approximation: any tainted operand taints every result;
    memory, regions and block arguments included; iterated to a fixpoint.
  - Freezing is exactly this leak class — but `Staging_NI` has no rule for it yet.
]

#slide(title: "The new rule: freezing is a conversion")[
  #hyp
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    node((0, 0), "rt", [runtime taint], w: 3, h: 1.2, fill: c-secret.lighten(80%))
    node((4.8, 1.1), "dim", [`tensor.dim`], w: 2.8, h: 0.8, fill: c-muted)
    node((4.8, -1.1), "frz", [*freeze + fold*], w: 2.8, h: 0.8, fill: c-new.lighten(70%), stroke: 1.4pt + c-new.darken(20%))
    node((9.4, 0), "stg", [staging taint], w: 3, h: 1.2, fill: c-stage.lighten(50%))
    node((14.4, 1.1), "lb", [loop bound], w: 3.2, h: 0.8)
    node((14.4, -1.1), "lit", [*constant / literal*], w: 3.6, h: 0.8, stroke: 1.4pt + c-new.darken(20%))
    arrow("rt.east", "dim.west")
    arrow("rt.east", "frz.west")
    arrow("dim.east", "stg.west")
    arrow("frz.east", "stg.west")
    arrow("stg.east", "lb.west", label: [violation])
    arrow("stg.east", "lit.west")
    content((14.4, -2.0), text(size: 11pt)[unless `{aisec.declassify}`])
  }))
  #v(0.3em)
  #text(size: 16pt)[
    A foldable op with a runtime-tainted operand yields *staging* taint; a staging-tainted
    value materialized as a constant is a violation. Grey = existing, green = new.
  ]
]

#slide(title: "Worked example: quantization scale")[
  #hyp
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    node((0, 0), "w", [$w$ #text(size: 10pt)[protected]], w: 2.2, h: 0.9, fill: c-secret.lighten(70%))
    node((3, 0), "abs", [`abs`], w: 1.6, h: 0.9, fill: c-secret.lighten(85%))
    node((5.5, 0), "mx", [`max`], w: 1.6, h: 0.9, fill: c-secret.lighten(85%))
    node((8, 0), "dv", [`/127`], w: 1.6, h: 0.9, fill: c-secret.lighten(85%))
    node((11.6, 0), "c", [`arith.constant` \ `0.787…`], w: 3.4, h: 1.1, fill: c-stage.lighten(50%), stroke: 1.4pt + c-secret)
    node((15.6, 0), "err", [*error* \ staging leak], w: 2.8, h: 1.1, fill: c-secret.lighten(70%))
    arrow("w.east", "abs.west")
    arrow("abs.east", "mx.west")
    arrow("mx.east", "dv.west")
    arrow("dv.east", "c.west", label: [freeze])
    arrow("c.east", "err.west")
    content((4.0, -1.1), text(size: 11pt, fill: c-secret)[runtime taint])
    content((11.6, -1.1), text(size: 11pt, fill: c-stage.darken(40%))[staging taint])
  }))
  #v(0.3em)
  - Mark the weight `{stagingni.protected}`; the pass flags the fold *before* any code is generated.
  - Repair: keep this subgraph a runtime computation, or tag the constant `{aisec.declassify}` if releasing `max|w|` is acceptable.
]

#slide(title: "Calibration: the defense must agree with the attack")[
  #table(
    columns: (1.3fr, 1fr, 1fr),
    stroke: none,
    inset: 8pt,
    fill: (_, y) => if calc.odd(y) { c-muted.lighten(50%) },
    table.header[*case*][*`leak_check` (dynamic)*][*`Staging_NI` (static)*],
    [`quant_scale`, `wmax`, `wnorm` frozen], [leak #measured], [must fire],
    [same surfaces, non-frozen], [A = B #measured], [must stay silent],
    [frozen + `{aisec.declassify}`], [A ≠ B (expected)], [must stay silent],
    [`wsum` frozen], [inconclusive #measured], [fires (over-approx.)],
  )
  #v(0.4em)
  #text(size: 16pt)[
    The static check is sound and all-inputs; the dynamic one is precise at one config point.
    `wsum` is where they are allowed to disagree: the leak is real in principle, the bait
    just can't hold the float sum fixed.
  ]
]

#slide(title: "Plan")[
  #align(center, cetz.canvas(length: 1.4cm, {
    import cetz.draw: *
    let steps = (
      ("s1", [*1* \ pin one GPU \ config point]),
      ("s2", [*2* \ `leak_check` \ CUDA port]),
      ("s3", [*3* \ `Staging_NI` \ freeze rule]),
      ("s4", [*4* \ calibrate \ against 2]),
    )
    for (i, (n, b)) in steps.enumerate() {
      node((i * 4.6, 0), n, b, w: 3.6, h: 1.8, fill: if i < 2 { c-secret.lighten(85%) } else { c-ok.lighten(80%) })
    }
    arrow("s1.east", "s2.west")
    arrow("s2.east", "s3.west")
    arrow("s3.east", "s4.west")
  }))
  #v(0.4em)
  - Steps 2 and 3 are independent and can run in parallel; step 4 needs both.
  - Rule lands first at FX level (the real Inductor path), then in `Staging_NI` on MLIR output.
  - Hardware: one cloud GPU. Nothing else new.
]

#focus-slide[
  `leak_check` shows the weight in the code. \
  `Staging_NI` says so before compiling.
]
