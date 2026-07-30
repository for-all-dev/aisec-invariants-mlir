"""HEIR: the `--convert-to-data-oblivious` pipeline, one pass at a time.

HEIR's hardening passes are the closest thing in any of the three compilers to what this
package checks, so the useful thing to do with them is not to trust the intent but to
run the property at each stage and see which obligation each pass actually discharges.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from xdsl.parser import Parser
from xdsl.utils.exceptions import ParseError

from fcvdct.context import make_context
from fcvdct.selfcomp import check_module
from fcvdct.structural import check_lowering

ROOT = Path(__file__).parent.parent
UNROLL = 8
"""The kernels use `tensor<8x...>`, so the hardened loop unrolls exactly."""


def kernel(name: str):  # type: ignore[no-untyped-def]
    ctx = make_context()
    path = ROOT / "kernels" / "heir" / f"{name}.mlir"
    return check_module(
        ctx, Parser(ctx, path.read_text(), str(path)).parse_module(), max_visits=UNROLL
    )


def violated(name: str) -> set[str]:
    return {o.kind for o in kernel(name).obligations if o.verdict == "insecure"}


def test_the_pipeline_closes_the_channels_one_at_a_time():
    """The three stages of `--convert-to-data-oblivious`, in HEIR's own order.

    Stage 1 is the result worth having: after the extract hardening the *address*
    channel is closed and a new *control* one is open, because the emitted `scf.if`
    branches on `j == secret`. The pipeline is only safe once `--convert-if-to-select`
    has run as well, which is exactly why HEIR runs it last.
    """
    assert violated("secret_extract") == {"address"}
    assert violated("static_extract") == {"control"}
    assert violated("static_extract_select") == set()


def test_the_hardened_form_is_checked_not_vacuous():
    """9 address observations are proved equal, not skipped: the loop is unrolled."""
    result = kernel("static_extract_select")
    counts = {o.kind: o.n_observations for o in result.obligations}
    assert counts["address"] == 9
    assert result.verdict == "secure"
    assert not result.bounded, "a constant-bound affine.for must give an exact verdict"


@pytest.mark.parametrize(
    ("template", "verdict"),
    [
        ("if_to_select_speculative", "ct-preserving"),
        ("if_to_select_unspeculatable", "ct-breaking"),
        ("mod_arith_add_to_arith", "ct-breaking"),
        ("mod_arith_subifge_to_arith", "ct-preserving"),
        ("mod_arith_subifge_branchy", "ct-breaking"),
        ("tensor_ext_rotate_static", "ct-preserving"),
        ("tensor_ext_rotate_dynamic", "ct-breaking"),
    ],
)
def test_templates(template: str, verdict: str):
    ctx = make_context()
    path = ROOT / "templates" / "heir" / f"{template}.mlir"
    result = check_lowering(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert result.verdict == verdict, result.reason


def test_heirs_own_secret_marking_is_understood():
    """`{secret.secret}` is what `--secretize` writes; no re-annotation needed."""
    ctx = make_context()
    path = ROOT / "kernels" / "heir" / "secret_extract.mlir"
    assert "secret.secret" in path.read_text()
    result = check_module(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert result.verdict == "insecure"
    assert result.secrets == ("arg1",)


def test_data_dependent_affine_bounds_are_refused():
    """The case the hardenings exist to remove must not be read in as if it were static."""
    ctx = make_context()
    source = """
    func.func @f(%n: index {secret.secret}) {
      affine.for %i = 0 to %n {
        affine.yield
      }
      func.return
    }
    """
    with pytest.raises(ParseError):
        Parser(ctx, source, "dynamic").parse_module()
