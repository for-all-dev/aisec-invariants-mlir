"""Tests for the cache-line leakage-contract computation."""

from hypothesis import given
from hypothesis import strategies as st

from ctverify import AccessLayout, cacheline_verdict


def test_secure_ct_stays_secure():
    # No secret-dependent address -> coarser observer sees nothing either.
    res = cacheline_verdict("secure", AccessLayout(4, 8))
    assert res.contract_verdict == "secure"


def test_small_table_fits_one_line():
    # 8 * 4 = 32 B -> one cache line -> secure under [cache-line] though [ct] leaks.
    res = cacheline_verdict("insecure", AccessLayout(elem_size=4, index_count=8))
    assert res.contract_verdict == "secure"
    assert res.distinct_lines == 1
    assert res.span_bytes == 32


def test_wide_table_crosses_lines():
    res = cacheline_verdict("insecure", AccessLayout(elem_size=4, index_count=64))
    assert res.contract_verdict == "insecure"
    assert res.distinct_lines == 4
    assert res.span_bytes == 256


def test_embedding_row_gather_crosses_lines():
    res = cacheline_verdict("insecure", AccessLayout(elem_size=128, index_count=32))
    assert res.contract_verdict == "insecure"
    assert res.distinct_lines == 32


def test_unaligned_is_conservative():
    res = cacheline_verdict("insecure", AccessLayout(4, 8, aligned=False))
    assert res.contract_verdict == "insecure"


def test_custom_line_size():
    # With a 16 B line, the same 32 B span now crosses lines.
    res = cacheline_verdict("insecure", AccessLayout(4, 8), line_bytes=16)
    assert res.contract_verdict == "insecure"


@given(
    elem=st.integers(min_value=1, max_value=4096),
    count=st.integers(min_value=2, max_value=4096),
    line=st.sampled_from([16, 32, 64, 128]),
)
def test_secure_iff_span_within_one_line(elem, count, line):
    # For an aligned base at offset 0, all reachable addresses share one line
    # exactly when the max offset (count-1)*elem is below the line size.
    res = cacheline_verdict("insecure", AccessLayout(elem, count), line_bytes=line)
    expected_secure = (count - 1) * elem < line
    assert (res.contract_verdict == "secure") is expected_secure
