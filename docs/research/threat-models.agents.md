# Attacker capability profiles, across all the prototypes

Repo-wide consolidation. AI-drafted; owner reviews. Claim discipline per
[`prototypes/leak_check/PRINCIPLES.md`](../../prototypes/leak_check/PRINCIPLES.md):
**[measured]** = a run recorded in this repository, **[source]** = read from a tool's or
compiler's own code, **[inference]** = reasoning here, not checked.

Purpose: the prototypes have accumulated real results against several different adversaries, and
no document says which adversary each result binds against. This note fixes one vocabulary,
names the capability axes that vocabulary does not carry, and gives every measured result its
coordinates.

---

## 1. Four classification frameworks already exist, and they compose

The first thing to settle is that we are not short of a taxonomy — we have four, written
independently, each answering a genuinely different question. They are not competitors and the
consolidation is not to pick one.

| framework | where | question it answers |
|---|---|---|
| **leak class × observer ring** | [`fcvd_ct/artifact/attacker_profile.py`](../../prototypes/fcvd_ct/artifact/attacker_profile.py) | *Who is the attacker, and what can they see?* |
| **layers A / B / C / D** | [`formal_verif.pipeline.agents.md`](formal_verif.pipeline.agents.md) | *What kind of evidence is this — proof in a model, or detection on silicon?* |
| **evidence levels L0–L4** + four-valued outcome | [`compiler_harness/mlir/L0_L1_L2_PIPELINE.md`](../../prototypes/compiler_harness/mlir/L0_L1_L2_PIPELINE.md) | *How far does the evidence reach, and what is left as a named assumption?* |
| **the differential 2×2** | [`leak_check.methodology.siddharth.md`](leak_check.methodology.siddharth.md) | *Whose fault is it — the source, or the compiler?* |

A result is fully specified only when it has a coordinate on all four: an **observer**, an
**evidence kind**, an **evidence level**, and an **attribution**. Most results in the repo state
one or two and leave the rest implicit, which is why the same word ("secure") means four different
things across the prototypes.

Worth noticing that L0 already *asks* for the threat model — it is defined as declaring "secrets,
public inputs, **observer projections**, authorized release policies, helper summaries, ... and
target timing facts". The compiler_harness fixtures have a slot for exactly the content of this
note; the other prototypes do not, and mostly have not filled one in elsewhere either.

---

## 2. The observer vocabulary we adopt

`attacker_profile.py`'s grid is canonical and nothing below replaces it. Two axes: **what leaks**
(functional, timing, microarchitectural, power) and **who is watching** — eight rings ordered
strictly by how directly the observer reaches secret state, so that every observer who *infers*
sits outside every observer who *reads*:

| ring | observer | holds |
|---|---|---|
| O0 | Public transcript | outputs, errors, response length |
| O1 | Remote timing | end-to-end latency, repeated-query statistics |
| O2 | Constant-time trace | branches, address classes, latency classes |
| O3 | Local microarchitecture | cache sets and lines, pages, predictors, contention |
| O4 | Physical observer | power, EM, acoustic, thermal, frequency |
| O5 | TEE / HSM host | a host's powers minus what the enclave declares unreachable |
| O6 | Host / debugger | process memory, registers, logs, files, core dumps |
| O7 | Invasive observer | buses, internal memories, chip probes |

The ordering is the load-bearing part: it is what makes "proved at O2 and carried outward to O1"
a statement with content, and what makes O6-and-inward *moot* rather than uncovered.

The rest of this note is five capability axes the ring order does not encode, and one class of
measured result that has no cell in the grid.

---

## 3. Five axes the ring order does not carry

### 3.1 Which asset — and therefore whether repetition helps

The axis with the largest effect on attacker economics, and the one most often left implicit.

