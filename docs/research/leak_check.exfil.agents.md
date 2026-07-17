# Artifact exfiltration: AOTInductor persists secret weights to a shared, other-readable file

Companion to the `leak_check` prototype. This is an **artifact-exfiltration** result
(direct persistence to disk), not a side channel. The secret is the model weights.

Code: `prototypes/leak_check/probe_exfil.py`, `prototypes/leak_check/tests/test_exfil.py`.
Raw evidence: `prototypes/leak_check/probe_exfil.out`.

    cd prototypes/leak_check && uv run python probe_exfil.py   # -> probe_exfil.out

## Config point (PRINCIPLES §2)

One config point, and not Siddarth's or the count-confound note's:

- **torch 2.13.0+cu130** (CPU path), **Python 3.14.0**, Arch Linux
  (`Linux-7.1.3-arch1-2-x86_64-with-glibc2.43`).
- **umask 0022** (the process umask at run time; this matters, see §4).
- AOTInductor (`torch._inductor.aoti_compile_and_package`) **present**.
- Single-user host; `/tmp` is `0o777`, `/tmp/torchinductor_q` is `0o755`.

Nothing here establishes behavior on other torch versions, other OSes, or a
different umask.

## Summary

At this config point, `aoti_compile_and_package` bakes the raw weight bytes into a
content-addressed shared object (`*.wrapper.so`) and places it in torch's default
inductor cache dir, `/tmp/torchinductor_<user>/`, at mode **0o755**
(owner rwx, group r-x, **other r-x**). Every directory on the path from that file up
to `/tmp` is other-traversable (`0o755`, `0o755`, `0o777`). The file **persists after
the compiling process exits** — the probe scans only after the child process is dead.
So on a shared host any other local user can read the file and recover the weights.

Plain `torch.compile` (Inductor kernel cache) persists **none** of the weight bytes —
its weights are runtime inputs, not baked constants.

The probe fills a `Linear(64,64)` weight with four greppable byte sentinels
(`b"LEAK"`, `b"W3IG"`, `b"\xde\xad\xbe\xef"`, and the float `1234567.0`), compiles,
then searches every file under the cache dir for each sentinel's exact 32-byte run.

## 1. What persists, and what does not (measured)

From `probe_exfil.out`:

| build | artifact | weight bytes present? | mode |
|---|---|---|---|
| `torch.compile` (Inductor) | kernel cache files | **no** | — |
| AOTInductor | `*.wrapper.so` in cache dir | **yes** (all 4 sentinels) | **0o755** |
| AOTInductor | `.pt2` package (user-chosen path) | yes (all 4 sentinels) | 0o644 |

The `.wrapper.so` is the finding. It is placed by the **compiler** in the inductor
cache dir; the probe writes the `.pt2` package to a *separate* private directory, and
the `.wrapper.so` still appears in the cache dir, so its presence is not an artifact of
where the package was pointed. The sentinel bytes are recovered verbatim from it
(`recovered[ascii_LEAK] = b'LEAKLEAKLEAKLEAK'`).

The `.pt2` package containing the weights is **expected** — a package format holds its
own weights — and its location is the user's choice; it is recorded for completeness,
not as the finding. (It, too, is `0o644` by umask, so a user who saves a package under a
shared path exposes it; that is a usage question, not compiler behavior.)

`TORCHINDUCTOR_FORCE_DISABLE_CACHES=1` does **not** suppress the `.wrapper.so`: the
"caches disabled" pass writes and leaves the same weight-bearing `0o755` file.

## 2. The full exposure chain (measured)

The "default SHARED cache dir" pass compiles into the real `/tmp/torchinductor_q` and
reports the ancestor modes of the newly-created `.wrapper.so`:

```
NEW HIT mode=0o755 group=r other=r  /tmp/torchinductor_q/<hash>/<hash>.wrapper.so
    dir 0o755 /tmp/torchinductor_q/<hash>
    dir 0o755 /tmp/torchinductor_q
    dir 0o777 /tmp
```

Every component is readable/traversable by other. (The probe removes the sentinel-bearing
files it created in shared `/tmp` afterward, for hygiene; persistence is already
established by the scan running after the child exited.)

## 3. Controls (PRINCIPLES §5, measured)

```
positive (0644 sentinel file): detected = True    (want True)
negative (random bytes):       detected = False   (want False)
```

The 32-byte needle makes a coincidental match ~2^-256; the negative control confirms no
false positive on random content. `tests/test_exfil.py` re-checks the detector logic
(controls, sentinel round-trip, mode decoding, ancestor walk) without a compile, in ms.

## 4. Threat model (crisp)

- **Who can read it:** any local principal that is not the owning user — a different
  UID on a shared host, a co-tenant, a compromised low-privilege service. No elevated
  access is needed; the file and its whole directory chain are other-readable.
- **What they get:** the model's weight tensor bytes, baked as constants into the
  `.so`. `objdump`/`grep`/`strings` recovers them; no reverse engineering of a format is
  required for the raw floats.
- **When / how long:** from the moment the compile writes the `.so` until `/tmp` is
  cleared (reboot, `tmpreaper`, manual cleanup). The file is a **content-addressed cache
  entry**, intended to persist and be reused across runs, so the window is long, not
  transient.

**Important scoping caveat (measured).** The `0o755`/`0o644` modes are the process
**umask** (`0o022` here) applied to the compiler's file creation. The compiler does
**not** tighten these to `0o600`. Under a hardened `umask 0077` the same files would be
`0o700`/`0o600` and **not** other-readable — the directory would still be shared, but the
files would not be world-readable. So the precise claim is: *the compiler persists secret
weight bytes into a shared, world-traversable location and relies on the ambient umask
for their confidentiality; under the common default `umask 0022` that yields
other-readable weight files.*

## 5. Claim labels (PRINCIPLES §1)

- **Measured (this config point):** AOTInductor bakes all four weight sentinels into a
  `*.wrapper.so` at `0o755` in the default shared cache dir, under an entirely
  other-traversable directory chain; the file persists past the compiling process's exit;
  `torch.compile`'s kernel cache persists none of the weight bytes; the `.wrapper.so` is
  placed independent of the package path; `force_disable_caches` does not suppress it;
  positive control fires, negative stays silent.
- **Hypothesized:** that a co-tenant with a distinct UID can actually open the file
  (verified only by mode bits and the traversable chain here, on a single-user host — not
  by a second real UID reading it).
- **Not established:** the same behavior on other torch versions, other OSes, or under a
  non-default umask; whether GPU-path AOTI (`cu130` present but CPU path exercised)
  differs; whether any tmp-cleanup policy shortens the window in practice.

## 6. Mitigations (not measured, for the record)

`export TORCHINDUCTOR_CACHE_DIR=<private 0700 dir>` moves the artifacts out of the shared
location; a hardened `umask 0077` removes the other-readable bit; per-user `/tmp`
(systemd `PrivateTmp=`) isolates the whole tree. None of these are the compiler's default,
which is the point.
