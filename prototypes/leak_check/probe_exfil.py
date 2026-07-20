"""
Probe: does the compiler PERSIST secret weight bytes to a shared, readable,
long-lived file on disk?

This is an artifact-exfiltration probe, not a side channel. The secret is the
model weights. The interesting claim is about PERSISTENCE + PERMISSIONS +
LIFETIME, not merely "an artifact contains weights" (which for a package format
is working-as-intended). Concretely we ask:

  When torch compiles a model, do the secret weight bytes land in a file that
  (a) lives in a shared temp dir, (b) is readable by group/other, and
  (c) survives the compiling process's exit?

If all three hold, any local user can recover the weights by reading a file.

Method
------
The model's weights are filled with MAGIC, greppable byte sentinels (see
SENTINELS). We compile the model two ways:

  * torch.compile (Inductor) — weights are runtime inputs; the kernel cache is
    not expected to hold them. Measured, not assumed.
  * AOTInductor packaging (aoti_compile_and_package) — bakes constants (the
    weights) into a self-contained .so / package.

The compile runs in a CHILD process. The parent scans the cache dir only AFTER
the child has exited, so every hit is by construction a file that outlived the
process that wrote it. For each file containing a sentinel we record the
redacted path, octal mode, group/other readability, and the permission chain of
its ancestor directories up to /tmp.

Controls (PRINCIPLES §5)
------------------------
  * positive: a file WE write with sentinel bytes at 0644 must be detected.
  * negative: a fresh file of random non-sentinel bytes must NOT match.

Usage
-----
  python probe_exfil.py                 # full run, prints a report
  python probe_exfil.py --child <dir>   # internal: the compile worker

Scope: one config point. Record torch version, OS, umask, AOTI availability;
see docs/research/leak_check.exfil.agents.md.
"""

import os

