# Compiler harness ↔ SPS rev-4 alignment audit

Generated 2026-07-31 by a 39-agent audit workflow (adversarially verified).
Corpus: `/Users/johnwu/sync-files/obsidian-notes/SPS` · Harness: `prototypes/compiler_harness`
Baseline at time of audit: `make check` = 114 tests, 100 passed, 14 unsupported, 0 failures.

---

# Audit of `prototypes/compiler_harness` against the SPS rev-4 corpus

---

## 1. Verdict on alignment

**The harness is substantially correct and unusually well-disciplined about what it does not claim.** That is the headline, and it should not be buried.

The three-axis result model is honoured everywhere. Nothing in 84 `.test` files asserts `ModelStatus` or `NFConforms`. `contracts/FIXTURE_TIERS.md:7-27` scopes `PreflightV1` to parsing, shape, and non-authoritative scanner behaviour, and every fixture stays inside it. `README.md:8-11` states plainly that the checked-in bitcode is LLVM 17.0.6 *candidate* material, not frozen canonical artifacts. This is exactly the partial-prototype discipline `SPS_Rev4_Normative_Specification.md:4820-4824` demands, and it is honoured better than most shipped conformance suites honour their own rules.

Where I pushed hardest, the harness won. Three high-severity accusations I raised did **not** survive verification: the `sps/Inputs/report-*.json` fixtures are not a smuggled fake `Proved` (they are validator unit-test inputs, and `make check-sps` prints `SKIPPED: … no ModelStatus was computed`); the MEM-04/MEM-05 memory-intrinsic oracles are correct because §10.7's "residual" means *post-normalizer*, not *in the input* (profile `:2399-2402`), and the same pre-normalizer-input pattern is used deliberately by FRZ-02/03 in the same catalogue; and `artifacts/audience-mismatch` does not model a contract-emitted release — `events: ["release-carrier"]` is a `SPS-Harness-Candidate-*` field that `check_harness.py:1323-1328` enforces as a *required* pairing, and nothing reads it as an effect.

But alignment is not the same as coverage, and this is where the honest verdict is harder.

**The harness is aligned with roughly the half of the theory it touches, and silent on the other half.** §21 — 4,413 lines, **47.6% of the normative spec** — has no materialized semantic implementation: the checked-in harness contains no canonical PONF/SMT construction or replay pipeline. Of the 14 `QueryKindV1` members, only `AuditAll` and `HighVariation` are meaningfully exercised by current matchers. Most of the fixed §7 event inventory likewise has no materialized `ConformanceV1` semantic witness; names in a future harness contract are not event execution. The result-arm and reason-class counts below describe the audit baseline and should be read as coverage inventory, not as a claim that an identifier string is absent from every later test fixture.

And the conformance matrix says so itself: `contracts/rev4-conformance-matrix.json` covers NF-A01–A15 and NF-CM01–CM12 with **17 preflight-seed, 9 pending, 1 infrastructure-seed — zero passing**.

So: aligned, honest, and about half-built. The defects below are real but mostly latent; the coverage gaps are the bigger story.

---

## 2. Issues found

Ranked by severity within groups. I have **not** padded severity — several findings that looked critical on first pass are marked low or medium here because the harness's own claim boundary already contains them.

### Group A — Cross-file identifier binding is completely unenforced (highest-impact live defects)

These four are the sharpest findings in the audit, and all four were **reproduced empirically today** by mutating a bundle, repairing the sidecar digest in `artifact.json`, and running `c/check_harness.py artifacts` — which printed `artifacts checks passed`, exit 0, in every case.

**A1 — `dom(M.releaseBindings) = dom(R)` is unenforced; release binding IDs are free text.** *(medium)*
- Harness: `prototypes/compiler_harness/artifacts/*/policy.json` (`release_bindings`); `rg release_bindings` over the whole harness returns hits **only inside `.json` data files** — no tool reads the field. I confirmed this: zero non-JSON consumers.
- Theory: `/Users/johnwu/sync-files/obsidian-notes/SPS/SPS_Rev4_Normative_Specification.md:2697` (WFInputs item 3, `dom(M.releaseBindings)=dom(R)`); failure disposition is `Unknown(ManifestMismatch)` per `SPS_Lecture_Notes/part5-soundness.tex:296-298`.
- Defect: setting `release_bindings` to `["totally_bogus_release_id_not_in_table"]` while the release table declares only `masked_class_v1` passes cleanly. This is also *why* `ManifestMismatch` is one of the 17 zero-coverage reason classes — its precondition cannot be violated in a way the harness notices.
- Fix: add a `WFInputs` binding-completeness pass to `c/check_harness.py` resolving `release_bindings` ⊆ `dom(release-table.entries)`, with a negative arm in `artifacts/interfaces-negative.test`.

**A2 — Release-table `audience` may name an undeclared principal.** *(medium)*
- Harness: `prototypes/compiler_harness/artifacts/audience-mismatch/release-table.json` (`entries[0].audience`).
- Theory: `SPS_Rev4_Normative_Specification.md:2697` (WFInputs item 3); `:1839` conditions `IdentityReleaseOfHigh` on `Audience(q,A)`.
- Defect: `audience = ["mallory"]` — a principal in no `policy.principals` and no coalition — passes. This is the *audience relation the entire `audience-mismatch` bundle exists to teach*, and its domain is unchecked.
- Fix: same pass; require `audience ⊆ policy.principals`.

**A3 — Release-table `footprint` may name an undeclared component.** *(medium)* Same mechanism; `footprint = ["ghost_component"]` passes. WFInputs items 3 and 4.

**A4 — `fixed_observation_model` is a free string; a bundle may declare a different observation profile and pass.** *(medium — cheapest fix, sharpest omission)*
- Harness: `prototypes/compiler_harness/artifacts/*/policy.json` (`fixed_observation_model`); zero non-JSON consumers, confirmed.
- Theory: `SPS_Rev4_Normative_Specification.md:3094` (§7 fixes exactly one profile); `:3096` — "coarsening an event kind is not configuration"; `SPS_Rev4_Metatheory_and_Written_Proofs.md` §1.6 is titled "The one observation profile."
- Defect: `fixed_observation_model = "Theta_something_else"` passes. **Every** `expected-report.json` matcher in the `artifacts/` stratum is conditioned on Θ_ct and nothing binds it.
- Fix: one equality assertion against the single legal constant.

All four survive `artifacts/interfaces-negative.test`, whose eight `CHECK` lines at `:19-26` cover report-row shape, ABI argument typing, and carrier multiplicity — **no cross-file identifier resolution and no observation-model pin**.

### Group B — `check_sps_run_report.py` validates less than it and its README claim

These were originally filed as three separate findings (report-envelope over-claim, coalition-row vacuity, `querySchedule` absence). **They are one defect**, and should be triaged as one: the checker never descends past the top level of the report.

**B1 — Canonicality and field-exactness are enforced only at the top level, so both the failure message and `sps/README.md` are false.** *(medium-high — this is the one genuine live over-claim)*
- Harness: `prototypes/compiler_harness/tools/check_sps_run_report.py:53-55` re-serializes the **parsed dict** with `json.dumps(..., separators=(",",":"))`, which preserves insertion order — so it checks "compact, and the same order as authored," not canonicality. `require_exact_keys` is applied only to the top-level report and to `runEvidence`.
- Theory: `SPS_Rev4_Normative_Specification.md:371-372` — objects contain exactly the fields shown by their schema, in shown order, with no duplicate or unknown fields.
- Defect (reproduced): take `sps/Inputs/report-proved.json`, scramble `querySchedule`'s four schema fields into a different order, and replace `releasePolicyReview` with `{"status":…, "zzz_unknown_field":1, "formatId":"WRONG"}`. Output: `verified 02-branchless-repair: canonical CompletedV1 SPSRunReportV1`, exit 0.
- `prototypes/compiler_harness/sps/README.md:27-28` claims the checker "rejects duplicate, unknown, or reordered report fields." Duplicate rejection *is* recursive (`strict_object` via `object_pairs_hook`); unknown/reordered rejection is top-level only. **The documented scope is not honest here**, which is what raises this above the other checker gaps.
- Fix: recurse `require_exact_keys` over every schema'd nested object; re-canonicalize from a schema-ordered rebuild rather than from parse order.

**B2 — `querySchedule` and `queryResults` interiors are never validated.** *(medium)*
- Harness: `tools/check_sps_run_report.py:147-150` isinstance-checks only that the two are lists.
- Theory: `SPS_Rev4_Normative_Specification.md:4563-4568` (four-field `PublicQueryScheduleV1`, so `{}` is not one); `:4768-4769` — `queryResults` has exactly one row per schedule ordinal in numeric order.
- Defect: all three `sps/Inputs/report-*.json` carry `"querySchedule":{}`, `"queryResults":[]`, `"preflightSummaries":[]` and pass as "canonical CompletedV1 SPSRunReportV1". The success string at `:183` is materially broader than what is checked.
- Fix: validate schedule shape, ordinal-count agreement, and per-ordinal row presence. This is a **precondition for B3 and B4**, which both want to inspect fields inside those objects.

**B3 — `releasePolicyReview` is accepted as a one-field object.** *(medium)*
- Harness: `tools/check_sps_run_report.py:161-163` checks only `releasePolicyReview.status == policyReviewStatus`.
- Theory: `SPS_Rev4_Normative_Specification.md:4613-4623` defines `ReleasePolicyReviewReportV1` as nine fields (formatId, four digests, summands, totals, lints, status); `:4786` makes `Complete` mean `lints=[]` — unverifiable when `lints` is absent.
- Fix: require the nine-field record; assert `lints==[]` for `Complete`. Note the *quantitative* half of §2.4.3 — `ReleasePolicyReviewSummandV1`, `ReleasePolicyReviewTotalV1`, `contributionBits`, `ExactAdmittedMaximum`, `ConservativeDeclaredCap` — has **zero occurrence in the harness**, and that is the part that makes a release review mean anything.

**B4 — The `Findings` axis uses a subset test over `lintClass` only.** *(medium, latent)*
- Harness: `prototypes/compiler_harness/tools/check_sps_run_report.py:106-111` collects only `lint.get("lintClass")` and applies `required <= actual_classes`.
- Theory: `SPS_Rev4_Normative_Specification.md:4786-4788` (`Findings(S)` iff S is *exactly* the lint set); `:4605-4611` makes `coalitionScope` a field of every `ReleasePolicyLintV1`; `:1839` makes `IdentityReleaseOfHigh` fire only when `Audience(q,A) ∧ Class_A(c)=High`.
- Defect (reproduced): a case-04 report whose sole `IdentityReleaseOfHigh` lint carries `coalitionScope = ConcreteCoalition(["owner"])` — illegal, since `secret` is Low for `{owner}` per `SPS_Lecture_Notes/artifacts/common/policy-manifest.logical.yaml:38-41` — **plus** an extra unrequested `CoalitionEntryTotalOverThreshold` lint, exits rc=0.
- **Fix — and this matters:** do **not** implement this by copying scope tuples out of `SPS_Lecture_Notes/artifacts/04-authorized-release-first/expected.logical.yaml`. That file self-declares `normativeInterface: false, checkerProduced: false` at lines 2-4, and the same case's `scenario.logical.yaml:61` states the oracle class-only, exactly as the harness does. The exactness requirement rests on `spec:4786-4788`, so the fix must **derive** the expected lint set from the policy manifest and release table. Mirroring harder from a non-normative teaching YAML reproduces the mirror-is-not-an-oracle problem in B5.
- Latency note: all seven `sps/teaching-*.test:1` are `REQUIRES`-gated and currently `UNSUPPORTED`, so this cannot admit a false result today.

**B5 — The three-coalition oracle rows are a mirror, not an independent oracle.** *(medium, latent)*
- Harness: `prototypes/compiler_harness/tools/check_sps_lecture_cases.py:208-213` compares `integration/Inputs/sps-lecture/cases.json`'s `audit_all_expectations` only against literals hardcoded at `:37-90`. Nothing ever compares them to a report. **(The originally-filed location pointed at this file while the whole failure mechanism is in `check_sps_run_report.py` — triage the pair together or you will edit the wrong file.)**
- Theory: `SPS_Rev4_Normative_Specification.md:4768-4769`.
- Correct characterisation: the rows *are* executed by `integration/sps-lecture-0*.test:5`, so this is a real drift pin — the JSON and the Python are separate artifacts and can disagree. The defect is **non-independence**, not vacuity. When the teaching tests are ungated, a verifier that inverts the `{observer}` row of case 01 while still aggregating to the right `ModelStatus` passes.
- Fix: subsumed by B2 — locate each row's descriptor in `querySchedule` and assert the corresponding `queryResults` row's raw solver result and `QueryDispositionV1`.

### Group C — Fixture defects and conformance-coverage gaps

