"""Constant-time verification for MLIR, built on FCVD (xdsl-smt)."""

from .leakage import DEFAULT_MODEL, LeakageTrace, recording
from .pdl_ct import CTResult, build_query, check_pattern

__all__ = [
    "DEFAULT_MODEL",
    "LeakageTrace",
    "recording",
    "CTResult",
    "build_query",
    "check_pattern",
]