# Determinism knobs BEFORE importing torch (cf. measured_run.py).
os.environ.setdefault("PYTHONHASHSEED", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import glob  # noqa: E402  (stdlib, order-independent; grouped after env setup)
import platform  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402

import numpy as np  # noqa: E402  (must follow the determinism setup above)

# --- Sentinels: 4-byte units tiled across the weights. Each is chosen to be a
#     run that cannot occur by chance in a 32-byte window (needle = unit * 8). ---
SENTINELS: dict[str, bytes] = {
    "ascii_LEAK": b"LEAK",
    "ascii_W3IG": b"W3IG",
    "magic_deadbeef": b"\xde\xad\xbe\xef",
    # 1234567.0 as little-endian float32 (a plain, searchable float value).
    "float_1234567": np.float32(1234567.0).tobytes(),
}
DIM = 64  # Linear(DIM, DIM) -> DIM*DIM floats = 4*DIM*DIM bytes of weights.


def build_weight() -> np.ndarray:
    """A [DIM, DIM] float32 whose raw bytes are tiled sentinel runs."""
    names = list(SENTINELS)
    rows_per = DIM // len(names)
    w = np.empty((DIM, DIM), dtype=np.float32)
    row_bytes = DIM * 4  # bytes in one weight row
    for i, name in enumerate(names):
        unit = SENTINELS[name]
        block = (unit * (row_bytes // len(unit) + 1))[:row_bytes]
        r0 = i * rows_per
        r1 = DIM if i == len(names) - 1 else r0 + rows_per
        for r in range(r0, r1):
            w[r] = np.frombuffer(block, dtype=np.float32)
    return w


def needles() -> dict[str, bytes]:
    """A 32-byte run per sentinel: coincidental matches are ~2^-256."""
    return {name: unit * 8 for name, unit in SENTINELS.items()}


# --------------------------------------------------------------------------- #
# Child worker: compile the sentinel model, writing into a given cache dir.
# --------------------------------------------------------------------------- #
def child(cache_dir: str, pkg_path: str, disable_caches: bool) -> None:
    os.environ["TORCHINDUCTOR_CACHE_DIR"] = cache_dir
    if disable_caches:
        os.environ["TORCHINDUCTOR_FORCE_DISABLE_CACHES"] = "1"

    import torch

    torch.manual_seed(0)
    torch.set_num_threads(1)

    w = build_weight()
    model = torch.nn.Linear(DIM, DIM, bias=False)
    with torch.no_grad():
        model.weight.copy_(torch.from_numpy(w))
    x = torch.zeros(1, DIM)

    # (a) torch.compile / Inductor kernel cache.
    fn = torch.compile(model, fullgraph=True)
    with torch.no_grad():
        for _ in range(2):
            fn(x)

    # (b) AOTInductor packaging, if present. The package goes to pkg_path, which
    #     is OUTSIDE the scanned cache dir, so every hit found under the cache
    #     dir is unambiguously an artifact the COMPILER chose to place there.
    if hasattr(torch._inductor, "aoti_compile_and_package"):
        ep = torch.export.export(model, (x,))
        torch._inductor.aoti_compile_and_package(ep, package_path=pkg_path)
        print(f"CHILD aoti_package={pkg_path}")
    else:
        print("CHILD aoti_unavailable")
    print("CHILD done")


# --------------------------------------------------------------------------- #
# Scanning & reporting (parent side).
# --------------------------------------------------------------------------- #
HOME = os.path.expanduser("~")


def redact(path: str, cache_dir: str) -> str:
    """Strip PII: absolute /home and the run-specific cache prefix."""
    p = path.replace(cache_dir, "<cache>") if cache_dir else path
    p = p.replace(HOME, "<home>")
    return p


def mode_of(path: str) -> int:
    return os.stat(path).st_mode & 0o777


def readability(mode: int) -> str:
    g = "r" if mode & 0o040 else "-"
    o = "r" if mode & 0o004 else "-"
    return f"group={g} other={o}"


def ancestor_chain(path: str, stop: str = "/tmp") -> list[tuple[str, str]]:
    """Octal modes from the file's dir up to (and including) `stop`."""
    chain = []
    d = os.path.dirname(path)
    while True:
        chain.append((oct(mode_of(d)), d))
        if d == stop or d == "/" or os.path.dirname(d) == d:
            break
        d = os.path.dirname(d)
    return chain


def scan(cache_dir: str) -> list[dict]:
    """Every file under cache_dir that contains a sentinel run."""
    ndl = needles()
    hits = []
    for p in sorted(glob.glob(os.path.join(cache_dir, "**"), recursive=True)):
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "rb") as f:
                data = f.read()
        except OSError:
            continue
        found = [name for name, n in ndl.items() if n in data]
        if found:
            m = mode_of(p)
            hits.append(
                {
                    "path": p,
                    "mode": m,
                    "sentinels": found,
                    "size": len(data),
                    "readable": readability(m),
                }
            )
    return hits


def recover_snippet(path: str, name: str) -> bytes:
    """Pull the sentinel run back out of the file (undeniable recovery)."""
    n = needles()[name]
    with open(path, "rb") as f:
        data = f.read()
    i = data.find(n)
    return data[i : i + 16]


def run_controls(scan_dir: str) -> tuple[bool, bool]:
    """Positive: a 0644 sentinel file is detected. Negative: random bytes aren't."""
    unit = SENTINELS["ascii_LEAK"]
    pos = os.path.join(scan_dir, "_control_positive.bin")
    with open(pos, "wb") as f:
        f.write(unit * 4096)
    os.chmod(pos, 0o644)

    neg = os.path.join(scan_dir, "_control_negative.bin")
    rng = np.random.default_rng(0)
    with open(neg, "wb") as f:
        f.write(rng.integers(0, 256, size=16384, dtype=np.uint8).tobytes())
    os.chmod(neg, 0o644)

    ndl = needles()
    with open(pos, "rb") as f:
        pos_bytes = f.read()
    with open(neg, "rb") as f:
        neg_bytes = f.read()
    pos_hit = any(n in pos_bytes for n in ndl.values())
    neg_hit = any(n in neg_bytes for n in ndl.values())
    os.remove(pos)
    os.remove(neg)
    return pos_hit, neg_hit


def default_cache_dir() -> str | None:
    try:
        from torch._inductor.runtime.cache_dir_utils import cache_dir

        return cache_dir()
    except Exception:
        return None


def _run_child(cache_dir: str, pkg_path: str, disable_caches: bool) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, __file__, "--child", cache_dir, pkg_path]
        + (["--disable-caches"] if disable_caches else []),
        capture_output=True,
        text=True,
        timeout=1200,
    )


