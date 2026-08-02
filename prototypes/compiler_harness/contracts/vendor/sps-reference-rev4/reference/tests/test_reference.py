from __future__ import annotations

import sys
import subprocess
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

REFERENCE_DIR = Path(__file__).resolve().parents[1]
if str(REFERENCE_DIR) not in sys.path:
    sys.path.insert(0, str(REFERENCE_DIR))

from sps_ref.canonical import canonical_bytes, load_json_bytes
from sps_ref.encoding import decode_bits, encode_bits
from sps_ref.engine import compile_program
from sps_ref.errors import ReplayError, SchemaError
from sps_ref.model import parse_coalition
from sps_ref.ponf import build_reference_ponf
from sps_ref.product import build_product
from sps_ref.replay import replay_witness
from sps_ref.smt import lower_reference_ponf, lower_reference_product
from sps_ref.solve import (
    parse_model_response,
    product_variables,
    run_exhaustive,
    run_z3,
)
from sps_ref.terms import bv_binary, bv_lit, var


def _program(*, classification: str = "High", return_secret: bool = True) -> dict:
    value = {"var": "value"} if return_secret else {
        "const": {"width": 8, "value": 0}
    }
    return {
        "formatId": "SPS-Reference-Program-v2",
        "entryId": "test.entry",
        "entryHost": "entry",
        "observerProfile": "EventInterfaceOnly",
        "inputs": [
            {
                "id": "value",
                "width": 8,
                "classification": classification,
                "host": "entry",
            }
        ],
        "abi": {
            "return": {
                "outputId": "return.value",
                "width": 8,
                "host": "caller",
                "byteOrder": "BigEndian",
            },
            "roots": [],
        },
        "statements": [
            {"op": "return", "site": "return.site", "value": value}
        ],
    }


