"""
Run and parse ``binsec -checkct`` — the constant-time / non-interference check.

This is the reusable engine behind the formal_verif prototype's layer A: point
it at *any* ``-m32`` binary plus an SSE script that declares the secret/public
globals, choose the observation channels (feature set), and get a structured
verdict back instead of scraping stdout by hand.

    from ctverify import run_checkct, LAYER_A
    res = run_checkct("bin/a_div_divisor_O0", "a.cfg", features=LAYER_A)
    res.verdict            # "insecure"
    res.leaks              # [Leak(instruction="0x8049934", kind="divisor")]
    res.to_dict()          # JSON-ready
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field

# Observation channels understood by ``binsec -checkct-features``. The default
# constant-time property is control-flow + memory-access; layer A adds the
# variable-latency arithmetic channels (experimental upstream).
DEFAULT_CT: tuple[str, ...] = ("control-flow", "memory-access")
LAYER_A: tuple[str, ...] = DEFAULT_CT + ("multiplication", "dividend", "divisor")

_STATUS = re.compile(r"Program status is\s*:\s*(secure|insecure|unknown)", re.I)
_LEAK = re.compile(r"Instruction\s+(0x[0-9a-fA-F]+)\s+has\s+([a-z ]+?)\s+leak", re.I)
_STATS = re.compile(r"(\d+)\s*/\s*(\d+)\s+([a-z ]+?)\s+checks pass", re.I)


class BinsecNotFound(RuntimeError):
    """Raised when the binsec executable is not on PATH."""


@dataclass(frozen=True)
class Leak:
    """A single leaking instruction and the channel it leaks on."""

    instruction: str
    kind: str  # "control flow" | "memory access" | "divisor" | "dividend" | "multiplication"


@dataclass
class CheckResult:
    """Structured result of one checkct run."""

    verdict: str  # "secure" | "insecure" | "unknown"
    features: list[str]
    leaks: list[Leak] = field(default_factory=list)
    # channel -> [passed, total], e.g. {"memory access": [26, 27]}
    stats: dict[str, list[int]] = field(default_factory=dict)
    binary: str | None = None

    @property
    def secure(self) -> bool:
        return self.verdict == "secure"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["secure"] = self.secure
        return d


def parse_checkct(output: str, features) -> CheckResult:
    """Parse binsec's combined stdout+stderr into a :class:`CheckResult`."""
    status = _STATUS.search(output)
    verdict = status.group(1).lower() if status else "unknown"

    leaks = [
        Leak(instruction=m.group(1), kind=m.group(2).strip().lower())
        for m in _LEAK.finditer(output)
    ]

    stats: dict[str, list[int]] = {}
    for m in _STATS.finditer(output):
        passed, total, channel = int(m.group(1)), int(m.group(2)), m.group(3).strip().lower()
        stats[channel] = [passed, total]

    return CheckResult(verdict=verdict, features=list(features), leaks=leaks, stats=stats)


def run_checkct(
    binary: str,
    sse_script: str,
    *,
    features=LAYER_A,
    isa: str = "x86-32",
    timeout: int = 240,
    binsec: str = "binsec",
) -> CheckResult:
    """Invoke ``binsec -checkct`` on *binary* and return a parsed verdict.

    *sse_script* is a binsec SSE config declaring ``secret``/``public`` globals.
    *features* selects the observation channels (see :data:`DEFAULT_CT`,
    :data:`LAYER_A`). Raises :class:`BinsecNotFound` if binsec is not installed.
    """
    if shutil.which(binsec) is None:
        raise BinsecNotFound(
            f"{binsec!r} not on PATH — install it (opam) and run `eval $(opam env)`"
        )
    cmd = [
        binsec,
        "-sse",
        "-checkct",
        "-checkct-features",
        ",".join(features),
        "-checkct-leak-info",
        "instr",
        "-isa",
        isa,
        "-sse-script",
        sse_script,
        "-sse-timeout",
        str(timeout),
        binary,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 60)
    result = parse_checkct(proc.stdout + proc.stderr, features)
    result.binary = binary
    return result