def do_pass(label: str, disable_caches: bool) -> list[dict]:
    """Compile in a child using a private cache dir; scan after it exits."""
    cache_dir = tempfile.mkdtemp(prefix="exfil_cache_")
    pkg_dir = tempfile.mkdtemp(prefix="exfil_pkg_")
    pkg_path = os.path.join(pkg_dir, "aoti_package.pt2")
    print(f"\n=== pass: {label} (private cache dir, force_disable_caches={disable_caches}) ===")
    print("cache dir: <cache>  (real path redacted; contains only compiler-placed files)")

    proc = _run_child(cache_dir, pkg_path, disable_caches)
    for line in proc.stdout.splitlines():
        if line.startswith("CHILD"):
            print("  " + redact(redact(line, cache_dir), pkg_dir))
    if proc.returncode != 0:
        print(f"  child FAILED rc={proc.returncode}\n{redact(proc.stderr[-1200:], cache_dir)}")
        return []

    # The child has exited. Every hit below therefore PERSISTS past process exit.
    hits = scan(cache_dir)
    if not hits:
        print("  no sentinel bytes found in any COMPILER-placed file under the cache dir.")
    for h in hits:
        rp = redact(h["path"], cache_dir)
        print(f"  HIT mode={oct(h['mode'])} {h['readable']}  size={h['size']}  {rp}")
        print(f"      sentinels: {', '.join(h['sentinels'])}")
        name = h["sentinels"][0]
        snip = recover_snippet(h["path"], name)
        print(f"      recovered[{name}] = {snip!r}")
        for cm, cd in ancestor_chain(h["path"]):
            print(f"      dir {cm} {redact(cd, cache_dir)}")

    # The AOTI package itself (user-chosen path). Containing weights is expected
    # for a package format; recorded for completeness, not as the finding.
    if os.path.exists(pkg_path):
        with open(pkg_path, "rb") as f:
            pdata = f.read()
        phit = [n for n, ndl in needles().items() if ndl in pdata]
        pm = mode_of(pkg_path)
        print(
            f"  package (user-chosen path): mode={oct(pm)} {readability(pm)} "
            f"size={len(pdata)} sentinels={phit}  [expected: a package holds its weights]"
        )
    # hygiene: these private temp trees hold sentinel weights; remove them.
    shutil.rmtree(cache_dir, ignore_errors=True)
    shutil.rmtree(pkg_dir, ignore_errors=True)
    return hits


def do_pass_shared(shared_dir: str) -> list[dict]:
    """End-to-end exposure at torch's DEFAULT (shared) cache dir.

    Attribution: snapshot pre-existing files, compile into the shared dir in a
    child, then report only files THIS compile created (so we never read other
    jobs' data). Hygiene: the sentinel-bearing files we created are removed
    afterward — persistence past process exit is already shown by the scan
    happening after the child died; leaving greppable secrets in shared /tmp
    would be its own footgun.
    """
    print("\n=== pass: default SHARED cache dir (end-to-end exposure) ===")
    print(f"shared cache dir: {redact(shared_dir, '')}")
    before = set(glob.glob(os.path.join(shared_dir, "**"), recursive=True))

    pkg_dir = tempfile.mkdtemp(prefix="exfil_pkg_")  # package kept OUT of shared /tmp
    proc = _run_child(shared_dir, os.path.join(pkg_dir, "aoti_package.pt2"), disable_caches=False)
    if proc.returncode != 0:
        print(f"  child FAILED rc={proc.returncode}\n{redact(proc.stderr[-1200:], '')}")
        return []

    after = set(glob.glob(os.path.join(shared_dir, "**"), recursive=True))
    new_files = [p for p in sorted(after - before) if os.path.isfile(p)]
    ndl = needles()
    hits = []
    for p in new_files:
        try:
            with open(p, "rb") as f:
                data = f.read()
        except OSError:
            continue
        found = [name for name, n in ndl.items() if n in data]
        if found:
            m = mode_of(p)
            hits.append({"path": p, "mode": m, "sentinels": found, "readable": readability(m)})
            print(f"  NEW HIT mode={oct(m)} {readability(m)}  {redact(p, '')}")
            print("      full path chain to /tmp, all traversable/readable by other:")
            for cm, cd in ancestor_chain(p):
                print(f"      dir {cm} {redact(cd, '')}")
    # hygiene: remove the sentinel-bearing artifacts we created in shared /tmp.
    for p in new_files:
        try:
            os.remove(p)
        except OSError:
            pass
    shutil.rmtree(pkg_dir, ignore_errors=True)
    if not hits:
        print("  no NEW sentinel-bearing file created in the shared dir.")
    return hits


