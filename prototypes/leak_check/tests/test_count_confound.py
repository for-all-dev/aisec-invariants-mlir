"""
Calibration of the non-interference criterion itself (PRINCIPLES 5: a positive
control must fire and a negative control must stay silent).

`corpus.py` calibrates the criterion against real kernels; that needs valgrind
and takes ~an hour. This calibrates the DECISION LOGIC against recorded counts
by stubbing the measurement, so it runs in milliseconds without valgrind.

The cases below are the two failures this criterion exists to prevent, both
observed for real at this config point:

  * a diff SMALLER than what the harness manufactures on its own
    (softmax's -573; the context floor covers it), and
  * a diff LARGE but not repeatable across contexts
    (branchless' Ir moving 495 on md5-identical weights; only the stability
    check covers it -- no magnitude test can).

    uv run pytest test_noninterference.py -q
"""

import os

import pytest

import noninterference as NI

_ZEROS = dict(Bi=0, Dr=0, Dw=0)


def rows(*pairs):
    """One (Ir, Bc) per context."""
    return [dict(Ir=ir, Bc=bc, **_ZEROS) for ir, bc in pairs]


@pytest.fixture
def stub(monkeypatch):
    """Replay per-context counts for each class; no valgrind, no files."""

    def install(zero_rows, rand_rows, taint_leak=False):
        def fake_counts(model, secret, compile=False, repeats=NI.REPEATS, ctx_dir=None):
            return zero_rows if secret == "zero" else rand_rows

        monkeypatch.setattr(NI, "counts", fake_counts)
        monkeypatch.setattr(
            NI.I,
            "memcheck_taint",
            lambda model, secret, compile=False: {
                "leak": taint_leak,
                "reports": ["stub report"] if taint_leak else [],
            },
        )

    return install


def measure():
    return NI._measure_build("m", "zero", "rand", compile=True)


# --- negative controls: must stay silent -----------------------------------


def test_context_artifact_does_not_fire(stub):
    """
    branchless-shaped: counts swing by hundreds across contexts and the paired
    diff disagrees with itself. Large, deterministic, and meaningless.
    """
    stub(
        rows((99_485, 400), (99_466, 400), (99_212, 400)),
        rows((99_212, 400), (99_707, 400), (99_564, 400)),
    )
    r = measure()
    assert not r["ir_stable"]  # +(-273), +241, +352 -- no agreement
    assert not r["distinguishable"]


def test_large_but_unstable_does_not_fire(stub):
    """
    The guard a floor cannot provide: a diff that CLEARS the floor but doesn't
    reproduce across contexts. Both classes move ~1000 with layout, so the
    floor is ~1000, but the paired diff swings 4000..6000 -- bigger than
    either class moves alone, which no single-class spread can catch.
    """
    stub(
        rows((100_000, 400), (101_000, 400), (100_000, 400)),
        rows((106_000, 400), (105_000, 400), (106_000, 400)),
    )
    r = measure()
    assert abs(r["ir_diff"]) > r["ir_floor"]  # magnitude alone WOULD fire
    assert not r["ir_stable"]  # ...but it isn't repeatable
    assert not r["distinguishable"]


def test_sub_floor_diff_does_not_fire(stub):
    """
    softmax-shaped: a perfectly stable -573/-93 that is nonetheless smaller
    than what layout alone does to each class (Ir ~1700, Bc ~274).
    """
    stub(
        rows((2_504_002, 130_284), (2_505_698, 130_558), (2_505_698, 130_558)),
        rows((2_503_429, 130_191), (2_505_125, 130_465), (2_505_125, 130_465)),
    )
    r = measure()
    assert r["ir_pairs"] == [-573] * 3 and r["ir_stable"]  # stable, but...
    assert abs(r["ir_diff"]) <= r["ir_floor"]  # ...inside what layout alone does
    assert abs(r["bc_diff"]) <= r["bc_floor"]
    assert not r["distinguishable"]


def test_branchless_exact_zero(stub):
    """A truly oblivious kernel: identical in every context."""
    stub(
        rows((2_000_000, 400), (2_000_123, 400), (1_999_888, 400)),
        rows((2_000_000, 400), (2_000_123, 400), (1_999_888, 400)),
    )
    r = measure()
    assert r["ir_diff"] == 0 and r["ir_pairs"] == [0, 0, 0]
    assert not r["distinguishable"]


# --- positive controls: must fire ------------------------------------------


def test_real_leak_fires(stub):
    """exp-shaped: same diff in every context, orders above the floor."""
    stub(
        rows((3_000_000, 5_000), (3_000_400, 5_000), (2_999_700, 5_000)),
        rows((38_061_760, 8_416_064), (38_062_160, 8_416_064), (38_061_460, 8_416_064)),
    )
    r = measure()
    assert r["ir_pairs"] == [35_061_760] * 3  # identical across contexts
    assert r["ir_stable"] and r["distinguishable"]


def test_bc_alone_can_distinguish(stub):
    """Equal Ir, branch counts differ stably: still a secret-dependent path."""
    stub(
        rows((2_000_000, 400), (2_000_000, 400), (2_000_000, 400)),
        rows((2_000_000, 9_000), (2_000_000, 9_000), (2_000_000, 9_000)),
    )
    r = measure()
    assert r["bc_stable"] and r["distinguishable"]


def test_taint_needs_no_magnitude(stub):
    """Taint reports a dependence, not a magnitude: no floor, no stability."""
    stub(
        rows((99_485, 400), (99_466, 400), (99_212, 400)),
        rows((99_212, 400), (99_707, 400), (99_564, 400)),
        taint_leak=True,
    )
    r = measure()
    assert not r["counts_distinguish"]  # counts are uninterpretable...
    assert r["distinguishable"]  # ...but taint fired


# --- the context machinery itself ------------------------------------------


@pytest.fixture
def secret_file(tmp_path):
    p = tmp_path / "w.npy"
    p.write_bytes(b"x" * 64)
    return str(p)


def test_context_varies_path_length(secret_file):
    """
    The floor is only meaningful if repeats actually differ. Path length is the
    knob: identical weights at different paths counted 99,212 vs 99,707.
    """
    with NI.context_dir() as d:
        with NI._context(secret_file, 0, d) as p0, NI._context(secret_file, 1, d) as p1:
            assert len(p0) != len(p1)
            assert os.path.exists(p0) and os.path.exists(p1)
        assert not os.path.exists(p0)  # cleaned up after use


def test_both_classes_share_a_context_per_repeat(tmp_path):
    """Pairing requires it: repeat i must be the same path for either class."""
    a, b = tmp_path / "a.npy", tmp_path / "b.npy"
    a.write_bytes(b"a" * 64)
    b.write_bytes(b"b" * 64)
    with NI.context_dir() as d:
        with NI._context(str(a), 2, d) as pa:
            seen = pa
        with NI._context(str(b), 2, d) as pb:
            assert pb == seen  # same context, different secret


def test_context_dirs_are_private(secret_file):
    """
    Two concurrent measurements must not share paths. A fixed shared location
    let a test delete a running corpus measurement's secret mid-run.
    """
    with NI.context_dir() as d1, NI.context_dir() as d2:
        assert d1 != d2
        with NI._context(secret_file, 0, d1) as p1, NI._context(secret_file, 0, d2) as p2:
            assert p1 != p2
            assert os.path.exists(p1) and os.path.exists(p2)
        # ...but the LENGTH must match, or the nuisance variable drifts on its own
        assert len(d1) == len(d2)
    assert not os.path.exists(d1)
