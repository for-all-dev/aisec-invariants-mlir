"""
Tests for the differential non-interference verdict logic (noninterference.py).

The real instruments shell out to valgrind + torch; here we substitute them so
we can drive every quadrant of the 2x2 truth table (distinguishable under
eager? x under compiled?) deterministically and cheaply. What's under test is
the *decision*, which is where a bug would silently mislabel a compiler leak.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

import instruments
import noninterference as NI

ZERO, RAND = "zero", "rand"


def _install_fakes(monkeypatch, *, eager_leak, compiled_leak, channel="cg"):
    """Make the model distinguishable (or not) per build, via a chosen channel.

    channel="cg"    -> the difference shows up in the callgrind Ir count
    channel="taint" -> the difference shows up as a memcheck taint report
    """

    def callgrind_count(model, secret, compile=False):
        distinguish = compiled_leak if compile else eager_leak
        bumped = channel == "cg" and distinguish and secret == RAND
        return {"Ir": 100 if bumped else 50, "Bc": 5, "Bi": 0}

    def memcheck_taint(model, secret, compile=False):
        distinguish = compiled_leak if compile else eager_leak
        leak = channel == "taint" and distinguish
        return {"leak": leak, "reports": ["dep"] if leak else []}

    monkeypatch.setattr(instruments, "callgrind_count", callgrind_count)
    monkeypatch.setattr(instruments, "memcheck_taint", memcheck_taint)


@pytest.mark.parametrize("channel", ["cg", "taint"])
@pytest.mark.parametrize(
    ("eager_leak", "compiled_leak", "expected"),
    [
        (True, True, "authored"),
        (False, True, "compiler-introduced"),
        (True, False, "compiler-removed"),
        (False, False, "oblivious"),
    ],
)
def test_verdict_quadrants(monkeypatch, channel, eager_leak, compiled_leak, expected):
    _install_fakes(monkeypatch, eager_leak=eager_leak, compiled_leak=compiled_leak, channel=channel)
    result = NI.analyze("m", ZERO, RAND)
    assert result["verdict"] == expected
    assert result["eager"]["distinguishable"] is eager_leak
    assert result["compiled"]["distinguishable"] is compiled_leak


def test_diff_is_signed_but_any_nonzero_distinguishes(monkeypatch):
    # A leak that shows up as *fewer* instructions for the random secret must
    # still count: the criterion is "differs", not "increases".
    def callgrind_count(model, secret, compile=False):
        return {"Ir": 10 if secret == RAND else 50, "Bc": 5, "Bi": 0}

    monkeypatch.setattr(instruments, "callgrind_count", callgrind_count)
    monkeypatch.setattr(
        instruments, "memcheck_taint", lambda *a, **k: {"leak": False, "reports": []}
    )
    result = NI.analyze("m", ZERO, RAND)
    assert result["eager"]["ir_diff"] == -40
    assert result["eager"]["distinguishable"] is True
    assert result["verdict"] == "authored"


@given(
    eager_leak=st.booleans(),
    compiled_leak=st.booleans(),
    channel=st.sampled_from(["cg", "taint"]),
)
def test_verdict_is_a_pure_function_of_the_two_booleans(eager_leak, compiled_leak, channel):
    # Property: the verdict depends only on (distinguishable-in-eager,
    # distinguishable-in-compiled), whatever channel carried the signal.
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    try:
        _install_fakes(mp, eager_leak=eager_leak, compiled_leak=compiled_leak, channel=channel)
        verdict = NI.analyze("m", ZERO, RAND)["verdict"]
    finally:
        mp.undo()

    expected = {
        (True, True): "authored",
        (False, True): "compiler-introduced",
        (True, False): "compiler-removed",
        (False, False): "oblivious",
    }[(eager_leak, compiled_leak)]
    assert verdict == expected