def main() -> None:
    import torch

    print("probe_exfil: compiler artifact exfiltration of secret weights")
    print(f"torch={torch.__version__}  python={sys.version.split()[0]}")
    print(f"platform={platform.platform()}")
    cur = os.umask(0o022)
    os.umask(cur)
    print(f"umask={oct(cur)}")
    aoti = hasattr(torch._inductor, "aoti_compile_and_package")
    print(f"AOTInductor available: {aoti}")

    dcd = default_cache_dir()
    if dcd:
        print("\n--- default (SHARED) cache location, the real-world threat surface ---")
        print(f"torch's default cache dir: {redact(dcd, '')}")
        if os.path.isdir(dcd):
            print(f"  dir {oct(mode_of(dcd))} {redact(dcd, '')}")
            for cm, cd in ancestor_chain(dcd + "/x"):
                print(f"  dir {cm} {redact(cd, '')}")
        else:
            print("  (does not exist yet on this host)")
        print(
            "  Files the compiler writes here inherit the process umask; under the\n"
            "  default umask 0022 that is 0644/0755 (group- and other-readable),\n"
            "  and /tmp is world-traversable."
        )

    # Controls first (PRINCIPLES §5): calibrate the detector before trusting it.
    scan_dir = tempfile.mkdtemp(prefix="exfil_ctrl_")
    pos_hit, neg_hit = run_controls(scan_dir)
    os.rmdir(scan_dir)
    print("\n--- controls ---")
    print(f"  positive (0644 sentinel file): detected = {pos_hit}   (want True)")
    print(f"  negative (random bytes):       detected = {neg_hit}   (want False)")
    if not pos_hit or neg_hit:
        print("  CONTROLS FAILED — detector is not trustworthy; aborting verdict.")
        return

    hits_cached = do_pass("caches enabled", disable_caches=False)
    hits_nocache = do_pass("caches disabled", disable_caches=True)
    hits_shared = do_pass_shared(dcd) if dcd else []

    # --- verdict ---
    print("\n=== verdict ===")

    def gun(hits: list[dict]) -> list[dict]:
        # other-readable file holding secret bytes, persisting past exit.
        return [h for h in hits if h["mode"] & 0o004]

    # The undeniable case: a file that is other-readable AND sits under a
    # fully other-traversable directory chain (the shared-dir pass).
    guns = gun(hits_shared)
    any_hit = hits_cached or hits_nocache or hits_shared
    if guns:
        print("GUN FIRED: secret weight bytes in an OTHER-READABLE file under a")
        print("fully other-traversable dir chain, persisting after the compiling")
        print("process exited (default shared cache dir).")
        for h in guns:
            print(
                f"  mode={oct(h['mode'])} ({h['readable']}) "
                f"sentinels={h['sentinels']} {os.path.basename(h['path'])}"
            )
        print(
            "\nRepro: run this model through aoti_compile_and_package with the\n"
            "default TORCHINDUCTOR_CACHE_DIR, then, as ANOTHER user:\n"
            "  grep -rl LEAK /tmp/torchinductor_*/   # -> the weight-bearing .so"
        )
    elif any_hit:
        print("Secret bytes DO persist, but only in owner-readable (0600) files.")
        print("Not an other-readable leak at this config point.")
    else:
        print("No secret weight bytes persisted in any compiled artifact.")
        print("Well-behaved at this config point (report as such).")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--child":
        child(sys.argv[2], sys.argv[3], disable_caches="--disable-caches" in sys.argv)
    else:
        main()