**C1 — The NF-A08 release wrapper pins four of five Class-B attributes and then declares the set closed.** *(medium)*
- Harness: `prototypes/compiler_harness/mlir/release-carrier/pinned-control/release_carrier_pinned.control.mlir:43` — `passthrough = ["noinline", "nomerge", "noduplicate", "nobuiltin"]`; `:19-22` enumerates four; `:25-26` asserts "The set is closed over exactly the intensional properties the carrier has to preserve"; the CHECK-SAME at `:35` pins the same four.
- Theory: `/Users/johnwu/sync-files/obsidian-notes/SPS/SPS_Rev4_LLVM_Normal_Form_and_Conformance_Profile.md:3185-3186` (NF-A08) and `:1226-1233` (Class B) both list **five**, with `"nooutline"` at `:1230`.
- Defect: `"nooutline"` is missing and the prose claim of closure is affirmatively false. The harness contradicts **itself**: `tools/check_rev4_high_value_fixtures.py:221` requires all five, `:255` makes REL-11 the missing-`"nooutline"` case, and `tools/check_sps_lecture_cases.py:174` requires the literal five-attribute group with failure message "wrapper Class-B attribute set is incomplete."
- **No tooling excuse.** I added `"nooutline"` and round-tripped through `/opt/homebrew/opt/llvm/bin/mlir-opt`; `mlir-translate --mlir-to-llvmir` emits exactly `attributes #0 = { nobuiltin noduplicate noinline nomerge "nooutline" }`.
- **Six sites, not one.** Fix `release_carrier_pinned.control.mlir:19-26,35,43`; `integration/policy-carrier-loss.test:15`; the sed pattern at `integration/release-carrier-inline-survival.test:32`; `FIXTURE_REVIEW_GUIDE.md:423`; `c/release_carrier.c:36-37` and `:45` (which claims "The MLIR fixtures pin the full set" — false); and `c/argmax_release_body.c:56`, which carries only `__attribute__((noinline))` while its lecture source `part3b-examples.tex:1296` pins all five.
- Severity is medium, not high: the fixture is `PreflightV1` (`snapshot.yaml:13,18` — `expect: shape-only`, `sps: not-run`), it is not an input to any rev-4 checker, and the two dependent integration tests measure whether the MLIR inliner honours `noinline`, which stays true with the fifth pin added. Only the framing text and the pinned literals are wrong.
- Worth noting: `SPS_Lecture_Notes/part5-soundness.tex:263-264` already records that "At MLIR level, in the current fixture corpus, no such discipline exists." The teaching layer pre-documented this.

**C2 — Two of three `ModelStatus` aggregation oracles do not implement the blocker-cardinality collapse.** *(medium, currently unexercised)*
- Harness: `prototypes/compiler_harness/tools/artifact_bundle.py:331` unconditionally overwrites `unknown_reason` on every `NotConstructed` row (last-row-wins), and `:345` then requires `model == {"tag":"Unknown","args":[unknown_reason]}` exactly. `prototypes/compiler_harness/c/check_harness.py:961` computes only the tag and `:979` accepts any nonempty subset `model_reasons ⊆ unavailable_reasons`; since `OpenModelObligations` is never a row reason, it rejects the profile-mandated answer while silently accepting a narrower one.
- Theory: `SPS_Rev4_LLVM_Normal_Form_and_Conformance_Profile.md:2907-2909` and `SPS_Rev4_Normative_Specification.md:4192-4196` — if `Blockers={r}` return `Unknown(r)`; if it contains multiple reasons return `Unknown(OpenModelObligations)`.
- `tools/check_rev4_high_value_fixtures.py:321-325` implements it **correctly**, so the three tools disagree with each other.
- Narrowing: `check_harness.py:940` accumulates into a `set`, so bundles whose multiple unavailable rows share one reason class aggregate correctly in all three tools. Divergence requires ≥2 **distinct** classes — a case no checked-in fixture currently exercises.
- Fix: hoist the correct collapse from `check_rev4_high_value_fixtures.py:321-325` into a shared helper used by all three, and add a two-distinct-blocker fixture.

**C3 — `timing_contracts: []` is the absence of the required object, not an instance of it.** *(low-medium)*
- Harness: every `prototypes/compiler_harness/artifacts/*/contracts.json` carries `"timing_contracts": []`. `rg TimingEnvironmentContract` over the harness returns nothing.
- Theory: `SPS_Rev4_Normative_Specification.md:2255-2258` — "An explicit empty contract — with an empty choice domain, occurrence map, latency table, and coupling map — is **required** when no ideal timing choice is modeled."
- The teaching layer already has the correct object: `/Users/johnwu/sync-files/obsidian-notes/SPS/SPS_Lecture_Notes/artifacts/common/timing-environment.logical.yaml`, six fields including `latencyClasses: [latencyClassId: lat.fixed.1]`, with its own note "This is the required explicit empty timing-choice contract." Nothing in the harness mirrors it, so `WFInputs` item 11 (`spec:2723-2725`, latency-class table total on every latency-emitting site) is unexpressible.

**C4 — Normative error-field semantics have no materialized `ConformanceV1` witness.** *(conformance-coverage gap; no current soundness exposure)*
- Boundary: the nine `artifacts/*/abi.json` files are deliberately `SPS-Harness-Candidate-ABI-v1` preflight descriptors, not `ABISchema` objects (`README.md:82-96`; `contracts/FIXTURE_TIERS.md:14-17,29-33,78-85`; `tools/artifact_bundle.py:2-9`). Their seven candidate keys therefore are not six missing normative fields, and promotion requires replacement rather than field retrofit.
- Normative schema: the complete 12-field `ABISchema` is at `spec:578-596`: `abiId`, `targetDataLayout`, `entries`, `carriers`, `namedCarriers`, `outputBindings`, `returnClassBindings`, `terminalOutputOrder`, `contractEventOutputOrder`, `errorFields`, `ubRiskErrorFieldId`, `aliasTopologyBindings`. The six trailing fields are `returnClassBindings` through `aliasTopologyBindings` at `:587-596`; the earlier finding incorrectly substituted `namedCarriers` (`:585`) for `aliasTopologyBindings` (`:596`). `EntryABIV1.declaredErrorFields` is at `:602-609`, `ErrorFieldBindingV1` at `:642-652`, and exact ID/source/encoding obligations at `:828-854`.
- Gap: no materialized conformance fixture binds an application `DeclaredFailure`, the mandatory verifier UB-risk field, policy payload visibility, and the exact error sequences. `mlir/explicit-error-oracle/` is a public-store preflight family (`sps: not-run`), not a formal `Error`-event fixture. Empty candidate `error_visibility` is not what removes an event: under the normative projection, tag/site/occurrence/ID/class remain structural and visibility gates only payload (`spec:3229-3232,3267-3276`).
- Fix: add a harness-namespaced, nonclaimable future-`ConformanceV1` contract plus a feature-gated semantic test; do not modify the nine candidate ABIs.

### Group D — Documentation and hygiene

**D1 — Conformance-matrix record list uses a filename no tool accepts.** *(low)* `prototypes/compiler_harness/contracts/rev4-conformance-matrix.json:10` spells it `manifest.sps.json`; `contracts/FIXTURE_TIERS.md:45`, `mlir/REV4_PREFLIGHT_WORKFLOW.md:88`, and `c/check_harness.py:571` all spell it `sps-manifest.sps.json` (both verified). Two normative-looking checklists in the same directory is the condition under which the first real `ConformanceV1` fixture gets built wrong. One-word rename. The `expected/run-report.matcher.json` entry is **not** a defect — `README.md:37-42` and `FIXTURE_TIERS.md:59-76` both explicitly provide for an `SPS-Harness-*` matcher in a `ConformanceV1` directory.

**D2 — `source_artifact` is declared but never read.** *(low)* `prototypes/compiler_harness/integration/Inputs/sps-lecture/cases.json:474` names the frozen upstream sketch; `rg source_artifact` returns hits only inside `cases.json`. I diffed case 06's mirror against its oracle today — byte-identical bodies, so no live drift — but the binding is unenforced. Reproduced: changing `and i8 %secret, 2` to `and i8 %secret, 1` in the case-06 capture shape still passes `check_sps_lecture_cases.py` and the SHAPE FileCheck. Related: `integration/Inputs/sps-lecture/README.md:14` calls what it checks "the decisive branch/release prefix order," which slightly overstates for case 06, where the order is decisive only together with released-bit/branched-bit disjointness.

**D3 — A countermodel citation names the wrong countermodel.** *(low)* `prototypes/compiler_harness/mlir/release-carrier/lost-bad/release_carrier_lost.bad.mlir:5` cites "Countermodel MT-CM4" and then states the invalid principle "a release is identified by a policy name attached to the operation that publishes it." MT-CM4's actual invalid principle is "local per-template checks determine global trace order" (`SPS_Rev4_Metatheory_and_Written_Proofs.md:88-107`, the closed seven-row table). This is the harness's only MT-CM4 citation, so MT-CM4 currently has **no** witness.

**D4 — `examples/` (7 MLIR files) and `ext/` (16 files, ~500 KB) are never executed.** *(low)* `lit.cfg.py:23` puts `examples` in `config.excludes`; `config.suffixes = [".mlir", ".test"]` at `:18` means `ext/`'s six `st.*.mir` MachineIR dumps and `ext/spillg.ll` are never discovered. `examples/actors/README.md:3-4` nevertheless asserts "They parse and pin shapes" — I ran all seven through `mlir-opt` and all seven parse, so the claim is currently true and silently unpinned. `ext/` is register-allocation spill evidence adjacent to `p4-risk/register-allocation-spill.test` with no test, no README, and no claim-boundary statement — it sits outside every tier in `contracts/FIXTURE_TIERS.md`. Also: `build/memory_effect_observation_examples.mlir` is untracked by git, unreferenced, and contains three §6/§7 memory-effect scenarios no fixture covers.

**D5 — Stale inventory counts.** *(trivial)* `README.md:25` and `sps/README.md:3` both say "seven" `sps/` tests; lit discovers 8.

---

## 3. Tests to add

### 3a. Buildable today — no verifier, no LLVM 22.1.8

**P0 — closes an empirically demonstrated hole**

