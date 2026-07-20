"""
Calibration of the exfiltration detector (PRINCIPLES §5: a positive control must
fire and a negative control must stay silent).

`probe_exfil.py`'s full run compiles a model with AOTInductor and takes tens of
seconds; this test exercises only the DETECTOR (sentinel construction, scanning,
recovery, controls) in milliseconds, so CI can trust the instrument without
running a compile.

    uv run pytest tests/test_exfil.py -q
"""

import os
import tempfile

import probe_exfil as PE


def test_controls_calibrate():
    """The positive control fires and the negative control stays silent."""
    d = tempfile.mkdtemp()
    try:
        pos_hit, neg_hit = PE.run_controls(d)
    finally:
        os.rmdir(d)
    assert pos_hit is True
    assert neg_hit is False


def test_weight_contains_every_sentinel():
    """Each sentinel's 32-byte needle is present in the raw weight bytes."""
    raw = PE.build_weight().tobytes()
    for name, needle in PE.needles().items():
        assert needle in raw, f"{name} missing from weight bytes"


def test_scan_finds_and_recovers_sentinels():
    """A file of weight bytes is detected; the sentinel run is recoverable."""
    d = tempfile.mkdtemp()
    try:
        f = os.path.join(d, "artifact.bin")
        with open(f, "wb") as fh:
            fh.write(PE.build_weight().tobytes())
        hits = PE.scan(d)
        assert len(hits) == 1
        assert set(hits[0]["sentinels"]) == set(PE.SENTINELS)
        snip = PE.recover_snippet(f, "ascii_LEAK")
        assert snip.startswith(b"LEAK")
    finally:
        for name in os.listdir(d):
            os.remove(os.path.join(d, name))
        os.rmdir(d)


def test_scan_silent_on_random_bytes():
    """Non-sentinel content produces no hit (no false positives)."""
    import numpy as np

    d = tempfile.mkdtemp()
    try:
        f = os.path.join(d, "rand.bin")
        rng = np.random.default_rng(1)
        with open(f, "wb") as fh:
            fh.write(rng.integers(0, 256, size=65536, dtype=np.uint8).tobytes())
        assert PE.scan(d) == []
    finally:
        for name in os.listdir(d):
            os.remove(os.path.join(d, name))
        os.rmdir(d)


def test_readability_and_ancestor_chain():
    """Mode decoding and the ancestor-chain walk behave as the report relies on."""
    assert PE.readability(0o644) == "group=r other=r"
    assert PE.readability(0o600) == "group=- other=-"
    assert PE.readability(0o640) == "group=r other=-"
    d = tempfile.mkdtemp(dir="/tmp")
    try:
        f = os.path.join(d, "x")
        chain = PE.ancestor_chain(f)
        assert chain[-1][1] == "/tmp"
    finally:
        os.rmdir(d)
