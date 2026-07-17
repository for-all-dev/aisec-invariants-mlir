"""
Tests for the deterministic parsers in instruments.py.

These lock in the contract the verdict logic relies on: the callgrind reader
picks the fully-counted `totals:` line (not `summary:`), and the memcheck reader
counts leak reports *only* inside the marked taint region.
"""

import pytest

import instruments

CALLGRIND = """\
version: 1
creator: callgrind
positions: line
events: Ir Bc Bi Dr Dw
summary: 0 0 0 0 0
fl=main.py
fn=forward
10 123 45 6 7 8
totals: 123 45 6 7 8
"""


def test_parse_callgrind_reads_totals(tmp_path):
    p = tmp_path / "out.cg"
    p.write_text(CALLGRIND)
    counts = instruments._parse_callgrind(str(p))
    assert counts == {"Ir": 123, "Bc": 45, "Bi": 6, "Dr": 7, "Dw": 8}


def test_parse_callgrind_ignores_summary_line(tmp_path):
    # `summary:` tracks *collection* (left off) and reads 0; it must not shadow
    # the real `totals:` figures.
    p = tmp_path / "out.cg"
    p.write_text(CALLGRIND)
    assert instruments._parse_callgrind(str(p))["Ir"] == 123


def test_parse_callgrind_raises_without_totals(tmp_path):
    p = tmp_path / "bad.cg"
    p.write_text("events: Ir Bc Bi\n")  # no totals line
    with pytest.raises(RuntimeError):
        instruments._parse_callgrind(str(p))


LEAK = "==42== Conditional jump depends on uninitialised value(s)"

MEMCHECK_LEAK = f"""\
==42== Memcheck, a memory error detector
==42== taint region begin
{LEAK}
==42== taint region end
==42== {LEAK}
"""

MEMCHECK_CLEAN = """\
==42== taint region begin
==42== all good in here
==42== taint region end
"""


def test_parse_memcheck_counts_only_in_region(tmp_path):
    p = tmp_path / "leak.mc"
    p.write_text(MEMCHECK_LEAK)
    res = instruments._parse_memcheck(str(p))
    # One report inside the region; the identical line *after* `end` is ignored.
    assert res["leak"] is True
    assert len(res["reports"]) == 1


def test_parse_memcheck_clean(tmp_path):
    p = tmp_path / "clean.mc"
    p.write_text(MEMCHECK_CLEAN)
    res = instruments._parse_memcheck(str(p))
    assert res["leak"] is False
    assert res["reports"] == []
