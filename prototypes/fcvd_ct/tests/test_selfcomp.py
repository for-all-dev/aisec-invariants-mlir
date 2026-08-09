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


# ---- step 4: the taint prefilter ------------------------------------------------


PREFILTER_CORPUS = [
    "ct_mask",
    "public_index",
    "secret_index",
    "secret_branch",
    "secret_divisor",
    "secret_free",
]


@pytest.mark.parametrize("kernel", PREFILTER_CORPUS)
def test_prefilter_never_changes_a_verdict(kernel: str):
    """The prefilter is one-sided: skipping a solver call must never move a verdict.

    Byte-identical obligations with and without it, over the whole labelled corpus --
    a prefilter that decided anything the solver would not have decided fails here.
    """
    ctx, module = load(kernel)
    with_filter = check_module(ctx, module)
    ctx2, module2 = load(kernel)
    without = check_module(ctx2, module2, prefilter=False)
    assert with_filter.verdict == without.verdict
    for one, other in zip(with_filter.obligations, without.obligations, strict=True):
        assert (one.kind, one.verdict, one.n_observations) == (
            other.kind,
            other.verdict,
            other.n_observations,
        )


def test_prefilter_skips_the_clean_sink_and_says_so():
    """public_index: the address sink exists (1 observation) but only the value is
    secret, so the solver is skipped -- and the skip is printed, never silent."""
    ctx, module = load("public_index")
    result = check_module(ctx, module)
    address = next(o for o in result.obligations if o.kind == "address")
    assert address.verdict == "secure"
    assert address.n_observations == 1
    assert "solver skipped" in address.reason


def test_prefilter_counts_the_guard_as_part_of_the_sink():
    """An address that is a public constant, observed under a secret branch: the value
    is clean but the guard is not, so the prefilter must NOT skip the address query --
    `traces_agree` compares guards, and the two runs may disagree on reaching it."""
    source = """
builtin.module {
  func.func @guarded(%t: memref<8xi8>, %s: i1 {fcvdct.secret}) -> i8 {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %r = scf.if %s -> (i8) {
      %a = memref.load %t[%c0] : memref<8xi8>
      scf.yield %a : i8
    } else {
      %b = memref.load %t[%c1] : memref<8xi8>
      scf.yield %b : i8
    }
    func.return %r : i8
  }
}
"""
    ctx, module = load("guarded", source)
    result = check_module(ctx, module)
    address = next(o for o in result.obligations if o.kind == "address")
    assert "solver skipped" not in address.reason, (
        "a secret guard taints the sink; the solver must be consulted"
    )
    control = next(o for o in result.obligations if o.kind == "control")
    assert control.verdict == "insecure", "the branch on the secret is the leak itself"
