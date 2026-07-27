# seabmc_l2 — self-composition unit proofs over the compiler_harness fixtures

Discharging the **L2** level of `prototypes/compiler_harness/mlir/L0_L1_L2_PIPELINE.md`
("a relational witness: equal public inputs and authorized releases, different
secrets, and different observations") with SeaBMC as the engine, instead of
hand-written `.bad.mlir` witnesses.

Status: **working.** Two jobs discharge, each as a calibrated pair — the leaky
fixture yields a counterexample, the repaired one verifies:

| job | channel | bad | fixed |
|---|---|---|---|
| `secret_embedding_index` | address (load) | **sat** | **unsat** |
| `explicit_error_oracle` | declassification | **sat** | **unsat** |

`secret_embedding_index`: both fixtures return the *same* secret-dependent
value, so nothing but the access pattern could produce this separation.

`explicit_error_oracle`: exercises the **`R` premise** of the release-relative
property — the API deliberately releases one bit (padding validity), so that
release appears as a *hypothesis* the two runs are constrained to agree on, and
only surplus distinguishability is a violation. Needs no metadata and no
`--horn-shadow-mem-load-is-def`: plain output equality suffices.

Requires the SeaHorn branch `feat/opsem-read-metadata` (seahorn + sea-dsa) and
`--horn-shadow-mem-load-is-def`. **Read that flag's caveat in
`docs`/the journal note before using it on anything else** — it is opt-in for
correctness reasons, not just cost.

## Layout

Follows the unit-proof layout used in `priyasiddharth/verify-mbedtls`
(`jobs/<name>/{unit_proof,env}/`):

```
jobs/secret_embedding_index/
  env/observation.h                              Obs_Theta: per-element read footprint
  unit_proof/secret_embedding_index_bad_harness.c    expect sat   (leak witness)
  unit_proof/secret_embedding_index_fixed_harness.c  expect unsat (calibration)
jobs/explicit_error_oracle/
  unit_proof/explicit_error_oracle_bad_harness.c     expect sat   (leak witness)
  unit_proof/explicit_error_oracle_fixed_harness.c   expect unsat (calibration)
```

## Validating a job before trusting its verdict

Neither verdict of a pair means anything alone, and a green `unsat` is the easy
way to fool yourself — twice already an `unsat` here meant "the observation is
degenerate" or "the front end discharged the assertion", both of which read
exactly like "verified, no leak". Each job is checked by perturbation:

| job | perturbation | expected | proves |
|---|---|---|---|
| embedding | `assume((s0&15)==(s1&15))` | unsat | witness is caused precisely by index divergence |
| embedding | `assume((s0&15)!=(s1&15))` | sat | and fires whenever it does |
| oracle | `assume(d0==d1)` | unsat | witness is precisely the surplus error detail |
| oracle | drop the `R` premise from **fixed** | sat | `R` is load-bearing, not vacuously true |

That last one guards a failure specific to declassification: if `R` were strong
enough to equate the runs by itself, both harnesses would report `unsat` and the
leaky one would look verified. Also confirm seahorn does not print
"no assertion was found" -- that is a vacuous `unsat`.

The fixtures are `#include`d from `../../../../compiler_harness/c/` rather than
copied, so these proofs track that corpus instead of drifting from it.

## The property

Address-channel non-interference, sequential self-composition: two runs in one
`main` over one shared public table, footprint cleared between them, secrets two
free `nd_u32()` values. The **return value is deliberately excluded** from the
observation — both the bad and the fixed fixture return `table[secret & 15]`, so
only the access pattern separates them.

```
for all public p, secrets s0, s1:  Obs(P,p,s0) == Obs(P,p,s1)
Obs = { i : table[i] was read }        (via sea_reset_read / sea_is_read)
```

Requires the SeaHorn branch `feat/opsem-read-metadata` (seahorn + sea-dsa) and
`--horn-shadow-mem-load-is-def`.

## History: why this took two engine fixes (2026-07-25)

Kept because the failure mode is instructive and the calibration discipline is
what caught it. Originally **both** harnesses reported `unsat` — the leaky one
alone reads exactly like "verified, no leak".

### Superseded: the footprint was not element-precise

Both harnesses report **unsat**. That is not "no leak" — the observation itself
is degenerate. Measured on the bad harness:

| assertion | verdict | reading |
|---|---|---|
| `f0 == 0` | sat | the footprint is non-empty, so stamping does happen |
| `f0 == 0xFFFF` | **unsat** | the footprint is **always all 16 elements** |
| `f0 == f1`, `s0=0`, `s1=8` pinned | unsat | index makes no difference |

So a load at a **secret-dependent (symbolic) address marks the whole object**,
not the element. The observation is `top` for every run, hence trivially equal,
hence unsat for both the leaky and the repaired fixture.

### Root cause: metadata is keyed by the pointer BASE, and only a *constant*
### offset gets folded into it

Metadata addressing drops the pointer's offset field —
`ExtraWideMemManagerCore` passes `ptr.getBase()` to every metadata entry point
(`getMetadata` :683, `setMetadata` :706, both `memsetMetadata` :666/:675 in
`lib/seahorn/BvOpSem2ExtraWideMemMgr.cc`), and `ptrAdd` explicitly keeps the
base fixed while accumulating into the offset ("base, size remain unchanged",
:463). So an object has **one metadata slot**.

The degradation is *conditional*, which is why it is easy to miss. Measured on
an 8-element `uint32_t` array, resetting every element then loading exactly one
(re-confirmed by temporarily restoring the base-keyed code, so it is reproducible
and not an artifact of one probe):

| load | probe | verdict | |
|---|---|---|---|
| `t[0]`, constant index | `is_read(&t[0])` | sat | marked ✓ |
| `t[0]`, constant index | `is_read(&t[1..3,7])` | unsat | clean — **precise** |
| `t[i]`, symbolic, pinned to 2 | `is_read(&t[2])` | sat | marked ✓ |
| `t[i]`, symbolic, pinned to 2 | `is_read(&t[0])` | sat | **marked — collapsed** |

So precision failed exactly in the secret-dependent case the proof depends on.

**Why constant differed from symbolic is not established.** An earlier version of
this note claimed a constant offset is "folded so each element presents a distinct
base"; that is **wrong**. `ExtraWideMemManagerCore::gep` preserves the base and
accumulates into the offset for constant and symbolic indices alike
(`BvOpSem2ExtraWideMemMgr.cc:182`), and instrumenting `metadataPtr` confirms it:
in both cases the base prints as the *same* symbolic value and only the offset
differs (`off=0,4,...,28`). Under base-keying both cases should therefore have
collapsed, yet the constant one reproducibly does not. The mechanism remains
unexplained; do not rely on the constant-index behaviour.

The fix does not depend on that question — keying on base+offset is correct
regardless, and is validated end to end below.

Not a factor, despite first appearances: the 8-byte metadata word
(`g_MetadataBitWidth = 64`) versus 4-byte elements.
`storeAlignedWordToMem` is `array::store(mem, ptr, val)`
(`BvOpSem2MemRepr.hh:69`), an array indexed by the full byte address, so
distinct addresses are independent entries and word width does not affect
precision.

This is sound (it marks a superset of what was read) but useless for
discrimination: it can answer *"was this object read at all"*, not *"which
element"*.

**The calibration pair is what caught this.** The leaky harness alone reports
`unsat`, which reads exactly like "verified, no leak". Never run one of these
without its counterpart.

### The fix

Two changes on `feat/opsem-read-metadata`:

1. **Address-keyed READ metadata.** `ExtraWideMemManagerCore::metadataPtr()`
   now returns `getAddressable(p)` (base+offset) for `MetadataKind::READ` and
   `p.getBase()` for every other kind — so `sea_is_modified` keeps meaning "was
   anything in this object modified" while READ resolves per element.
2. **Always define a MemDef's write register.** A load-as-def whose write
   register was left undefined (the scalar path, `op0 == nullptr`) produced an
   unconstrained memory version, hence spurious counterexamples. It is now
   defined unconditionally — stamped when there is an address, otherwise a
   pass-through copy.

### Resolved: node-gated MemDefs

An earlier version of the flag made **every** load a MemDef, which was both
unsound and slow. Two `verify-c-common` jobs (`hash_table_create`,
`hash_table_put`) silently flipped `unsat` -> **`sat`** — spurious
counterexamples on verified code — and `hash_iter_begin_done2` slowed **18.8x**.

Cause: a MemDef for a node that the interprocedural mod/ref summary classifies
read-only leaves its call sites passing `shadow.mem.arg.ref` (in-only) while a
new memory version exists inside the callee, so the shadow SSA is inconsistent
across the boundary. (Ruled out first, by experiment: the metadata stamp itself
— fails with tracking off, where the stamp is a provable no-op — and COI
pruning, via `--horn-bmc-coi=false`.)

Fix in `ShadowMem.cc`: `computeReadTracked()` records the DSA nodes whose READ
metadata the program actually observes (`sea_is_read`/`sea_reset_read`), and
`visitLoadInst` emits a MemDef only for those. Such a node is additionally
marked **modified** — `n->setModified()` *and* `m_modList` — so the mod/ref
summary matches the defs emitted.

Measured on `verify-c-common` (228 jobs):

| configuration | result | time |
|---|---|---|
| flag off (baseline) | 228/228 | 219.2s |
| flag on, node-gated | **228/228** | **216.4s** |
| flag on, ungated | 223/228, 2 spurious `sat` | 18.8x worst case |

A program that never queries read metadata is now completely unaffected by the
flag — same verdicts, same runtime.

## Open

- [ ] Next job, needing no address channel at all: `explicit_error_oracle` —
      pure output equality under a declassification `assume`.
