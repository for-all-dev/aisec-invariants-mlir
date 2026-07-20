"""
Fast calibration for the freezing-taint escalation's PARSING and DECISION logic
(no valgrind, no torch.compile, so ms-level in `uv run pytest`). The slow compile-
time behaviour is recorded in probe_freezing_taint.out; here we pin the pieces the
verdict rests on:

  * parse_memcheck_log finds reports at the literal-EMIT site (the Python float
    formatter that writes the constant into the generated C++), and attributes a
    report to the weight buffer ONLY when its --track-origins origin is a Valgrind
    CLIENT REQUEST (our vg_make_undefined);
  * torch's own in-region noise (origin = a stack allocation) is NOT counted as
    weight-origin -- the real report shape seen in the runs, where the emit-site
    reports' origin is severed at the aten reduction's c10::Scalar;
  * decide_taint turns the classified counts into proven-origin / emit-isolated /
    blind per the controls (frozen emit-site fires, non-frozen control silent).
"""

import textwrap

from probe_freezing_taint import decide_taint, parse_memcheck_log

# A synthetic memcheck --track-origins log fragment in the real ==PID== format, with
# the VALGRIND_PRINTF markers (**PID**) that bracket the taint region. This is the
# shape the frozen run ACTUALLY produced:
#   (1) BEFORE the region: a client-request report that must be ignored (out of region);
#   (2) IN region: torch stack-allocation noise (empty_generic) -- NOT an emit site;
#   (3) IN region: the fold's folded scalar being FORMATTED into the C++ literal
#       (format_float_internal), origin severed at the aten reduction's c10::Scalar
#       (a stack allocation) -- an emit-site report that is NOT weight-origin.
_FROZEN_LOG = textwrap.dedent(
    """\
    ==111== Memcheck, a memory error detector
    ==111== Conditional jump or move depends on uninitialised value(s)
    ==111==    at 0x1: foo (in /x/libtorch_cpu.so)
    ==111==  Uninitialised value was created by a client request
    ==111==    at 0x2: bar (in /x/vgshim.so)
    ==111==
    **111** ### LEAKCHECK taint region begin ###
    ==111== Conditional jump or move depends on uninitialised value(s)
    ==111==    at 0x3: at::detail::empty_generic (in /x/libtorch_cpu.so)
    ==111==  Uninitialised value was created by a stack allocation
    ==111==    at 0x4: baz (in /x/libtorch_cpu.so)
    ==111==
    ==111== Conditional jump or move depends on uninitialised value(s)
    ==111==    at 0x5: format_float_internal (in /x/python3.14)
    ==111==    by 0x6: _PyFloat_FormatAdvancedWriter (in /x/python3.14)
    ==111==  Uninitialised value was created by a stack allocation
    ==111==    at 0x7: c10::Scalar at::native::local_scalar_dense (in /x/libtorch_cpu.so)
    ==111==
    **111** ### LEAKCHECK taint region end ###
    ==111== ERROR SUMMARY: 3 errors
    """
)

# The non-frozen control: markers bracket the compile; the only in-region report is
# torch's generic empty_generic noise -- NO emit-site report at all (no literal is
# formatted from an undefined value, because nothing is folded).
_NONFROZEN_LOG = textwrap.dedent(
    """\
    **222** ### LEAKCHECK taint region begin ###
    ==222== Conditional jump or move depends on uninitialised value(s)
    ==222==    at 0x1: at::detail::empty_generic (in /x/libtorch_cpu.so)
    ==222==  Uninitialised value was created by a stack allocation
    ==222==    at 0x2: baz (in /x/libtorch_cpu.so)
    ==222==
    **222** ### LEAKCHECK taint region end ###
    """
)

# A hypothetical log where --track-origins DID name the weight buffer at the emit
# site (client-request origin) -- the strongest form, which the real run did NOT
# reach. Kept to pin the proven-origin branch of the decision logic.
_FROZEN_LOG_ORIGIN_NAMED = textwrap.dedent(
    """\
    **333** ### LEAKCHECK taint region begin ###
    ==333== Conditional jump or move depends on uninitialised value(s)
    ==333==    at 0x1: format_float_internal (in /x/python3.14)
    ==333==  Uninitialised value was created by a client request
    ==333==    at 0x2: vg_make_undefined (in /x/vgshim.so)
    ==333==
    **333** ### LEAKCHECK taint region end ###
    """
)


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def test_parser_finds_emit_site_report_with_severed_origin(tmp_path):
    reports = parse_memcheck_log(_write(tmp_path, "frozen.mc", _FROZEN_LOG))
    # The pre-region report is excluded; two in-region reports remain.
    assert len(reports) == 2
    emit = [r for r in reports if r["site"] == "emit"]
    assert len(emit) == 1
    # Real shape: the emit-site report's origin is severed (a stack allocation), so it
    # is NOT counted as weight-origin.
    assert emit[0]["weight_origin"] is False
    assert "format_float_internal" in " ".join(emit[0]["error_frames"])


def test_parser_nonfrozen_has_no_emit_site(tmp_path):
    reports = parse_memcheck_log(_write(tmp_path, "nf.mc", _NONFROZEN_LOG))
    assert [r for r in reports if r["site"] == "emit"] == []


def test_parser_origin_named_when_client_request_at_emit(tmp_path):
    reports = parse_memcheck_log(_write(tmp_path, "on.mc", _FROZEN_LOG_ORIGIN_NAMED))
    emit_weight = [r for r in reports if r["site"] == "emit" and r["weight_origin"]]
    assert len(emit_weight) == 1


def test_decide_emit_isolated_when_frozen_emits_and_control_silent():
    # The real outcome: emit fires under freezing, control silent, origin not named.
    frozen = {"markers": 2, "emit": 289, "emit_weight": 0}
    nonfrozen = {"markers": 2, "emit": 0, "emit_weight": 0}
    d = decide_taint(frozen, nonfrozen)
    assert d["emit_isolated"] and d["control_silent"]
    assert not d["origin_named"] and not d["proven_origin"] and not d["blind"]


def test_decide_proven_origin_when_weight_named_at_emit():
    frozen = {"markers": 2, "emit": 10, "emit_weight": 3}
    nonfrozen = {"markers": 2, "emit": 0, "emit_weight": 0}
    d = decide_taint(frozen, nonfrozen)
    assert d["proven_origin"] and d["origin_named"] and d["emit_isolated"]


def test_decide_blind_when_markers_present_but_no_emit():
    frozen = {"markers": 2, "emit": 0, "emit_weight": 0}
    nonfrozen = {"markers": 2, "emit": 0, "emit_weight": 0}
    d = decide_taint(frozen, nonfrozen)
    assert d["blind"] and not d["emit_isolated"] and not d["proven_origin"]


def test_decide_not_isolated_when_control_also_emits():
    # If the non-frozen control ALSO formats an undefined value, freezing is not
    # isolated -- must not read as an isolated signal.
    frozen = {"markers": 2, "emit": 5, "emit_weight": 0}
    nonfrozen = {"markers": 2, "emit": 5, "emit_weight": 0}
    d = decide_taint(frozen, nonfrozen)
    assert not d["emit_isolated"] and not d["control_silent"]
