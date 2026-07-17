"""
Leakage-contract verdicts at a chosen observation granularity — layer B.

``binsec -checkct`` (memory-access) decides the ``[ct]`` contract: does a load
address depend on the secret at *byte* granularity? A real cache attacker sees
only which cache *line* is touched. This module re-expresses the verdict as
``program |= contract`` for a coarser observer, so a byte-level leak whose
reachable addresses all fall in one line is secure under ``[cache-line]``.

The verdict is *computed* from the access layout (element size and index range,
with a line-aligned base), not asserted:

    for a secret-dependent access base + i*elem, i in [0, index_count):
        distinct_lines = |{ (i*elem) // line_bytes }|
        distinct_lines == 1  -> secure   (all secrets share one line)
        distinct_lines  > 1  -> insecure (the secret moves the line)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

LINE_BYTES = 64  # x86 cache line


@dataclass(frozen=True)
class AccessLayout:
    """Ground-truth layout of a secret-dependent access (from the source)."""

    elem_size: int  # bytes per indexed element (or the stride between choices)
    index_count: int  # number of distinct secret-selected indices
    aligned: bool = True  # is the table base cache-line aligned?


@dataclass
class ContractResult:
    ct_verdict: str
    contract_verdict: str
    line_bytes: int
    distinct_lines: int | None
    span_bytes: int | None
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def cacheline_verdict(
    ct_verdict: str, layout: AccessLayout, line_bytes: int = LINE_BYTES
) -> ContractResult:
    """Compute the ``[cache-line]`` verdict from the ``[ct]`` verdict and layout."""
    ct_verdict = ct_verdict.lower()

    # A coarser observer never sees more than the byte observer: if [ct] is
    # secure the address is secret-independent, so [cache-line] is secure too.
    if ct_verdict != "insecure":
        return ContractResult(
            ct_verdict, ct_verdict, line_bytes, None, None, "no secret-dependent address"
        )

    elem, count = layout.elem_size, layout.index_count
    if elem == 0 or count <= 1:
        return ContractResult(
            ct_verdict,
            "insecure",
            line_bytes,
            None,
            None,
            "byte leak with unknown/singleton layout — not softened",
        )

    if not layout.aligned:
        return ContractResult(
            ct_verdict, "insecure", line_bytes, None, None, "base alignment unknown — conservative"
        )

    lines = {(i * elem) // line_bytes for i in range(count)}
    span = (count - 1) * elem + elem
    if len(lines) == 1:
        return ContractResult(
            ct_verdict, "secure", line_bytes, 1, span, f"span {span} B fits 1 cache line"
        )
    return ContractResult(
        ct_verdict,
        "insecure",
        line_bytes,
        len(lines),
        span,
        f"reaches {len(lines)} cache lines (span {span} B)",
    )
