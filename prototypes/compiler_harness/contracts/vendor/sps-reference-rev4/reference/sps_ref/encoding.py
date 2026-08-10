"""Exact LSB-numbered bit packing used by executable reference fixtures."""

from __future__ import annotations

from .errors import SchemaError
from .terms import Term, bv_lit, extract


def encode_bits(value: int, bit_width: int, byte_order: str) -> bytes:
    if (
        not isinstance(bit_width, int)
        or isinstance(bit_width, bool)
        or bit_width <= 0
    ):
        raise SchemaError("bit width must be positive")
    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaError("value must be an integer")
    if byte_order not in {"LittleEndian", "BigEndian"}:
        raise SchemaError("invalid byte order")
    byte_width = (bit_width + 7) // 8
    if value < 0 or value >= 1 << bit_width:
        raise SchemaError("value does not fit declared bit width")
    significance = bytes((value >> (8 * index)) & 0xFF for index in range(byte_width))
    return significance if byte_order == "LittleEndian" else significance[::-1]


def decode_bits(raw: bytes, bit_width: int, byte_order: str) -> int:
    if (
        not isinstance(bit_width, int)
        or isinstance(bit_width, bool)
        or bit_width <= 0
    ):
        raise SchemaError("bit width must be positive")
    if not isinstance(raw, bytes):
        raise SchemaError("encoded value must be bytes")
    if byte_order not in {"LittleEndian", "BigEndian"}:
        raise SchemaError("invalid byte order")
    byte_width = (bit_width + 7) // 8
    if len(raw) != byte_width:
        raise SchemaError("encoded byte length mismatch")
    significance = raw if byte_order == "LittleEndian" else raw[::-1]
    value = sum(byte << (8 * index) for index, byte in enumerate(significance))
    if value >= 1 << bit_width:
        raise SchemaError("nonzero canonical high-padding bit")
    return value


def encode_term_bytes(value: Term, byte_order: str) -> list[Term]:
    if value.sort != "BV" or value.width is None:
        raise SchemaError("only bitvectors can be byte encoded")
    byte_width = (value.width + 7) // 8
    padded_width = byte_width * 8
    significance: list[Term] = []
    for index in range(byte_width):
        low = 8 * index
        available = max(0, min(8, value.width - low))
        if available == 8:
            significance.append(extract(value, low, 8))
        elif available > 0:
            partial = extract(value, low, available)
            # Canonical zero high padding is represented as an 8-bit value.
            significance.append(
                Term("BV", 8, "concat", (bv_lit(8 - available, 0), partial))
            )
        else:
            significance.append(bv_lit(8, 0))
    if padded_width < value.width:
        raise SchemaError("internal byte packing width error")
    return significance if byte_order == "LittleEndian" else list(reversed(significance))
