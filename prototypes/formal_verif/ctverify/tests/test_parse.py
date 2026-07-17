"""Parser tests on real binsec -checkct output samples (no binsec needed)."""

from ctverify import DEFAULT_CT, LAYER_A, parse_checkct

CONTROL_FLOW_LEAK = """\
[checkct:result] Instruction 0x8049908 has control flow leak (0.042s)
[checkct:result] Program status is : insecure (0.059)
[checkct:info] 4 / 5 control flow checks pass
[checkct:info] 38 / 38 memory access checks pass
"""

DIVISOR_LEAK = """\
[checkct:result] Instruction 0x8049934 has divisor leak (0.042s)
[checkct:result] Program status is : insecure (0.145)
[checkct:info] 3 / 3 control flow checks pass
[checkct:info] 27 / 27 memory access checks pass
[checkct:info] 0 / 0 multiplication checks pass
[checkct:info] 1 / 2 division checks pass
"""

SECURE = """\
[checkct:result] Program status is : secure (0.030)
[checkct:info] 5 / 5 control flow checks pass
[checkct:info] 27 / 27 memory access checks pass
"""


def test_control_flow_leak():
    res = parse_checkct(CONTROL_FLOW_LEAK, DEFAULT_CT)
    assert res.verdict == "insecure"
    assert not res.secure
    assert len(res.leaks) == 1
    assert res.leaks[0].instruction == "0x8049908"
    assert res.leaks[0].kind == "control flow"
    assert res.stats["control flow"] == [4, 5]


def test_divisor_leak_kind_and_stats():
    res = parse_checkct(DIVISOR_LEAK, LAYER_A)
    assert res.verdict == "insecure"
    assert res.leaks[0].kind == "divisor"
    assert res.stats["division"] == [1, 2]
    assert res.stats["multiplication"] == [0, 0]


def test_secure_has_no_leaks():
    res = parse_checkct(SECURE, DEFAULT_CT)
    assert res.verdict == "secure"
    assert res.secure
    assert res.leaks == []


def test_unknown_when_no_status_line():
    assert parse_checkct("garbage output", DEFAULT_CT).verdict == "unknown"


def test_to_dict_is_json_ready():
    res = parse_checkct(DIVISOR_LEAK, LAYER_A)
    d = res.to_dict()
    assert d["verdict"] == "insecure"
    assert d["secure"] is False
    assert d["leaks"][0]["kind"] == "divisor"
