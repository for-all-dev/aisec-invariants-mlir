"""
Static flush-to-zero / denormals-are-zero check — the formal denormal layer.

Motivation (honest). binsec cannot help with the denormal timing channel for a
blunt reason: it does not even DECODE floating-point instructions — it cuts the
path as "uninterpreted" and returns ``unknown`` (verified on this box). So on FP
code the formal A/B layer is not "clean", it is SILENT, and the ~40x
subnormal-operand slowdown (Andrysco et al., IEEE S&P 2015) is invisible to it.

You cannot prove *timing* with a solver, but you CAN prove the *configuration*
that removes the channel: if the binary programs the CPU's MXCSR with
flush-to-zero (FTZ, bit 15) and denormals-are-zero (DAZ, bit 6), subnormals are
turned into 0 in hardware, so there is no microcode assist and no
value-dependent latency. That is a static, per-binary property — checkable
without running anything and without a solver — so it slots into the pipeline
right after the binsec A/B step as the denormal safety net's formal half. Layer D
then confirms empirically that the channel is actually gone.

Method (and its limits). We disassemble (``objdump -d``) and look for an
``ldmxcsr`` (the instruction that loads MXCSR) whose value has the FTZ/DAZ bits
set, by OR-ing the immediates of nearby ``or``/``mov`` instructions in the same
basic block (``or $0x40,%eax`` = DAZ; ``or $0x80,%ah`` = FTZ, i.e. bit 15). This
is a deliberately simple window heuristic, not a full data-flow proof: it can be
fooled by an immediate built far from the ``ldmxcsr`` or by a later ``and`` that
clears the bits. It is sound enough to distinguish an ``-ffast-math`` /
``_MM_SET_FLUSH_ZERO_MODE`` build (FTZ+DAZ set) from a default build (no
``ldmxcsr`` at all), which is the case that matters.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import asdict, dataclass

FTZ_BIT = 1 << 15  # MXCSR.FTZ
DAZ_BIT = 1 << 6  # MXCSR.DAZ

# both ldmxcsr and the VEX form vldmxcsr (used by -mavx / -march=native builds)
_LDMXCSR = re.compile(r"\bv?ldmxcsr\b")
# immediate OR/MOV into a register OR a memory slot, e.g.
#   "or   $0x40,%eax"   "or  $0x80,%ah"   "orl $0x8040,-0x4(%rbp)"
_IMM = re.compile(r"\b(?:or|mov|xor)[lqbw]?\s+\$0x([0-9a-fA-F]+),(\S+)")
_WINDOW = 16  # instructions to scan back from an ldmxcsr


class ObjdumpNotFound(RuntimeError):
    """Raised when objdump is not on PATH."""


@dataclass
class FtzResult:
    binary: str | None
    has_ldmxcsr: bool
    ftz: bool  # FTZ (bit 15) programmed
    daz: bool  # DAZ (bit 6) programmed
    verdict: str  # "flushed" | "partial" | "none"
    detail: str

    @property
    def denormals_flushed(self) -> bool:
        """True only when BOTH FTZ and DAZ are set (inputs and results zeroed)."""
        return self.ftz and self.daz

    def to_dict(self) -> dict:
        d = asdict(self)
        d["denormals_flushed"] = self.denormals_flushed
        return d


def _imm_to_mask(hex_val: str, dest: str) -> int:
    val = int(hex_val, 16)
    # a high-byte register (ah/bh/ch/dh) writes bits 8..15 of the dword
    reg = dest.lstrip("%")
    if len(reg) == 2 and reg[0] in "abcd" and reg[1] == "h":
        val <<= 8
    return val


def parse_ftz(objdump_text: str, binary: str | None = None) -> FtzResult:
    """Parse ``objdump -d`` output and decide whether FTZ/DAZ are programmed."""
    lines = objdump_text.splitlines()
    mask = 0
    has_ld = False
    for i, line in enumerate(lines):
        if not _LDMXCSR.search(line):
            continue
        has_ld = True
        # For each (v)ldmxcsr site, OR the immediates of nearby or/mov/xor within
        # the same block, then fold that into the global mask — FTZ and DAZ are
        # often programmed at two separate ldmxcsr sites.
        local = 0
        start = max(0, i - _WINDOW)
        for prev in lines[start:i]:
            if prev.strip() == "" or ">:" in prev:  # basic-block / function boundary
                local = 0  # only attribute immediates after the last boundary
            m = _IMM.search(prev)
            if m:
                local |= _imm_to_mask(m.group(1), m.group(2))
        mask |= local

    ftz = bool(mask & FTZ_BIT)
    daz = bool(mask & DAZ_BIT)
    if ftz and daz:
        verdict, detail = "flushed", "FTZ+DAZ programmed via ldmxcsr — subnormals flushed to zero"
    elif ftz or daz:
        verdict = "partial"
        which = "FTZ (results)" if ftz else "DAZ (inputs)"
        detail = f"only {which} set — subnormal channel only partly closed"
    elif has_ld:
        verdict, detail = "none", "ldmxcsr present but no FTZ/DAZ bits detected"
    else:
        verdict, detail = "none", "no ldmxcsr — MXCSR left at default, denormals NOT flushed"
    return FtzResult(
        binary=binary, has_ldmxcsr=has_ld, ftz=ftz, daz=daz, verdict=verdict, detail=detail
    )


def run_ftz(binary: str, *, objdump: str = "objdump") -> FtzResult:
    """Disassemble *binary* and return its FTZ/DAZ static verdict."""
    if shutil.which(objdump) is None:
        raise ObjdumpNotFound(f"{objdump!r} not on PATH")
    proc = subprocess.run([objdump, "-d", binary], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"objdump failed: {proc.stderr.strip()}")
    return parse_ftz(proc.stdout, binary=binary)
