"""Build the attacker-profile artifact: leak class x observer layer.

    uv run python artifact/attacker_profile.py > artifact/attacker-profile.html

The taxonomy is written here by hand -- it is a judgement, not a measurement --
but every number in the "how much is actually closed" column is read live from
the same coverage machinery the translation map uses, so the page cannot claim
more than the repository can back.
"""

from __future__ import annotations

import json
from pathlib import Path

from fcvdct.coverage import COMPILERS, Compiler, report

# ---------------------------------------------------------------- the two axes

OBSERVERS = [
    ("O0", "Public transcript", "Keys, ciphertexts, signatures, outputs, public errors."),
    ("O1", "Remote timing", "End-to-end latency, timeouts, repeated-query statistics."),
    (
        "O2",
        "Constant-time trace",
        "Branches, opcode classes, address and latency classes — not operands, "
        "registers or memory values.",
    ),
    ("O3", "Local microarchitecture", "Cache sets and lines, pages, predictors, contention."),
    ("O4", "Host / debugger", "Process memory, stopped registers, logs, files, core dumps."),
    (
        "O5",
        "TEE / HSM boundary",
        "Not a strength level: a declared boundary. Interface and leakage only, while isolation holds.",
    ),
    ("O6", "Physical observer", "Power, EM, acoustic, thermal, frequency behaviour."),
    ("O7", "Invasive observer", "Internal buses, memories, registers, chip probes."),
]

CLASSES = [
    (
        "functional",
        "Functional",
        "The answer itself, or anything derived from it: wrong results, padding oracles, "
        "error text, response length, compression ratio.",
    ),
    (
        "timing",
        "Timing",
        "How long the program itself ran: variable-latency instructions, trip counts, branch depth.",
    ),
    (
        "uarch",
        "Microarchitectural",
        "State the program left in shared hardware, which somebody else then measures — "
        "cache, TLB, branch predictor, execution ports, prefetchers, speculation.",
    ),
    (
        "power",
        "Power and emanations",
        "Switching activity as seen from outside: power, EM, acoustic, thermal. One physical "
        "phenomenon, several receivers.",
    ),
    (
        "residual",
        "Residual data",
        "Where the secret was left afterwards: memory, swap, core dumps, spilled registers. "
        "Nothing is measured during the run — the attacker arrives later and reads.",
    ),
    (
        "active",
        "Active (fault)",
        "Not an observation at all: voltage and clock glitching, lasers, Rowhammer. A second "
        "axis, not a ring of the onion.",
    ),
]

# state: covered | partial | gap | scoped-out
CELLS = {
    ("functional", "O0"): (
        "partial",
        "Value correctness of a PDL rewrite is proved by upstream "
        "verify-pdl and reported next to our own verdict. Nothing checks it for the structural "
        "templates or per program — fcvd-ct-pdl deliberately replaces the refinement "
        "criterion with false, so what it proves is about leakage, not about values.",
    ),
    ("timing", "O1"): (
        "partial",
        "The property is equality of an observation trace, not of a "
        "cycle count. It implies equal running time only under the assumption that every "
        "operation outside the model has data-independent latency — which is the leakage "
        "model, stated in leakage.py and never derived.",
    ),
    ("timing", "O2"): (
        "covered",
        "This cell is the one the pipeline is built for. O2 is a "
        "restatement of our leakage model almost word for word: branches, address classes, "
        "latency classes, and nothing about operands. Four obligations — control, address, "
        "latency, resource — are proved separately, so a verdict names the channel.",
    ),
    ("uarch", "O2"): (
        "partial",
        "Addresses are in the trace at full granularity, which is "
        "stronger than a cache-line contract. But an address trace is not a cache model.",
    ),
    ("uarch", "O3"): (
        "partial",
        "The binary layer proves a [cache-line] contract "
        "(prototypes/formal_verif/contract_b). Nothing models eviction, set conflicts, TLB, "
        "branch predictor, port contention or speculation.",
    ),
    ("power", "O1"): (
        "gap",
        "Not empty, and this is the uncomfortable one: DVFS makes power "
        "consumption change frequency, and frequency changes wall-clock time (Hertzbleed). A "
        "power channel can surface as remote timing, so declaring power out of scope does not "
        "fully hold.",
    ),
    ("power", "O6"): ("scoped-out", "Out of scope by decision, not by omission."),
    ("residual", "O4"): (
        "partial",
        "The resource obligation compares allocation sizes and which "
        "pointer reaches dealloc, so a secret-dependent allocation set is caught. Not checked: "
        "dead-store elimination removing a memset of a secret, and registers spilled to the "
        "stack — both are leaks the compiler itself creates.",
    ),
    ("uarch", "O4"): (
        "gap",
        "Page-fault and controlled-channel observation of an enclave. Nothing here addresses it.",
    ),
    ("power", "O7"): ("scoped-out", "Out of scope."),
    ("functional", "O4"): (
        "gap",
        "A core dump or a log carrying the answer is a functional leak "
        "at a host-level observer. Out of the compiler's reach, in the deployment's.",
    ),
    ("active", "O5"): (
        "scoped-out",
        "The whole row is outside the observer model: the attacker "
        "changes the computation instead of watching it. Constant-time proofs say nothing here.",
    ),
}

NOT_APPLICABLE_NOTE = "no meaningful leak of this class at this observer"


def coverage_numbers() -> list[dict[str, object]]:
    rows = []
    for path in sorted(COMPILERS.glob("*.json")):
        compiler = Compiler.load(path)
        result = report(compiler, prove=True, timeout=120)
        mentions = sum(op.occurrences for op in result.operations) or 1
        translatable = sum(op.occurrences for op in result.by_form(0)) + sum(
            op.occurrences for op in result.by_form(1)
        )
        rows.append(
            {
                "name": compiler.name,
                "share": round(100 * translatable / mentions, 1),
                "steps": len(result.stages),
                "specified": len([s for s in result.stages if s.proved or s.breaks]),
                "proved": len([s for s in result.stages if s.proved]),
                "breaks": len([s for s in result.stages if s.breaks]),
            }
        )
    return rows


def main() -> None:
    data = {
        "observers": [{"id": o, "name": n, "what": w} for o, n, w in OBSERVERS],
        "classes": [{"id": i, "name": n, "what": w} for i, n, w in CLASSES],
        "cells": [
            {"cls": c, "obs": o, "state": s, "note": note} for (c, o), (s, note) in CELLS.items()
        ],
        "coverage": coverage_numbers(),
    }
    template = Path(__file__).parent / "attacker.template.html"
    print(template.read_text().replace("__DATA__", json.dumps(data, ensure_ascii=False)))


if __name__ == "__main__":
    main()
