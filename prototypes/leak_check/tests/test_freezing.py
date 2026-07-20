"""
Fast calibration for the freezing probe's pure logic (no torch.compile, so ms-level
in `uv run pytest`). The compile-time behaviour itself is recorded in
probe_freezing.out; here we pin the pieces the driver's verdict rests on:

  * the bait actually holds the folded statistic fixed to the target (`_draw`/`stat`),
    so class A vs class B differ ONLY in that statistic;
  * `recover_literal` pulls the folded scalar back out of a kernel body and matches
    it against the expected statistic.
"""

import numpy as np
import pytest

import corpus_freezing as CF
from probe_freezing import recover_literal

# The underlying statistic each `_draw` is built to hit (the bait target). The
# folded scalar `stat()` returns is a function OF this (e.g. maxabs/127), which the
# recovery test covers separately.
_UNDERLYING = {
    "quant_scale": lambda w: float(np.max(np.abs(w))),
    "wmax": lambda w: float(np.max(w)),
    "wsum": lambda w: float(np.sum(w)),
    "wnorm": lambda w: float(np.linalg.norm(w.reshape(-1))),
}


@pytest.mark.parametrize("surface", CF.names())
def test_draw_hits_target_statistic(surface):
    _stat_name, va, vb = CF._BAIT[surface]
    a = CF._draw(surface, va, seed=1)
    b = CF._draw(surface, vb, seed=2)
    # The draw must land the class on its bait target (float32 rounding tolerated),
    # so the class label means what it says and A/B differ only in that statistic.
    f = _UNDERLYING[surface]
    assert f(a) == pytest.approx(va, rel=1e-4)
    assert f(b) == pytest.approx(vb, rel=1e-4)


@pytest.mark.parametrize("surface", CF.names())
def test_classes_differ_in_the_folded_statistic(surface):
    (_, a), (_, b), (_, _c) = CF.secret_classes(surface)
    assert CF.stat(surface, a) != CF.stat(surface, b)


def test_draw_is_deterministic():
    a1 = CF._draw("quant_scale", 1.0, seed=1)
    a2 = CF._draw("quant_scale", 1.0, seed=1)
    assert np.array_equal(a1, a2)


def test_recover_literal_extracts_the_folded_scalar():
    body = (
        'extern "C" void kernel() {\n'
        "  auto tmp1 = static_cast<float>(0.007874015718698502);\n"
        "  auto tmp2 = at::vec::Vectorized<float>(tmp1);\n"
        "}"
    )
    assert recover_literal(body, expected=1.0 / 127.0) == pytest.approx(1.0 / 127.0, rel=1e-3)


def test_recover_literal_returns_none_when_absent():
    body = 'extern "C" void kernel() { auto tmp0 = load(in_ptr0); }'
    assert recover_literal(body, expected=0.5) is None
