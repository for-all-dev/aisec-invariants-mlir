"""Template families (issue #63): one rule, checked on every instance a sweep declares."""

from __future__ import annotations

from pathlib import Path

import pytest
from xdsl.parser import Parser

from fcvdct.context import make_context
from fcvdct.structural import _run_z3, build_equivalence_query, check_equivalence
from fcvdct.sweep import check_template_text, instances, is_closed

ROOT = Path(__file__).parent.parent
POLYGEIST = ROOT / "templates" / "polygeist"


def test_sweep_is_the_cartesian_product():
    family = instances(
        "// fcvdct.sweep W = i8, i32\n// fcvdct.sweep N = 1, 4\nmemref<${N}x${W}> ${N * 2}\n"
    )
    assert [i.label for i in family] == ["W=i8, N=1", "W=i8, N=4", "W=i32, N=1", "W=i32, N=4"]
    assert family[-1].text.strip() == "memref<4xi32> 8"


def test_a_value_may_depend_on_an_earlier_parameter_and_duplicates_collapse():
    family = instances("// fcvdct.sweep N = 1, 4\n// fcvdct.sweep K = 0, N - 1\n${K}\n")
    # N=1 gives K=0 twice: checked once.
    assert [i.label for i in family] == ["N=1, K=0", "N=4, K=0", "N=4, K=3"]


def test_no_sweep_is_one_instance_and_says_so():
    assert [i.label for i in instances("builtin.module {}")] == ["single instance"]


def test_an_unbound_placeholder_is_an_error_not_a_silent_instance():
    with pytest.raises(ValueError, match="unsupported sweep expression"):
        instances("// fcvdct.sweep N = 1\n${M}\n")


def test_closed_means_no_hole():
    assert is_closed((POLYGEIST / "polygeist_to_llvm_arith.mlir").read_text())
    assert not is_closed((POLYGEIST / "mem2reg_if.mlir").read_text())


def test_one_bad_instance_rejects_the_family():
    """The family passes only if every instance does, and names the one that did not."""
    template = """
// fcvdct.sweep K = 0, 1, 2
builtin.module {
  func.func @source(%a: i8) -> i8 {
    %k = arith.constant ${K} : i8
    %r = arith.muli %a, %k : i8
    func.return %r : i8
  }
  func.func @target(%a: i8) -> i8 {
    %r = arith.addi %a, %a : i8
    func.return %r : i8
  }
}
"""
    swept = check_template_text(make_context(), template)
    assert swept.instances == 3
    assert swept.verdict == "rejected"
    assert swept.gate.equivalence.verdict == "not-equivalent"
    # K=2 is the only instance where a*K == a+a; the first refuting one is reported.
    assert swept.decided_by == {"equivalence": "K=0"}


@pytest.mark.parametrize(
    "name",
    [
        "mem2reg_if",
        "affine_cfg_raise_store",
        "lower_affine_for_load_store",
        "polygeist_to_llvm_arith",
        "polygeist_to_llvm_memref",
        "canonicalize_for_propagate",
        "loop_restructure_while",
    ],
)
def test_polygeist_templates_are_families_not_single_instances(name: str):
    """Issue #63, item 3: each Polygeist step template sweeps its shape parameters."""
    assert len(instances((POLYGEIST / f"{name}.mlir").read_text())) > 1


def test_memref_extent_assumption_is_load_bearing():
    """Found by the `lower_affine_for_load_store` sweep: a loop starting at 1 never
    touches cell 0, but the flattener parks the untaken iterations' accesses there. With
    the argument pointer free, the solver picks one valid at cell 1 and not at cell 0,
    and a correct lowering is reported as changing the meaning. The type's own contract
    -- every cell of a static memref argument is readable -- is what rules it out."""
    text = next(
        i.text
        for i in instances((POLYGEIST / "lower_affine_for_load_store.mlir").read_text())
        if i.label == "LB=1, UB=2, ST=1"
    )
    ctx = make_context()
    module = Parser(ctx, text).parse_module()
    assert check_equivalence(ctx, module).verdict == "equivalent"

    script, *_ = build_equivalence_query(ctx, module, assume_memref_extent=False)
    assert _run_z3(script, 60).stdout.strip().startswith("sat")
