"""
Overnight funnel: run every confidentiality probe cheapest-first, serialized, and
write a morning hit-report.

Why a funnel. The probes differ in cost by ~1000x -- a codegen diff is seconds,
a memcheck-taint pass under torch.compile is hours. So run the cheap, high-signal
ones first; an early smoking gun shortens the night, and the expensive tiers only
run on what is still open.

Why serialized. The timing tiers measure wall-clock; a second torch job on the
box is noise that manufactures or masks a leak. Everything runs one-at-a-time so
each measurement sees a quiet machine. This is not the place to parallelize.

Why a separate driver at all. Each probe is already a script that prints a verdict
and writes its own `.out` (the repo convention). This just sequences them, stamps
the config point once (PRINCIPLES 2), captures each log, scans it for the verdict
signatures below, and rolls up a report -- it decides nothing a probe didn't
already decide.

    uv run python sweep_overnight.py --dry-run     # print the plan, run nothing
    uv run python sweep_overnight.py --tiers 0,1   # only the fast tiers
    uv run python sweep_overnight.py               # the whole funnel (hours)

A job is skipped (not failed) if its script is absent -- the three surface probes
land on their own branches, so the funnel is useful before they all merge.
"""

import argparse
import datetime
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "sweep_logs")

# Signatures that mean "a probe called something a leak". Scanned per log; the
# probe already made the call, this only surfaces it. Kept broad on purpose --
# a missed hit is worse than a false flag a human then dismisses.
HIT_PAT = re.compile(
    r"COMPILER-INTRODUCED|COMPILER-REMOVED|DISTINGUISHABLE|"
    r"\bLEAKS?\b|SMOKING GUN|secret bytes|world-readable|folded literal|"
    r"value-dependent|\[!! ",
    re.I,
)
# Signatures that mean the probe's own control tripped -- the result is not
# trustworthy and a human must look. Surfaced separately from hits.
SUSPECT_PAT = re.compile(
    r"HARNESS ARTIFACT|control (failed|tripped)|normalizer|false positive|"
    r"NOT deterministic|under floor|layout, not secret",
    re.I,
)


class Job:
    def __init__(self, name, tier, script, args=(), timeout=1800, cost="", note=""):
        self.name = name
        self.tier = tier
        self.script = script
        self.args = list(args)
        self.timeout = timeout
        self.cost = cost
        self.note = note

    @property
    def present(self):
        return os.path.exists(os.path.join(HERE, self.script))

    @property
    def cmd(self):
        return [sys.executable, self.script, *self.args]


# Cheapest-first. Tier 0: codegen/artifact inspection, no valgrind (seconds-min).
# Tier 1: paired-context callgrind criterion (min/cell). Tier 2: memcheck taint,
# slow under torch.compile (hours). Tier 3: timing AUC -- the blind spot where the
# instruction stream is identical and taint is silent but cycles leak.
JOBS = [
    # Tier 0 -- fast, high signal. The three surface probes plus existing codegen checks.
    Job(
        "exfil",
        0,
        "probe_exfil.py",
        timeout=600,
        cost="~min",
        note="secret weight bytes persisted to a readable artifact",
    ),
    Job(
        "freezing",
        0,
        "probe_freezing.py",
        timeout=1200,
        cost="~min",
        note="constant-folded secret-derived literal in frozen codegen",
    ),
    Job(
        "autotune-select",
        0,
        "probe_autotune_select.py",
        timeout=1800,
        cost="~min",
        note="value-dependent autotune kernel choice",
    ),
    Job(
        "softmax-codegen",
        0,
        "probe_softmax.py",
        timeout=900,
        cost="~min",
        note="Check A: kernel-inspection control (known oblivious)",
    ),
    Job(
        "autotune",
        0,
        "probe_autotune.py",
        timeout=1800,
        cost="~min",
        note="original autotune probe (post-bugfix normalizer)",
    ),
    Job("fastmath", 0, "probe_fastmath.py", timeout=900, cost="~min"),
    # Tier 1+2 -- the differential corpus. run_all does callgrind (paired) AND the
    # slow memcheck taint per build, so it spans both tiers; give it hours.
    Job(
        "corpus",
        1,
        "run_all.py",
        timeout=14400,
        cost="~1h+",
        note="paired callgrind + taint over the whole corpus",
    ),
    Job(
        "activations",
        1,
        "run_activations.py",
        timeout=14400,
        cost="~1h+",
        note="CSI-NN activation sweep",
    ),
    # Tier 3 -- timing. Heaviest and noisiest; must run alone (the serialization
    # above guarantees it). Catches cycle-count leaks Tier 0-2 are blind to.
    Job(
        "denormal-timing",
        3,
        "denormal_probe.py",
        timeout=3600,
        cost="~min-h",
        note="denormal cycle-count leak, compiler 2x2 (invisible to Ir/taint)",
    ),
    Job(
        "honest-timing",
        3,
        "honest_timing.py",
        timeout=7200,
        cost="~10min-h",
        note="attacker-AUC timing over the branchless/branched 2x2x2",
    ),
]


