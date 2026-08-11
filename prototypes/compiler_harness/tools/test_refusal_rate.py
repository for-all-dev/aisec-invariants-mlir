#!/usr/bin/env python3
"""Unit regressions for the textual LLVM refusal-rate scanner."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import refusal_rate


class RefusalRateTest(unittest.TestCase):
    def analyze_lines(self, bodies: list[str]) -> list[refusal_rate.FuncStats]:
        definitions = []
        metadata = []
        for index, body in enumerate(bodies, start=1):
            definitions.extend(
                [
                    f"define i32 @f{index}() !dbg !{index} {{",
                    f"  {body}, !dbg !100",
                    "}",
                ]
            )
            metadata.append(f"!{index} = distinct !DISubprogram(")
        text = "\n".join([*definitions, *metadata])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calls.ll"
            path.write_text(text)
            functions, _, _ = refusal_rate.analyze(str(path))
        return functions

    def test_all_call_spellings_are_observations_and_require_models(self) -> None:
        functions = self.analyze_lines(
            [
                "%r = call i32 @external()",
                "%r = tail call i32 @external()",
                "%r = musttail call i32 @external()",
                "%r = notail call i32 @external()",
                "%r = invoke i32 @external() to label %ok unwind label %bad",
                "callbr void asm sideeffect \"\", \"\"() to label %ok [label %bad]",
                "%r = call i32 %callee(ptr @f7)",
            ]
        )

        self.assertEqual(len(functions), 7)
        for function in functions:
            self.assertTrue(function.attested)
            self.assertEqual(function.observations, 1)
            self.assertEqual(function.unattributed, 0)
            self.assertEqual(function.refusals(set()), ["absent-callee-model"])

    def test_debug_and_lifetime_intrinsics_remain_excluded(self) -> None:
        functions = self.analyze_lines(
            [
                "tail call void @llvm.dbg.value(metadata i32 0, metadata !1, "
                "metadata !DIExpression())",
                "call void @llvm.lifetime.start.p0(i64 8, ptr null)",
            ]
        )

        self.assertEqual([function.observations for function in functions], [0, 0])

    def test_atomic_memory_addresses_are_observations(self) -> None:
        functions = self.analyze_lines(
            [
                "%old = atomicrmw add ptr %p, i32 1 seq_cst",
                "%pair = cmpxchg ptr %p, i32 0, i32 1 seq_cst seq_cst",
            ]
        )

        self.assertEqual([function.observations for function in functions], [1, 1])
        self.assertEqual(
            [function.refusals(set()) for function in functions], [[], []]
        )

    def test_legal_punctuated_and_quoted_function_names_are_counted(self) -> None:
        text = "\n".join(
            [
                "define void @foo-bar() !dbg !1 {",
                "  ret void",
                "}",
                'define void @"foo bar"() !dbg !2 {',
                "  ret void",
                "}",
                "!1 = distinct !DISubprogram(",
                "!2 = distinct !DISubprogram(",
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "names.ll"
            path.write_text(text)
            functions, _, _ = refusal_rate.analyze(str(path))

        self.assertEqual(
            [function.name for function in functions], ["foo-bar", '"foo bar"']
        )


if __name__ == "__main__":
    unittest.main()
