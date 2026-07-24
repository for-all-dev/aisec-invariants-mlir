"""Tests for the static FTZ/DAZ parser (no binary / no objdump needed)."""

from infoleak.ftz import parse_ftz

# Real disassembly shape from a gcc -m32 -ffast-math build: DAZ via or $0x40,%eax
# and FTZ via or $0x80,%ah (i.e. bit 15), then ldmxcsr.
FASTMATH = """
0804977b <set_fast_math>:
 804977b:\t83 c8 40   \tor     $0x40,%eax
 804977e:\t80 cc 80   \tor     $0x80,%ah
 8049781:\t89 44 24 0c\tmov    %eax,0xc(%esp)
 8049785:\t0f ae 54 24 0c\tldmxcsr 0xc(%esp)
 804978a:\tc3         \tret
"""

# A default build: no ldmxcsr anywhere.
PLAIN = """
08049180 <main>:
 8049180:\t55         \tpush   %ebp
 8049181:\t89 e5      \tmov    %esp,%ebp
 8049183:\tc3         \tret
"""

# Only DAZ set, FTZ missing -> partial.
DAZ_ONLY = """
0804977b <x>:
 804977b:\t83 c8 40   \tor     $0x40,%eax
 8049781:\t89 44 24 0c\tmov    %eax,0xc(%esp)
 8049785:\t0f ae 54 24 0c\tldmxcsr 0xc(%esp)
"""


def test_fastmath_is_flushed():
    r = parse_ftz(FASTMATH)
    assert r.has_ldmxcsr
    assert r.ftz and r.daz
    assert r.denormals_flushed
    assert r.verdict == "flushed"


def test_plain_build_has_no_flush():
    r = parse_ftz(PLAIN)
    assert not r.has_ldmxcsr
    assert not r.denormals_flushed
    assert r.verdict == "none"


def test_daz_only_is_partial():
    r = parse_ftz(DAZ_ONLY)
    assert r.daz and not r.ftz
    assert not r.denormals_flushed
    assert r.verdict == "partial"
