"""The self-composition driver: one labelled kernel, four obligations.

The corpus is built in polarity pairs -- for every kernel that must come back secure
there is one that differs only in what the secret steers -- so a checker that always
answered "secure" would fail here, and so would one that always answered "insecure".
"""

from __future__ import annotations

from pathlib import Path

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.parser import Parser

from fcvdct.context import make_context
from fcvdct.selfcomp import check_module, separating_secrets

KERNELS = Path(__file__).parent.parent / "kernels"


def load(name: str, source: str | None = None) -> tuple[Context, ModuleOp]:
    ctx = make_context()
    text = (KERNELS / f"{name}.mlir").read_text() if source is None else source
    return ctx, Parser(ctx, text, name).parse_module()


@pytest.mark.parametrize(
    ("kernel", "verdict", "violated"),
    [
        ("ct_mask", "secure", None),
        ("public_index", "secure", None),
        ("secret_index", "insecure", "address"),
        ("secret_branch", "insecure", "control"),
        ("secret_divisor", "insecure", "latency"),
        ("secret_free", "insecure", "resource"),
        ("unsupported_float", "unknown", None),
    ],
)
def test_corpus(kernel: str, verdict: str, violated: str | None):
    ctx, module = load(kernel)
    result = check_module(ctx, module)
    assert result.verdict == verdict
    if violated is None:
        return
    # The obligation that fails must be the named one and only it: a verdict is
    # supposed to say which channel leaks, not merely that something does.
    insecure = {o.kind for o in result.obligations if o.verdict == "insecure"}
    assert insecure == {violated}


def test_unsupported_never_passes_silently():
    """A kernel we cannot lower is `unknown`, with the reason, and never `secure`."""
    ctx, module = load("unsupported_float")
    result = check_module(ctx, module)
    assert result.verdict == "unknown"
    assert "f32" in result.reason


def test_unlabelled_kernel_is_unknown():
    """No labelling, no property. This must not be reported as a proof."""
    ctx, module = load(
        "unlabelled",
        """
        func.func @unlabelled(%a: i32, %b: i32) -> i32 {
          %q = arith.divui %a, %b : i32
          func.return %q : i32
        }
        """,
    )
    result = check_module(ctx, module)
    assert result.verdict == "unknown"
    assert "marks no argument secret" in result.reason


def test_labelling_is_load_bearing():
    """The verdict follows the labels, not the shape of the program.

    `public_index` is secure because the index is public. Marking that same argument
    secret -- changing nothing else -- must flip the address obligation.
    """
    source = (KERNELS / "public_index.mlir").read_text()
    ctx, module = load(
        "public_index", source.replace("%public: index", "%public: index {fcvdct.secret}")
    )
    result = check_module(ctx, module)
    assert result.verdict == "insecure"
    assert {o.kind for o in result.obligations if o.verdict == "insecure"} == {"address"}


def test_staging_ni_attribute_is_accepted():
    """One marking serves both tools: `prototypes/Staging_NI` already uses this one."""
    source = (KERNELS / "secret_index.mlir").read_text()
    ctx, module = load("secret_index", source.replace("fcvdct.secret", "stagingni.protected"))
    assert check_module(ctx, module).verdict == "insecure"


def test_counterexample_names_the_two_secrets():
    """A violated obligation comes with the pair of inputs that separates the runs."""
    ctx, module = load("secret_index")
    result = check_module(ctx, module)
    (address,) = [o for o in result.obligations if o.kind == "address"]
    secrets = dict(separating_secrets(address.counterexample))
    assert len(secrets) == 2
    assert secrets["secret1_run0"] != secrets["secret1_run1"]


def test_secure_verdict_reports_what_it_checked():
    """`secure` with zero observations of a kind means "nothing of that kind happens",
    and the counts are part of the result so the two cannot be confused."""
    ctx, module = load("public_index")
    result = check_module(ctx, module)
    counts = {o.kind: o.n_observations for o in result.obligations}
    assert counts["address"] == 1
    assert counts["control"] == 0
