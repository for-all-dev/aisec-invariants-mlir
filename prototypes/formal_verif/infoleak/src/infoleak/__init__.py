"""infoleak — information-theoretic timing-leak estimation over binaries (layers C+D).

The measurement/estimation counterpart to ``ctverify`` (layers A/B). ``ctverify``
asks a solver whether a secret-dependent branch/address/var-latency op *exists*;
``infoleak`` runs the binary on real silicon and estimates how many *bits* the
wall-clock timing actually leaks — the mutual information ``I(secret; timing)``,
debiased against a permutation null, alongside the dudect/TVLA t-test.

  - layer D (:func:`estimate.estimate_leak`): the wall-clock net — bits/query.
  - layer C (:func:`contract_check.validate_against_silicon`): compare those
    measured bits to what an A/B contract allows, flagging a silicon-leaks-
    beyond-the-model violation.
"""

from .contract_check import (
    CONFIRMED,
    CONSISTENT,
    NOT_EXPLOITABLE,
    VIOLATED,
    SiliconVerdict,
    validate_against_silicon,
)
from .estimate import DUDECT_T_THRESHOLD, LeakEstimate, estimate_leak
from .ftz import FtzResult, ObjdumpNotFound, parse_ftz, run_ftz
from .measure import DriverNotFound, run_driver

__all__ = [
    "CONFIRMED",
    "CONSISTENT",
    "DUDECT_T_THRESHOLD",
    "DriverNotFound",
    "FtzResult",
    "LeakEstimate",
    "NOT_EXPLOITABLE",
    "ObjdumpNotFound",
    "SiliconVerdict",
    "VIOLATED",
    "estimate_leak",
    "parse_ftz",
    "run_ftz",
    "run_driver",
    "validate_against_silicon",
]
