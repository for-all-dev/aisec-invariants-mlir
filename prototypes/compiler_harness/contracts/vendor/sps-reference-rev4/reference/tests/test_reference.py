from __future__ import annotations

import sys
import os
import shutil
import subprocess
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

REFERENCE_DIR = Path(__file__).resolve().parents[1]
if str(REFERENCE_DIR) not in sys.path:
    sys.path.insert(0, str(REFERENCE_DIR))

from sps_ref.canonical import canonical_bytes, canonical_digest, load_json_bytes
from sps_ref.encoding import decode_bits, encode_bits
from sps_ref.engine import compile_program
from sps_ref.evidence import (
    canonical_relation_result_bytes,
    load_reference_profile,
    project_relation_result,
    run_relation_fixture,
    validate_reference_profile,
    validate_reduction_binding,
    validate_relation_fixture,
    validate_relation_result,
)
from sps_ref.errors import ReplayError, SchemaError
from sps_ref.model import parse_coalition
from sps_ref.ponf import build_reference_ponf
from sps_ref.product import build_product
from sps_ref.replay import replay_witness
from sps_ref.query import (
    build_reference_query,
    run_concrete_query,
    run_query_exhaustive,
    terminal_output_surface_violation,
)
from sps_ref.smt import lower_reference_ponf, lower_reference_query
from sps_ref.solve import (
    parse_model_response,
    product_variables,
    run_exhaustive,
    run_z3,
)
from sps_ref.terms import bool_lit, bv_binary, bv_lit, var


def _program(*, classification: str = "High", return_secret: bool = True) -> dict:
    value = {"var": "value"} if return_secret else {
        "const": {"width": 8, "value": 0}
    }
    return {
        "formatId": "SPS-Reference-Program-v3",
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
            "terminalOutputOrder": ["return.value"],
            "return": {
                "outputId": "return.value",
                "width": 8,
                "host": "caller",
                "byteOrder": "BigEndian",
            },
            "roots": [],
        },
        "admission": {"bool": True},
        "statements": [
            {"op": "return", "site": "return.site", "value": value}
        ],
    }