| Test | Witnesses | Notes |
|---|---|---|
| `contracts/wfinputs-binding-completeness.test` | `spec:2686-2740` (all 14 `WFInputs` conditions), esp. items 3, 4, 10, 11 | **The single highest-value test in this list.** Directly closes A1–A4. Pure Python over `artifacts/*/{policy,abi,contracts,release-table}.json`: resolve every identifier against its declaring table; pin `fixed_observation_model` to the one legal constant; require the explicit empty `TimingEnvironmentContract` (C3). Negative arms for each of the four mutations I reproduced. |
| `contracts/policy-host-visibility-binding-completeness.test` | `spec:3261-3265` (`LocVisible` = ∃h ∈ `EventObservationHostsV1`(event). `HostVisible_M`(h,A), "and no other location rule"); `:3235`; `:3267-3281` | I enumerated the key sets of all nine `artifacts/*/policy.json`: **not one declares a host-visibility basis**, yet `LocVisible` gates the payload half of five of seven Θ_ct projection rows. Every `Proved`/`Counterexample` matcher in `artifacts/` rests on a premise the descriptor cannot express. |
| `sps/report-nested-canonicality.test` + checker extension | `spec:371-372`; `:4563-4568`; `:4613-4623`; `:4768-4769`; `:4786` | Closes B1–B3 in one change: recursive `require_exact_keys`, schedule shape, one-row-per-ordinal, nine-field policy review, `lints==[]` for `Complete`. **Do this before writing the aggregator** so the oracle leads the implementation. |
| `sps/report-nonclaim-arms.test` | `spec:4650-4671`, `:4687-4692` (`ConfigurationRejectedV1`, `ReportingFailedV1`, `disposition: "NoModelStatus"`, six + two closed reason enums) | Zero occurrence of any of these ten identifiers today; `check_sps_run_report.py:133-134` hard-rejects non-`CompletedV1`. Pure JSON. This is the arm carrying the "no `ModelStatus` is issued" rule — the harness's own safety boundary — and it is untested. |
| `contracts/public-reason-classes-order-and-closure.test` | profile `:2772-2823` (closed 48/49-member enumeration in canonical byte order), `:2914-2917` (no extension registry); `spec:8993-9002` | `c/check_harness.py:100-152` stores the list as a **frozenset** — membership is exactly right and in canonical order in the source text, but a frozenset cannot express order or count. Convert to an ordered tuple; assert length and self-sort; negative arm appending a plausible `ReleaseAudienceMismatch`. |
| `tools/countermodel-citation-consistency.test` | `SPS_Rev4_Metatheory_and_Written_Proofs.md:88-107` | Closes D3 and makes the coverage story self-auditing. Scan every fixture and `.test` for `MT-CM<n>` / `NF-(A\|CM)<nn>`; reject identifiers outside the closed ranges; require each MT-CM citation to carry §0.2's invalid-principle string (fails today on the release-carrier file); emit the inverse report of countermodels with zero citing fixtures (currently surfaces MT-CM1 and MT-CM4). |
| `integration/metatheory-cm4-global-trace-order.test` | MT-CM4, `Metatheory:4248-4270`; global-order rule `spec:3301`; `SiteOrderAlignment` `spec:7126` | MT-CM4 has **no faithful witness** (see D3). New C reduction: a secret bit selects between two arms writing the **same two values to the same two public sinks in opposite order**. `grep -c 'store i8' \| FileCheck: 4` proves per-template multiplicity is equal across arms while `Bad_A` is reached at the first aligned event — the exact regression a future per-row event checker needs. |
| `integration/metatheory-cm1-unary-refinement-refusal.test` | MT-CM1, `Metatheory:4165-4196`; A-P4 `:1727`; `spec:92-104`, `:4406-4408` | MT-CM1 has **no witness**; `grep -rn 'MT-CM1\|PairedRefines'` returns nothing. Also gives the deployment axis its **first negative test** — every bundle is *required* to declare `Open` (`tools/artifact_bundle.py:268`, `c/check_harness.py:985-991`) but no fixture shows what an invalid `Closed` looks like, and `artifacts/interfaces-negative.test`'s eight diagnostics include none on that axis. |
| `integration/rev4-retirement-coverage-hole.test` | `SPS_Lecture_Notes/part5-soundness.tex:161-227` | **The most important teaching-layer claim with no fixture.** The lecture's own named, argued soundness-adjacent gap: for any release effectively injective in the secret (hash, MAC, ciphertext), every admitted pair retires at the first release, everything after is outside the theorem, and the verdict is still `Proved`. `:194-206` explains why none of the four coverage queries fires; `:216-219` proposes a per-`(A,e)` retirement statistic that "could ship now." The harness has **zero** occurrence of `retirement`, `sealed`, `havoc`, or `injective`. |
| `integration/rev4-nf-a02-scalar-fp-surface.test` | profile `:3130-3139` (NF-A02); `Metatheory:2487` (Lemma R5.0N); `spec:4849` | `grep -rEn '\b(fadd\|fmul\|fsub\|fdiv\|fcmp\|fneg\|fptrunc\|fpext\|sitofp\|uitofp)\b'` over the entire harness returns **zero hits**. NF-A02 is `pending` with zero seeds. Accepted arm: bit-preserving movement + `fcmp`. Rejected arms: `fadd`, `fptrunc`, `sitofp`. |
| `integration/rev4-nf-cm02-residual-vector.test` and `integration/rev4-nf-a05-vector-scalarization.test` | profile `:3373-3379` (NF-CM02), `:3158-3164` (NF-A05); `ResidualVector` at `:2772-2823` | `grep -rEn '<4 x \|masked\.'` returns **zero hits** — no vector or masked IR anywhere. **Verified on the installed LLVM 17.0.6:** with `-mattr=+avx2` exactly 2 masked intrinsic calls survive `scalarize-masked-mem-intrin`; `opt -passes=scalarizer` leaves `define <4 x i32> @lanewise` intact. NF-A05's criterion is quantitative ("zero vector items"), so the escape-free arm gives it a real zero. |
| `integration/rev4-nf-a06-masked-guarded-lanes.test` | profile `:3166-3173`; `spec:3096`, `:3211` | NF-A06's load-bearing clause is that introduced branch/address events **remain visible to analysis**. Nothing in the harness counts events introduced by a lowering. **Verified today:** generic-triple lowering yields 0 residual masked intrinsics and exactly 8 `br i1` in `@masked` — pin the cardinality, following `integration/bitcode-carrier-survival.test:44-45`. |
| `integration/rev4-nf-a03-cm03-annotation-vs-abi-attribute.test` | profile `:3141-3148` (NF-A03), `:3381-3387` (NF-CM03) | The two halves of one boundary: `nsw`/`inbounds`/`!range`/`nonnull` **may** be weakened; `sret`/`byval`/`inreg`/`signext` **must not**. **Verified today:** both stripped modules verify clean under LLVM 17.0.6 and both byte-differ from the original — so the accept/refuse split cannot come from the verifier and must be an explicit two-class oracle. |
| `integration/rev4-nf-a14-unreachable-cleanup.test` | profile `:3248-3257` | The sharp clause: a CFG-**reachable** block with the same unsupported construct causes the `Unknown` "even if a later semantic query could show its guard infeasible." Nothing pins entry-reachability as the discriminator. **Verified today:** `simplifycfg` takes `freeze i32 poison` count 2 → 1, deletes `dead:`, repairs the PHI. |
| `integration/rev4-nf-a07-analysis-inlining.test` | profile `:3175-3181`; `Metatheory:2273`, `:2349` | NF-A07's load-bearing words are "expands it **without mutating T**." `not cmp %t.bc %t.inlined.bc` (the technique `integration/rev4-high-value-artifact-freeze.test:7` already uses) establishes that IR-mutating inlining cannot be the licensed mechanism. Also the harness's only `Recursion`/`IndirectCall` witnesses — `grep` for both returns nothing outside the reason-class list. |

**P1 — closes a normative gap with no live exposure**

| Test | Witnesses |
|---|---|
| `artifacts/coalition-isolation-and-derivation.test` | `spec:3628-3640` (V1 performs **no** coalition-signature result reuse; a result for one coalition never classifies another), `:557`; `Metatheory:3223-3242` (R6.6), `:1752-1805` (R1.1/R1.2). `artifacts/audience-mismatch`'s `{bob}` row is SAT/CandidateOnly while the **superset** `{alice,bob}` row is UNSAT/Discharged — correct, because the release retires the obligation for the audience — but nothing records *why*. That is the single most likely thing a reviewer "fixes" into a bug. Note `examples/actors/t1_audience_mismatch.mlir` and `t6_downward_closure.mlir` already carry the prose argument; wire them in rather than rewriting them. |
| `integration/rev4-adaptive-sequence-invocation-claim.test` | `spec:4183-4185`, `:4841`; `Metatheory:1714`. All ten `policy.json` declare `SingleInvocation` (verified); `PersistentInvariantEncodingUnsupported` appears only in `check_harness.py`'s allowlist. Three rows exercise the single-blocker precise arm, the cardinality collapse **with** an adaptive claim (which no existing AGG row does), and the claim-driven-not-inferred rule. Executes against real logic today via `check_rev4_high_value_fixtures.py:312-325`. |
| `integration/rev4-release-activation-claims.test` | `spec:1073-1075`, `:1154-1157`, `:9042`, `:9046-9049`, `:4839`; `Metatheory:4334-4360` (MT-CM7 release variant). `ReleaseActivationClaim` is a **total** map with three constructors and four distinct disposition rows; no fixture declares any activation claim. |
| `integration/rev4-expected-variable-assertion-gate.test` | `spec:2921-2928` (the gate fires **iff** the exact triple is named by an identity-bound `expectedVariableAssertion`; **no inference** from name, width, or High classification), `:9022-9025`. AGG-07 covers only the positive half. Rows A and B differ in exactly one field, so a checker that infers from the High class cannot satisfy both. |
| `integration/rev4-nf-a15-timing-lint-independence.test` | profile `:3259-3269`; `spec:3552-3557`, `:4851`. NF-A15's seeds are three artifacts in three different families; the profile wants **both** lint variants for one derived coalition in one fixture. The load-bearing half is a matcher test: two rows identical except for lint presence must have **byte-identical** `expected_model_status` and `expected_deployment_status`. That is the technique that catches a lint leaking into `Blockers`. |
| `integration/rev4-nf-cm05-loop-remainder-split.test` | profile `:3397-3407`, `:2919-2922` (`LoopRemainder` is reserved for an exactly modeled reachable `BoundExhausted` and **never** for an engine-cap remainder, which is `ResourceLimit`). NF-CM05's matrix entry cites only a bundle and carries no gap note, so it reads as covered. |
| `integration/rev4-nf-a09-bound-adequacy-kloop-irrelevance.test` | profile `:3198-3208`; `Metatheory:4197-4223` (MT-CM2), `:2312`. The harness has the refusal side but not the acceptance side, and nothing encodes "the value of `K_loop[L]` supplies no semantic premise" — the exact confusion MT-CM2 exists to refute. The important half is pure Python: two rows differing only in the declared cap must carry byte-identical expectations. |
| Candidate-subsystem negative controls | `SPS_Lecture_Notes/part3a-candidates.tex:840-869` is a 13-row negative-control table backed by `/Users/johnwu/sync-files/obsidian-notes/SPS/SPS_Candidate_Directed_Trace_and_SMT_Framework.md` (956 lines) and a seven-file `01-secret-branch/candidate-search/` bundle. **Zero harness footprint**; `CandidateSearchRecordV1` has zero occurrence. Several rows are cheap MLIR/LLVM shapes: may-alias weak update; rare untraced branch with zero dynamic coverage; divergence-then-reconvergence; opaque SHA-256 release expression. |
| Θ_ct projection mirroring | The seven `latency-intent.logical.yaml` and seven `selected-events.logical.yaml` in the lecture artifacts are **entirely unmirrored**. `01-secret-branch/selected-events.logical.yaml` gives concrete lane inputs (`secret: "00000000"` vs `"00000001"`), a `kind: BranchSuccessor` event at `selectedSequenceIndex: 0`, and `firstDifference.disposition: Bad_A` — a directly pinnable projection oracle. (Incidental drift: the lecture says `entry: fixture.entry`; `cases.json:29` says `"fixture_entry"`.) |

**P2** — `artifacts/nf-a01-pass-trace-and-capture-identity.test`; wiring `examples/` and `ext/` into lit or documenting their exclusion (D4); `p4-risk/` and `diagnostic/` currently draw no findings and no proposals at all — §10 (`spec:3484-3560`) deserves at least an inventory pass.

### 3b. Blocked on the checker

Everything touching §21 — the PONF term language (`spec:5987-6155`), exact allocation identity and byte encoding (`:6156-6433`), guarded-transition/coupling/ledger constraints (`:6434-7682`), query templates (`:7683-8269`), canonical SMT serialization (`:8270-`, `:9203-9255`). Also most of the §7 event inventory, which still lacks materialized `ConformanceV1` semantic witnesses even where a future contract now pins required intent; the mechanism/timing coupling subsystem as a whole (§2.5 `:1863-2144`); and §16/§17 P4 beyond the MT-CM1 shape test.

---

## 4. Readiness to implement

**Verdict: ready-for-a-named-subset.** Not "start building the whole verifier against this harness." Not "not ready" either. The blocker is not specification quality.

### The spec is in better shape than most shipped standards

The transition dispatcher is a closed 25-rule table with an **exhaustive first-match partition** and overlap-or-no-match ⇒ `Unknown(UnsupportedOpcode)` (`spec:6439-6469`, `:6478+`). SMT emission is pinned to the byte — prologue, the full constructor→SMT-head table, a closed-world clause forbidding any other head, `let`, or quantifier, down to LF endings and single inter-token spaces (`spec:9203-9255`). The solver takes **zero options**: `exactSolverOptions` MUST be the empty list (`spec:2576`). The evidence padding macro is written out (`spec:2589-2618`). Reason classes are a closed enumeration with no extension registry (profile `:2772-2823`, `:2914-2917`). Roadmap §6B (`:1197-1292`) closes eight implementation ambiguities on purpose.

Of the 23 modules in `MODULES.md`, **19 are spec-complete**. Two absences are optional for a base-V1 result: the `LatencyClassTableV1` instance (an empty timing environment is legal, `spec:2154-2157`), and Tier F (M19–M23) which may not change a verdict (`MODULES.md:128-130`). **`MODULES.md:186` is stale** — it lists the `SPS-PolicyExpr-NF-v1` grammar as missing; it is fully specified at `spec:1164-1298`, including the closed constructor list, field order, syntax-directed typing with `natWidth(m)=max(1,⌈log₂(m+1)⌉)`, and the `IncreasingIndex`/`LowestIndex` argmax tie rule.

I found exactly **three** genuinely ambiguous points, all narrow: (1) "the more specific stable encoder/solver reason" for `PossibleUB` is not literally single-valued across `spec:3456`/`:4838` and profile `:2894-2912` — pin one reason per fixture, do not accept a set; (2) §15(11)(b) says "return `Unknown(r)`" where r ranges over rich `RestrictedBlockerRecordV1` values (`spec:8963-8969`) while profile `:2907-2909` says the status carries the *class* — project to `reasonClass` only and assert no `restrictedDetail`/`scheduleOrdinal` leaks; (3) solver identity is a free TCB parameter (`spec:2584-2586`). Z3 4.12.4 is installed.

**No open roadmap issue blocks starting.** `SPS_Rev4_Issue_Resolution_and_Research_Roadmap.md:1731-1733`: "Nothing in this section is a premise of a rev-4 Proved result." Every RR-1…RR-12 item sits at promotion stage ≥2 (`:1977-1986`); Stage 0 — Rev-4 baseline is a closed, enumerated work item.

### Hard blockers

**1. LLVM 22.1.8 does not exist on this machine.** `/opt/homebrew/opt/llvm → 17.0.6_1`; `llvm@16` and `llvm@17` are both symlinks to 17.0.6; `llvm-config` is not on PATH. `NFConforms` clause 1 (profile `:1735`) requires the successful **22.1.8** parse; clause 2 (`:1736`) requires the canonical hash from the pinned 22.1.8 writer (`:147`). And `TransitionRuleTableV1.llvmVersion` is the literal `"22.1.8"` (`spec:6441`) **inside the digested table** — so even the transition digest is version-bound. There is no degraded mode. Start this build now, in parallel; it is long-lead and gates all of Tiers B–E.