| asset | lifetime | does query repetition help? | consequence |
|---|---|---|---|
| **Model weights** | static across every inference | **yes, decisively** | a weak, noisy channel plus API access suffices; average until clean |
| **User input / prompt / activations** | fresh per query | **no, for a given secret** | the channel must resolve the secret in one execution |
| **Sparsity / pruning pattern** | static | yes | structural, not value-carrying; the asset in `mlir_leak/sparse` |
| **Shapes and extents** | static per deployment, or per query | yes | the asset in `mlir_leak`'s `dynshape` and in `Staging_NI` |
| **Model architecture** | static, and coarse | yes | leaks from control structure, not from values |

The last three matter because they are leaked by *structure* rather than by values, which is why
they are invisible to instruments that watch value flow and visible to `Staging_NI` and to
`--sparsification`'s address channel.

The weight column is the argument already made in
[`formal_verif.threat-model.agents.md`](formal_verif.threat-model.agents.md): a crypto key is used
once and must be extracted from a one-shot noisy channel; a weight is re-exposed on every forward
pass, so time is on the attacker's side. That argument is **specific to the weight asset** and it
reverses for user data, where each secret is observed exactly once and the classical constant-time
threat model applies unchanged.

The reversal has a corollary [inference]: user data is attackable in one shot precisely when the
leak is **address-shaped and the secret is small**. Two results in the repo are already that
shape — onnx-mlir's `onnx.Gather` lowered to a load at a secret index
([`compiler-choice-circt-heir-onnx.agents.md`](compiler-choice-circt-heir-onnx.agents.md) §2) and
`proofs_l2_seabmc`'s `secret_embedding_index` — and in both the secret is a token id. One
cache-line observation of an embedding-row gather narrows a 50k-entry vocabulary substantially in
a single query, with no averaging. So the two assets do not merely have different economics; they
make *different leaks* matter. Variable-latency arithmetic on a weight is a slow grind that
repetition wins. A gather on a token id is immediate.

Most of the corpus marks *weights* secret (`w.cfg`'s `secret global W`, `aisec.protected`,
`stagingni.protected`, `{secret.secret}`). The two gather results are close to the only place user
data is the asset, and they deserve to be a first-class second corpus rather than incidental rows.

### 3.2 Build time versus run time

Every ring O0–O5 describes an observer of a **running program**, and each needs either
co-residency or query access. An observer of the compiler's **persistent output** needs neither:
the artifact exists before the program is ever run, survives every run, and reading it costs one
`open(2)`. This is not a finer-grained ring — it is off the axis, because the axis is ordered by
directness of access to *runtime* secret state. See §4.

### 3.3 Who controls the build configuration

Across the corpus the same source flips between secure and insecure by changing something that is
not the source:

- `-O0` vs `-O3`, and gcc vs clang **at identical flags** [measured,
  [`leak_check.lessons.agents.md`](leak_check.lessons.agents.md)]
- `torch._inductor.config.freezing` on vs off [measured, [`leak_check.freezing.agents.md`](leak_check.freezing.agents.md)]
- the process `umask` and `TORCHINDUCTOR_CACHE_DIR` [measured, [`leak_check.exfil.agents.md`](leak_check.exfil.agents.md)]
- FTZ/DAZ build flags, which close the denormal channel entirely [measured, layer D]

"Who chooses the flags" is therefore an attacker-relevant capability, and it is a *different
principal* in each deployment of §6. When a serving platform compiles a tenant's model, the
platform picks `freezing`, the cache directory and the umask, and the tenant — whose weights are
the asset — picks none of them. The config-point discipline is usually stated as an epistemic
caution; it is equally a threat-model statement: **the party who fixes the config point decides
the security of the deployment, and it need not be the party who owns the secret.**

### 3.4 How much the compiler itself is trusted

Three postures, only the first two of which appear in the corpus:

1. **Honest but optimizing** — the compiler is doing its job and a channel is a side effect. The
   premise of `leak_check`, `mlir_leak`, `formal_verif`'s quadrants, the whole
   compiler-introduced-vs-authored 2×2.
