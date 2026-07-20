"""
Tests for the overnight sweep orchestrator's decision surface.

The driver runs nothing itself worth testing with valgrind; what can silently rot
is the verdict scanning (a missed hit reads as a clean night) and the skip-if-
absent logic (the surface probes land later, so the funnel must tolerate their
absence). Both are exercised here without launching a single torch job.
"""

import sweep_overnight as S


def test_hit_signatures_match_real_probe_output():
    # Lines these probes actually print; every one must register as a hit.
    for line in [
        "  VERDICT  : COMPILER-INTRODUCED  [!! predicted oblivious !!]",
        "eager    : DISTINGUISHABLE dIr=+35,061,760",
        "-> LEAKS",
        "SMOKING GUN: secret bytes recovered from world-readable .so",
        "recovered folded literal: scale=0.787402 (== max|w|/127)",
    ]:
        assert S.HIT_PAT.search(line), line


def test_clean_lines_do_not_falsely_hit():
    for line in [
        "  VERDICT  : OBLIVIOUS  [MATCHES PREDICTION]",
        "attacker AUC=0.501  leakage strength=0.002  -> clean",
        "A1. generated code identical (normalized): True",
    ]:
        assert not S.HIT_PAT.search(line), line


def test_suspect_signatures_flag_tripped_controls():
    # A hit sitting next to one of these is not evidence — the report must say so.
    for line in [
        "HARNESS ARTIFACT — within-class spread is nonzero",
        "dIr under floor -> noise",
        "[varies across contexts: layout, not secret]",
    ]:
        assert S.SUSPECT_PAT.search(line), line


def test_absent_script_is_skipped_not_run(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "HERE", str(tmp_path))
    monkeypatch.setattr(S, "LOG_DIR", str(tmp_path / "logs"))
    job = S.Job("ghost", 0, "does_not_exist.py")
    assert not job.present
    r = S.run_job(job, "ts")
    assert r["status"] == "absent" and r["log"] is None and r["hits"] == []


def test_report_separates_guns_from_tripped_controls(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "HERE", str(tmp_path))
    gun = {
        "job": S.Job("g", 0, "g.py"),
        "status": "ok",
        "log": str(tmp_path / "g.log"),
        "hits": ["-> LEAKS"],
        "suspects": [],
    }
    # A "hit" whose control tripped must NOT be promoted to a clean gun.
    tainted = {
        "job": S.Job("t", 0, "t.py"),
        "status": "ok",
        "log": str(tmp_path / "t.log"),
        "hits": ["DISTINGUISHABLE"],
        "suspects": ["layout, not secret"],
    }
    clean = {
        "job": S.Job("c", 0, "c.py"),
        "status": "ok",
        "log": str(tmp_path / "c.log"),
        "hits": [],
        "suspects": [],
    }
    for r in (gun, tainted, clean):
        # str(): these result dicts hold mixed value types, so ty infers
        # `r["log"]` as a union that open()'s overloads reject. It is a str.
        open(str(r["log"]), "w").close()
    path, guns = S.write_report({"torch": "x"}, [gun, tainted, clean], "ts")
    body = open(str(path)).read()
    assert "Candidate guns (2)" in body  # gun + tainted both have hits
    assert "Control flags — treat as unverified" in body  # tainted is annotated
    assert "g.log" in body and "c.log" in body
