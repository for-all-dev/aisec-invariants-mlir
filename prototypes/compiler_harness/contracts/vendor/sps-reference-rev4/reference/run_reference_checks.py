#!/usr/bin/env python3
"""Run the executable SPS Rev-4 reference fixtures."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from sps_ref.canonical import canonical_bytes, load_json_bytes
from sps_ref.encoding import decode_bits, encode_bits
from sps_ref.engine import CompiledProgram, compile_program
from sps_ref.errors import ReferenceError, SolverUnavailableError
from sps_ref.expand import expand_program
from sps_ref.evidence import canonical_relation_result_bytes, run_relation_fixture
from sps_ref.model import load_fixture, parse_coalition, parse_program
from sps_ref.ponf import audit_reference_ponf, build_reference_ponf
from sps_ref.product import build_product
from sps_ref.query import build_reference_query, run_query_exhaustive
from sps_ref.replay import replay_witness, run_concrete_exhaustive
from sps_ref.smt import lower_reference_ponf, lower_reference_query
from sps_ref.solve import (
    parse_model_response,
    run_cvc5,
    run_exhaustive,
    run_z3,
)


HERE = Path(__file__).resolve().parent
SPS_DIR = HERE.parent
FIXTURE_DIR = HERE / "fixtures"
CATALOG_PATH = HERE / "fixture-catalog.json"
ASSURANCE_PATH = HERE / "assurance-status.json"
PROFILE_PATH = SPS_DIR / "SPS_Rev4_LLVM_Normal_Form_and_Conformance_Profile.md"
INTERFACE_BUILDER = SPS_DIR / "interfaces" / "rev4.1" / "build_interfaces.py"


class FixtureFailure(Exception):
    pass


def _exact_keys(value: Any, keys: set[str], context: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise FixtureFailure(
            f"{context}: expected fields {sorted(keys)}, found {actual}"
        )


def _compile_pair(
    fixture: dict[str, Any],
) -> tuple[CompiledProgram, CompiledProgram, Any]:
    _exact_keys(fixture["input"], {"program", "coalition"}, fixture["caseId"])
    program = parse_program(fixture["input"]["program"])
    coalition = parse_coalition(fixture["input"]["coalition"])
    left = compile_program(program, "L")
    right = compile_program(program, "R")
    return left, right, coalition


def _run_noninterference(
    fixture: dict[str, Any], optional_solver_status: dict[str, str]
) -> None:
    _exact_keys(
        fixture["expected"],
        {"status", "firstBadCause", "replayAccepted"},
        f"{fixture['caseId']}.expected",
    )
    left, right, coalition = _compile_pair(fixture)
    product = build_product(left, right, coalition)
    query = build_reference_query(
        left, right, coalition, "ReferenceAuditAll"
    )
    ponf = build_reference_ponf(left, right, coalition)
    audit_reference_ponf(ponf, left, right, coalition)
    if canonical_bytes(ponf) != canonical_bytes(
        build_reference_ponf(left, right, coalition)
    ):
        raise FixtureFailure(f"{fixture['caseId']}: nondeterministic PONF")
    product_smt = lower_reference_query(query)
    smt = lower_reference_ponf(ponf)
    if smt != product_smt:
        raise FixtureFailure(
            f"{fixture['caseId']}: serialized PONF lowering disagrees with product"
        )
    if smt != lower_reference_ponf(ponf):
        raise FixtureFailure(f"{fixture['caseId']}: nondeterministic SMT lowering")

    exhaustive = run_query_exhaustive(query)
    concrete = run_concrete_exhaustive(left, right, coalition)
    try:
        z3 = run_z3(smt)
    except SolverUnavailableError as exc:
        raise FixtureFailure(f"{fixture['caseId']}: {exc}") from exc
    expected_status = fixture["expected"]["status"]
    if (
        exhaustive.status != expected_status
        or concrete.status != expected_status
        or z3.status != expected_status
    ):
        raise FixtureFailure(
            f"{fixture['caseId']}: expected {expected_status}; "
            f"symbolic-exhaustive={exhaustive.status}, "
            f"concrete-exhaustive={concrete.status} ({concrete.detail}), "
            f"z3={z3.status} ({z3.detail})"
        )

    cvc5 = None
    if os.environ.get("CVC5", "") or shutil.which("cvc5") is not None:
        cvc5 = run_cvc5(smt)
        optional_solver_status["cvc5"] = "available-and-checked"
        if cvc5.status != expected_status:
            raise FixtureFailure(
                f"{fixture['caseId']}: cvc5={cvc5.status}, "
                f"expected {expected_status} ({cvc5.detail})"
            )
    else:
        optional_solver_status["cvc5"] = "unavailable-open"

    expected_replay = fixture["expected"]["replayAccepted"]
    expected_cause = fixture["expected"]["firstBadCause"]
    if expected_status == "sat":
        for backend, witness in [
            ("symbolic-exhaustive", exhaustive.witness),
            ("concrete-exhaustive", concrete.witness),
            ("z3", z3.witness),
            *(([("cvc5", cvc5.witness)]) if cvc5 is not None else []),
        ]:
            if witness is None:
                raise FixtureFailure(
                    f"{fixture['caseId']}: {backend} omitted a SAT witness"
                )
            replay = replay_witness(left, right, coalition, witness)
            if replay.accepted != expected_replay:
                raise FixtureFailure(
                    f"{fixture['caseId']}: {backend} replay acceptance "
                    f"{replay.accepted}, expected {expected_replay}"
                )
            if replay.bad_cause != expected_cause:
                raise FixtureFailure(
                    f"{fixture['caseId']}: {backend} replay cause "
                    f"{replay.bad_cause}, expected {expected_cause}"
                )
    elif expected_replay or expected_cause is not None:
        raise FixtureFailure(
            f"{fixture['caseId']}: UNSAT fixture cannot expect replay"
        )


def _run_bit_encoding(fixture: dict[str, Any]) -> None:
    _exact_keys(
        fixture["input"], {"value", "bitWidth", "byteOrder"}, fixture["caseId"]
    )
    _exact_keys(
        fixture["expected"], {"encodedHex", "roundTrip"}, fixture["caseId"]
    )
    raw = encode_bits(
        fixture["input"]["value"],
        fixture["input"]["bitWidth"],
        fixture["input"]["byteOrder"],
    )
    if raw.hex() != fixture["expected"]["encodedHex"]:
        raise FixtureFailure(
            f"{fixture['caseId']}: encoded {raw.hex()}, "
            f"expected {fixture['expected']['encodedHex']}"
        )
    decoded = decode_bits(
        raw, fixture["input"]["bitWidth"], fixture["input"]["byteOrder"]
    )
    if decoded != fixture["expected"]["roundTrip"]:
        raise FixtureFailure(
            f"{fixture['caseId']}: decoded {decoded}, "
            f"expected {fixture['expected']['roundTrip']}"
        )


def _run_expand(fixture: dict[str, Any]) -> None:
    _exact_keys(fixture["input"], {"program"}, fixture["caseId"])
    _exact_keys(
        fixture["expected"], {"horizon", "nodeKinds"}, fixture["caseId"]
    )
    table = expand_program(fixture["input"]["program"])
    kinds = [row["kind"] for row in table["nodes"]]
    if table["horizon"] != fixture["expected"]["horizon"]:
        raise FixtureFailure(
            f"{fixture['caseId']}: horizon {table['horizon']}, "
            f"expected {fixture['expected']['horizon']}"
        )
    if kinds != fixture["expected"]["nodeKinds"]:
        raise FixtureFailure(
            f"{fixture['caseId']}: node kinds {kinds}, "
            f"expected {fixture['expected']['nodeKinds']}"
        )


def _run_refusal(fixture: dict[str, Any]) -> None:
    _exact_keys(fixture["input"], {"program"}, fixture["caseId"])
    _exact_keys(fixture["expected"], {"reason"}, fixture["caseId"])
    try:
        compile_program(fixture["input"]["program"], "L")
    except ReferenceError as exc:
        if exc.reason != fixture["expected"]["reason"]:
            raise FixtureFailure(
                f"{fixture['caseId']}: refusal {exc.reason}, "
                f"expected {fixture['expected']['reason']}"
            ) from exc
        return
    raise FixtureFailure(f"{fixture['caseId']}: expected fail-closed refusal")


def _run_artifact_mutation(fixture: dict[str, Any]) -> None:
    _exact_keys(
        fixture["input"], {"program", "coalition", "mutation"}, fixture["caseId"]
    )
    _exact_keys(fixture["expected"], {"reason"}, fixture["caseId"])
    left = compile_program(fixture["input"]["program"], "L")
    right = compile_program(fixture["input"]["program"], "R")
    coalition = parse_coalition(fixture["input"]["coalition"])
    artifact = deepcopy(build_reference_ponf(left, right, coalition))
    mutation = fixture["input"]["mutation"]
    if mutation != "replace-first-bad-expression-with-false":
        raise FixtureFailure(f"{fixture['caseId']}: unknown mutation {mutation}")
    artifact["auditBadCauseRows"][0]["expression"] = {
        "op": "bool",
        "sort": "Bool",
        "value": False,
    }
    try:
        audit_reference_ponf(artifact, left, right, coalition)
    except ReferenceError as exc:
        if exc.reason != fixture["expected"]["reason"]:
            raise FixtureFailure(
                f"{fixture['caseId']}: mutation refusal {exc.reason}, "
                f"expected {fixture['expected']['reason']}"
            ) from exc
        return
    raise FixtureFailure(f"{fixture['caseId']}: mutated artifact was accepted")


def _run_product_profile_refusal(fixture: dict[str, Any]) -> None:
    _exact_keys(
        fixture["input"],
        {"program", "coalition", "witness"},
        fixture["caseId"],
    )
    _exact_keys(
        fixture["expected"],
        {"productReason", "replayReason"},
        fixture["caseId"],
    )
    program = parse_program(fixture["input"]["program"])
    left = compile_program(program, "L")
    right = compile_program(program, "R")
    coalition = parse_coalition(fixture["input"]["coalition"])
    try:
        build_product(left, right, coalition)
    except ReferenceError as exc:
        if exc.reason != fixture["expected"]["productReason"]:
            raise FixtureFailure(
                f"{fixture['caseId']}: product refusal {exc.reason}, "
                f"expected {fixture['expected']['productReason']}"
            ) from exc
    else:
        raise FixtureFailure(f"{fixture['caseId']}: product profile was accepted")
    try:
        replay_witness(left, right, coalition, fixture["input"]["witness"])
    except ReferenceError as exc:
        if exc.reason != fixture["expected"]["replayReason"]:
            raise FixtureFailure(
                f"{fixture['caseId']}: replay refusal {exc.reason}, "
                f"expected {fixture['expected']['replayReason']}"
            ) from exc
        return
    raise FixtureFailure(f"{fixture['caseId']}: unsupported replay was accepted")


def _run_model_wire(fixture: dict[str, Any]) -> None:
    _exact_keys(fixture["input"], {"variables", "response"}, fixture["caseId"])
    _exact_keys(fixture["expected"], {"accepted", "values"}, fixture["caseId"])
    raw_variables = fixture["input"]["variables"]
    if (
        not isinstance(raw_variables, list)
        or not all(
            isinstance(row, list)
            and len(row) == 2
            and isinstance(row[0], str)
            and isinstance(row[1], int)
            and not isinstance(row[1], bool)
            and row[1] > 0
            for row in raw_variables
        )
    ):
        raise FixtureFailure(f"{fixture['caseId']}: malformed variable table")
    variables = tuple((row[0], row[1]) for row in raw_variables)
    try:
        values = parse_model_response(fixture["input"]["response"], variables)
    except ValueError:
        if fixture["expected"]["accepted"]:
            raise FixtureFailure(f"{fixture['caseId']}: valid model was rejected")
        return
    if not fixture["expected"]["accepted"]:
        raise FixtureFailure(f"{fixture['caseId']}: malformed model was accepted")
    if values != fixture["expected"]["values"]:
        raise FixtureFailure(
            f"{fixture['caseId']}: normalized values {values}, "
            f"expected {fixture['expected']['values']}"
        )


def _validate_assurance_status() -> None:
    try:
        status = load_json_bytes(ASSURANCE_PATH.read_bytes())
    except (OSError, ReferenceError) as exc:
        raise FixtureFailure(f"cannot read assurance manifest: {exc}") from exc
    _exact_keys(
        status,
        {"formatId", "claimBoundary", "claims", "refusals"},
        "assurance-status.json",
    )
    if (
        status["formatId"] != "SPS-Reference-Assurance-Status-v2"
        or status["claimBoundary"] != "ExecutableReferenceOnly"
    ):
        raise FixtureFailure("assurance manifest has an unsafe claim boundary")
    claims = status["claims"]
    required = {
        "normativeLLVMV2": "Open(NotImplemented)",
        "normativeInterfacesV2": "Open(SchemaAndVectorsOnly)",
        "normativePONF": "Open(ReferenceSliceOnly)",
        "writtenProofMechanization": "Open(NotMechanized)",
        "adaptiveInvocation": "Unknown(PersistentInvariantEncodingUnsupported)",
        "strongHostObserver": "Open(ObserverProfileNotModeled)",
        "p4Deployment": "Open(P4EvidenceProfileUnavailable)",
        "crossSolver": "Open(RequiresSecondInstalledSolver)",
    }
    if not isinstance(claims, list):
        raise FixtureFailure("assurance claims must be a list")
    actual: dict[str, str] = {}
    for row in claims:
        _exact_keys(row, {"claimId", "status"}, "assurance claim")
        if row["claimId"] in actual:
            raise FixtureFailure(f"duplicate assurance claim {row['claimId']}")
        actual[row["claimId"]] = row["status"]
        if "Proved" in row["status"] or row["status"].startswith("Closed"):
            raise FixtureFailure(f"unsafe closed assurance claim {row}")
    if actual != required:
        raise FixtureFailure(
            f"assurance claims differ: expected {required}, found {actual}"
        )
    if not isinstance(status["refusals"], list) or not status["refusals"]:
        raise FixtureFailure("assurance refusal inventory is empty")


def _run_interface_builder(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=SPS_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _validate_rev41_interfaces(
    interface_dist: Path | None = None,
    interface_manifest: Path | None = None,
) -> None:
    if (interface_dist is None) != (interface_manifest is None):
        raise FixtureFailure(
            "--interface-dist and --interface-manifest must be supplied together"
        )
    if interface_dist is None and interface_manifest is None:
        result = _run_interface_builder([sys.executable, str(INTERFACE_BUILDER)])
    else:
        assert interface_dist is not None and interface_manifest is not None
        dist = interface_dist.resolve()
        manifest = interface_manifest.resolve()
        command = [
            sys.executable,
            str(INTERFACE_BUILDER),
            "--check-dist",
            str(dist),
            "--manifest",
            str(manifest),
        ]
        try:
            manifest_relative = manifest.relative_to(dist)
        except ValueError:
            result = _run_interface_builder(command)
        else:
            if not manifest_relative.parts:
                raise FixtureFailure("interface manifest cannot be the dist directory")
            with tempfile.TemporaryDirectory(prefix="sps-interface-dist-") as temporary:
                staged_dist = Path(temporary) / "dist"

                def ignore_manifest(directory: str, names: list[str]) -> set[str]:
                    relative = Path(directory).resolve().relative_to(dist)
                    if relative == manifest_relative.parent:
                        return {manifest_relative.name} & set(names)
                    return set()

                try:
                    shutil.copytree(dist, staged_dist, ignore=ignore_manifest)
                except OSError as exc:
                    raise FixtureFailure(
                        f"cannot stage interface distribution: {exc}"
                    ) from exc
                command[command.index(str(dist))] = str(staged_dist)
                result = _run_interface_builder(command)
    if result.returncode != 0:
        raise FixtureFailure(
            "Rev4.1 interface package failed validation: " + result.stdout.strip()
        )


def _profile_fixture_families() -> set[str]:
    import re

    text = PROFILE_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"NF-FX-[A-Z0-9-]+", text))


def _fixture_catalog() -> list[dict[str, str]]:
    try:
        catalog = load_json_bytes(CATALOG_PATH.read_bytes())
    except (OSError, ReferenceError) as exc:
        raise FixtureFailure(f"cannot read fixture catalog: {exc}") from exc
    _exact_keys(catalog, {"formatId", "cases"}, "fixture-catalog.json")
    if catalog["formatId"] != "SPS-Reference-Fixture-Catalog-v3":
        raise FixtureFailure("fixture catalog has the wrong formatId")
    rows = catalog["cases"]
    if not isinstance(rows, list) or not rows:
        raise FixtureFailure("fixture catalog must contain a nonempty case list")
    expected_files: list[str] = []
    expected_cases: list[str] = []
    for index, row in enumerate(rows):
        _exact_keys(
            row,
            {"file", "caseId", "familyId", "kind"},
            f"fixture-catalog.json.cases[{index}]",
        )
        if not all(isinstance(row[key], str) and row[key] for key in row):
            raise FixtureFailure(f"fixture catalog row {index} has a non-string field")
        filename = row["file"]
        if Path(filename).name != filename or not filename.endswith(".json"):
            raise FixtureFailure(f"fixture catalog row {index} has an unsafe file")
        expected_files.append(filename)
        expected_cases.append(row["caseId"])
    if expected_files != sorted(expected_files) or len(expected_files) != len(
        set(expected_files)
    ):
        raise FixtureFailure("fixture catalog files must be sorted and unique")
    if len(expected_cases) != len(set(expected_cases)):
        raise FixtureFailure("fixture catalog caseIds must be unique")
    discovered = sorted(
        path.relative_to(FIXTURE_DIR).as_posix()
        for path in FIXTURE_DIR.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    if discovered != expected_files:
        raise FixtureFailure(
            f"fixture set differs from catalog: expected {expected_files}, "
            f"found {discovered}"
        )
    return rows


def run_all(
    run_tests: bool = True,
    interface_dist: Path | None = None,
    interface_manifest: Path | None = None,
) -> int:
    _validate_assurance_status()
    _validate_rev41_interfaces(interface_dist, interface_manifest)
    profile_families = _profile_fixture_families()
    catalog = _fixture_catalog()
    cases: set[str] = set()
    executable_families: set[str] = set()
    optional_solver_status: dict[str, str] = {}
    handlers = {
        "noninterference": lambda fixture: _run_noninterference(
            fixture, optional_solver_status
        ),
        "bit-encoding": _run_bit_encoding,
        "expand": _run_expand,
        "refusal": _run_refusal,
        "artifact-mutation": _run_artifact_mutation,
        "product-profile-refusal": _run_product_profile_refusal,
        "model-wire": _run_model_wire,
    }
    for catalog_row in catalog:
        path = FIXTURE_DIR / catalog_row["file"]
        fixture = load_fixture(path)
        actual_header = {
            "file": path.name,
            "caseId": fixture["caseId"],
            "familyId": fixture["familyId"],
            "kind": fixture["kind"],
        }
        if actual_header != catalog_row:
            raise FixtureFailure(
                f"{path.name}: catalog header {catalog_row}, "
                f"fixture header {actual_header}"
            )
        case_id = fixture["caseId"]
        if case_id in cases:
            raise FixtureFailure(f"duplicate fixture case {case_id}")
        cases.add(case_id)
        family = fixture["familyId"]
        if family not in profile_families:
            raise FixtureFailure(f"{case_id}: family {family} is absent from profile")
        executable_families.add(family)
        handler = handlers.get(fixture["kind"])
        if handler is None:
            raise FixtureFailure(f"{case_id}: unsupported kind {fixture['kind']}")
        handler(fixture)
        print(f"PASS {case_id}")

    if run_tests:
        suite = unittest.defaultTestLoader.discover(str(HERE / "tests"))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        if not result.wasSuccessful():
            raise FixtureFailure("reference unit tests failed")

    print(
        "SPS executable reference checks: PASSED "
        f"({len(cases)} cases, {len(executable_families)}/"
        f"{len(profile_families)} profile families executable)"
    )
    print(
        "Optional cross-solver status: "
        + ", ".join(
            f"{name}={value}" for name, value in sorted(optional_solver_status.items())
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--relation-fixture",
        type=Path,
        help="run one external SPS executable-reference relation fixture",
    )
    parser.add_argument(
        "--binding",
        type=Path,
        help="validate and bind the external harness reduction mapping",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="-",
        help="canonical evidence result path, or - for stdout",
    )
    parser.add_argument(
        "--skip-unit-tests", action="store_true", help="run fixtures only"
    )
    parser.add_argument(
        "--interface-dist",
        type=Path,
        help="validate this Rev4.1 interface distribution instead of the default",
    )
    parser.add_argument(
        "--interface-manifest",
        type=Path,
        help="validate against this Rev4.1 interface manifest instead of the default",
    )
    args = parser.parse_args()
    try:
        if args.relation_fixture is not None or args.binding is not None:
            if args.relation_fixture is None or args.binding is None:
                raise FixtureFailure(
                    "--relation-fixture and --binding must be supplied together"
                )
            fixture = load_json_bytes(args.relation_fixture.read_bytes())
            binding = load_json_bytes(args.binding.read_bytes())
            result = run_relation_fixture(
                fixture,
                binding,
                fixture_path=args.relation_fixture,
                binding_path=args.binding,
            )
            raw = canonical_relation_result_bytes(result)
            if args.output == "-":
                sys.stdout.buffer.write(raw)
            else:
                Path(args.output).write_bytes(raw)
            return 0
        return run_all(
            run_tests=not args.skip_unit_tests,
            interface_dist=args.interface_dist,
            interface_manifest=args.interface_manifest,
        )
    except (FixtureFailure, ReferenceError) as exc:
        print(f"SPS executable reference checks: FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
