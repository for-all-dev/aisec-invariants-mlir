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

# Ordered by how direct the access to secret state is, which is what the picture
# claims to show. That puts every observer who *infers* outside every observer who
# *reads*: a physical probe on the power line is closer to the switching activity
# than a cache, but further from the secret than a debugger holding the memory.
OBSERVERS = [
    ("O0", "Public transcript", "Keys, ciphertexts, signatures, outputs, public errors."),
    ("O1", "Remote timing", "End-to-end latency, timeouts, repeated-query statistics."),
    (
        "O2",
        "Constant-time trace",
        "Branches, opcode classes, address and latency classes — not operands, registers or "
        "memory values.",
    ),
    ("O3", "Local microarchitecture", "Cache sets and lines, pages, predictors, contention."),
    ("O4", "Physical observer", "Power, EM, acoustic, thermal, frequency behaviour."),
    (
        "O5",
        "TEE / HSM host",
        "Every power a host has, minus the state the enclave declares unreachable — so it is back "
        "to inferring, with better instruments than anyone outside.",
    ),
    ("O6", "Host / debugger", "Process memory, stopped registers, logs, files, core dumps."),
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

# Every intersection gets a state -- an empty cell would be an opinion nobody stated.
#
#   unreachable  the class is not observable from this ring at all
#   covered      proved; either here or carried outward from a stronger observer
#   partial      partly, under an assumption that is written down
#   nothing      observable from here, and we cover none of it
#   moot         the observer already reads secret state directly, so a leakage
#                proof of this class no longer decides the outcome
CELLS = {
    # ---- functional: the values themselves. Observer-independent, so the row runs
    # blue until the observer stops needing to infer at all.
    ("functional", "O0"): (
        "covered",
        "The transcript is exactly what this observer gets, and value "
        "equivalence is the other half of what FCVD gives: the refinement criterion relates what "
        "two programs compute. Upstream verify-pdl proves it per rewrite, and every pattern in the "
        "corpus carries that verdict beside ours.",
    ),
    ("functional", "O1"): (
        "covered",
        "Same proof. A clock adds nothing to what the answer reveals.",
    ),
    ("functional", "O2"): (
        "covered",
        "Same proof. The constant-time trace carries no values by "
        "construction — operands are outside the model.",
    ),
    ("functional", "O3"): (
        "covered",
        "Same proof. What a cache observer recovers is addresses, "
        "which is the microarchitectural row, not this one.",
    ),
    ("functional", "O4"): (
        "covered",
        "Same proof. Power reveals activity, not the returned value.",
    ),
    ("functional", "O5"): (
        "covered",
        "What this observer is handed is the declared interface — the "
        "transcript again, and the same proof applies to it.",
    ),
    ("functional", "O6"): (
        "moot",
        "With process memory in hand the answer is readable whatever the "
        "compiler did. Value equivalence still holds; it is no longer what decides the outcome.",
    ),
    ("functional", "O7"): ("moot", "A probe on the bus reads the value directly."),
    # ---- timing: how long the program itself ran
    ("timing", "O0"): (
        "unreachable",
        "A transcript has no clock. Nothing of this class reaches "
        "here — which is stronger than being covered, not weaker.",
    ),
    ("timing", "O1"): (
        "covered",
        "Carried outward rather than proved separately: O2 sees strictly "
        "more than O1 — every branch and every latency class, not only the total — so two runs "
        "indistinguishable in the constant-time trace are indistinguishable in end-to-end latency.",
    ),
    ("timing", "O2"): (
        "covered",
        "The cell the pipeline is built for. O2 restates our leakage model "
        "almost word for word: branches, address classes, latency classes, nothing about operands. "
        "Four obligations — control, address, latency, resource — are proved separately, so a "
        "verdict names the channel it fails on.",
    ),
    ("timing", "O3"): (
        "partial",
        "The address trace is proved equal, which removes the main source "
        "of cache-timing variation. Eviction, set conflicts and contention are not modelled, so a "
        "local observer can still time what we do not describe.",
    ),
    ("timing", "O4"): (
        "covered",
        "Carried outward as at O1. A physical observer holds a better "
        "clock, but equal traces still take equal time under the model.",
    ),
    ("timing", "O5"): (
        "covered",
        "The host times the enclave from outside, which is O1 measurement "
        "of an O2-proved trace. A boundary changes who holds the clock, not what leaks through it.",
    ),
    ("timing", "O6"): (
        "moot",
        "An observer who can stop the process and read its registers has no use for a stopwatch.",
    ),
    ("timing", "O7"): ("moot", "Registers are read, not timed."),
    # ---- microarchitectural: state left in shared hardware
    ("uarch", "O0"): ("unreachable", "Shared hardware state is not in the transcript."),
    ("uarch", "O1"): (
        "unreachable",
        "Remote measurement sees aggregate latency, not cache sets. "
        "What does surface that way is already constrained by the timing row.",
    ),
    ("uarch", "O2"): (
        "partial",
        "Addresses are in the trace at full granularity, which is stronger "
        "than a cache-line contract — but an address trace is not a cache model.",
    ),
    ("uarch", "O3"): (
        "partial",
        "The observer this class is named for. The binary layer proves a "
        "[cache-line] contract (prototypes/formal_verif/contract_b). Nothing here models eviction, "
        "set conflicts, TLB, branch predictor, port contention or speculation.",
    ),
    ("uarch", "O4"): (
        "nothing",
        "Cache and bus activity show up in the power trace — Collide+Power "
        "is the published instance. Visible from here, and we cover none of it.",
    ),
    ("uarch", "O5"): (
        "nothing",
        "The sharp case: a host that controls paging steals the enclave's "
        "page-fault sequence and reads its access pattern from that. Nothing here addresses it.",
    ),
    ("uarch", "O6"): ("moot", "Reading the memory outright beats inferring it from the cache."),
    ("uarch", "O7"): ("moot", "Internal memories are read directly."),
    # ---- power and emanations
    ("power", "O0"): ("unreachable", "No physical quantity reaches a transcript."),
    ("power", "O1"): (
        "nothing",
        "The anomaly of this grid, and it points at the row above. DVFS "
        "makes consumption change frequency and frequency changes wall-clock time (Hertzbleed), so "
        "a power channel reaches a remote observer with no physical access at all. Equal "
        "observation traces then stop implying equal running times — which is what the timing row "
        "rests on.",
    ),
    ("power", "O2"): (
        "unreachable",
        "The constant-time trace has no notion of energy per "
        "operation; nothing of this class is expressible in it.",
    ),
    ("power", "O3"): (
        "nothing",
        "A co-resident process sees the frequency effects above without "
        "any privilege. Not addressed.",
    ),
    ("power", "O4"): (
        "nothing",
        "The observer this class is named for. Nothing in the pipeline "
        "speaks about energy per operation, and an IR-level leakage model is the wrong place to "
        "start.",
    ),
    ("power", "O5"): (
        "nothing",
        "Software-readable energy counters (RAPL) put a power channel "
        "inside the host's reach while the enclave runs on the same package — Platypus is the "
        "published instance.",
    ),
    ("power", "O6"): ("moot", "A debugger does not need the power trace."),
    ("power", "O7"): ("moot", "Neither does a probe."),
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