def config_point():
    """Stamp the (toolchain, machine) the whole sweep is scoped to (PRINCIPLES 2)."""

    def cap(cmd):
        try:
            return subprocess.run(
                cmd, cwd=HERE, capture_output=True, text=True, timeout=60
            ).stdout.strip()
        except Exception as e:  # noqa: BLE001 -- best-effort provenance, never fatal
            return f"(unavailable: {e})"

    torch_v = cap([sys.executable, "-c", "import torch;print(torch.__version__)"])
    vg = cap(["valgrind", "--version"])
    sha = cap(["git", "rev-parse", "--short", "HEAD"])
    uname = cap(["uname", "-srm"])
    return {"torch": torch_v, "valgrind": vg, "git": sha, "uname": uname}


def run_job(job, ts):
    log_path = os.path.join(LOG_DIR, f"{ts}_tier{job.tier}_{job.name}.log")
    print(f"  [tier {job.tier}] {job.name:<18} ({job.cost}) ... ", end="", flush=True)
    if not job.present:
        print("SKIP (script absent)")
        return {"job": job, "status": "absent", "log": None, "hits": [], "suspects": []}

    with open(log_path, "w") as fh:
        fh.write(f"# {job.name}: {' '.join(job.cmd)}\n\n")
        fh.flush()
        try:
            proc = subprocess.run(
                job.cmd, cwd=HERE, stdout=fh, stderr=subprocess.STDOUT, timeout=job.timeout
            )
            status = "ok" if proc.returncode == 0 else f"exit {proc.returncode}"
        except subprocess.TimeoutExpired:
            status = "TIMEOUT"

    hits, suspects = [], []
    with open(log_path, errors="replace") as fh:
        for line in fh:
            if HIT_PAT.search(line):
                hits.append(line.strip())
            if SUSPECT_PAT.search(line):
                suspects.append(line.strip())
    flag = "GUN?" if hits else ("suspect" if suspects else "clean")
    print(f"{status:<10} {flag}")
    return {"job": job, "status": status, "log": log_path, "hits": hits, "suspects": suspects}


