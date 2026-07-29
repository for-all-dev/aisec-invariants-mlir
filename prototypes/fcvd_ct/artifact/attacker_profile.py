"""Build the attacker-profile artifact: leak class x observer layer.

    uv run python artifact/attacker_profile.py > artifact/attacker-profile.html

Two axes. What leaks -- four classes, and the list closes. Who is watching -- the
observer onion, ordered by how direct the access to secret state is. The grid is
their product, and the block the MLIR pipeline closes is functional x timing out
to O2.

The content here is a judgement rather than a measurement, so it is written out
rather than derived.
"""

from __future__ import annotations

import json
from pathlib import Path

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
]

# state: covered | partial | gap | bridge | scoped-out
CELLS = {
    ("functional", "O0"): (
        "covered",
        "Functional equivalence is the other half of what FCVD gives: "
        "the refinement criterion relates the values two programs compute. Upstream verify-pdl "
        "proves it for a rewrite and every pattern in the corpus carries that verdict beside ours.",
    ),
    ("timing", "O0"): (
        "covered",
        "Nothing of this class is visible from the public transcript alone — a transcript has no "
        "clock. The bracket covers it because the property proved at O2 is monotone outward: a "
        "weaker observer cannot separate runs a stronger one could not.",
    ),
    ("timing", "O1"): (
        "covered",
        "Carried outward from O2 rather than proved separately. O2 sees "
        "strictly more than O1 — every branch and every latency class, not just the total — so two "
        "runs that are indistinguishable in the constant-time trace are indistinguishable in "
        "end-to-end latency. Proving against the stronger observer closes the weaker one.",
    ),
    ("timing", "O2"): (
        "covered",
        "The cell the pipeline is built for. O2 is a restatement of our "
        "leakage model almost word for word: branches, address classes, latency classes, and "
        "nothing about operands. Four obligations — control, address, latency, resource — are "
        "proved separately, so a verdict names the channel it fails on.",
    ),
    ("uarch", "O2"): (
        "partial",
        "Addresses are in the trace at full granularity, which is stronger "
        "than a cache-line contract. But an address trace is not a cache model.",
    ),
    ("uarch", "O3"): (
        "partial",
        "The binary layer proves a [cache-line] contract "
        "(prototypes/formal_verif/contract_b). Nothing here models eviction, set conflicts, TLB, "
        "branch predictor, port contention or speculation.",
    ),
    ("power", "O1"): (
        "bridge",
        "Not empty, and this is the uncomfortable one: DVFS makes power "
        "consumption change frequency, and frequency changes wall-clock time (Hertzbleed). A power "
        "channel can surface as remote timing, so declaring power out of scope does not fully hold.",
    ),
    ("power", "O6"): ("scoped-out", "Out of scope by decision, not by omission."),
}

NOT_APPLICABLE_NOTE = "no meaningful leak of this class at this observer"


def main() -> None:
    data = {
        "observers": [{"id": o, "name": n, "what": w} for o, n, w in OBSERVERS],
        "classes": [{"id": i, "name": n, "what": w} for i, n, w in CLASSES],
        "cells": [
            {"cls": c, "obs": o, "state": s, "note": note} for (c, o), (s, note) in CELLS.items()
        ],
        # the block the MLIR pipeline closes: functional and timing, out to O2
        "closed": {"classes": ["functional", "timing"], "upto": "O2"},
    }
    template = Path(__file__).parent / "attacker.template.html"
    print(template.read_text().replace("__DATA__", json.dumps(data, ensure_ascii=False)))


if __name__ == "__main__":
    main()