def _internal_load_program(*, overwrite: bool = True) -> dict:
    statements = [
        {
            "op": "store",
            "site": "store.secret",
            "root": "slot",
            "offset": 0,
            "value": {"var": "secret"},
            "byteOrder": "LittleEndian",
        }
    ]
    if overwrite:
        statements.append(
            {
                "op": "store",
                "site": "store.public",
                "root": "slot",
                "offset": 0,
                "value": {"var": "public"},
                "byteOrder": "LittleEndian",
            }
        )
    statements.append(
        {
            "op": "return",
            "site": "return.site",
            "value": {
                "load": {
                    "root": "slot",
                    "offset": 0,
                    "width": 8,
                    "byteOrder": "LittleEndian",
                }
            },
        }
    )
    return {
        "formatId": "SPS-Reference-Program-v3",
        "entryId": "test.internal",
        "entryHost": "entry",
        "observerProfile": "EventInterfaceOnly",
        "inputs": [
            {"id": "public", "width": 1, "classification": "Low", "host": "entry"},
            {"id": "secret", "width": 1, "classification": "High", "host": "entry"},
        ],
        "abi": {
            "terminalOutputOrder": ["return.value"],
            "return": {
                "outputId": "return.value",
                "width": 8,
                "host": "caller",
                "byteOrder": "LittleEndian",
            },
            "roots": [
                {
                    "id": "slot",
                    "byteLength": 1,
                    "host": "entry",
                    "terminalOutput": False,
                    "outputId": None,
                    "initialBytes": [0],
                    "initialized": [False],
                }
            ],
        },
        "admission": {"bool": True},
        "statements": statements,
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
        query = build_reference_query(left, right, coalition, "ReferenceAuditAll")
        ponf = build_reference_ponf(left, right, coalition)
        self.assertEqual(
            lower_reference_ponf(ponf),
            lower_reference_query(query),
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

    def test_admission_nonempty_and_high_variation_are_separate_queries(self) -> None:
        coalition = parse_coalition(
            {"id": "observer", "principals": [], "controlledHosts": ["caller"]}
        )
        program = _program(return_secret=False)
        left = compile_program(program, "L")
        right = compile_program(program, "R")
        admission = build_reference_query(
            left, right, coalition, "ReferenceAdmissionNonempty"
        )
        variation = build_reference_query(
            left, right, coalition, "ReferenceHighVariation", "value"
        )
        self.assertEqual(run_query_exhaustive(admission).status, "sat")
        self.assertEqual(
            run_concrete_query(admission, left, right, coalition).status, "sat"
        )
        self.assertEqual(run_query_exhaustive(variation).status, "sat")

        empty = _program(return_secret=False)
        empty["admission"] = {"bool": False}
        empty_left = compile_program(empty, "L")
        empty_right = compile_program(empty, "R")
        empty_query = build_reference_query(
            empty_left, empty_right, coalition, "ReferenceAdmissionNonempty"
        )
        self.assertEqual(run_query_exhaustive(empty_query).status, "unsat")

        constrained = _program(return_secret=False)
        constrained["admission"] = {
            "eq": [
                {"var": "value"},
                {"const": {"width": 8, "value": 0}},
            ]
        }
        constrained_left = compile_program(constrained, "L")
        constrained_right = compile_program(constrained, "R")
        constrained_query = build_reference_query(
            constrained_left,
            constrained_right,
            coalition,
            "ReferenceHighVariation",
            "value",
        )
        self.assertEqual(run_query_exhaustive(constrained_query).status, "unsat")
        self.assertEqual(
            run_concrete_query(
                constrained_query,
                constrained_left,
                constrained_right,
                coalition,
            ).status,
            "unsat",
        )

    def test_explicit_successor_identity_controls_the_branch_observation(self) -> None:
        coalition = parse_coalition(
            {"id": "observer", "principals": [], "controlledHosts": []}
        )
        safe = _program(return_secret=False)
        safe["statements"].insert(
            0,
            {
                "op": "if",
                "site": "branch.site",
                "condition": {
                    "eq": [
                        {"var": "value"},
                        {"const": {"width": 8, "value": 1}},
                    ]
                },
                "thenSuccessor": "merge",
                "elseSuccessor": "merge",
                "then": [],
                "else": [],
            },
        )
        bad = deepcopy(safe)
        bad["statements"][0]["elseSuccessor"] = "other"
        for program, expected in ((safe, "unsat"), (bad, "sat")):
            left = compile_program(program, "L")
            right = compile_program(program, "R")
            query = build_reference_query(left, right, coalition, "ReferenceAuditAll")
            self.assertEqual(run_query_exhaustive(query).status, expected)
            self.assertEqual(
                run_concrete_query(query, left, right, coalition).status, expected
            )

    def test_internal_root_load_is_not_a_terminal_root_output(self) -> None:
        coalition = parse_coalition(
            {"id": "observer", "principals": [], "controlledHosts": ["caller"]}
        )
        for overwrite, expected in ((True, "unsat"), (False, "sat")):
            program = _internal_load_program(overwrite=overwrite)
            left = compile_program(program, "L")
            right = compile_program(program, "R")
            self.assertEqual(
                [event.kind for event in left.events if event.kind in {"Output", "Termination"}],
                ["Output", "Termination"],
            )
            query = build_reference_query(left, right, coalition, "ReferenceAuditAll")
            self.assertEqual(run_query_exhaustive(query).status, expected)
            self.assertEqual(
                run_concrete_query(query, left, right, coalition).status, expected
            )

    def test_terminal_surface_detects_closed_mutation_matrix(self) -> None:
        program = _program()
        compiled = compile_program(program, "L")
        with patch(
            "sps_ref.query.concrete_terminal_surface_violation",
            side_effect=AssertionError("symbolic surface called concrete oracle"),
        ):
            self.assertFalse(
                bool(
                    terminal_output_surface_violation(compiled).evaluate(
                        {"L.input.value": 0}
                    )
                )
            )
        output, termination = compiled.events
        mutations = {
            "omitted-event": replace(compiled, events=(termination,)),
            "reordered-events": replace(
                compiled, events=(termination, output)
            ),
            "wrong-output-id": replace(
                compiled,
                events=(replace(output, output_id="wrong.output"), termination),
            ),
            "same-length-wrong-encoding": replace(
                compiled,
                events=(
                    replace(output, value_bytes=(bv_lit(8, 255),)),
                    termination,
                ),
            ),
            "uninitialized-terminal-byte": replace(
                compiled,
                events=(
                    replace(output, output_initialized=(bool_lit(False),)),
                    termination,
                ),
            ),
        }
        for name, corrupted in mutations.items():
            with self.subTest(name=name):
                violation = terminal_output_surface_violation(corrupted)
                self.assertTrue(
                    bool(violation.evaluate({"L.input.value": 0}))
                )

        root_first = _internal_load_program()
        root_first_root = root_first["abi"]["roots"][0]
        root_first_root["terminalOutput"] = True
        root_first_root["outputId"] = "slot-output"
        root_first["abi"]["terminalOutputOrder"] = [
            "slot-output",
            "return.value",
        ]
        root_first_compiled = compile_program(root_first, "L")
        self.assertEqual(
            [
                event.output_id
                for event in root_first_compiled.events
                if event.kind == "Output"
            ],
            ["slot-output", "return.value"],
        )
        root_first_environment = {
            "L.input.public": 0,
            "L.input.secret": 0,
        }
        self.assertFalse(
            bool(
                terminal_output_surface_violation(root_first_compiled).evaluate(
                    root_first_environment
                )
            )
        )
        root_output, return_output, root_termination = root_first_compiled.events
        reordered = replace(
            root_first_compiled,
            events=(return_output, root_output, root_termination),
        )
        self.assertTrue(
            bool(
                terminal_output_surface_violation(reordered).evaluate(
                    root_first_environment
                )
            )
        )

        duplicate_order = deepcopy(root_first)
        duplicate_order["abi"]["terminalOutputOrder"] = [
            "return.value",
            "return.value",
        ]
        with self.assertRaises(SchemaError):
            compile_program(duplicate_order, "L")

    def test_binding_internal_alloca_fields_are_disjoint(self) -> None:
        program = _internal_load_program()
        fixture = {
            "formatId": "SPS-Executable-Reference-Fixture-v3",
            "familyId": "NF-FX-OUTPUT-RETURN",
            "caseId": "binding.internal",
            "kind": "relation",
            "requirementRefs": ["Normative 21.4"],
            "input": {
                "program": program,
                "coalition": {
                    "id": "observer",
                    "principals": ["observer"],
                    "controlledHosts": ["caller"],
                },
            },
            "expected": {
                "auditAll": {"status": "unsat", "firstDifference": None},
                "admissionNonempty": "sat",
                "highVariation": [{"componentId": "secret", "status": "sat"}],
                "terminalOutputSurface": "unsat",
            },
        }
        validate_relation_fixture(fixture)
        digest = "0" * 64
        binding = {
            "formatId": "SPS-Harness-Reference-Reduction-Binding-v1",
            "harnessCase": "precision-control/binding-internal",
            "referenceCaseId": "binding.internal",
            "entry": "test.internal",
            "files": [
                {"role": role, "path": f"{role}.json", "sha256": digest}
                for role in ("abi", "c", "mlir", "policy", "referenceFixture", "snapshot")
            ],
            "arguments": [
                {"referenceInput": "public", "component": "public", "argumentIndex": 1, "argumentName": "public", "fullWidth": 32, "reducedWidth": 1, "classification": "Low"},
                {"referenceInput": "secret", "component": "secret", "argumentIndex": 0, "argumentName": "secret", "fullWidth": 32, "reducedWidth": 1, "classification": "High"},
            ],
            "roots": [
                {"referenceRoot": "slot", "storageKind": "InternalAlloca", "abiRoot": None, "argumentIndex": None, "argumentName": None, "allocationSite": "alloca.slot", "byteLength": 1, "initialClassification": "Uninitialized", "terminalVisibility": "NotTerminalOutput", "offsets": [0]}
            ],
            "coalition": {
                "referenceCoalitionId": "observer",
                "policyAdversaryId": "maximal",
                "policyAdversaryIndex": 0,
                "principals": ["observer"],
                "controlledHosts": ["caller"],
                "hostMappings": [
                    {"referenceHost": "caller", "policyHost": None, "boundaryClass": "PublicObservationEndpoint"}
                ],
            },
            "observations": [{"kind": "Output", "field": "valueBytes"}],
            "limitations": ["ExecutableReferenceOnly", "HandAuthoredReduction", "NotFrozenLLVM", "ReducedBitWidth"],
        }
        validate_reduction_binding(binding, fixture)
        for field in ("component", "argumentIndex", "argumentName"):
            duplicate = deepcopy(binding)
            duplicate["arguments"][1][field] = duplicate["arguments"][0][field]
            with self.subTest(duplicate_argument_field=field):
                with self.assertRaises(SchemaError):
                    validate_reduction_binding(duplicate, fixture)
        wrong_offsets = deepcopy(binding)
        wrong_offsets["roots"][0]["offsets"] = []
        with self.assertRaises(SchemaError):
            validate_reduction_binding(wrong_offsets, fixture)
        initialized_fixture = deepcopy(fixture)
        initialized_fixture["input"]["program"]["abi"]["roots"][0][
            "initialized"
        ] = [True]
        validate_relation_fixture(initialized_fixture)
        with self.assertRaises(SchemaError):
            validate_reduction_binding(binding, initialized_fixture)
        mixed = deepcopy(binding)
        mixed["roots"][0]["abiRoot"] = "slot"
        with self.assertRaises(SchemaError):
            validate_reduction_binding(mixed, fixture)
        missing = deepcopy(binding)
        missing["roots"][0]["allocationSite"] = None
        with self.assertRaises(SchemaError):
            validate_reduction_binding(missing, fixture)
        legacy_fixture = deepcopy(fixture)
        legacy_root = legacy_fixture["input"]["program"]["abi"]["roots"][0]
        legacy_root["terminalOutput"] = True
        legacy_root["outputId"] = "slot-output"
        legacy_fixture["input"]["program"]["abi"]["terminalOutputOrder"] = [
            "return.value",
            "slot-output",
        ]
        validate_relation_fixture(legacy_fixture)
        legacy = deepcopy(binding)
        legacy["roots"][0].update(
            {
                "storageKind": "ABIRoot",
                "abiRoot": "slot",
                "argumentIndex": 2,
                "argumentName": "slot",
                "allocationSite": None,
                "initialClassification": "Low",
                "terminalVisibility": "High",
            }
        )
        with self.assertRaises(SchemaError):
            validate_reduction_binding(legacy, legacy_fixture)
        if shutil.which(os.environ.get("Z3", "") or "z3") is not None:
            result = run_relation_fixture(fixture, binding)
            profile = load_reference_profile()
            validate_relation_result(
                result, profile, fixture=fixture, binding=binding
            )
            self.assertEqual(canonical_relation_result_bytes(result), canonical_bytes(result))
            self.assertFalse(canonical_relation_result_bytes(result).endswith(b"\n"))
            self.assertEqual(
                project_relation_result(result),
                {
                    "query.admission-nonempty": "sat",
                    "query.high-variation": ["secret"],
                    "query.terminal-output-surface": "unsat",
                    "query.audit-all": "unsat",
                    "backend.agreement": True,
                },
            )
            tampered = deepcopy(result)
            audit = next(
                row
                for row in tampered["queries"]
                if row["queryId"] == "ReferenceAuditAll"
            )
            audit["outcome"] = "sat"
            audit["firstDifference"] = {"kind": "Invented", "field": "field"}
            audit["validation"] = {
                "assignmentValidationRequired": True,
                "allSATAssignmentsValidated": True,
            }
            for backend in audit["backends"]:
                backend["outcome"] = "sat"
            tampered.pop("canonicalResultDigest")
            tampered["canonicalResultDigest"] = canonical_digest(tampered)
            with self.assertRaises(SchemaError):
                validate_relation_result(tampered, load_reference_profile())
            missing_backend = deepcopy(result)
            missing_backend["queries"][0]["backends"] = [
                row
                for row in missing_backend["queries"][0]["backends"]
                if row["backend"] != "z3"
            ]
            missing_backend.pop("canonicalResultDigest")
            missing_backend["canonicalResultDigest"] = canonical_digest(
                missing_backend
            )
            with self.assertRaises(SchemaError):
                validate_relation_result(
                    missing_backend, load_reference_profile()
                )
            with patch.dict(os.environ, {"CVC5": "/configured/cvc5"}):
                with self.assertRaises(SchemaError):
                    validate_relation_result(result, load_reference_profile())

            def reseal(mutated):
                mutated.pop("canonicalResultDigest")
                mutated["canonicalResultDigest"] = canonical_digest(mutated)

            missing_high = deepcopy(result)
            missing_high["queries"] = [
                row
                for row in missing_high["queries"]
                if row["queryId"] != "ReferenceHighVariation"
            ]
            reseal(missing_high)
            with self.assertRaises(SchemaError):
                validate_relation_result(
                    missing_high,
                    profile,
                    fixture=fixture,
                    binding=binding,
                )

            invented_high = deepcopy(result)
            next(
                row
                for row in invented_high["queries"]
                if row["queryId"] == "ReferenceHighVariation"
            )["componentId"] = "invented"
            reseal(invented_high)
            with self.assertRaises(SchemaError):
                validate_relation_result(
                    invented_high,
                    profile,
                    fixture=fixture,
                    binding=binding,
                )

            digest_mutations = (
                ("fixtureBinding", "canonicalFixtureDigest"),
                ("reductionBinding", "canonicalBindingDigest"),
                (None, "programDigest"),
                (None, "coalitionDescriptorDigest"),
            )
            for container, field in digest_mutations:
                mutated = deepcopy(result)
                target = mutated if container is None else mutated[container]
                target[field] = "1" * 64
                reseal(mutated)
                with self.subTest(context_digest=field):
                    with self.assertRaises(SchemaError):
                        validate_relation_result(
                            mutated,
                            profile,
                            fixture=fixture,
                            binding=binding,
                        )

            for field in ("ponfDigest", "exactSMTDigest"):
                mutated = deepcopy(result)
                mutated["queries"][0][field] = "1" * 64
                reseal(mutated)
                with self.subTest(query_digest=field):
                    with self.assertRaises(SchemaError):
                        validate_relation_result(
                            mutated,
                            profile,
                            fixture=fixture,
                            binding=binding,
                        )

    def test_profile_rejects_unknown_analogue_mapping(self) -> None:
        profile = load_reference_profile()
        mutated = deepcopy(profile)
        mutated["queryAnalogues"][2]["relationship"] = "EquivalentToOutputClosure"
        with self.assertRaises(SchemaError):
            validate_reference_profile(mutated)

    def test_solver_timeout_is_a_closed_unknown_result(self) -> None:
        program = _program()
        coalition = parse_coalition(
            {"id": "observer", "principals": [], "controlledHosts": ["caller"]}
        )
        left = compile_program(program, "L")
        right = compile_program(program, "R")
        query = build_reference_query(left, right, coalition, "ReferenceAuditAll")
        artifact = lower_reference_query(query)
        with patch(
            "sps_ref.solve.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["z3"], 30),
        ):
            result = run_z3(artifact)
        self.assertEqual(result.status, "unknown")
        self.assertIn("timed out", result.detail)


if __name__ == "__main__":
    unittest.main()