2. **Honest but unsafe by default** — the compiler is not wrong, its defaults are. AOTInductor
   writing weights into a shared cache directory and relying on the ambient umask is the measured
   instance.
3. **Malicious** — a compromised toolchain deliberately emitting a leak. **No prototype models
   this**, although [`initial`](../../prototypes/initial/)'s related work already cites Chen et
   al., *Your Compiler is Backdooring Your Model* (IEEE S&P 2026, arXiv:2509.11173). The posture
   is in the reading list and in none of the corpora.

The compiler's role is in fact inconsistent across the prototypes, and it is worth naming rather
than smoothing over: in `leak_check` / `mlir_leak` / `formal_verif` the compiler is the **suspect**;
in `compiler_harness` / `proofs_l2_seabmc` it is a neutral **boundary for attribution**; in
`initial` / `Staging_NI` it is the **enforcement point**; in `fcvd_ct` it is the **verified
artifact**. Four different relationships, all defensible, none stated side by side until now.

Posture 3 partitions `fcvd_ct`'s own results, which is not obvious [inference]:

- The **per-program** checks (P1/P4, and `formal_verif`'s binsec layers) examine the output the
  compiler actually produced, so they survive a malicious compiler for the property they check.
- The **universal** proofs (P3 structural templates, P5 PDL rewrites) prove a *specification* and
  rest on the named assumption that the C++ pattern implements the template. A malicious compiler
  is under no obligation to implement its own specification, so under posture 3 those proofs bind
  nothing.

Not a criticism — the universal quantification is what makes the template work valuable under
postures 1 and 2. It is a statement about *which trusted assumption each half rests on*, currently
recorded as "trusted assumption" without saying trusted against whom.

### 3.5 What the attacker is *allowed* to learn

Three different baselines are in use, and a verdict means something different under each:

| baseline | property | where |
|---|---|---|
| **Absolute** | the observation is independent of the secret, full stop | `formal_verif` A/B, `fcvd_ct` P1/P2, `mlir_leak`, `leak_check` |
| **Release-relative** | independent given the public outputs *and* the authorized declassifications | `initial` (`aisec.declassify`), `proofs_l2_seabmc`'s `explicit_error_oracle` (the padding-validity bit is a hypothesis the two runs agree on; only *surplus* distinguishability is a violation) |
| **Source-relative** | the target leaks no more than the source already did | `fcvd_ct` P5: `L_S(x) = L_S(x') ⟹ L_T(x) = L_T(x')` |

The release-relative baseline has a second parameter that is easy to miss: **who the authorized
recipient is.** `compiler_harness` carries fixtures (`wrong_party_plaintext`,
`wrong_host_fhe_reveal`, observers `host-authorized-plaintext-sinks` and
`audience-authorized-mailbox-sinks`) where the *value* is correct and the *audience* is not. That
is not a leak class in the §2 grid at all — no channel is involved — and it is the one adversary
in the repo who is not an observer of anything but a recipient of everything.

The third deserves emphasis because it is easy to over-read. `fcvd-ct-pdl` needs **no secret
labels at all** — the source program's own leakage is the declassification bound, which is exactly
what lets it quantify over every program the pattern matches. The price is that a `ct-preserving`
verdict is *not a safety claim*. It says the rewrite did not make things worse. A program can be
catastrophically leaky and every rewrite applied to it "ct-preserving". This should be stated
wherever those verdicts are quoted.

---

## 4. The missing class: persistence — and it already has a verifier

The grid has four leak classes: functional, timing, microarchitectural, power. Consider the two
results where the compiler is *unambiguously* the cause:

- **`freezing`** folds `w.abs().max()/127` into a `static_cast<float>` literal in the generated
  C++. An attacker who reads the generated code recovers `max|w|` exactly, **without running the
  kernel or timing anything** [measured].
- **AOTInductor** bakes raw weight bytes into a `*.wrapper.so` at mode `0o755` under an entirely
  other-traversable directory chain, persisting after the compiling process exits [measured].

Neither is functional (nothing was returned), timing (nothing was timed), microarchitectural (no
shared hardware state), nor power. Observer-wise O6 does list "files" — but O6 is *moot* across
the whole grid, on the correct reasoning that an observer holding process memory has nothing left
to infer. The exfil attacker holds no process memory. They are a different UID who can `open` a
file: strictly weaker than O6 and unlike anything in O0–O5. The grid's O6 conflates two very
different observers, and the repository's only two clear compiler-introduced findings fall into
the gap.

An earlier revision of `attacker_profile.py` did carry a **"residual data"** class — *"where the
secret was left afterwards: memory, swap, core dumps, spilled registers; nothing is measured
during the run, the attacker arrives later and reads"* — removed deliberately in `b4bd881`
because the page's brief asked for four classes. That was right for that page, whose scope is
stated up front as functional equivalence plus timing. Two observations for the repo-level model:

1. The removed class was **runtime** residue. A build artifact is a step further out still: it
   exists before any run and survives every run.
2. Both share the property that separates them from all four surviving classes — **the attacker
   arrives later and reads, rather than observing while the program runs.**

**The class is independently present in three prototypes and absent only from the grid.**

- `compiler_harness` already declares `public-log-and-artifact-sinks` as an observer model
  (`secret_logging_checkpoint`), and carries two *runtime-residue* fixtures with their own
  observers — `reduced-sequential-cross-tenant-output` (Redis pool reuse) and
  `reduced-sequential-cross-actor-response` (LeftoverLocals GPU scratch). Those are the "attacker
  arrives later and reads" shape exactly, at runtime rather than at build time.
- `leak_check` has the two measured build-time instances above.
- `Staging_NI` has the property.

**And that property already has a static verifier, in a prototype nobody has connected to it.**
`Staging_NI` implements *staging-time non-interference*: it detects when protected runtime data
influences a compile-time decision, so that "even though the tensor values themselves are never
revealed, the generated program structure may expose information about protected runtime data"
[source, `Staging_NI/readme.md`]. That is exactly the `freezing` finding, stated as a property
rather than found by a probe: `freezing` promotes the weight to a compile-time constant, a
secret-derived scalar becomes computable at staging time, and the value lands in the generated
code. `Staging_NI` is the analysis that would have predicted it; the `freezing` probe is its
measured instance in a production compiler. Neither document cites the other. Connecting them is
the single highest-value consolidation available right now, and it turns a pair of one-off probe
results into a property with a checker.

This reframes the headline claim. The honest three-part version:

> Against **execution-channel** observers (O1–O5), the compiler was measured to be protective:
> across five-plus adversarial probes Inductor introduced zero leaks and erased several.
> Against **domain-specific IR lowerings**, the compiler does introduce real execution-channel
> leaks — `sparse_tensor --sparsification`, CIRCT's `--convert-comb-to-arith`, HEIR's
> `--convert-secret-extract-to-static-extract`. Against **persistence** observers, the compiler is
> the threat in both measured instances.
>
> The compiler-introduced quadrant looked empty for a long time because the corpus was watching
> the wrong class, not because compilers are safe.

---

## 5. Instrument versus attacker

A recurring confusion worth settling once. Several of our channels are **instruments**, not
attacker capabilities — no real adversary runs the victim under Valgrind. An instrument is useful
insofar as it *soundly bounds* some real observer, and the direction of the bound matters.

| instrument | bounds which observer | direction | what breaks the bound |
|---|---|---|---|
| Valgrind taint (`ctgrind`-style) | any O2 digital-channel observer | **over** — fires on dependences no cache attacker can resolve | blind to analog: denormals read taint-clean [measured] |
| callgrind `Ir`/`Bc` counts | no real observer; a proxy for O2 | neither, and confounded by process context (path length, layout) [measured] | a few-hundred `dIr` without taint corroboration decides nothing |
| binsec `-checkct`, byte granularity | stronger than any real observer | **over** (deliberately) | the 32 B codebook is formally `insecure` and unexploitable by a cache attacker |
| binsec + `[cache-line]` contract (B) | O3 Flush+Reload / Prime+Probe | roughly tight, *for a 64 B observer* | granularity is hardcoded; see below |
| dudect / MI timing (D) | O1 remote clock, O3 local clock | **under** — a lower bound; a null is "not detected", never "proven clean" | the only genuinely attacker-shaped instrument we have |
| contract-vs-silicon (C) | O3/O4 beyond the model | detection | `d_denormal`: A/B say secure, chip leaks ~1 bit [measured] |
| `fcvd_ct` SMT self-composition | O2 per `leakage.py` | **over**, relative to the model | secret **memory contents are out of model** — the initial memory is shared, so a memref argument is public data [source] |
| SeaBMC relational witness (L2) | O2, release-relative | proof of *existence* of a separating pair | `sat` is a counterexample; `unsat` is bounded |
| codegen diff (`freezing` probe) | persistence: artifact reader | **tight** — the attacker reads the same bytes | keys on inline literals; blind to constant *buffers* [stated] |
| file-mode + sentinel scan (`exfil`) | persistence: other-UID local reader | **tight** | mode bits verified; a second real UID reading was not [stated] |
| `Staging_NI` taint | persistence: artifact reader, statically | **over** | a staging-time flow is not always recoverable from the artifact |

Three things fall out.

**`fcvd_ct` and `formal_verif` do not currently protect the same asset, despite comparable
verdicts.** `formal_verif`'s nanogpt corpus declares `secret global W` — the weights, in memory.
`fcvd_ct`'s self-composition shares the initial memory between the two runs, so **a memref
argument is public data** and only scalar arguments can be secret [source]. The leakage models
were deliberately aligned so the two layers "make comparable statements", and on the observation
side they do; on the *asset* side they do not, and a weight tensor is exactly the thing that does
not fit through the MLIR layer's labelling. Either secret memory becomes expressible, or the
MLIR-layer verdicts should be quoted as being about secret *indices and scalars*, which is what
they currently are. This is not recorded as a limitation anywhere.

**Layer B's granularity should be a profile parameter, not a constant.** It computes
`distinct_lines` against a hardcoded 64 B line. But the observer ring determines granularity, and
it is not scalar: the TEE host (O5) is *coarser* in space (4 KB pages, controlled-channel) and
*finer* in control flow (per-instruction, SGX-Step) than the cache attacker (O3). One number
cannot express that. What B wants is a **granularity vector per channel** —
`(address: 64 B | 4 KB, control: branch | instruction, latency: on | off)` — selected by the
profile. This is the most concrete piece of engineering this note implies, and it is what would
let `b_codebook_small`'s verdict be restated honestly as "secure against O3, insecure against O5"
instead of "`[cache-line]`-secure".

**No instrument covers the `power` row, and one cell of that row reaches O1.** The grid records
it: DVFS makes consumption change frequency and frequency changes wall-clock time (Hertzbleed),
so a power channel reaches a remote observer with no physical access — which also undercuts the
timing row's outward carry, since equal observation traces stop implying equal running times.
Unaddressed, and an IR-level leakage model is the wrong place to start; restated here so it is a
known blind spot at repo level and not only on the project page.

---

## 6. Four deployments, to make the profiles concrete

### D1 — Confidential inference in a TEE

Model owner's weights, untrusted host, enclave deployed *specifically* to hide the weights from
the operator. Asset: weights. Observer: **O5**, near-oracle — controlled-channel gives 4 KB-page
and SGX-Step gives per-instruction resolution. Repetition available.

Where the corpus bites hardest, because weight confidentiality is the deployment's *stated*
guarantee, so a secret-dependent gather is a direct break rather than a hypothetical. Also where
the tooling is weakest: the O5 `uarch` cell reads **nothing**, and layer B's 64 B contract is the
wrong granularity for the observer.

Open and undecided: **is the compiler inside or outside the enclave?** If outside, the weights are
exposed to the host before any side channel is considered and the whole persistence class is
trivially lost. This is a real design question for confidential inference and we have said nothing
about it.

### D2 — Multi-tenant cloud serving

Tenant's weights, end users' prompts, a semi-trusted platform, untrusted co-tenants. Two assets
with opposite economics (§3.1). Observers: **O3** (co-resident cache) and the persistence reader
(a different UID on the host).

The deployment the exfil result is about, and where §3.3 has teeth: the platform compiles, so the
platform picks the umask and the cache directory, while the tenant owns the weights.
`/tmp/torchinductor_<user>/` on a shared serving host is the finding, and its severity is a
property of the deployment rather than of the compiler.

### D3 — On-device / edge (the DRM case)

Proprietary model shipped to hardware the adversary owns. Asset: weights. The adversary holds
**O3, O4, O6, O7**, plus the artifact. The prior note calls this "a losing battle"; that is
correct and should stay blunt. Nothing here makes it winnable — the work raises cost, and cost is
the honest framing.

### D4 — Compiling *for* obliviousness (HEIR, FHE/MPC)

Structurally different from D1–D3 and the strongest motivation for the `fcvd_ct` line. Here the
compiler's job **is** to produce data-oblivious code, so a leak is not an accident of optimization
but a **correctness bug in a security mechanism**, and the compiler is a trusted component being
verified rather than a suspect being audited. The HEIR pass-by-pass result — the extract pass
closes `address` and opens `control`, and only the pipeline as a whole is safe — exists only in
D4 and is directly actionable: *a user running the extract pass alone would not be fine*.

---

## 7. Where each result binds

`persistence` is the class proposed in §4. "Attribution" uses the differential 2×2.

| result | class | ring | asset | baseline | compiler posture | attribution |
|---|---|---|---|---|---|---|
| `initial` — taint to `secret.reveal` without declassify | functional | O0 | weights | release-relative | honest | source |
| `Staging_NI` — staging-time NI | **persistence** | artifact reader | weights | absolute | honest | compiler |
| `compiler_harness` L0–L2 fixtures | mixed — 18 declared observer models | declared per fixture | mixed | release-relative | honest (a boundary for attribution) | regression evidence, not proof |
| `compiler_harness` Redis-reuse / LeftoverLocals | **persistence** (runtime residue) | next tenant / next actor | prior tenant's secret | absolute | honest | source |
| `compiler_harness` wrong-party / wrong-host | **audience** (not a channel) | the authorized recipient is wrong | plaintext, CKKS reveal | release-relative | honest | source |
| `proofs_l2_seabmc` `secret_embedding_index` | uarch (address) | O2 | **user input** | absolute | honest | source |
| `proofs_l2_seabmc` `explicit_error_oracle` | functional | O0 | mixed | **release-relative** | honest | source |
| `fcvd_ct` P1/P2 self-composition | timing | O2 | labelled | absolute | honest **or malicious** | per-program |
| `fcvd_ct` P3/P5 templates and PDL | timing + functional | O2 | any (unlabelled) | **source-relative** | honest **only** | universal over matching programs |
| `formal_verif` A — binsec `-checkct` | timing | O2 | weights | absolute | honest | either (2×2 at `-O0`/`-O2`) |
| `formal_verif` B — cache-line contract | uarch | O3 | weights | absolute | honest | either |
| `formal_verif` C — contract vs silicon | uarch/power | O3/O4 | weights | absolute | n/a (hardware) | hardware |
| `formal_verif` D — MI over wall clock | timing | O1 | weights | absolute | n/a (hardware) | either |
| `leak_check` taint + counts | timing/uarch | O2 (instrument) | weights | absolute | honest | **zero compiler-introduced across 5+ probes** |
| `leak_check` denormal (25×, AUC 1.000) | timing (power mechanism) | O1/O3 | weights | absolute | n/a | **hardware, not compiler** |
| `mlir_leak` `sparse_tensor --sparsification` | uarch (address) | O2/O3 | weights | absolute | honest-but-optimizing | **compiler** |
| CIRCT `--convert-comb-to-arith` | timing (latency) | O2 | weights | absolute | honest | **compiler** |
| HEIR `--convert-secret-extract-to-static-extract` | address → control | O2 | weights | absolute | D4 | **compiler**, and closed downstream |
| onnx-mlir `onnx.Gather` → krnl | uarch (address) | O3 | **user input** | absolute | honest | source (this is what a gather is) |
| `leak_check` `freezing` literal | **persistence** | artifact reader | weights | absolute | honest-but-optimizing | **compiler** |
| `leak_check` AOTInductor exfil | **persistence** | other-UID reader | weights | absolute | honest-but-unsafe-default | **compiler** |
| `leak_check/attacks/early_exit_gpt` | functional + timing | **O0 / O1**, query-budgeted | gate weights | n/a — offensive | n/a | end-to-end extraction, R²=1.000 at 1600 queries |
| `nanoGPT-analysis.claude` | functional + timing | O0 / O1, black-box API | weights (embedding matrix) | n/a — offensive | compiler as *amplifier* | superseded spike |

---

## 8. What this leaves open

1. **Connect `Staging_NI` to the `freezing` result** (§4). The property and its measured instance
   exist in the same repository and do not cite each other. Whether `Staging_NI`'s analysis
   actually fires on an IR shape corresponding to the frozen quantization scale is [inference],
   not measured — and it is a cheap, high-value experiment.
2. **The persistence class has probes but no general verifier for real artifacts.** The freezing
   probe's stated blind spot — constant *buffers* as opposed to inline literals — is
   [hypothesized] and unmeasured; BatchNorm-into-conv folding and folded quantized weight matrices
   are the obvious places to look.
3. **Layer B's granularity vector** (§5). The most concrete engineering item here.
4. **User data as an asset** is two rows. If D2 is a target deployment it needs its own corpus,
   and the one-shot economics mean different kernels matter — gathers and embedding lookups, not
   variable-latency arithmetic on weights.
5. **The malicious-compiler posture** is unmodelled while its motivating paper (Chen et al.,
   arXiv:2509.11173) already sits in `initial`'s related work; until it is, universal template
   proofs should be quoted with the posture attached.
6. **Whether the compiler runs inside the TEE** (D1) is undecided and changes what D1 can claim.
7. **The `power` row is empty everywhere**, and its O1 cell (Hertzbleed/DVFS) undercuts the timing
   row's outward carry.
8. **`fcvd_ct` cannot label secret memory** (§5). Either that changes, or the MLIR-layer verdicts
   get quoted as being about secret indices and scalars rather than about weights.
9. **Only O0/O1 has both a defense and a demonstrated attack.** `leak_check/attacks/early_exit_gpt`
   recovers a secret early-exit gate from latency alone at R²=1.000 in 1600 queries against real
   GPT-2 124M — the repo's only end-to-end validation that a profile is exploitable rather than
   merely present. Every other ring has defenses and instruments but no demonstrated attack, so
   "this leak matters" is argued from the literature (Flush+Reload, controlled-channel, SGX-Step,
   Cache Telepathy, DeepSniffer) rather than shown here. That is a legitimate position; it should
   be a stated one.
10. **[`journal/2026-07-06-two-approaches.siddharth.md`](journal/2026-07-06-two-approaches.siddharth.md)
   is stale.** It records the compiler-introduced quadrant as never having fired and leaves "which
   question is the deliverable" open. The quadrant has since fired three times —
   `sparse_tensor --sparsification`, `freezing`, and the artifact exfil — and two of the three are
   in a class that note's 2×2 could not express. Worth an update rather than a silent
   contradiction.