**2. The harness cannot currently accept a verifier.** Zero `ConformanceV1` fixtures exist — I found zero `artifact-identity.sps.json`, zero `sps-manifest.sps.json`, zero `sps-report.sps.json` on disk. All 84 `.test` files are `PreflightV1`. The conformance matrix is 0-of-27. The roadmap's 96 `ACC-*` acceptance rows (`§8`, `:1347-1612`) have **zero** harness representation — `grep -rho 'ACC-[A-Z0-9.]*'` returns nothing. The seven `sps/teaching-*.test` are permanently `UNSUPPORTED` here because `lit.cfg.py:374` derives the version feature from `llvm-config`, which reports 17.0.6. The harness is *correct* to be preflight-only, but an acceptance suite structurally forbidden from asserting `ModelStatus` is a bring-up gate, not a grader.

**3. The prototypes are not a starting point.** Be blunt about this. `prototypes/sps_scan/src/sps-scan.cpp` is 174 lines — a two-point SSA lattice. `prototypes/initial/lib/Transforms/VerifyNonInterference.cpp` and `prototypes/Staging_NI/lib/VerifyStagingNonInterference.cpp` are single-file MLIR passes. `/Users/johnwu/sync-files/obsidian-notes/SPS/SPS_Confidentiality_IFC_Implementation_Checklist.md:49-51,57-78` already audited all three: no abstract memory, no alias model, **fail-open default labeling**, unmodeled calls, no relational product. There is no Rust and no `Cargo.toml` anywhere in the repo, so `MODULES.md:36-38`'s I2 suggestion (a diagnostic newtype with no conversion into the verdict type) is a greenfield choice, not an existing constraint — which makes it cheap to adopt on day one and expensive to retrofit.

### The M5 normalizer TCB contradiction — resolve it now

The contradiction is real and present at all three citations. `MODULES.md:75` marks M5's TCB column **N**; `:81` says "M5 is the only untrusted module in the system"; `:40` is invariant I3 "The normalizer is untrusted." But profile `:1355-1356` says "The normalizer and its proof obligations remain in the TCB unless separately verified," and `spec:4514` puts "the final weakening pass and exhaustive normal-form auditor" in the model-level TCB. Sharpest form: `MODULES.md:75` defines M5 as the pair (`SPSPreCGPNormalize_v1`, `SPSFinalWeaken_v1`), and `spec:4514` names `SPSFinalWeaken_v1` **specifically**.

**The specification wins**, and `MODULES.md:8-10` concedes it. M5 is in the TCB.

But the two claims are about different failure modes, and the distinction drives implementation order. `MODULES.md` is right about **structural forgery**: M5 cannot forge `NFConforms`, because profile `:1338` says a `FreezeRewriteRecord` "is an audit locator, not an independently checkable proof. The consumer MUST recompute the non-undef/non-poison fact from T"; `:1135-1136` forbids justifying a freeze deletion from an `llvm.assume` or removed metadata; `:1147-1150` forbids `SPSFinalDeadCleanup_v1` using a solver or policy to call a reachable block dead; `:1881` makes incomplete telemetry a refusal; and `NFConforms` clause 6 (`:1744-1748`) re-audits the **residual** module, so `:1054-1055` holds — "Passing a stock LLVM scalarizer is not evidence."

The profile is talking about **semantic preservation**, which nothing checks. Profile `:1345-1348` imposes on M5 that every rewrite preserve functional results and declared visible effects on admitted executions. **No stage validates that.** Alive2 is explicitly disclaimed (`:1353-1355`).

Where a wrong `Proved` actually comes from, precisely: the theorem is about T, and T is also the shipped artifact (§3.5 exact-byte replay into core ISel). If M5 mis-lowers a `llvm.masked.store` under §5.2's table (profile `:1090-1091`) and drops a secret-dependent store, the resulting T is well-formed, the auditor accepts it, SPS proves T safe — and T is what runs. **The proof is not wrong about T.** It is wrong as an answer to the question the user asked, because T silently diverged from what the developer wrote and `-O2` produced. That is an attribution failure, not a soundness failure of the SPS logic, and it is exactly the residue §5.7 keeps in the TCB.

There is a second, sharper channel that I3 specifically closes and the TCB label alone does not: if M6 ever shares a classifier with M5 — the side-effect table in `SPSFinalDeadCleanup_v1` rule 2 (profile `:1144-1145`), or the `isGuaranteedNotToBeUndefOrPoison` producer (`:1322-1324`) — one bug both **produces** non-conformant IR and **blesses** it. That is a genuine wrong-`Proved` path, and it is created by an ordinary, well-intentioned refactor.