class ReferenceTests(unittest.TestCase):
    def test_nonbyte_padding_is_canonical(self) -> None:
        raw = encode_bits(1, 1, "LittleEndian")
        self.assertEqual(raw, b"\x01")
        self.assertEqual(decode_bits(raw, 1, "LittleEndian"), 1)
        with self.assertRaises(SchemaError):
            decode_bits(b"\x81", 1, "LittleEndian")

    def test_canonical_json_rejects_float(self) -> None:
        with self.assertRaises(SchemaError):
            canonical_bytes({"notCanonical": 1.5})
        with self.assertRaises(SchemaError):
            load_json_bytes(b'{"duplicate":0,"duplicate":1}')

    def test_term_evaluator_matches_bitvector_wrap(self) -> None:
        term = bv_binary("bvadd", var("x", 4), bv_lit(4, 3))
        self.assertEqual(term.evaluate({"x": 15}), 2)
        self.assertIn("bvadd", term.to_smt())

    def test_model_wire_rejects_reordering(self) -> None:
        variables = (("L.input.x", 8), ("R.input.x", 8))
        good = "((|L.input.x| #x00) (|R.input.x| (_ bv255 8)))"
        self.assertEqual(
            parse_model_response(good, variables),
            {"L.input.x": 0, "R.input.x": 255},
        )
        bad = "((|R.input.x| #x00) (|L.input.x| #xff))"
        with self.assertRaises(ValueError):
            parse_model_response(bad, variables)

    def test_low_equality_uses_entry_symbols(self) -> None:
        program = _program(classification="Low", return_secret=False)
        program["statements"].insert(
            0,
            {
                "op": "set",
                "site": "set.site",
                "target": "value",
                "value": {"const": {"width": 8, "value": 0}},
            },
        )
        coalition = parse_coalition(
            {"id": "observer", "principals": [], "controlledHosts": ["caller"]}
        )
        product = build_product(
            compile_program(program, "L"), compile_program(program, "R"), coalition
        )
        self.assertEqual(
            set(product_variables(product)),
            {"L.input.value", "R.input.value"},
        )

    def test_replay_is_independent_of_symbolic_event_payload(self) -> None:
        program = _program()
        coalition = parse_coalition(
            {"id": "observer", "principals": [], "controlledHosts": ["caller"]}
        )
        left = compile_program(program, "L")
        right = compile_program(program, "R")
        corrupted = replace(
            left,
            events=(
                replace(left.events[0], value_bytes=(bv_lit(8, 255),)),
                *left.events[1:],
            ),
        )
        witness = {"L.input.value": 0, "R.input.value": 1}
        with self.assertRaises(ReplayError):
            replay_witness(corrupted, right, coalition, witness)

    def test_replay_rejects_low_inequality_and_wrong_domain(self) -> None:
        program = _program(classification="Low")
        coalition = parse_coalition(
            {"id": "observer", "principals": [], "controlledHosts": ["caller"]}
        )
        left = compile_program(program, "L")
        right = compile_program(program, "R")
        with self.assertRaises(ReplayError):
            replay_witness(
                left,
                right,
                coalition,
                {"L.input.value": 0, "R.input.value": 1},
            )
        with self.assertRaises(ReplayError):
            replay_witness(
                left,
                right,
                coalition,
                {
                    "L.input.value": 0,
                    "R.input.value": 0,
                    "invented": 0,
                },
            )

    def test_compilation_owns_and_checks_canonical_program_snapshot(self) -> None:
        program = _program(return_secret=False)
        coalition = parse_coalition(
            {"id": "observer", "principals": [], "controlledHosts": ["caller"]}
        )
        left = compile_program(program, "L")
        right = compile_program(program, "R")
        program["statements"][0]["value"] = {"var": "value"}
        stale_product = build_product(left, right, coalition)
        environment = {"L.input.value": 0, "R.input.value": 1}
        self.assertFalse(bool(stale_product.bad.evaluate(environment)))
        fresh_product = build_product(
            compile_program(program, "L"),
            compile_program(program, "R"),
            coalition,
        )
        self.assertTrue(bool(fresh_product.bad.evaluate(environment)))

        left.program["statements"][0]["value"] = {"var": "value"}
        with self.assertRaises(SchemaError):
            build_product(left, right, coalition)

    def test_exhaustive_domain_is_owned_by_the_product(self) -> None:
        program = _program()
        coalition = parse_coalition(
            {"id": "observer", "principals": [], "controlledHosts": ["caller"]}
        )
        product = build_product(
            compile_program(program, "L"),
            compile_program(program, "R"),
            coalition,
        )
        self.assertEqual(run_exhaustive(product).status, "sat")
        with self.assertRaises(ValueError):
            run_exhaustive(product, {"L.input.value": 1})  # type: ignore[arg-type]

    def test_serialized_ponf_is_identity_bound_and_lowerable(self) -> None:
        program = _program()
        coalition = parse_coalition(
            {"id": "observer", "principals": [], "controlledHosts": ["caller"]}
        )
        left = compile_program(program, "L")
        right = compile_program(program, "R")
        product = build_product(left, right, coalition)
        ponf = build_reference_ponf(left, right, coalition)
        self.assertEqual(
            lower_reference_ponf(ponf),
            lower_reference_product(product),
        )
        self.assertEqual(len(ponf["canonicalProgramDigest"]), 64)
        self.assertEqual(len(ponf["coalitionDescriptorDigest"]), 64)
        tampered = deepcopy(ponf)
        tampered["exactSMTDigest"] = "0" * 64
        with self.assertRaises(SchemaError):
            lower_reference_ponf(tampered)

    def test_expression_schema_rejects_boolean_extract_indices(self) -> None:
        program = _program()
        program["statements"][0]["value"] = {
            "extract": {
                "value": {"var": "value"},
                "low": True,
                "width": 1,
            }
        }
        with self.assertRaises(SchemaError):
            compile_program(program, "L")

    def test_solver_timeout_is_a_closed_unknown_result(self) -> None:
        program = _program()
        coalition = parse_coalition(
            {"id": "observer", "principals": [], "controlledHosts": ["caller"]}
        )
        product = build_product(
            compile_program(program, "L"),
            compile_program(program, "R"),
            coalition,
        )
        artifact = lower_reference_product(product)
        with patch(
            "sps_ref.solve.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["z3"], 30),
        ):
            result = run_z3(artifact)
        self.assertEqual(result.status, "unknown")
        self.assertIn("timed out", result.detail)


if __name__ == "__main__":
    unittest.main()
