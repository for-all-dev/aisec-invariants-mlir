"""The coverage report: what a compiler needs before this method can be run on it."""

from __future__ import annotations

import json
from pathlib import Path

from fcvdct.coverage import (
    COMPILERS,
    OP_MENTION,
    Compiler,
    report,
    semantics_registry,
)


def mentions(text: str) -> list[str]:
    return [f"{dialect}.{op}" for dialect, op in OP_MENTION.findall(text)]


def test_operation_mentions_are_operations():
    """Types, attribute aliases, SSA names and parametrised attributes are not ops."""
    assert mentions("%0 = arith.addi %a, %b : i32") == ["arith.addi"]
    assert mentions("%c = secret.conceal %x : !secret.secret<i16>") == ["secret.conceal"]
    assert mentions("%f = arith.addf %a, %b fastmath<none> : f32") == ["arith.addf"]
    assert mentions("#hw.output_file<.>") == []
    assert mentions("%my.value = foo") == []


def test_registry_is_read_from_the_live_semantics():
    registry = semantics_registry()
    # An operation with upstream semantics, one lowered structurally, and one this
    # package translates itself.
    assert registry["arith.addi"] == "SMT semantics"
    assert registry["func.func"] == "structural lowering"
    assert "if-conversion" in registry["cf.cond_br"]
    assert "bounded" in registry["scf.for"]
    assert "onnx.Gemm" not in registry


def descriptor(tmp_path: Path, **overrides: object) -> Compiler:
    checkout = tmp_path / "checkout" / "test"
    checkout.mkdir(parents=True)
    (checkout / "a.mlir").write_text(
        "func.func @f(%a: i32) -> i32 {\n"
        "  %0 = arith.addi %a, %a : i32\n"
        "  // arith.muli in a comment does not count\n"
        "  %1 = onnx.Gemm %0 : i32\n"
        "  func.return %1 : i32\n"
        "}\n"
    )
    raw: dict[str, object] = {
        "name": "toy",
        "repo": "-",
        "commit": "0",
        "checkout": str(tmp_path / "checkout"),
        "dialects": ["arith", "func", "onnx"],
        "test_globs": ["test/*.mlir"],
        "pipeline": [
            {"pass": "--toy", "from": ["arith"], "to": ["onnx"], "cited": "nowhere:1"},
            {"pass": "--toy2", "from": ["onnx"], "to": ["arith"], "cited": "nowhere:2"},
        ],
        "templates": [],
    }
    raw.update(overrides)
    path = tmp_path / "toy.json"
    path.write_text(json.dumps(raw))
    return Compiler.load(path)


def test_forms_are_counted_from_the_corpus(tmp_path: Path):
    result = report(descriptor(tmp_path), prove=False)
    forms = {op.name: op.form for op in result.operations}
    assert forms == {"arith.addi": 0, "func.func": 0, "func.return": 0, "onnx.Gemm": 2}
    # A comment mentioning an operation must not inflate the count.
    assert all(op.name != "arith.muli" for op in result.operations)
    # The stage whose inputs are all translatable is ready; the one over `onnx` is not.
    assert [stage.ready for stage in result.stages] == [True, False]


def test_an_unproved_template_covers_nothing(tmp_path: Path):
    """`select_to_cf` is ct-breaking, so claiming coverage from it must not work."""
    claimed = [{"file": "select_to_cf.mlir", "covers": ["onnx.Gemm"]}]
    compiler = descriptor(tmp_path, templates=claimed)

    trusted = report(compiler, prove=False)
    assert {op.name: op.form for op in trusted.operations}["onnx.Gemm"] == 1

    proved = report(compiler, prove=True)
    assert {op.name: op.form for op in proved.operations}["onnx.Gemm"] == 2
    assert proved.failed_templates and "select_to_cf" in proved.failed_templates[0]


def test_shipped_descriptors_parse_and_cite_their_source():
    for path in sorted(COMPILERS.glob("*.json")):
        compiler = Compiler.load(path)
        assert compiler.pipeline, f"{path.name} has no pipeline"
        for stage in compiler.pipeline:
            assert ":" in stage.cited, f"{stage.pass_name} does not say where it was read"