Consequences: treat M5 as TCB (no lighter review); **keep I3 anyway**, enforced as a build-graph edge — `Auditor(module, ArtifactIdentity)` with no `&Normalizer` parameter, checked by a CI dependency-cycle test (`MODULES.md:27-28`, `:48-49`); **build M6 before or alongside M5, never after** (writing the auditor second invites reusing the normalizer's classifiers); fund M5's §5.2 metamorphic tests as TCB-grade work (profile `:1051` already requires them); and report the residue — the completion checklist requires the full TCB in the generated report (roadmap `:2103`).

**File a correction:** `MODULES.md:75` should read `Y`; `:81` should say M5 cannot forge `NFConforms` but its §5.7 preservation obligation is unverified and in the TCB; `:186` should drop the M2 grammar from the missing table. `:189` already admits "TCB statement predates M19 and the VBRC validator," so the document knows it is drifting.

### Build order

**Stage 0 (new, prepended).** Build LLVM 22.1.8 from `llvmorg-22.1.8` and pin it. Write `CanonInterfaceJSONV1` and its digest wrapper (`spec:166-197`). Nothing downstream is meaningful without both, and everything after is version-bound through `transitionRuleTableDigest`.

**Stage 1 — Tier A alone** (M1 CoalitionDeriver, M2 PolicyExprEvaluator, M3 SidecarCodec, M4 Aggregator). `MODULES.md:138-143`'s exit criteria, with one correction: the Aggregator criterion says "counterexample-before-Unknown-before-Proved with all reasons retained," which understates it. Add the **cardinality collapse** (0 ⇒ `Proved`, exactly 1 ⇒ that class, ≥2 ⇒ `OpenModelObligations`, `spec:4192-4196`) and a **two-distinct-blocker fixture** — precisely the case C2 shows two of three existing oracles get wrong.

**Stage 2 — M10 integer subset.** `MODULES.md:94-97`'s ~20 opcodes map to 12 of the 25 real rules: `IntBinaryTotalV1`, `IntDivRemPartialV1`, `ShiftPartialV1`, `IntegerCompareV1`, `IntegerCastV1`, `SelectV1`, `GEPV1`, `LoadV1`, `StoreV1`, `BranchV1`, `PhiEdgeAssignmentV1`, `EntryReturnV1`. Correct call.

**Stage 3 — Tier B** (M5–M9). I3 is enforced structurally here or never (above).

**Stage 4 — M13–M16.** **I1 is enforced here or never.** `ReplayEngine` (M16) must be a separate build target with no dependency edge to M13–M15. If you factor a "shared evaluator" out of the encoder and the replayer, replay validates the encoder against itself and `ReplayCovered_A` (`spec:3691-3713`) becomes decoration. This stage produces the first demonstrable result and needs neither timing nor releases.

**Stage 5 — releases** (M9, M18, ledger). **Stage 6 — timing** (needs an authored `LatencyClassTableV1`).

**Tier F (M19–M23): defer entirely.** But bake I2 into the type system on day one.

Scope constraints to accept up front: `AdaptiveSequence` always adds a blocker in V1 (`spec:4183-4185`) — single-invocation only; `DeploymentStatus` is a constant, `P4EvidenceBundle` is "a mathematical metavariable only" and `DeploymentClosed(C,I)` "is not an implementable V1 status constructor" (`spec:4406-4408`) — do not build a P4 validator; and there is **no coalition-signature reuse and no selective-SMT success path** (`spec:3628-3640`, `:4207-4209`) — every (e,A) is built, solved, replayed, and reported independently. That is the dominant cost and there is no approved shortcut.

Design for **digest reproducibility from commit one**. `CanonicalReleaseTableDigest`, `CanonicalPONFDigest`, horizon/transition identities, and `exact_formula_digest` reproducibility is the stage-0→1 promotion condition (roadmap `:1979`). It is a build-system property and cannot be added later.

### Smallest first slice

**Tier A + the aggregator's acceptance suite. No LLVM, no solver, no bitcode.**

1. `CanonInterfaceJSONV1` + digest wrapper (`spec:166-197`) — ~200 lines, fully pinned, and every later digest depends on it.
2. **M4 Aggregator** against the §20 fixture table (`spec:4826-4854`, 21 rows) plus the cardinality collapse, including the two-blocker fixture.
3. **M1** — downward closure including the empty coalition.
4. **M2** — bounded argmax with `IncreasingIndex`/`LowestIndex` (`spec:1280-1282`).
5. **M3** — byte-identical round trip.

Why this slice: it is the only tier a non-compiler engineer can review by hand (`MODULES.md:66-69`), it needs neither blocker, and **the harness can already grade part of it today** — `tools/check_sps_run_report.py` runs ungated and its `REPORT_FIELDS` at lines 13-28 match `spec:4626-4639` field-for-field and in order. That is a real, existing, correct oracle.

Three things to do alongside it:

- **Land the Group A binding-completeness test and the B1–B3 checker extension before writing any module code**, so the oracles lead the implementation rather than trailing it.
- **Author the first `ConformanceV1` fixture directory** — even one, hand-written — so the tier stops being hypothetical. Reconcile D1's filename first.
- **Start the LLVM 22.1.8 build now.**

Stage 1 exit criterion: Tier A lands with the aggregator passing all 21 §20 rows and the cardinality collapse. That gives real signal that the corpus is implementable, without touching a compiler.

---

## 5. What this audit did not cover

**Not read, or read only in passing:**
- §21 in depth — 4,413 lines, 47.6% of the normative spec. I established it has **zero** harness footprint but did not audit the section's internal consistency, the PONF term language, the memory encoding, or the SMT lowering table beyond confirming they are pinned.
- `/Users/johnwu/sync-files/obsidian-notes/SPS/SPS_Candidate_Directed_Trace_and_SMT_Framework.md` (956 lines) — read only enough to confirm the 13-row negative-control table it backs has no harness footprint.
- The `SPS_Rev4_Metatheory_and_Written_Proofs.md` proofs themselves. I verified countermodel statements and lemma **numbering/citations**, not the arguments. R1–R12 soundness was assumed, not checked.
- The roadmap's 96 `ACC-*` rows individually. I confirmed the count and that zero appear in the harness.

**Harness surfaces I inventoried but did not test:**
- `prototypes/compiler_harness/p4-risk/` (6 files) and `prototypes/compiler_harness/diagnostic/` (7 files) — no finding, no proposal. §10 (`spec:3484-3560`) drew zero findings from me; that is an absence of examination, not a clean bill.
- `prototypes/compiler_harness/ext/` — I confirmed the 16 files are never discovered by lit and contain MachineIR spill dumps, but did not analyze what they show.
- The `c/` C-reduction family beyond `release_carrier.c` and `argmax_release_body.c`.
- Whether the nine `artifacts/*/` bundles are *semantically* right. I tested that their identifiers are unenforced (Group A); I did not independently recompute their expected reports.

**Methodological limits:**
- All empirical reproduction ran on **LLVM 17.0.6 and MLIR from `/opt/homebrew/opt/llvm`**. Every "verified today" claim about pass behaviour is a 17.0.6 claim. The normative boundary is 22.1.8 and behaviour may differ.
- I did not run the full `make check` suite to completion, only targeted subsets (`make check-sps`, individual `lit -a` invocations, and direct checker runs).
- Mutation testing was **manual and targeted** — I mutated specific fields I suspected were unbound. A systematic mutation campaign over every sidecar field would likely find more Group A defects; the four I found were the first four I tried.
- No performance, no build-system, no CI-configuration review.
- I did not evaluate whether `PublicReasonClassesV1` in `c/check_harness.py:100-152` has 48 or 49 members against the profile source; I confirmed membership is drift-free and canonically ordered but the exact count is asserted from the frozenset, which is why the P2 test above exists.
---

## Completeness criticism of the audit

I re-walked both trees. The audit is accurate where it looks, but it looked at roughly the surface the harness already advertises. Below: what it never opened, what it never asked about, five new empirically confirmed defects, and the internal inconsistencies among its own findings.

---

## 1. Harness directories and files never examined at all

**`examples/` — 7 MLIR files, zero execution, zero mention in the audit.** `lit.cfg.py:23` puts `"examples"` in `config.excludes`, so `examples/actors/{t1_audience_mismatch,t2_joint_visibility,t5_clearance_violation,t6_downward_closure,t9_placement_incomplete}.mlir` and `examples/integrity/{t3,t4}*.mlir` are never parsed by any test. `examples/actors/README.md:3-4` nevertheless asserts "They parse and pin shapes." I ran all seven through `/opt/homebrew/opt/llvm/bin/mlir-opt`: all seven parse today, so the claim is currently true and silently unpinned — the exact bit-rot posture the audit's D2 objected to for `source_artifact`, in a stratum it never opened. `examples/actors/t1_audience_mismatch.mlir` and `t6_downward_closure.mlir` are also the only places in the tree that spell out the R1/R6.6 coalition-monotonicity argument the audit's `artifacts/coalition-isolation-and-derivation.test` proposal wants to encode — the proposal was written as if that prose did not exist.

**`ext/` — 16 files, ~500 KB, zero mention.** `ext/spill.c`, `ext/spillg.ll`, and six `ext/st.*.mir` MachineIR dumps (`st.greedy.mir`, `st.virtregrewriter.mir`, `st.prologepilog.mir`, `st.stack-slot-coloring.mir`, `st.machine-scheduler.mir`, `st.finalize-isel.mir`) plus two compiled binaries. `config.suffixes = [".mlir", ".test"]` (`lit.cfg.py:18`) means no `.mir` or `.ll` file here is ever discovered. This is register-allocation spill evidence — P4-risk material adjacent to `p4-risk/register-allocation-spill.test` — checked into the repo with no test, no README, and no claim-boundary statement. It is the only MachineIR in the tree and it sits outside every tier in `contracts/FIXTURE_TIERS.md`.

**`build/memory_effect_observation_examples.mlir`** is untracked by git (`git ls-files build/` returns nothing), unreferenced by any test, and lives under a directory `lit.cfg.py:22` excludes. It contains three §6/§7 memory-effect scenarios (`@secret_round_trip`, `@pc_tainted_store`, `@secret_selected_store`) that no fixture covers.

**`p4-risk/` (6 files) and `diagnostic/` (7 files)** get no finding and no proposal in the entire audit. `diagnostic/README.md` and the six diagnostic `.test` files are the harness's §10 stratum; §10 (`spec:3484-3560`) draws zero findings.

---

## 2. Normative sections with zero corresponding finding or proposal

### §21 — 4,413 lines, 47.6% of the normative spec, essentially untouched

`SPS_Rev4_Normative_Specification.md:4862-9274`. I grepped the whole harness (excluding `.venv`/`build`) for `SMT-LIB`, `smtlib`, `QF_`, `declare-fun`, `define-fun`, `sortRegistry`, `canonicalName`, `QueryKindV1` — **zero hits for every one**. `PONF` appears in exactly five files and never outside prose. So §21.2 (PONF term language, `:5987-6155`), §21.3 (exact allocation identity and memory encoding, `:6156-6433`), §21.4 (guarded transition, coupling, ledger constraints, `:6434-7682`), §21.5 (query templates, `:7683-8269`) and §21.6 (canonical serialization, `:8270-`) have no witness of any kind. The audit touches §21 only through `:9022-9049`'s disposition table, in two P1 proposals.

**10 of 14 `QueryKindV1` members (`spec:5397-5411`) have zero occurrence anywhere in the harness**: `ReleaseConformance`, `AdmissionNonempty`, `ReleaseActivation`, `LLVMDefinedness`, `Initialization`, `BoundAdequacy`, `OutputClosure`, `CouplingTotality`, `CouplingFiberTotal`, `CouplingSymmetry`, `CouplingSchedulePreservation`. Only `AuditAll` and `HighVariation` are exercised; `StructuralAlloca` appears once, in a C comment. The audit proposed a test for exactly one of the ten (`ReleaseActivation`).

**23 of 48 `PublicReasonClassesV1` members have zero occurrence in any fixture** (I enumerated all 48 from `c/check_harness.py:100-152` against `artifacts/ mlir/ integration/ contracts/ p4-risk/ sps/ diagnostic/ examples/`). After subtracting the seven the audit's proposals would create, **17 remain with neither a witness nor a proposal**: `ArtifactMismatch`, `ContractReleaseUnsupported`, `CouplingFiberCoverageFailure`, `DiagnosticHealthFailure`, `HorizonDerivationMismatch`, `HorizonDerivationUnsupported`, `ManifestMismatch`, `OutputClosureMismatch`, `PONFIntrinsicUnsupported`, `PublicBoundBindingMismatch`, `ReleaseConformanceMismatch`, `ReleaseConformanceUnknown`, `StableIdentityMismatch`, `ToolInconsistency`, `UnclassifiedAnnotation`, `UnclassifiedIR`, `UnsupportedOpcode`. `check_harness.py:715` validates membership in the closed set, so a fixture *could* name any of them today — the gap is fixtures, not tooling.

### §7 — the fixed observation model has no materialized event semantics

`spec:3094-3307` defines fifteen constructors across §7.1-7.2. The audit previously called this fourteen and then listed thirteen unwitnessed names as twelve. More importantly, raw identifier occurrence was the wrong metric: a harness matcher or future contract is not an executed event semantics. There is still no materialized `ConformanceV1` implementation of the complete fixed inventory, projection, schedules, and global trace order. The new error-event contract pins the intended `DeclaredFailure` and verifier-UB sequences without pretending that this materialization already exists.

### §2.5.1 `TimingEnvironmentContract` — zero footprint, and required non-empty

`spec:2145-2260`. `rg TimingEnvironmentContract` over the harness returns nothing; so does `timing_environment`. `spec:2255-2258` states that "An explicit empty contract—with an empty choice domain, occurrence map, latency table, and coupling map—is **required** when no ideal timing choice is modeled." Every `artifacts/*/contracts.json` carries `"timing_contracts": []` — an empty *list of contracts*, which is the absence of the required explicit empty contract, not an instance of it. The teaching layer already supplies the correct object at `SPS_Lecture_Notes/artifacts/common/timing-environment.logical.yaml` with all six fields including `latencyClasses: [latencyClassId: lat.fixed.1]`, and its own note reads "This is the required explicit empty timing-choice contract." Nothing in the harness mirrors it. `WFInputs` item 11 (`spec:2723-2725`, "the latency-class table is total on every latency-emitting site") is therefore unexpressible.

### §2.5 `MechanismContract` and the entire coupling subsystem

`spec:1863-2144`. `MechanismContract` appears only in `tools/check_rev4_high_value_fixtures.py` and `integration/Inputs/sps-rev4-high-value/cases.json` as a matcher string. Combine with the four zero-coverage `Coupling*` query kinds, the zero-coverage `CouplingFiberCoverageFailure` reason, `A-P4`'s paired coupling (`Metatheory:1727-1749`), and the missing timing contract: **the mechanism/timing coupling subsystem is a coherent, load-bearing cluster with no coverage and no proposal at all**.

### §2.3 error-field semantics — no materialized `ConformanceV1` witness

The nine `artifacts/*/abi.json` files implement a separate, deliberately reduced `SPS-Harness-Candidate-ABI-v1` schema and are not malformed attempts at the 12-field normative `ABISchema` (`spec:578-596`). The real gap is that no materialized conformance bundle yet exercises application `DeclaredFailure`, the mandatory `ubRiskErrorFieldId`, error payload binding/visibility, or the independent closure rows. The new harness-namespaced future contract makes those obligations and their negative mutations executable while remaining `PreflightV1`, `claimable:false`, and `ModelStatus: NotComputed`.

### §16/§17 P4 — one proposal, no objects

`PairedRefines`, `MechanismRefines`, `TimingRefines`, `DeploymentClosed`, `PHT`, `BTI` all have zero occurrence. `P4EvidenceBundle` appears only in `README.md`. The audit's MT-CM1 proposal is the sole coverage attempt for `spec:4213-4500` (288 lines).

### §19 — two of the three `SPSRunReportV1` arms do not exist

`spec:4650-4671` defines `ConfigurationRejectedV1` and `ReportingFailedV1`, each carrying `disposition: "NoModelStatus"` and a closed reason enum (`ConfigurationRejectionReasonV1`, six constructors; `SPSReportingFailureReasonV1`, two). **Zero occurrence of any of these ten identifiers.** `tools/check_sps_run_report.py:133-134` hard-rejects anything that is not `CompletedV1`. This is pure-JSON, buildable today, and it is the arm that carries the load-bearing "no `ModelStatus` is issued" rule (`spec:4687-4692`). Also zero occurrence: `PreflightTriageSummaryV1`, `QueryDescriptorV1`, `PublicQueryScheduleV1`, `ReleasePolicyReviewSummandV1`, `ReleasePolicyReviewTotalV1`, `contributionBits`, `ExactAdmittedMaximum`, `ConservativeDeclaredCap`, `RestrictedEvidenceBundleV1`. The audit's D1 reaches `ReleasePolicyLintV1`'s scope fields but never the *quantitative* half of §2.4.3 — the bit-budget summands and totals — which is the part that makes a release review mean anything.

### §3 `WFInputs` — 14 conditions, one proposal

`spec:2686-2740`. This is the buildable-now class the assignment names, and the audit produced a single proposal against it (host visibility ≈ item 10's "mandatory visibility basis"). See §5 below for four items I falsified empirically.

---

## 3. Lecture `.tex` worked claims with no harness fixture

**`part5-soundness.tex:161-227` — "The coverage hole: retirement."** The teaching layer's own named, argued, *unrecorded-in-the-corpus* soundness-adjacent gap: for any release effectively injective in the secret (hash, MAC, ciphertext), every admitted pair retires at the first release, everything after is outside the theorem, and the verdict is still `Proved`. `:194-206` explains why none of the four coverage queries fires. `:216-219` proposes a remedy that "could ship now": a per-`(A,e)` retirement statistic. The harness has **zero** occurrence of `retirement`, `sealed`, `uninterpreted`, `havoc`, or `injective`; `Retired` appears only in `c/check_harness.py`. This is the single most important teaching-layer claim with no fixture, and the audit's D2 spends its entire length on case 06 — the *same* §12 mechanism — without ever noticing that the lecture flags a coverage collapse in it.

**`part3a-candidates.tex:840-869` — a 13-row negative-control table for the candidate subsystem**, backed by `SPS_Candidate_Directed_Trace_and_SMT_Framework.md` (956 lines) and the seven-file `SPS_Lecture_Notes/artifacts/01-secret-branch/candidate-search/` bundle. Zero harness footprint; `CandidateSearchRecordV1` (`part3a:770`) has zero occurrence. Several rows are cheap MLIR/LLVM shapes (`may-alias store/load → weak update retains every possible writer`; `rare untraced branch → candidate exists with zero dynamic coverage`; `divergence then CFG reconvergence → first control difference remains bad`; `opaque SHA-256 release expression → unsupported V1 policy expression, never authorization`).

**Seven `latency-intent.logical.yaml` + seven `selected-events.logical.yaml` in the lecture artifacts are entirely unmirrored.** `01-secret-branch/selected-events.logical.yaml` gives concrete lane inputs (`secret: "00000000"` vs `"00000001"`), a `kind: BranchSuccessor` event at `selectedSequenceIndex: 0`, and `firstDifference.disposition: Bad_A`. That is a directly pinnable Θ_ct projection oracle and `integration/Inputs/sps-lecture/cases.json` mirrors none of it — it mirrors only `shape_contract`, the three coalition rows, and the status matchers. (Incidental drift: the lecture says `entry: fixture.entry`; `cases.json:29` says `"fixture_entry"`.)

**`part4-inner.tex:322`** gives the *reason* the D6 defect is a defect — `"nooutline"` guards against "call relocated into a fresh function ⇒ site identity gone" — which is exactly the property the MLIR fixture's "closed over exactly the intensional properties the carrier has to preserve" sentence denies needing.

---

## 4. New confirmed defects (all reproduced today)

### N1 — `dom(M.releaseBindings) = dom(R)` is unenforced; the release binding domain is free text
`spec:2697` (WFInputs item 3) requires `dom(M.releaseBindings)=dom(R)`; `part5-soundness.tex:296-298` states its failure is `Unknown(ManifestMismatch)`. **`rg release_bindings` over the whole harness returns hits only in data files — no tool reads the field.** Repro: in a scratch copy I set `artifacts/audience-mismatch/policy.json` `release_bindings` to `["totally_bogus_release_id_not_in_table"]` (the table still declares only `masked_class_v1`), repaired `artifact.json`'s `candidate_sidecar_sha256["policy.json"]`, and `check_harness.py artifacts` printed `artifacts checks passed`, exit 0. Severity: medium. This is also why `ManifestMismatch` is one of the 17 zero-coverage reason classes — its precondition cannot be violated in a way the harness notices.

### N2 — release-table `audience` may name an undeclared principal
Same repro method: `entries[0].audience = ["mallory"]`, digest repaired → `artifacts checks passed`. `mallory` is in no `policy.principals` and no coalition. This is the *audience* relation the whole `artifacts/audience-mismatch` bundle exists to teach (`examples/actors/README.md:11-20`), and its domain is unchecked. WFInputs item 3.

### N3 — release-table `footprint` may name an undeclared component
`entries[0].footprint = ["ghost_component"]` → `artifacts checks passed`. WFInputs items 3 and 4.

### N4 — `fixed_observation_model` is a free string; a bundle may declare a different observation profile and pass
`policy.fixed_observation_model = "Theta_something_else"` → `artifacts checks passed`. §7 (`spec:3094`) fixes exactly one profile, `Metatheory §1.6` is titled "The one observation profile," and `spec:3096` — cited in the audit's own NF-A06 proposal — says coarsening an event kind is not configuration. Every `expected-report.json` matcher in the artifacts stratum is conditioned on Θ_ct and nothing binds it. Cheapest possible fix; sharpest possible omission.

(N1-N4 all survive `artifacts/interfaces-negative.test`, whose eight `CHECK` lines at `:19-26` cover report-row shape, ABI argument typing, and carrier multiplicity — no cross-file identifier resolution and no observation-model pin.)

### N5 — `check_sps_run_report.py` accepts unknown fields and non-schema field order in every nested object, so both its failure message and `sps/README.md` are false
`tools/check_sps_run_report.py:53-55` re-serializes the *parsed* dict with `json.dumps(..., separators=(",",":"))`, which preserves insertion order — so it checks "compact, and the same order as authored," not canonicality. `require_exact_keys` is applied only to the top-level report and `runEvidence`. Repro: I took `sps/Inputs/report-proved.json`, rewrote `querySchedule` with its four schema fields in scrambled order, and replaced `releasePolicyReview` with `{"status":…, "zzz_unknown_field":1, "formatId":"WRONG"}`. Output: `verified 02-branchless-repair: canonical CompletedV1 SPSRunReportV1`, exit 0. `spec:371-372` requires "objects contain exactly the fields shown by their schema, in shown order, with no duplicate or unknown fields." `sps/README.md:27-28` claims the checker "rejects duplicate, unknown, or reordered report fields" — duplicate rejection is recursive (`strict_object` via `object_pairs_hook`), unknown/reordered rejection is top-level only. **This directly refutes the audit's stated ground for downgrading D4 from high to medium**, which was that "`sps/README.md:27-31` accurately enumerates the checker's real scope … the documented scope is honest and only the printed string overreaches."

### N6 — the D6 (`"nooutline"`) defect has two more sites than the audit's expanded list
The audit's verifier note found four (MLIR fixture, `policy-carrier-loss.test:15`, `FIXTURE_REVIEW_GUIDE.md:423`, `c/release_carrier.c:36-37,45`). Add: **`c/argmax_release_body.c:56` carries only `__attribute__((noinline))`**, while `part3b-examples.tex:1296` — the lecture's Example A, which this file is the reduction of — pins `argmax_release` with all five. And the lecture states the five-attribute set in four independent places (`part4-inner.tex:287`, `:322`, `part5-soundness.tex:261`, `part3b-examples.tex:1296`), none of which the audit cited; `part5-soundness.tex:263-264` separately records that "At MLIR level, in the current fixture corpus, **no such discipline exists**," which is the teaching layer pre-documenting the exact defect D6 reports as novel.

---

## 5. Inconsistencies between the confirmed defects

**D5 contradicts itself in one record.** Its `whyItMatters` asserts "cases.json is a mirror of the checker code rather than an independent oracle: **the two cannot disagree**." Its own `verifierNote` then says "the JSON and the Python are separate artifacts and can disagree, so 'the two cannot disagree' is also wrong." The finding as shipped states a claim its own verification retracts, and the `claim` field was rewritten while `whyItMatters` was not.

**D5's `harnessLocation` does not match D5's claim.** It points at `tools/check_sps_lecture_cases.py:208-213`, but the entire claim body, the failure mechanism, and the `suggestedFix` are about `tools/check_sps_run_report.py`. Anyone triaging by location will fix the wrong file.

**D4 and D5 are the same defect.** Both: `check_sps_run_report.py` never validates `querySchedule`/`queryResults`; both cite `spec:4768-4769`; both are demonstrated on the same three `sps/Inputs/report-*.json` stubs with `querySchedule: {}` and `queryResults: []`; D4's fix ("validate field sets, ordinal-count agreement") strictly contains D5's ("locate each `audit_all_expectations` row's descriptor in `querySchedule`"). They differ only in which consequence is foregrounded. They should be one finding; as two they double-count severity.

**D2 is substantially a third copy of D5.** D2's verifier note generalizes to "every AuditAll row in all seven sps-lecture fixtures is a mirrored label rather than a derived result" — which *is* D5's thesis, applied to the same `cases.json`. D2's only surviving distinct content is that `cases.json:474`'s `source_artifact` is declared but never read.

**D1's suggested fix commits the error D5 condemns.** D1 tells the harness to "store the source's per-lint scope tuple … in `cases.json`" and byte-compare — while D1's own verifier note concedes the cited source (`04-authorized-release-first/expected.logical.yaml`) declares `normativeInterface: false, checkerProduced: false`, and that the *other* source (`scenario.logical.yaml:61`) states the oracle class-only, exactly as the harness does. So D1's remedy is "mirror harder from a file the finding itself declares non-authoritative" — the mirror-is-not-an-oracle failure D5 exists to name. If the exactness requirement rests on `spec:4786-4788` (as D1's claim says it does), the fix must derive the lint set from the policy manifest and release table, not copy a teaching YAML.

**D1 and D4 target the same object at adjacent lines and are sequenced backwards.** D1 wants byte-equality over `releasePolicyReview`'s ordered `lints` list; D4 wants `releasePolicyReview` to *be* the nine-field `ReleasePolicyReviewReportV1` (which is what gives it a `lints` field at all). D4 is a precondition for D1. Shipped as independent items, D1 is unimplementable until D4 lands.

**D3 and D6 are consistent with everything else.** No conflicts found there.

---

## 6. Additional proposals, in the order I would build them

1. **`artifacts/binding-resolution-negative.test`** (P0, pure Python, ~1 day). Extend `c/check_harness.py` with cross-file identifier resolution over `WFInputs` items 3/4/10 and add the four negative arms N1-N4 to `artifacts/interfaces-negative.test`'s pattern: undeclared release id, undeclared audience principal, undeclared footprint component, non-`Theta_ct` observation model. Expect `Unknown(ManifestMismatch)` for the first (`part5-soundness.tex:296-298`), giving one of the 17 orphan reason classes its first witness. All four repro'd above; each is a one-line mutation plus a digest repair.
2. **`sps/report-nonstatus-arms.test`** (P0, pure JSON). Three fixtures for `ConfigurationRejectedV1` × two representative `ConfigurationRejectionReasonV1` and one `ReportingFailedV1`, plus a negative arm asserting that a rejection/failure report carrying *any* `modelStatus` field is refused. Requires teaching `check_sps_run_report.py` the union it currently rejects at `:133-134`. Covers `spec:4650-4692`, which today has zero footprint.
3. **`sps/report-canonicality.test`** (P0, pure Python). Fix N5: recursive schema-order and unknown-field rejection, driven by a declared field-order table for `PublicQueryScheduleV1`, `PublicQueryResultRowV1`, `ReleasePolicyReviewReportV1`, `ReleasePolicyLintV1`, `ProtectedEvidenceReferenceV1` (`spec:4556-4639`). Negative arms: scrambled nested order, unknown nested field, duplicate nested key. Subsumes D4's and D1's mechanics and repairs `sps/README.md:27-28`.
4. **`integration/retirement-coverage-collapse.test`** (P0). The lecture's own unrecorded gap. An LLVM fixture whose release is effectively injective in the secret (e.g. a multiply-xor-shift finalizer over the full secret word), with `cases.json` rows asserting that all four coverage queries — `AdmissionNonempty`, pair-domain nonemptiness, `HighVariation`, `ReleaseActivation` — are satisfied *and* that the fixture's expected disposition records near-total retirement. Cites `part5-soundness.tex:161-227` and `spec:3791-3798`. Pairs naturally as the negative control for the audit's case-06 work.
5. **`artifacts/timing-environment-empty-contract.test`** (P1). Give every bundle the explicit empty `TimingEnvironmentContract` `spec:2255-2258` requires (mirroring `SPS_Lecture_Notes/artifacts/common/timing-environment.logical.yaml`), and add a negative arm rejecting `"timing_contracts": []` as *absence* rather than the required empty object. First footprint for §2.5.1.
6. **Future `ConformanceV1` error-event fixture** (P1). Add a new harness-namespaced, nonclaimable contract and a separately feature-gated materialized-verifier test; leave all nine `artifacts/*/abi.json` files unchanged. The positive case binds one application `DeclaredFailure(app.error)`, the mandatory sole `VerifierUBRiskPayloadV1` field, policy payload visibility, and both exact sequences: `Failure -> Error -> Latency -> terminal outputs -> Termination` (`spec:6601`) and `UBRisk -> Failure -> Error -> Termination(UBFailure)` with no ordinary latency/output suffix (`spec:3050-3057`). Negative arms remove or dangle application/UB IDs, violate the exact `declaredErrorFields` set, mismatch payload source/type/encoding, name an undeclared visibility ID, and reorder an event. This is an executable future-materialization contract, not a present semantic witness and not a retrofit of candidate descriptors.
7. **`integration/mtcm7-vacuous-admission.test`** (P1). The primary MT-CM7 form (`Metatheory:4334-4360`): authored preconditions `h=0 ∧ h=1` in `admission_constraints`, expecting `Unknown(VacuousAdmission)` — plus the `WFInputs` item 5 rule that *joint* satisfiability is required and "pairwise satisfiability of individual predicates is insufficient" (`spec:2706-2710`), which nothing checks. MT-CM7 is the only one of the seven required negative results with zero occurrence in the tree; `AGG-06`'s matcher row is not a fixture.
8. **`integration/coupling-query-kinds.test`** (P1). One `MechanismContract` fixture exercising `CouplingTotality`, `CouplingFiberTotal`, `CouplingSymmetry`, `CouplingSchedulePreservation` as scheduled descriptors, with a negative arm producing `Unknown(CouplingFiberCoverageFailure)`. Four query kinds and one reason class, all at zero.
9. **Un-exclude `examples/`** or move it under `docs/`. Either it is checked (drop `"examples"` from `lit.cfg.py:23` and add a parse-only `.test`) or its README should stop claiming it parses. Same call for `ext/` and `build/memory_effect_observation_examples.mlir`.

---

## 7. What I did not examine

I did not read `SPS_Rev4_Issue_Resolution_and_Research_Roadmap.md` (2,113 lines, non-normative), `SPS_Confidentiality_IFC_Implementation_Checklist.md` (587 lines), `SPS_Candidate_Directed_Trace_and_SMT_Framework.md` (956 lines — I established only that it has zero harness footprint), or `MODULES.md`. I did not read `SPS_Rev4_Metatheory_and_Written_Proofs.md` past §9 (R7), so R8-R12 and their boundary sections are unaudited by me. Within §21 I read only the section headers, `21.6`'s opening, and the disposition table — I did not verify any PONF term-language or query-template rule against anything. On the harness side I did not read `mlir/` fixture bodies beyond the release-carrier family, did not read `c/check_harness.py` outside lines 100-160, 700-1000 and 1050-1300, did not read `tools/check_rev4_high_value_fixtures.py` or `tools/artifact_bundle.py` in full, did not open the 78 `artifacts/` files beyond `audience-mismatch` plus a scripted key/value survey of all nine `abi.json`/`policy.json`, and did not verify the audit's D7 (truncated in my input) at all. I ran no lit invocation of the full suite; my four `check_harness.py` repros and the `check_sps_run_report.py` repro were run directly against scratch copies with the harness's own `.venv` interpreter.
---

# Appendix: standalone readiness assessment

I have what I need. Here is the assessment.

---

# Is the rev-4 checker ready to implement?

**Verdict up front: ready-for-a-named-subset.** Not "ready" in the sense of "start building the whole verifier against this harness." Not "not-ready" either — the spec is unusually implementable and there is a real first slice. The blocker is not specification quality; it is that **the harness cannot yet accept a verifier**, and one absolute prerequisite (LLVM 22.1.8) is not installed.

---

## 1. Module-by-module specification status (M1–M23)

I checked each module against the sections MODULES.md cites. Summary: **19 of 23 are spec-complete**, 2 are spec-ambiguous, 2 have a genuinely absent authored artifact — and both absences are optional for a base-V1 result.

### Tier A — pure, no LLVM, no solver

| Module | Status | Evidence |
|---|---|---|
| **M1** `CoalitionDeriver` | **spec-complete** | Downward closure, `Class_A`, `Audience`, visibility monotonicity all defined; `DEF-PAYLOAD-VISIBILITY` at `SPS_Rev4_Normative_Specification.md:552`, monotonicity at `:557`. `Sig_e(A)` exists but is explicitly *unusable* in V1 — spec `:3628` bans coalition-signature reuse, so M1 need not emit it. |
| **M2** `PolicyExprEvaluator` | **spec-complete** — MODULES.md is stale here | MODULES.md:186 lists "the `SPS-PolicyExpr-NF-v1` grammar artifact itself" as missing. It is not missing. Spec `:1164-1176` pins the `SemanticsVersion` closed value; `:1201-1220` gives sorts and roles; `:1228-1259` gives the complete closed constructor list; `:1261-1276` pins every field name *and its order* for `CanonInterfaceJSONV1`; `:1278-1298` gives syntax-directed typing including `natWidth(m)=max(1,ceil(log2(m+1)))`; `:1280-1282` fixes the argmax `IncreasingIndex`/`LowestIndex` tie rule; `:1286-1287` explicitly excludes SHA-256. This is directly codeable. |
| **M3** `SidecarCodec` | **spec-complete** | `CanonInterfaceJSONV1` fully pinned at spec `:166-182` (field order, sorted sets, map-as-sorted-array, minimal decimal naturals, two-lowercase-hex-per-byte, identifier regex `[A-Za-z][A-Za-z0-9._:-]{0,127}`, 64-hex digests, duplicate-key rejection). The global constructor wire rule at `:184-197` removes the last serialization degree of freedom. |
| **M4** `Aggregator` | **spec-complete** | §15 `:4108-4209`. Blocker-cardinality collapse at `:4192-4196`, restated as a map at profile `:2907-2909`. Counterexample precedence `:4186-4191`, anti-manufacture `:4202-4205`, `AdaptiveSequence` rule `:4183-4185`. |

Tier A is the strongest part of the corpus. Four pure functions, zero external dependencies, every canonical byte pinned.

### Tier B — needs LLVM

| Module | Status | Evidence |
|---|---|---|
| **M5** `Normalizer` | **spec-complete, trust status contradictory** (see §6) | §5.1 properties at profile `:1042-1052`; §5.2 vector envelope + lowering table `:1057-1101`; §5.3 nine ordered weakening steps `:1118-1133`; `SPSFinalDeadCleanup_v1` two rules to fixpoint `:1138-1152`; §5.6 freeze `:1304-1341`. |
| **M6** `Auditor` | **spec-complete** | `NFConforms` twelve clauses at profile `:1733-1764`; residual inventory (19 categories) `:1775-1797`; fall-through is `Unknown(UnclassifiedIR)` `:1799-1801`; audit record contents `:1817-1845`. |
| **M7** `FreezeCapture` | **spec-complete but toolchain-blocked** | Profile `:144` `T=Parse_{22.1.8}(B)`; `:147` canonical writer must be the pinned 22.1.8 bitcode writer. Not implementable on the installed toolchain. |
| **M8** `Binder` | **spec-complete** | Profile §4 `:602-1040`; `StableIRBindingTableV1` at spec `:2322`; failure mode fixed at roadmap `:1259-1262` (`Unknown(StableIdentityMismatch)`). |
| **M9** `CarrierAuditor` | **spec-complete** | Profile §4.4 `:991-1039`; NF-A08 five-attribute Class-B pin at `:3185-3187` and `:1226-1233`. |

### Tier C — semantics core

| Module | Status | Evidence |
|---|---|---|
| **M10** `TransitionRules` | **spec-complete** | `TransitionRuleTableV1` at spec `:6439-6469` — 25 literal rule IDs in canonical order — followed by an **exhaustive first-match dispatch partition** at `:6478+`, with overlap-or-no-match = `Unknown(UnsupportedOpcode)`. This is the single largest TCB item and it is fully tabulated, not prose. |
| **M11** `EventEmitter`/`Project_A` | **spec-complete for structure; latency table absent** | Event words fixed at spec `:3168` (control) and `:3190` (aligned-payload); `EventObservationHostsV1` total by constructor `:3235`; `LocVisible` sole location rule `:3261`; the field projection table `:3267-3281`; occurrence convention `:3126`. The **`LatencyClassTableV1` instance** for a real target is absent (MODULES.md:187) — but the schema is at spec `:2153/:2165-2167`, and spec `:2154-2157` makes `pairedChoiceCoupling` the empty map when `occurrences` is empty. **An empty timing environment is legal**, so M11 is implementable without the missing artifact. |
| **M12** `MemoryModel` | **spec-complete** | §21.3 exact allocation identity and byte encoding at spec `:6156-6433`; profile §10 `:2109-2407`. |

### Tier D — encoding and solving

| Module | Status | Evidence |
|---|---|---|
| **M13** `PONFBuilder` | **spec-complete** | §21.1 envelope `:4879-5986`, §21.2 term language `:5987-6155`, §21.4 constraints `:6434-7682`, §21.5 query templates `:7683-8269`. |
| **M14** `SMTLowering` | **spec-complete — byte-deterministic** | Spec `:9203-9255`. Exact prologue (`(set-option :produce-models true)` then `(set-logic QF_AUFBV)`), the full constructor→SMT-head table `:9223-9240`, the closed-world clause `:9242-9245` ("No other SMT-LIB head, indexed operator, `let`, quantifier…"), and `CanonSMTLIB_v1`'s printer rules down to LF endings, one space between head and operand, and a final LF. `exact_formula_digest` at `:9253-9254`. I have rarely seen an SMT emission this tightly pinned. |
| **M15** `SolverDriver` | **spec-complete and unusually easy** | Spec `:2575-2587`: `exactSolverOptions` MUST be the empty list; no flag, tactic, seed, or timeout option is passed. Limits are enforced by an external supervisor from `ResourceLimitsV1`. |
| — | **spec-ambiguous (one point)** | Spec `:2584-2586` leaves solver name/version/build a free TCB parameter ("V1 assumes that build's default `QF_AUFBV` answers are sound"). You must *choose* and pin one; the spec will not choose for you. Z3 4.12.4 is installed. |

### Tier E — adjudication

| Module | Status | Evidence |
|---|---|---|
| **M16** `ReplayEngine` | **spec-complete** | `ReplayCovered_A` five conditions at spec `:3691-3713`; `RULE-REPLAY-COUNTEREXAMPLE` `:3715-3730`; the 14-row `ReplayValidationProfileV1` at `:8657-8691`; external-origin acceptance `:8734-8749`, `:8900-8908`. |
| **M17** `CoverageQueries` | **spec-complete** | `AdmissionNonempty` `:2819-2828`; expected-variable gate `:2921-2928`; `CouplingFiberTotal` as a *logical premise* `:3910-3920`. |
| **M18** `ReleaseConformanceProver` | **spec-complete** | §2.4 six conditions; prefix-causal ledger cases at `:3791-3806`; roadmap 6B.1 closes output construction `:1202-1213`. |

### Tier F — non-authoritative (M19–M23)

All five are **optional for a conforming verifier** (MODULES.md:128-130) and none may change a verdict. **Skip the entire tier for a first implementation.** M19's three §13 theorems are explicitly deferred (MODULES.md:188); the audit-all fallback is the V1 path.

### Spec-ambiguous items — the honest list

Only three, and none is structural:

1. **"the more specific stable encoder/solver reason."** Spec `:3456` and `:4838`/`:4843` permit substituting a more specific reason for `PossibleUB`. Profile `:2894-2912` constrains this to a deterministic map, but the two authorities are not literally single-valued. **Pin one reason per fixture in your acceptance suite; do not accept a set.**
2. **Blocker record → public reason projection.** §15(11)(b) `:4192` says "return `Unknown(r)`" where `r` ranges over rich `RestrictedBlockerRecordV1` values (`:8963-8969`), while profile `:2907-2909` says the status "carries that class." A conforming implementation must project to `reasonClass` only. Assert no `restrictedDetail`/`scheduleOrdinal` leaks.
3. **Solver identity.** Free parameter, see M15 above.

---

## 2. Hard prerequisites, and what exists in this repo

I searched the whole repo (`prototypes/{Staging_NI, compiler_harness, formal_verif, initial, leak_check, mlir_leak, nanoGPT-analysis.claude, proofs_l2_seabmc, sps_scan}`), not just the harness.

| Prerequisite | Substitute? | Exists here? |
|---|---|---|
| **LLVM 22.1.8 (`llvmorg-22.1.8`)** | **None** | **No.** `/opt/homebrew/opt/llvm → 17.0.6_1`; `llvm@16` and `llvm@17` are both symlinks to 17.0.6. `llvm-config` is not even on PATH. `NFConforms` clause 1 (profile `:1735`) requires "the successful LLVM 22.1.8 parse," clause 2 (`:1736`) requires the canonical hash from the pinned 22.1.8 writer (`:147`). `TransitionRuleTableV1.llvmVersion` is the literal `"22.1.8"` (spec `:6441`), and it is inside the digested table — so the transition digest itself is version-bound. There is no degraded mode. |
| **Canonical JSON (`CanonInterfaceJSONV1`)** | None | **Partially.** `tools/check_sps_run_report.py:45-56` enforces compact canonical form + duplicate-key rejection for the *report* only. No general encoder exists. This is ~200 lines of work and is fully specified (spec `:166-197`). |
| **Stable IR binding IDs** | None | **No.** `StableIRBindingTableV1` (spec `:2322`) is unimplemented. Roadmap 6B.6 `:1259-1262` forbids source-location-derived locators. |
| **`ArtifactIdentityV1`** | None | **No.** Zero `artifact-identity.sps.json` on disk (I checked). |
| **`SPSLLVMNFManifest`** | None | **No.** Zero `sps-manifest.sps.json` on disk. |
| **PONF/SMT-LIB lowering** | None | **No.** No PONF builder anywhere in the repo. |
| **A solver** | Any sound QF_AUFBV | **Yes.** Z3 4.12.4 at `/opt/homebrew/bin/z3`. cvc5 absent (wanted for the stage-1 cross-solver gate, roadmap `:1980`). |
| **Independent replay engine** | None — and subject to **I1** | **No.** |
| **Receipt/evidence protection** | None | **No** implementation, but **fully specified**: AES-256-GCM, fresh 256-bit key + 96-bit nonce per bundle, the `PadEvidenceV1(p,L) = UInt64BE(\|p\|) \|\| p \|\| zeros` macro and its `UnpadEvidenceV1` inverse, constant ciphertext length `L` (spec `:2589-2618`). Directly codeable. |

### The prototypes are not a starting point

Be blunt about this. `sps_scan/src/sps-scan.cpp` is **174 lines** — a two-point SSA lattice. `initial/lib/Transforms/VerifyNonInterference.cpp` and `Staging_NI/lib/VerifyStagingNonInterference.cpp` are single-file MLIR passes. The implementation checklist already audited all three and found no abstract memory, no alias model, fail-*open* default labeling, unmodeled calls, and no relational product (`SPS_Confidentiality_IFC_Implementation_Checklist.md:49-51`, `:57-78`). None of them is on the rev-4 architecture. **There is no Rust and no Cargo.toml anywhere in the repo** — so MODULES.md's I2 enforcement suggestion (a `Diagnostic<T>` newtype with no `From` impl into the verdict type, MODULES.md:36-38) is a greenfield choice, not an existing constraint.

### The harness cannot currently accept a verifier — this is the real blocker

The assignment premise is "build the checker **against this harness as the acceptance suite**." That premise does not hold today:

- **Zero `ConformanceV1` fixtures exist.** The tier is defined at `contracts/FIXTURE_TIERS.md:35-57` and reserved at `README.md:37`, but I found zero `artifact-identity.sps.json`, zero `sps-manifest.sps.json`, zero `sps-report.sps.json` on disk. All 84 `.test` files are `PreflightV1`.
- **The conformance matrix is 0-for-27.** `contracts/rev4-conformance-matrix.json` covers NF-A01–A15 and NF-CM01–CM12 with statuses: **17 preflight-seed, 9 pending, 1 infrastructure-seed. None passing.**
- **The 96 `ACC-*` acceptance rows have zero harness representation.** `grep -rho 'ACC-[A-Z0-9.]*'` over the harness returns nothing; the roadmap's §8 matrix (`:1347-1612`) contains 96 rows.
- **The seven `sps/teaching-*.test` files are permanently UNSUPPORTED here.** They carry `REQUIRES: sps-verifier, llvm-22.1.8, sps-teaching-materialized`, and `lit.cfg.py:374` derives the version feature from `llvm-config`, which reports 17.0.6.
- The harness is *correct* to be preflight-only — this is exactly the §20 partial-prototype rule (spec `:4820-4824`), and the discipline is genuinely good. But an acceptance suite that asserts nothing about `ModelStatus` cannot grade a verifier that produces one.

---

## 3. Correct dependency order under I1–I3

MODULES.md §3 (`:138-162`) gives a six-stage order. It is sound. I would make three amendments.

**Stage 0 (new, prepended): toolchain + canonical bytes.** Build LLVM 22.1.8 from `llvmorg-22.1.8` and pin it; write `CanonInterfaceJSONV1` and its digest wrapper. Nothing downstream is meaningful without both. Everything after this is version-bound through `transitionRuleTableDigest` (spec `:6441`).

**Stage 1 — Tier A alone** (M1–M4). Unchanged. Exit criteria at MODULES.md:138-143 are right, with one correction: the `Aggregator` exit criterion says "counterexample-before-`Unknown`-before-`Proved` with all reasons retained," which understates the requirement. Add the **cardinality collapse** (0 → `Proved`, exactly 1 → that class, ≥2 → `OpenModelObligations`, spec `:4192-4196`) and a **two-blocker fixture** that would tempt a "most severe wins" implementation.

**Stage 2 — M10 integer subset.** MODULES.md:94-97 names ~20 opcodes. Against the real table (spec `:6478+`) that maps to `IntBinaryTotalV1`, `IntDivRemPartialV1`, `ShiftPartialV1`, `IntegerCompareV1`, `IntegerCastV1`, `SelectV1`, `GEPV1`, `LoadV1`, `StoreV1`, `BranchV1`, `PhiEdgeAssignmentV1`, `EntryReturnV1` — 12 of 25 rules. Correct call.

**Stage 3 — Tier B** (M5–M9). **I3 is enforced structurally here or never.** M6 takes `(module, ArtifactIdentity)` and no handle to M5 (MODULES.md:48-49). The profile independently mandates the same shape for the one case where it bites: `:1338` — "The consumer MUST recompute the non-undef/non-poison fact from $T$." Make the build graph express this; a code-review convention will not hold.

**Stage 4 — M13–M16, structural guards only.** **I1 is enforced here or never.** `ReplayEngine` (M16) is a separate build target with no dependency edge to M13–M15, checked by a CI cycle test (MODULES.md:27-28). If you factor a "shared evaluator" out of the encoder and the replayer, replay validates the encoder against itself and `ReplayCovered_A` (spec `:3691-3713`) becomes decoration. This is the stage that produces the first demonstrable result and it needs neither latency nor releases.

**Stage 5 — releases** (M9, M18, ledger). **Stage 6 — timing** (needs an authored `LatencyClassTableV1`).

**Tier F (M19–M23): defer entirely.** But bake **I2** into the type system on day one — a diagnostic type with no conversion into `ModelStatus` (MODULES.md:36-38). Retrofitting I2 after M20 exists is how a Tier F module quietly acquires a vote.

---

## 4. Do any open roadmap issues block an implementation started now?

**No.** This is the cleanest finding in the assessment, and it cuts in favor of starting.

`SPS_Rev4_Issue_Resolution_and_Research_Roadmap.md:1731-1733` states it directly: "Nothing in this section is a premise of a rev-4 Proved result. A research track becomes normative only through a future versioned specification…" Every `RR-1` … `RR-12` item (general pc, phi-gated slicing, affine coverage, relational summaries, arbitrary LLVM profiles, probabilistic timing) sits at **promotion stage 2 or later** (`:1977-1986`). **Stage 0 — Rev-4 baseline** (`:1979`) is a closed, enumerated work item.

Better still, roadmap §6B (`:1197-1292`) exists specifically to close implementation ambiguities, and it closes eight of them: output construction (6B.1), the coupling-filter ban (6B.2), the host-visible/P4 boundary (6B.3), closed instruction semantics (6B.4), deterministic allocation-free contracts (6B.5), stable identity and one finite expansion (6B.6), concrete-coalitions-only (6B.7), and protected evidence (6B.8).

Three items constrain **scope**, not viability:
- **`AdaptiveSequence` is unsupported in V1** — always adds `PersistentInvariantEncodingUnsupported` (spec `:4183-4185`). Single-invocation only.
- **`DeploymentStatus` is a constant.** Base V1 must return `Open(P4EvidenceProfileUnavailable)`; `P4EvidenceBundle` is "a mathematical metavariable only" and `DeploymentClosed(C,I)` "is not an implementable V1 status constructor" (spec `:4406-4408`). Do not build a P4 validator.
- **No selective-SMT success path** (spec `:4207-4209`) and **no coalition-signature reuse** (`:4152-4154`, roadmap 6B.7). Every `(e,A)` is built, solved, replayed, and reported independently. Budget for this: it is the dominant cost and there is no approved shortcut.

The one thing that will bite: the **rev-4 completion checklist** (`:2048-2109`) has ~24 boxes, and reproducibility of `CanonicalReleaseTableDigest`, `CanonicalPONFDigest`, horizon/transition identities, and `exact_formula_digest` is the stage-0→1 promotion condition (`:1979`). Digest reproducibility is a *build-system* property. Design for it from commit one; it cannot be added later.

---

## 5. The M5 normalizer TCB contradiction

**The contradiction is real and still present at all three citations.** I verified each verbatim.

- **MODULES.md:75** — the M5 row's TCB column is `**N**`.
- **MODULES.md:81** — "M5 is the only untrusted module in the system. That is deliberate: a normalizer bug becomes a refusal at M6 rather than a false proof."
- **MODULES.md:40** — invariant **I3**, "The normalizer is untrusted."
- **Profile `:1355-1356`** (§5.7) — "The normalizer and its proof obligations remain in the TCB unless separately verified."
- **Spec `:4514`** (§18) — the model-level TCB includes "the final weakening pass and exhaustive normal-form auditor."

Note the sharpest form of it: MODULES.md:75 defines M5 as the pair (`SPSPreCGPNormalize_v1`, `SPSFinalWeaken_v1`). Spec `:4514` names **`SPSFinalWeaken_v1` specifically** as TCB. So M5 is not merely disputed — half of it is named in the normative TCB list while the row is marked untrusted.

### Which authority wins

The specification, unambiguously — and MODULES.md concedes it in its own preamble: "Nothing here is normative… where this document and the normative specification disagree, the specification controls" (MODULES.md:8-10). **M5 is in the TCB.**

### But the two claims are about different failure modes, and the distinction is what matters for implementation

MODULES.md's claim is true for **structural forgery**, and the profile supplies the mechanisms that make it true:

- The only semantically dangerous rewrite, `freeze(x) → x`, requires an independently recomputed fact: profile `:1338` — "The record is an audit locator, not an independently checkable proof. The consumer MUST recompute the non-undef/non-poison fact from $T$." A `FreezeRewriteRecord` is a *locator*, never evidence.
- Profile `:1135-1136` forbids the normalizer from using an `llvm.assume`, removed metadata, or a removed attribute to justify a freeze deletion.
- `SPSFinalDeadCleanup_v1` may not use a solver, policy classification, admission precondition, future release, or product invariant to call a CFG-reachable block dead (profile `:1147-1150`).
- Missing or incomplete normalizer telemetry is `Unknown(NormalizerMismatch)` (profile `:1881`) — a refusal.
- `NFConforms` clause 6 (profile `:1744-1748`) re-audits the *residual* module, so profile `:1054-1055` holds: "Passing a stock LLVM scalarizer is not evidence that the module is in normal form. Conformance depends on the residual audit."

**M5 therefore cannot forge `NFConforms`.** MODULES.md is right about that.

The profile's claim is about **semantic preservation**, which nothing in the pipeline checks. Profile `:1345-1348` imposes on M5: "For any admitted execution on which the pre-normalized module is defined, every normalizer rewrite MUST preserve its functional result and declared externally visible effects." **No stage validates that obligation.** NF-A01 checks exact byte replay of frozen `T` into core ISel — it does not check `S → T` refinement. Alive2 is explicitly disclaimed as insufficient: "It is not a blanket proof for this profile, particularly for interprocedural, memory, masked CFG, or ABI transformations" (profile `:1353-1355`).

### Where a wrong `Proved` could actually come from

Precisely here, and it is worth being exact because the failure is subtle:

The theorem is about `T`, and `T` is also the shipped artifact (§3.5 exact-byte replay into core ISel). So if M5 mis-lowers a `llvm.masked.store` under §5.2's table (profile `:1090-1091`) and drops a secret-dependent store, the resulting `T` is well-formed, the auditor accepts it, SPS proves `T` safe — and `T` is what runs. The proof is **not wrong about `T`**.

It is wrong as an answer to the question the user asked. `T` is no longer the program the developer wrote and `-O2` produced. The `Proved` is a true statement about an artifact that silently diverged from its source. That is an **attribution failure, not a soundness failure of the SPS logic** — and it is exactly the residue §5.7 keeps in the TCB.

There is a second, sharper path MODULES.md's I3 is *specifically* designed to close, and it must be closed in the build graph: if M6 ever shares a classifier with M5 — the side-effect table in `SPSFinalDeadCleanup_v1` rule 2 (profile `:1144-1145`), or the `isGuaranteedNotToBeUndefOrPoison` producer (profile `:1322-1324`) — then one bug both **produces** non-conformant IR and **blesses** it. That is a genuine wrong-`Proved` channel, and it is created by an ordinary, well-intentioned refactor.

### What this means for implementation order

1. **Treat M5 as TCB.** Spec `:4514` controls. Do not let MODULES.md's `N` justify lighter review, weaker tests, or an unaudited contributor.
2. **Keep I3 anyway.** It is not redundant. It is independently mandated by profile `:1338` and it closes the shared-classifier channel that the TCB label alone does not. `Auditor(module, ArtifactIdentity)` — no `&Normalizer` parameter, enforced by a CI dependency-cycle check, per MODULES.md:27-28 and :48-49.
3. **Build M6 before, or in parallel with, M5 — never after.** Writing the auditor second invites reusing the normalizer's classifiers "since they already exist."
4. **Fund M5's §5.2 metamorphic tests as TCB-grade work.** Profile `:1051` already requires "positive, negative, and metamorphic tests." The vector-lowering table and `SPSFinalDeadCleanup_v1` are where an undetectable divergence lives, because their input is the one object never re-audited.
5. **Report the residue.** The completion checklist requires "The complete TCB and all open P4 obligations are in the generated report" (roadmap `:2103`). The unverified §5.7 preservation obligation belongs in that TCB statement explicitly.

**Correction worth filing:** MODULES.md:75 should read `Y`, MODULES.md:81 should be rewritten to say M5 cannot forge `NFConforms` but its §5.7 preservation obligation is unverified and in the TCB, and MODULES.md:186 should drop the M2 grammar from the "missing" table — the grammar is fully specified at spec `:1164-1298`. MODULES.md:189 already flags that "TCB statement predates M19 and the VBRC validator," so the document knows it is drifting.

---

## 6. Verdict

**Ready-for-a-named-subset.**

The specification is, genuinely, in better shape than most shipped standards. The transition dispatcher is a closed table with an exhaustive first-match partition (spec `:6478+`). The SMT emission is pinned to the byte, down to line endings and inter-token spaces (spec `:9245-9250`). The solver takes **zero options** (spec `:2576`). The evidence padding macro is written out (spec `:2608-2610`). Reason classes are a closed 49-member list with no extension registry (profile `:2772-2823`, `:2914-2917`). Roadmap §6B closes eight implementation ambiguities on purpose. I found only three genuinely ambiguous points, all narrow.

### The single biggest blocker

**Not the spec. The acceptance suite.** The harness has 84 tests, every one `PreflightV1`; zero `ConformanceV1` fixtures; a conformance matrix that is 0-of-27; and zero of the roadmap's 96 `ACC-*` rows represented. You cannot build a verifier against an acceptance suite that is structurally forbidden from asserting `ModelStatus` or `NFConforms`. The harness is *correctly* preflight-only — spec `:4820-4824` is exactly the rule it is honoring — but that makes it a bring-up gate, not a grader.

**Second blocker, and it gates everything:** LLVM 22.1.8 does not exist on this machine (17.0.6 only, `llvm-config` not on PATH). `NFConforms` clauses 1–2 have no substitute, and `"22.1.8"` is inside the digested `TransitionRuleTableV1` (spec `:6441`), so even the transition-table digest is version-bound.

### Smallest first slice that produces real signal

**Tier A + the aggregator's acceptance suite. No LLVM, no solver, no bitcode.**

1. `CanonInterfaceJSONV1` + digest wrapper (spec `:166-197`). ~200 lines, fully pinned, and every later digest depends on it.
2. **M4 `Aggregator`** against the §20 fixture table (spec `:4826-4854`, 21 rows) plus the blocker-cardinality collapse (`:4192-4196`) — including a **two-blocker fixture** that a "most severe wins" implementation fails.
3. **M1 `CoalitionDeriver`** — downward closure including the empty coalition.
4. **M2 `PolicyExprEvaluator`** — bounded argmax, `IncreasingIndex`/`LowestIndex` (spec `:1280-1282`).
5. **M3 `SidecarCodec`** — byte-identical round trip.

Why this slice: it is the only tier a non-compiler engineer can review by hand (MODULES.md:66-69), it needs neither of the two blockers, and **the harness can already grade part of it today** — `tools/check_sps_run_report.py` runs ungated and its `REPORT_FIELDS` at lines 13-28 match spec `:4626-4639` field-for-field and in order. That is a real, existing, correct oracle.

Do these three things alongside it:

- **Extend `check_sps_run_report.py` before writing the aggregator**, so the oracle leads the implementation. It currently never validates that an `Unknown` `reasonClassId` is a member of the 49-string `PublicReasonClassesV1`, never checks the query scope matrix or `queryScheduleDigest == SHA256(CanonInterfaceJSONV1(schedule))`, never checks one-result-row-per-ordinal, and never asserts that a `Proved` report still carries `Open(P4EvidenceProfileUnavailable)`. Its three fixtures pass with `querySchedule: {}` and `queryResults: []`.
- **Author the first `ConformanceV1` fixture directory** — even one, even hand-written — so the tier stops being hypothetical. Note the record list in `contracts/rev4-conformance-matrix.json:10` says `manifest.sps.json` while `contracts/FIXTURE_TIERS.md:45` says `sps-manifest.sps.json`; reconcile that before anyone builds to the wrong list.
- **Start the LLVM 22.1.8 build now, in parallel.** It is long-lead and nothing in Tier B, C, D, or E can be validated without it.

Stage 1 exit criterion should be MODULES.md:138-143's, amended as in §3 above. If Tier A lands with the aggregator passing all 21 §20 rows and the cardinality collapse, you will have real signal that the corpus is implementable — and you will have it without touching a compiler.
