"""onnx-mlir: the gather lowering, and what the compiler does not offer.

The check that matters here is not that a lowering is wrong -- `--convert-onnx-to-krnl`
does the ordinary thing -- but that the ordinary thing turns private indices into
addresses, and that onnx-mlir, unlike HEIR, ships no pass that undoes it.
"""

from __future__ import annotations

from pathlib import Path

from xdsl.parser import Parser

from fcvdct.context import make_context
from fcvdct.selfcomp import check_module
from fcvdct.structural import check_lowering

ROOT = Path(__file__).parent.parent


def kernel(name: str, unroll: int = 8):  # type: ignore[no-untyped-def]
    ctx = make_context()
    path = ROOT / "kernels" / "onnx_mlir" / f"{name}.mlir"
    return check_module(
        ctx, Parser(ctx, path.read_text(), str(path)).parse_module(), max_visits=unroll
    )


def test_gather_lowering_creates_the_address_channel():
    ctx = make_context()
    path = ROOT / "templates" / "onnx_mlir" / "gather_to_krnl.mlir"
    result = check_lowering(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert result.verdict == "ct-breaking", result.reason
    assert (result.n_source_observations, result.n_target_observations) == (0, 3)


def test_the_lowered_gather_leaks_and_the_oblivious_one_does_not():
    leaking = kernel("gather_secret_index")
    assert leaking.verdict == "insecure"
    assert {o.kind for o in leaking.obligations if o.verdict == "insecure"} == {"address"}

    oblivious = kernel("gather_oblivious")
    assert oblivious.verdict == "secure"
    # Proved equal, not absent: every one of the 18 reads is compared.
    counts = {o.kind: o.n_observations for o in oblivious.obligations}
    assert counts["address"] == 18
    assert not oblivious.bounded
