"""ctverify — reusable constant-time / leakage-contract verdicts over binaries.

Wraps ``binsec -checkct`` (layer A) and computes cache-line leakage-contract
verdicts (layer B) with a structured, JSON-ready result. See the module docs in
``checkct`` and ``contract``.
"""

from .checkct import (
    DEFAULT_CT,
    LAYER_A,
    BinsecNotFound,
    CheckResult,
    Leak,
    parse_checkct,
    run_checkct,
)
from .contract import LINE_BYTES, AccessLayout, ContractResult, cacheline_verdict

__all__ = [
    "DEFAULT_CT",
    "LAYER_A",
    "LINE_BYTES",
    "AccessLayout",
    "BinsecNotFound",
    "CheckResult",
    "ContractResult",
    "Leak",
    "cacheline_verdict",
    "parse_checkct",
    "run_checkct",
]
