"""
Run the native measurement driver and collect (class, cycles) samples.

The driver (``csrc/driver.c`` linked with a corpus TU) emits CSV to stdout, one
measured kernel call per line. This module just runs it and parses the stream
into two parallel NumPy arrays for :func:`infoleak.estimate.estimate_leak`.

Keeping measurement (native, per-CPU) and estimation (portable, numeric) in
separate stages means the same estimator runs over a driver built for *any*
corpus, exactly as ``ctverify`` runs over any ``-m32`` binary in layers A/B.
"""

from __future__ import annotations

import shutil
import subprocess

import numpy as np


class DriverNotFound(RuntimeError):
    """Raised when the measurement driver binary does not exist / isn't runnable."""


def run_driver(
    driver: str,
    kernel: str,
    *,
    n: int = 20000,
    warmup: int = 2000,
    seed: int = 12345,
    timeout: int = 300,
) -> tuple[np.ndarray, np.ndarray]:
    """Invoke *driver* on *kernel* and return ``(classes, cycles)`` arrays."""
    if shutil.which(driver) is None and not _is_runnable_path(driver):
        raise DriverNotFound(f"{driver!r} not found — build it first (see run.sh)")
    proc = subprocess.run(
        [driver, kernel, str(n), str(warmup), str(seed)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"driver failed (rc={proc.returncode}): {proc.stderr.strip()}")
    return _parse_csv(proc.stdout)


def _is_runnable_path(path: str) -> bool:
    import os

    return os.path.isfile(path) and os.access(path, os.X_OK)


def _parse_csv(text: str) -> tuple[np.ndarray, np.ndarray]:
    classes: list[int] = []
    cycles: list[int] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("class"):  # header
            continue
        a, _, b = line.partition(",")
        classes.append(int(a))
        cycles.append(int(b))
    if not classes:
        raise RuntimeError("driver produced no samples")
    return np.array(classes, dtype=np.int64), np.array(cycles, dtype=np.int64)
