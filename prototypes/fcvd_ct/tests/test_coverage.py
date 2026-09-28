"""The coverage report: what a compiler needs before this method can be run on it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from xdsl.parser import Parser

from fcvdct.context import make_context
from fcvdct.coverage import (
    COMPILERS,
    OP_MENTION,
    Compiler,
    report,
    semantics_registry,
)
from fcvdct.memref_ops import UnsupportedMemRef
from fcvdct.translation import TranslationMeasure, measure_text, translate


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
        '  %1 = "onnx.Gemm"(%0) : (i32) -> i32\n'
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
    # `arith.addi` translates on its own; the function does not, because its body holds
    # an operation with no semantics -- and its terminator is judged with it.
    translated = {op.name: op.translated for op in result.operations}
    assert translated == {"arith.addi": 1, "func.func": 0, "func.return": 0, "onnx.Gemm": 0}
    assert result.translation is not None
    assert (result.translation.functions, result.translation.functions_translated) == (1, 0)
    # The stage whose inputs all translate is ready; the one over `onnx` is not.
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


def measured(text: str, dialects: tuple[str, ...] = ("arith", "func", "memref")):
    ctx = make_context()
    ctx.allow_unregistered = True
    result = TranslationMeasure()
    measure_text(ctx, text, set(dialects), OP_MENTION, result)
    return result


def test_a_registered_name_is_not_a_translated_occurrence():
    """Issue #63: `memref.alloca` has a rule, but not one that accepts a dynamic size."""
    result = measured(
        "func.func @f(%n: index, %x: i8) {\n"
        "  %s = memref.alloca() : memref<4xi8>\n"
        "  %d = memref.alloca(%n) : memref<?xi8>\n"
        "  func.return\n"
        "}\n"
    )
    assert result.translated["memref.alloca"] == 1
    assert result.rejected["memref.alloca"] == 1
    assert "dynamic" in next(iter(result.reasons["memref.alloca"]))


@pytest.mark.parametrize("memref_type", ["memref<?xi8>", "memref<4xi32>"])
def test_memref_access_upstream_would_get_wrong_is_refused(memref_type: str):
    """Upstream reads a dynamic extent as -1, which makes every access UB -- a vacuous
    translation. It has to be refused instead, and so does a non-i8 element."""
    ctx = make_context()
    element = memref_type.split("x")[-1].rstrip(">")
    module = Parser(
        ctx,
        f"func.func @f(%m: {memref_type}, %i: index) -> {element} {{\n"
        f"  %v = memref.load %m[%i] : {memref_type}\n"
        f"  func.return %v : {element}\n"
        "}\n",
    ).parse_module()
    function = next(iter(module.body.ops))
    reason = translate(ctx, function)  # type: ignore[arg-type]
    assert reason.startswith(UnsupportedMemRef.__name__)


def test_an_unparsable_split_is_unmeasured_not_translated():
    result = measured(
        "func.func @ok(%a: i32) -> i32 {\n"
        "  %0 = arith.addi %a, %a : i32\n"
        "  func.return %0 : i32\n"
        "}\n"
        "// -----\n"
        "func.func @bad(%a: i32) -> i32 {\n"
        "  %0 = arith.addi %a, %a : i32\n"
        "  %1 = notadialect.op %0 : i32\n"
        "  func.return %1 : i32\n"
        "}\n"
    )
    assert (result.splits, result.splits_parsed) == (2, 1)
    assert result.translated["arith.addi"] == 1
    assert result.unparsed["arith.addi"] == 1