def write_report(cfg, results, ts):
    path = os.path.join(HERE, "SWEEP_REPORT.md")
    guns = [r for r in results if r["hits"]]
    suspects = [r for r in results if r["suspects"] and not r["hits"]]
    with open(path, "w") as f:
        f.write(f"# Overnight sweep report — {ts}\n\n")
        f.write("Config point (PRINCIPLES 2 — scope every verdict to this):\n\n")
        for k, v in cfg.items():
            f.write(f"- **{k}**: {v}\n")
        f.write(
            "\n> A hit here is a probe's own verdict surfaced, not an "
            "independent finding. Read the linked log; confirm the probe's "
            "control held (a hit next to a `suspect` line is not evidence). "
            "Confirm a count-channel hit against the taint channel before "
            "calling it a gun (PRINCIPLES 1).\n\n"
        )

        f.write(f"## Candidate guns ({len(guns)})\n\n")
        if not guns:
            f.write(
                "None. Every probe that ran reported clean. If Tier 0-3 all "
                "ran, the empty compiler-introduced quadrant is itself a "
                "result: this toolchain, at this config point, did not "
                "introduce a confidentiality leak these probes can see.\n\n"
            )
        for r in guns:
            j = r["job"]
            f.write(f"### {j.name} (tier {j.tier}) — {r['status']}\n")
            if j.note:
                f.write(f"_{j.note}_\n\n")
            f.write(f"Log: `{os.path.relpath(r['log'], HERE)}`\n\n")
            for h in r["hits"][:12]:
                f.write(f"- `{h}`\n")
            if r["suspects"]:
                f.write(
                    f"\n**Control flags — treat as unverified:** "
                    f"{len(r['suspects'])} suspect line(s), e.g. "
                    f"`{r['suspects'][0]}`\n"
                )
            f.write("\n")

        if suspects:
            f.write(f"## Control tripped, no hit ({len(suspects)})\n\n")
            for r in suspects:
                f.write(
                    f"- **{r['job'].name}**: `{r['suspects'][0]}` "
                    f"→ `{os.path.relpath(r['log'], HERE)}`\n"
                )
            f.write("\n")

        f.write("## Full run table\n\n")
        f.write("| tier | probe | status | verdict | log |\n|---|---|---|---|---|\n")
        for r in sorted(results, key=lambda r: (r["job"].tier, r["job"].name)):
            j = r["job"]
            verdict = (
                "GUN?"
                if r["hits"]
                else (
                    "suspect" if r["suspects"] else ("skip" if r["status"] == "absent" else "clean")
                )
            )
            log = os.path.relpath(r["log"], HERE) if r["log"] else "—"
            f.write(f"| {j.tier} | {j.name} | {r['status']} | {verdict} | {log} |\n")
    return path, guns


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print the plan and exit; run nothing")
    ap.add_argument(
        "--tiers",
        default="0,1,3",
        help="comma-separated tiers to run (default 0,1,3; taint rides in tier 1's corpus job)",
    )
    ap.add_argument("--only", default="", help="comma-separated job names to run")
    args = ap.parse_args()

    tiers = {int(t) for t in args.tiers.split(",") if t.strip()}
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    plan = [j for j in JOBS if j.tier in tiers and (not only or j.name in only)]
    plan.sort(key=lambda j: (j.tier, j.name))

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    print(
        f"Overnight sweep {ts} | tiers={sorted(tiers)} | "
        f"{len(plan)} jobs, serialized cheapest-first\n"
    )

    if args.dry_run:
        for j in plan:
            mark = " " if j.present else "×"
            print(
                f"  [{mark}] tier {j.tier}  {j.name:<18} {j.cost:<9} "
                f"timeout={j.timeout}s  {j.script}"
            )
        print("\n(× = script absent, would be skipped)  — dry run, nothing executed.")
        return

    os.makedirs(LOG_DIR, exist_ok=True)
    cfg = config_point()
    print("config point: " + " | ".join(f"{k}={v}" for k, v in cfg.items()) + "\n")

    results = [run_job(j, ts) for j in plan]
    path, guns = write_report(cfg, results, ts)
    print(
        f"\nReport: {os.path.relpath(path, HERE)}  "
        f"({len(guns)} candidate gun(s), {sum(1 for r in results if r['status'] not in ('ok', 'absent'))} non-clean exits)"
    )
    # Non-zero exit if anything flagged, so an overnight `&&` chain can gate on it.
    sys.exit(1 if guns else 0)


if __name__ == "__main__":
    main()
