# proofs_l2_seabmc — self-composition unit proofs over the compiler_harness fixtures

Discharging the **L2** level of `prototypes/compiler_harness/mlir/L0_L1_L2_PIPELINE.md`
("a relational witness: equal public inputs and authorized releases, different
secrets, and different observations") with SeaBMC as the engine, instead of
hand-written `.bad.mlir` witnesses.

The directory holds **two kinds of property**, both 2-safety, registered by
different functions because their calibration rules differ:

- **non-interference** (`add_l2_job`) — the L2 property above, as a bad/fixed pair;
- **functional equivalence** (`add_equiv_job`) — two implementations of one
  function agree on every input. Not non-interference; see
  [Equivalence proofs](#equivalence-proofs-add_equiv_job).

Status: **working.** Seven non-interference jobs discharge, each as a calibrated
pair — the leaky fixture yields a counterexample, the repaired one verifies:

| job | channel | bad | fixed |
|---|---|---|---|
| `secret_embedding_index` | address (load) | **sat** | **unsat** |
| `explicit_error_oracle` | declassification | **sat** | **unsat** |
| `ckks_unsafe_release` | declassification | **sat** | **unsat** |
| `leftoverlocals_scratch` | value (residue in shared scratch) | **sat** | **unsat** |
| `wrong_party_plaintext` | value (observation scope) | **sat** | **unsat** |
| `breach_compressed_length` | value (length oracle) | **sat** | **unsat** |
| `redis_pool_reuse` | value (cross-tenant response) | **sat** | **unsat** |

plus three equivalence claims over the KyberSlash pair:

| claim | verdict | |
|---|---|---|
| `kyberslash1_equiv` | **unsat** | equivalent over the whole `uint16` domain |
| `kyberslash2_equiv_full` | **sat** | **not** equivalent over `uint16` — see below |
| `kyberslash2_equiv_domain` | **unsat** | equivalent once `c < q` is assumed |

`secret_embedding_index`: both fixtures return the *same* secret-dependent
value, so nothing but the access pattern could produce this separation.

`explicit_error_oracle` and `ckks_unsafe_release`: exercise the **`R` premise**
of the release-relative property — the API deliberately releases something, so
that release appears as a *hypothesis* the two runs are constrained to agree on,
and only surplus distinguishability is a violation. The oracle's `R` is one bit
(padding validity); CKKS's is a function (`ckks_sanitize_model`). Neither needs
metadata or `--horn-shadow-mem-load-is-def`: plain output equality suffices.

Only `secret_embedding_index` requires the SeaHorn branch
`feat/opsem-read-metadata` (seahorn + sea-dsa) and
`--horn-shadow-mem-load-is-def`. **Read that flag's caveat in
`docs`/the journal note before using it on anything else** — it is opt-in for
correctness reasons, not just cost. Every other job runs on a stock build.

## Running

### Quick start

```sh
cd prototypes/proofs_l2_seabmc
cmake -S . -B build -DSEAHORN_ROOT=<seahorn>/build/run   # dir containing bin/sea
ctest --test-dir build --output-on-failure
```

`SEAHORN_ROOT` is the directory holding `bin/sea` — for a source build that is
`<seahorn>/build-rel/run`, **not** the repository root. Expect 19 tests
(7 pairs + 5 equivalence claims and probes) in a few seconds. A successful
configure prints the paths it resolved:

```
-- sea: /path/to/seahorn/build-rel/run/bin/sea
-- sea runtime libs: /path/to/seahorn/deps/yices-2.6.1/lib:/path/to/seahorn/deps/z3-4.8.9/lib
```

### Command reference

```sh
# configure (SEAHORN_ROOT may come from the environment instead of -D)
cmake -S . -B build -DSEAHORN_ROOT=<seahorn>/build/run
SEAHORN_ROOT=<seahorn>/build/run cmake -S . -B build

# run
ctest --test-dir build                       # all of them
ctest --test-dir build --output-on-failure   # show sea's output on failure
ctest --test-dir build -N                    # list tests, run nothing
ctest --test-dir build -R secret_embedding   # one job (regex on test name)
ctest --test-dir build -R _sat_test          # only the leak-witness direction
ctest --test-dir build -R kyberslash         # only the equivalence claims
ctest --test-dir build -R _probe_            # only the reachability probes
ctest --test-dir build -V                    # verbose

# extra sea flags for every proof (as in verify-c-common)
VERIFY_FLAGS="--horn-bmc-coi=false" ctest --test-dir build

# one proof directly, echoing the sea command it runs
python3 build/verify.py --expect=sat -v \
  jobs/explicit_error_oracle/unit_proof/explicit_error_oracle_bad_harness.c

# after adding or editing a job's CMakeLists.txt
cmake -S . -B build          # re-runs configure; ctest alone will not pick it up

# start over
rm -rf build
```

`build/` is gitignored. Building out of tree also works: `cmake -S . -B /tmp/l2`.

### Configure options

| variable | meaning | default |
|---|---|---|
| `SEAHORN_ROOT` | directory containing `bin/sea` | `$ENV{SEAHORN_ROOT}`, else search `PATH` |
| `SEA_LD_LIBRARY_PATH` | where z3/yices live | auto-detected next to the install |
| `SEA_SUBCOMMAND` | sea subcommand | `bpf` |
| `SEA_BASE_FLAGS` | opsem flags common to every proof | see `CMakeLists.txt` |
| `SEA_READ_CHANNEL_FLAGS` | extra flags for address-observing jobs | `--horn-bv2-tracking-mem --horn-shadow-mem-load-is-def` |

CMake bakes the solver paths into the generated `build/verify.py`, so **no
`LD_LIBRARY_PATH` is needed**. Without that, a missing libz3 surfaces as an
unhelpful "error while loading shared libraries" from `seapp` mid-pipeline, far
from the actual cause. Override with `-DSEA_LD_LIBRARY_PATH=...` if the guess
is wrong.

Nothing is compiled by this project: each proof is one C file that `#include`s
its fixture, and `sea` drives clang itself, so the CMake project is
`LANGUAGES NONE` and only registers tests.

### Reading a result

`unsat` = the property holds on all inputs = **no leak**.
`sat` = counterexample = **the leak witness**. So the `_bad` tests expect `sat`
and the `_fixed` tests expect `unsat`; both are pass conditions.

**`verify.py` fails a proof it cannot trust, not just one that mismatches.** If
sea prints any of these, the test fails as `VACUOUS` whatever the verdict was:

| marker | meaning |
|---|---|
| `no assertion was found` | the front end discharged the assertion |
| `Failed to get register` | an unimplemented intrinsic havocs the assertion |
| `Possibly all assertions have been discharged by the front-end` | clang folded the assertion before SeaHorn ran |
| `The program has no main() function` | same cause, other half of the message |

Every one of these produced a convincing false green at some point while these
proofs were being written. The last two were added after `redis_pool_reuse`
tripped them (see [Adding a job](#adding-a-job)) — they had gone unnoticed
because that failure emits *no verdict at all*, which surfaced only as the much
vaguer "sea produced no sat/unsat verdict". Exit codes: `0` matched, `1`
mismatched or vacuous, `2` sea could not run.

### Requirements

`secret_embedding_index` needs a SeaHorn with the **read-metadata channel** —
`sea_is_read` / `sea_reset_read` implemented and `--horn-shadow-mem-load-is-def`
available (seahorn + sea-dsa branch `feat/opsem-read-metadata`). On a stock
SeaHorn the flag is unrecognised and `sea_is_read` is an unimplemented stub that
havocs the assertion, which `verify.py` reports as VACUOUS rather than passing.
`explicit_error_oracle` needs no such support and runs on a stock build.

## Layout

Follows the unit-proof layout used in `priyasiddharth/verify-mbedtls`
(`jobs/<name>/{unit_proof,env}/`):

```
CMakeLists.txt        locates sea, defines the flag sets, registers the jobs
verify.py.in          the test driver (configured into build/verify.py)
jobs/secret_embedding_index/
  CMakeLists.txt                                   registers the pair
  env/observation.h                                Obs_Theta: per-element read footprint
  unit_proof/secret_embedding_index_bad_harness.c    expect sat   (leak witness)
  unit_proof/secret_embedding_index_fixed_harness.c  expect unsat (calibration)
jobs/explicit_error_oracle/
  CMakeLists.txt
  unit_proof/explicit_error_oracle_bad_harness.c     expect sat   (leak witness)
  unit_proof/explicit_error_oracle_fixed_harness.c   expect unsat (calibration)
jobs/{ckks_unsafe_release,leftoverlocals_scratch,wrong_party_plaintext,
      breach_compressed_length,redis_pool_reuse}/    same bad/fixed shape
jobs/kyberslash_equiv/                               equivalence, not L2
  CMakeLists.txt
  unit_proof/kyberslash1_equiv.c                     expect unsat (+ probe)
  unit_proof/kyberslash2_equiv_full.c                expect sat   (counterexample)
  unit_proof/kyberslash2_equiv_domain.c              expect unsat (+ probe)
```

### Adding a job

Create `jobs/<name>/unit_proof/<name>_{bad,fixed}_harness.c`, each `#include`ing
its fixture from `../../../../compiler_harness/c/`, then a `CMakeLists.txt`:

```cmake
add_l2_job(NAME  <name>
           BAD   unit_proof/<name>_bad_harness.c      # must be sat
           FIXED unit_proof/<name>_fixed_harness.c    # must be unsat
           FLAGS ${SEA_READ_CHANNEL_FLAGS})           # only if Obs is an address
```

and `add_subdirectory(jobs/<name>)` at the top level.

**Pairing is enforced at configure time, not by convention.** Omitting `BAD` or
`FIXED` is a hard CMake error, because an `unsat` on its own is
indistinguishable from a proof that checks nothing — a degenerate observation,
or one aimed at the wrong thing, yields `unsat` too. Only the leaky fixture's
`sat` shows the observation can see the leak at all, which is what makes the
repaired fixture's `unsat` informative. A missing harness file is also a
configure error rather than a confusing failure at test time.

If a counterpart genuinely does not exist — some fixtures are `unknown` for want
of an L0 contract rather than repaired — pass
`UNPAIRED_JUSTIFICATION "<why>"`. That configures, but warns loudly, so the
exception is deliberate and visible in the build log.

### Three ways a harness silently stops proving anything

All three were hit while writing the jobs here. None announces itself; each just
returns a verdict that looks fine.

**1. Sharing a public variable between the two runs can let clang fold the
assertion away.** The natural encoding gives both runs the same `p`. If the
fixed fixture returns one of its arguments unchanged, both calls inline to the
*same SSA value*, `r0 == r1` folds to `true` before SeaHorn runs, and `main`
empties out — sea then emits no verdict at all. `redis_pool_reuse` hit exactly
this. The fix is to give each run its own public inputs and relate them with
`assume(b0 == b1)`: `assume` is opaque to clang, so the equality has to be
discharged by the solver. It is also the more faithful encoding, since "equal
public inputs" is a *hypothesis* of the theorem rather than a syntactic
convenience.

**2. `volatile` on a keep-alive sink is load-bearing.** In
`secret_embedding_index`, `g_keepalive` exists so that `seaopt -O3` — which runs
*before* ShadowMem — cannot delete the loads whose addresses are the entire
observation. Measured: with `volatile`, 2 `load i32` survive; with a plain
global sink, **0**; with no sink, **0**. A `volatile` store is an observable
side effect and therefore not dead code, so liveness propagates back through the
loads. Drop the `volatile` as tidying and the leaky fixture quietly returns
`unsat`.

**3. Do not assert on the values a keep-alive sink carries.** In that same job
`r0`/`r1` are the fixtures' return values, and *both* fixtures return
`table[secret & 15]` — a legitimately secret-dependent value. Asserting
`r0 == r1` reports a leak on the **fixed** fixture. The sink consumes them; the
assertion must not.

**Widening the observation is not free either.** Obs is part of the property.
`wrong_party_plaintext` is the clearest case: both fixtures write the plaintext
to `*authorized_mailbox`, correctly, so including it in Obs turns the fixed
direction into a false alarm. Likewise `ckks_unsafe_release` and
`dynamic_kv_length` return a private value in both variants — the return must
stay out of Obs.

## Equivalence proofs (`add_equiv_job`)

A different property with a different calibration rule, so a different function:

```cmake
add_equiv_job(NAME    <name>
              HARNESS unit_proof/<name>.c
              EXPECT  unsat)          # or sat
```

**`EXPECT unsat` automatically registers a reachability probe** — the same
harness recompiled with `-DSEA_PROBE`, expected `sat` — and the harness must
provide that branch:

```c
#ifdef SEA_PROBE
  sassert(f(c) == 0);        /* expect sat: a model exists, f is evaluated */
#else
  sassert(f(c) == g(c));     /* the claim */
#endif
```

This is the equivalence analogue of the bad/fixed pairing rule, aimed at the
failure modes an equivalence proof actually has. An `unsat` is also what you get
from an unsatisfiable `assume` — which makes every claim vacuously true and
which **none of `verify.py`'s vacuity markers catch** — or from calls folded to
constants leaving a trivially true equality. The probe rules out both by
demanding a reachable concrete value. `EXPECT sat` needs no probe: a `sat`
exhibits a reachable trace by construction.

### Why there is no KyberSlash L2 job

KyberSlash's leak is the **latency** of a variable-time `udiv` on a
secret-derived numerator. SeaBMC's opsem models values and memory; a `udiv`
touches no memory, so the read-metadata machinery has nothing to attach to and
the channel is simply not representable. Neither naive formulation works:

- `sassert(r0 == r1)` returns **sat on the fixed fixture too** — `poly_tomsg`
  returns the message bit, which legitimately depends on the secret. A false
  alarm, which `add_l2_job`'s pairing gate would correctly refuse.
- adding the release premise makes Obs *equal* R, so both directions return
  `unsat` — the degenerate observation the vacuity screen exists to catch.

`prototypes/fcvd_ct` models this class properly at the MLIR level (its `latency`
obligation: "operands of `div`/`rem`"), though it has never been pointed at
these fixtures. That is the right home for a KyberSlash leak proof, not here.

### What is provable: the rewrite preserves the function

The obligation the constant-time fix silently incurs. It is not obvious on
paper — the additive constant moves from 1664 to 1665, and `t *= 80635u`
overflows `uint32` for large `c`, which is exactly where a hand argument fails.

`compiler_harness/c/equivalence_driver.c:125-132` checks both pairs by
enumeration over `c ∈ [0, 3329)`, while the parameter is `uint16_t`. Exhaustive
evaluation of the untested range (confirmed natively, not only in the solver):

| pair | mismatches in `[0, q)` | mismatches over full `uint16` |
|---|---|---|
| kyberslash1 | 0 | **0** — equivalent everywhere |
| kyberslash2 | 0 | **49** — first at `c = 13212`, where vuln=0 and fixed=15 |

So **the KyberSlash2 rewrite is equivalent only under `c < q`**, and the driver's
loop bound silently encodes that precondition without stating it — a reader
cannot tell the bound is load-bearing rather than a sampling choice. The
precondition is Kyber's own (coefficients are reduced mod `q` before
compression), so no real call site is affected; what was missing is that nothing
said so.

The `full`/`domain` pair locates the boundary exactly: `full` is `sat`, `domain`
is `unsat`, and together they entail that *every* counterexample has `c ≥ q`
without anyone having to read a model. This also answers
`L0_L1_L2_PIPELINE.md:188-189`, which notes the corpus's finite witnesses "do not
replace a proof over all inputs".

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
| every pair | point the **fixed** harness at the **bad** fixture | sat | the observation can see the leak at all |

That fourth row guards a failure specific to declassification: if `R` were strong
enough to equate the runs by itself, both harnesses would report `unsat` and the
leaky one would look verified.

The last row is the cheap check to run on any new job, and it is the one that
generalises — it is what makes a `unsat` mean "no leak" rather than "nothing was
being watched". All five value-channel jobs were validated this way (each flips
to `sat`); for `ckks_unsafe_release` the perturbed harness must keep including
the *fixed* fixture too, since that is where `ckks_sanitize_model` — the release
policy `R` — lives. Also confirm seahorn prints none of the vacuity markers
listed under [Reading a result](#reading-a-result).

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

- [x] `explicit_error_oracle` — pure output equality under a declassification
      `assume`, no address channel. Done.
- [x] Broaden past the two original jobs — five more value-channel pairs, and
      the KyberSlash equivalence claims. Done.
- [ ] The remaining `compiler_harness` pairs whose channel SeaBMC *can* see:
      `dynamic_kv_length`, `secret_logging_checkpoint`, `wrong_host_fhe_reveal`.
      Same shape as the value-channel jobs here; keep the private return value
      out of Obs for `dynamic_kv_length`.
- [ ] `clangover` and the two `wolfssl` pairs are **out of scope for this
      directory** for the same reason KyberSlash is: their channels are a
      compiler-introduced branch and a helper's operand-dependent latency.
      `prototypes/fcvd_ct` is where those belong.
- [ ] A KyberSlash *leak* proof would need a latency channel in the opsem —
      stamping `udiv`/`urem` operands into an observable accumulator. Feasible,
      but it duplicates what `fcvd_ct` already does at the MLIR level; worth
      doing only if the SeaBMC route is wanted specifically.
