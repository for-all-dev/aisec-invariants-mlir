#!/usr/bin/env python3
"""Validate the nonclaimable future-Conformance error-event contract.

This checker validates hand-authored intent that can be checked before the
LLVM 22.1.8 materializer and exact Rev-4 verifier exist. It does not establish
``WFInputs``, ``NFConforms``, replay coverage, or any result axis. Diagnostics
name the target conforming disposition as fixture documentation only.

Normative anchors in ``SPS_Rev4_Normative_Specification.md``:
  * ABISchema fields and ErrorFieldBindingV2: 578-596 and 642-652;
  * exact error binding rules: 828-854;
  * Error projection: 3229-3232 and 3267-3276;
  * DeclaredFailure event order: 6601;
  * verifier-UB event order: 3050-3057 and 6562-6565.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


CONTRACT_FIELDS = (
    "formatId",
    "fixtureTier",
    "targetTier",
    "claimable",
    "currentStatus",
    "caseId",
    "sourceShape",
    "requiredMaterializedFiles",
    "policyIntent",
    "abiIntent",
    "expectedSemantics",
)

ABI_FIELDS = (
    "abiId",
    "targetDataLayout",
    "entries",
    "carriers",
    "namedCarriers",
    "outputBindings",
    "returnClassBindings",
    "terminalOutputOrder",
    "contractEventOutputOrder",
    "errorFields",
    "ubRiskErrorFieldId",
    "aliasTopologyBindings",
)

VISIBILITY_FIELDS = ("worldVisible", "memberVisible", "minimallyJointVisible")
ERROR_BINDING_FIELDS = ("errorFieldId", "payloadType", "source", "encoding")
OUTPUT_BINDING_FIELDS = ("outputId", "source", "footprint")
RETURN_BITS_SOURCE_FIELDS = (
    "tag",
    "entryId",
    "bitOffset",
    "bitWidth",
    "encoding",
)
RETURN_BITS_FAILURE_SOURCE_FIELDS = (
    "tag",
    "entryId",
    "returnClass",
    "bitOffset",
    "bitWidth",
    "encoding",
)
RETURN_BIT_FIELDS = ("tag", "entryId", "bitIndex")
RETURN_CLASS_BINDING_FIELDS = ("entryId", "returnSiteAlias", "returnClass")
TERMINAL_OUTPUT_ORDER_FIELDS = ("entryId", "returnClass", "outputIds")
ENCODING_FIELDS = (
    "bitWidth",
    "byteWidth",
    "byteOrder",
    "highPaddingBits",
    "signedness",
)

ENCODING_I8 = {
    "bitWidth": 8,
    "byteWidth": 1,
    "byteOrder": "BigEndian",
    "highPaddingBits": 0,
    "signedness": "Unsigned",
}

UB_PAYLOAD_TYPE = {
    "tag": "TupleValueV2",
    "fields": [
        {
            "fieldId": "kind",
            "valueType": {"tag": "BVValueV2", "bitWidth": 8},
        },
        {
            "fieldId": "reasonClass",
            "valueType": {"tag": "BVValueV2", "bitWidth": 4},
        },
    ],
}

UB_ENCODING = {
    "bitWidth": 16,
    "byteWidth": 2,
    "byteOrder": "BigEndian",
    "highPaddingBits": 0,
    "signedness": "NotNumeric",
}

NEGATIVE_CASES = [
    {
        "caseId": "missing-error-fields",
        "targetOutcome": "ConfigurationRejectedV2(NoncanonicalInterface); NoModelStatus",
    },
    {
        "caseId": "dangling-declared-error-id",
        "targetOutcome": "Unknown(OutputBindingIncomplete)",
    },
    {
        "caseId": "declared-error-fields-mismatch",
        "targetOutcome": "Unknown(OutputBindingIncomplete)",
    },
    {
        "caseId": "dangling-ub-risk-error-id",
        "targetOutcome": "Unknown(OutputBindingIncomplete)",
    },
    {
        "caseId": "malformed-application-payload-binding",
        "targetOutcome": "Unknown(OutputBindingIncomplete)",
    },
    {
        "caseId": "malformed-application-payload-source",
        "targetOutcome": "Unknown(OutputBindingIncomplete)",
    },
    {
        "caseId": "malformed-ub-risk-payload-binding",
        "targetOutcome": "Unknown(OutputBindingIncomplete)",
    },
    {
        "caseId": "duplicate-verifier-ub-payload-binding",
        "targetOutcome": "Unknown(OutputBindingIncomplete)",
    },
    {
        "caseId": "dangling-error-visibility-id",
        "targetOutcome": "Unknown(ManifestMismatch)",
    },
    {
        "caseId": "reordered-declared-failure-events",
        "targetOutcome": "Unknown(OutputClosureMismatch)",
    },
    {
        "caseId": "reordered-ub-risk-events",
        "targetOutcome": "Unknown(OutputClosureMismatch)",
    },
]

UB_REASON_CLASS = "DivisorZero"


def fail(message: str) -> None:
    raise SystemExit(message)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            fail(f"duplicate JSON field: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(), object_pairs_hook=strict_object)
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path}: {error}")
    if not isinstance(value, dict):
        fail(f"{path} must contain one JSON object")
    return value


def require_fields(value: Any, fields: tuple[str, ...], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{name} must be an object")
    if tuple(value) != fields:
        fail(f"{name} fields/order mismatch: expected {fields}, got {tuple(value)}")
    return value


def require_sorted_unique_strings(value: Any, name: str) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) for item in value)
        or value != sorted(set(value))
    ):
        fail(f"{name} must be a sorted, duplicate-free string array")
    return value


def class_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def declared_failure_id(value: Any) -> str | None:
    if not isinstance(value, dict) or value.get("tag") != "DeclaredFailure":
        return None
    args = value.get("args")
    if not isinstance(args, list) or len(args) != 1 or not isinstance(args[0], str):
        fail("DeclaredFailure must carry exactly one ErrorFieldId")
    return args[0]


def visible(basis: dict[str, Any], item: str, coalition: list[str]) -> bool:
    if item in basis["worldVisible"]:
        return True
    if any(item in basis["memberVisible"][principal] for principal in coalition):
        return True
    return any(
        row.get("item") == item and set(row.get("principals", [])) <= set(coalition)
        for row in basis["minimallyJointVisible"]
        if isinstance(row, dict)
    )


def coalition_closure(maxima: Any, principals: list[str]) -> list[list[str]]:
    if not isinstance(maxima, list) or not maxima:
        fail("policyIntent.maximalAdversaryCoalitions must be nonempty")
    coalitions: set[tuple[str, ...]] = set()
    seen_maxima: set[tuple[str, ...]] = set()
    for maximum in maxima:
        members = require_sorted_unique_strings(
            maximum, "policyIntent.maximalAdversaryCoalitions row"
        )
        if not members:
            fail("policyIntent maximal coalition rows must be nonempty")
        unknown = sorted(set(members) - set(principals))
        if unknown:
            fail(f"maximal coalition names undeclared principal {unknown[0]!r}")
        member_tuple = tuple(members)
        if member_tuple in seen_maxima:
            fail("policyIntent maximal coalition rows must be unique")
        seen_maxima.add(member_tuple)
        for mask in range(1 << len(members)):
            coalitions.add(
                tuple(member for index, member in enumerate(members) if mask & (1 << index))
            )
    return [list(row) for row in sorted(coalitions, key=lambda row: (len(row), row))]


def validate_visibility_basis(
    basis: Any,
    name: str,
    principals: list[str],
    allowed_ids: set[str],
) -> dict[str, Any]:
    value = require_fields(basis, VISIBILITY_FIELDS, name)
    world = require_sorted_unique_strings(value["worldVisible"], f"{name}.worldVisible")
    members = value["memberVisible"]
    if not isinstance(members, dict) or list(members) != principals:
        fail(f"{name}.memberVisible must be total in policy principal order")
    referenced = set(world)
    for principal, identifiers in members.items():
        referenced.update(
            require_sorted_unique_strings(identifiers, f"{name}.memberVisible[{principal}]")
        )
    joint = value["minimallyJointVisible"]
    if not isinstance(joint, list):
        fail(f"{name}.minimallyJointVisible must be an array")
    seen_joint: set[tuple[tuple[str, ...], str]] = set()
    for index, row in enumerate(joint):
        if not isinstance(row, dict) or tuple(row) != ("principals", "item"):
            fail(f"{name}.minimallyJointVisible[{index}] is malformed")
        joint_principals = require_sorted_unique_strings(
            row["principals"], f"{name}.joint[{index}].principals"
        )
        if not joint_principals:
            fail(f"{name}.joint[{index}].principals must be nonempty")
        unknown_principals = sorted(set(joint_principals) - set(principals))
        if unknown_principals:
            fail(
                f"{name}.joint[{index}] names undeclared principal "
                f"{unknown_principals[0]!r}"
            )
        item = row["item"]
        if not isinstance(item, str):
            fail(f"{name}.joint[{index}].item must be a string")
        joint_key = (tuple(joint_principals), item)
        if joint_key in seen_joint:
            fail(f"{name}.minimallyJointVisible contains a duplicate row")
        seen_joint.add(joint_key)
        referenced.add(item)
    unknown = sorted(referenced - allowed_ids)
    if unknown:
        kind = "error field" if name.endswith("errorVisibility") else "identifier"
        fail(f"{name} references undeclared {kind} {unknown[0]!r}")
    return value


def validate_source_shape(root: Path, contract: dict[str, Any]) -> None:
    shape = root / contract["sourceShape"]
    try:
        text = shape.read_text()
    except OSError as error:
        fail(f"cannot read sourceShape {shape}: {error}")
    required = (
        "define i8 @sps_error_fixture(i1 %public_fail, i8 %secret_detail, i8 %public_divisor)",
        "declared_failure:",
        "ret i8 %secret_detail",
        "ordinary:",
        "%quotient = udiv i8 42, %public_divisor",
        "ret i8 %quotient",
    )
    for fragment in required:
        if fragment not in text:
            fail(f"sourceShape is missing required capture fragment: {fragment}")


def validate_contract(root: Path, contract_path: Path) -> dict[str, Any]:
    contract = require_fields(load_json(contract_path), CONTRACT_FIELDS, "contract")
    if contract["formatId"] != "SPS-Harness-Future-Conformance-Error-Contract-v2":
        fail("contract has the wrong harness formatId")
    if contract["fixtureTier"] != {"tag": "CandidateOnly"} or contract[
        "targetTier"
    ] != {"tag": "ConformanceV2"}:
        fail("contract must remain CandidateOnly with targetTier ConformanceV2")
    if contract["claimable"] is not False:
        fail("future error contract must remain claimable=false")
    if contract["currentStatus"] != {
        "nfConforms": "NotEvaluated",
        "modelStatus": "NotComputed",
        "deploymentStatus": "NotComputed",
        "policyReviewStatus": "NotComputed",
    }:
        fail("future error contract must keep all current result axes uncomputed")

    required_files = contract["requiredMaterializedFiles"]
    if required_files != [
        "artifact.bc",
        "artifact-identity.sps.json",
        "identity-evidence.sps.json",
        "sps-manifest.sps.json",
        "proof-configuration.sps.json",
        "aggregation-input.sps.json",
        "sps-report.sps.json",
    ]:
        fail("requiredMaterializedFiles does not match the ConformanceV2 tier contract")

    validate_source_shape(root, contract)

    policy = contract["policyIntent"]
    abi = require_fields(contract["abiIntent"], ABI_FIELDS, "abiIntent")
    expected = contract["expectedSemantics"]
    if not isinstance(policy, dict) or not isinstance(expected, dict):
        fail("policyIntent and expectedSemantics must be objects")

    principals = require_sorted_unique_strings(policy.get("principals"), "policyIntent.principals")
    hosts = set(require_sorted_unique_strings(policy.get("hosts"), "policyIntent.hosts"))
    components = policy.get("components")
    outputs = abi["outputBindings"]
    error_fields = abi["errorFields"]
    entries = abi["entries"]
    if not isinstance(components, dict) or not isinstance(outputs, dict):
        fail("policy components and ABI outputBindings must be objects")
    if not isinstance(error_fields, dict) or not error_fields:
        fail("abiIntent.errorFields must be a nonempty total map")
    if not isinstance(entries, dict) or len(entries) != 1:
        fail("abiIntent.entries must contain exactly one entry")

    entry_id, entry = next(iter(entries.items()))
    policy_entry = policy.get("entries", {}).get(entry_id)
    if not isinstance(entry, dict) or not isinstance(policy_entry, dict):
        fail("the ABI and policy must declare the same entry")
    allowed_classes = policy_entry.get("allowedReturnClasses")
    if not isinstance(allowed_classes, list) or not allowed_classes:
        fail("policy entry must declare nonempty allowedReturnClasses")
    declared_ids = {
        identifier
        for return_class in allowed_classes
        if (identifier := declared_failure_id(return_class)) is not None
    }
    if len(declared_ids) != 1:
        fail("the future error fixture must declare exactly one application ErrorFieldId")
    declared_id = next(iter(declared_ids))
    declared_class = {"tag": "DeclaredFailure", "args": [declared_id]}
    normal_class = {"tag": "NormalValue"}
    allowed_keys = {class_key(value) for value in allowed_classes}
    if len(allowed_classes) != 2 or allowed_keys != {
        class_key(normal_class),
        class_key(declared_class),
    }:
        fail("allowedReturnClasses must be exactly NormalValue and one DeclaredFailure")
    for identifier in sorted(declared_ids):
        if identifier not in error_fields:
            fail(
                f"DeclaredFailure ErrorFieldId {identifier!r} is absent from "
                "abiIntent.errorFields (target: Unknown(OutputBindingIncomplete))"
            )
    declared_error_fields = require_sorted_unique_strings(
        entry.get("declaredErrorFields"), "abiIntent.entries[].declaredErrorFields"
    )
    if set(declared_error_fields) != declared_ids:
        fail(
            "EntryABIV2.declaredErrorFields must equal exactly the application "
            "DeclaredFailure IDs; the verifier UB-risk field is not an application ID"
        )

    if list(outputs) != ["return.byte"]:
        fail("outputBindings must contain exactly the return.byte binding")
    output_binding = require_fields(
        outputs["return.byte"], OUTPUT_BINDING_FIELDS, "outputBindings['return.byte']"
    )
    if output_binding["outputId"] != "return.byte":
        fail("return.byte map key disagrees with binding.outputId")
    output_source = require_fields(
        output_binding["source"],
        RETURN_BITS_SOURCE_FIELDS,
        "outputBindings['return.byte'].source",
    )
    if output_source != {
        "tag": "ReturnBitsV2",
        "entryId": entry_id,
        "bitOffset": 0,
        "bitWidth": 8,
        "encoding": ENCODING_I8,
    }:
        fail("return.byte must bind the exact eight return bits with canonical BV8 encoding")
    expected_footprint = [
        {"tag": "ReturnBitV2", "entryId": entry_id, "bitIndex": bit_index}
        for bit_index in range(8)
    ]
    footprint = output_binding["footprint"]
    if not isinstance(footprint, list):
        fail("return.byte footprint must be an ordered array")
    for index, row in enumerate(footprint):
        require_fields(row, RETURN_BIT_FIELDS, f"return.byte.footprint[{index}]")
    if footprint != expected_footprint:
        fail("return.byte footprint must be the exact ordered ReturnBitV2 range 0..7")

    for identifier, binding in error_fields.items():
        binding = require_fields(
            binding, ERROR_BINDING_FIELDS, f"abiIntent.errorFields[{identifier!r}]"
        )
        if binding["errorFieldId"] != identifier:
            fail(f"errorFields map key {identifier!r} disagrees with binding.errorFieldId")
        require_fields(
            binding["encoding"],
            ENCODING_FIELDS,
            f"errorFields[{identifier!r}].encoding",
        )

    ub_id = abi["ubRiskErrorFieldId"]
    if not isinstance(ub_id, str) or ub_id not in error_fields:
        fail(
            f"ubRiskErrorFieldId {ub_id!r} is absent from abiIntent.errorFields "
            "(target: Unknown(OutputBindingIncomplete))"
        )
    if ub_id in declared_ids:
        fail("ubRiskErrorFieldId must not be an application DeclaredFailure ID")
    ub_binding = error_fields[ub_id]
    verifier_sources = [
        identifier
        for identifier, binding in error_fields.items()
        if isinstance(binding, dict)
        and isinstance(binding.get("source"), dict)
        and binding["source"].get("tag") == "VerifierUBRiskPayloadV2"
    ]
    if verifier_sources != [ub_id]:
        fail(
            "VerifierUBRiskPayloadV2 must be the source of exactly one error field, "
            f"found {len(verifier_sources)} (target: Unknown(OutputBindingIncomplete))"
        )
    if set(error_fields) != {declared_id, ub_id}:
        fail(
            "errorFields must contain exactly the application field and the mandatory "
            "verifier UB-risk field"
        )
    if ub_binding["source"] != {"tag": "VerifierUBRiskPayloadV2"}:
        fail(
            "ubRiskErrorFieldId must use the exact VerifierUBRiskPayloadV2 source "
            "(target: Unknown(OutputBindingIncomplete))"
        )
    if ub_binding["payloadType"] != UB_PAYLOAD_TYPE or ub_binding["encoding"] != UB_ENCODING:
        fail(
            "ubRiskErrorFieldId must use the fixed verifier UB payload type and encoding "
            "(target: Unknown(OutputBindingIncomplete))"
        )

    return_bindings = abi["returnClassBindings"]
    if not isinstance(return_bindings, list) or len(return_bindings) != 2:
        fail("returnClassBindings must classify exactly the two top-level ret sites")
    return_class_by_site: dict[str, Any] = {}
    for index, row in enumerate(return_bindings):
        row = require_fields(
            row, RETURN_CLASS_BINDING_FIELDS, f"returnClassBindings[{index}]"
        )
        site = row["returnSiteAlias"]
        if row["entryId"] != entry_id or not isinstance(site, str) or not site:
            fail("returnClassBindings row has a foreign entry or invalid site alias")
        if site in return_class_by_site:
            fail("returnClassBindings contains a duplicate return site")
        if class_key(row["returnClass"]) not in allowed_keys:
            fail("returnClassBindings contains an out-of-class return binding")
        return_class_by_site[site] = row["returnClass"]
        identifier = declared_failure_id(row["returnClass"])
        if identifier is not None and identifier not in error_fields:
            fail(
                f"returnClassBindings has dangling DeclaredFailure ErrorFieldId {identifier!r}"
            )
    if return_class_by_site != {
        "declared_failure.ret": declared_class,
        "ordinary.ret": normal_class,
    }:
        fail("returnClassBindings must bind the failure and ordinary ret sites exactly once")

    for identifier in sorted(declared_ids):
        binding = error_fields[identifier]
        payload_type = binding["payloadType"]
        source = binding["source"]
        if not isinstance(payload_type, dict) or payload_type.get("tag") != "BVValueV2":
            fail(f"errorFields[{identifier!r}] application payload must be BVValueV2")
        if not isinstance(source, dict) or source.get("tag") != "ReturnBitsAtFailureV2":
            fail(
                f"errorFields[{identifier!r}] must use ReturnBitsAtFailureV2 "
                "(target: Unknown(OutputBindingIncomplete))"
            )
        require_fields(
            source,
            RETURN_BITS_FAILURE_SOURCE_FIELDS,
            f"errorFields[{identifier!r}].source",
        )
        expected_class = {"tag": "DeclaredFailure", "args": [identifier]}
        if source.get("entryId") != entry_id or source.get("returnClass") != expected_class:
            fail(f"errorFields[{identifier!r}] source does not bind the same entry/failure class")
        if source.get("bitOffset") != 0:
            fail(f"errorFields[{identifier!r}] source must start at return bit zero")
        if source.get("bitWidth") != payload_type.get("bitWidth"):
            fail(f"errorFields[{identifier!r}] source width disagrees with payload type")
        nested_encoding = source.get("encoding")
        if nested_encoding != binding["encoding"]:
            fail(
                f"errorFields[{identifier!r}].source.encoding must equal its outer encoding "
                "(target: Unknown(OutputBindingIncomplete))"
            )
        if binding["encoding"] != ENCODING_I8:
            fail(f"errorFields[{identifier!r}] must use the unique canonical BV8 encoding")

    host_basis = validate_visibility_basis(
        policy.get("hostVisibility"), "policyIntent.hostVisibility", principals, hosts
    )
    validate_visibility_basis(
        policy.get("componentVisibility"),
        "policyIntent.componentVisibility",
        principals,
        set(components),
    )
    validate_visibility_basis(
        policy.get("outputVisibility"),
        "policyIntent.outputVisibility",
        principals,
        set(outputs),
    )
    error_basis = validate_visibility_basis(
        policy.get("errorVisibility"),
        "policyIntent.errorVisibility",
        principals,
        set(error_fields),
    )

    coalitions = coalition_closure(
        policy.get("maximalAdversaryCoalitions"), principals
    )
    observation_host = entry.get("returnObservationHost")
    if observation_host not in hosts:
        fail("returnObservationHost must name a declared policy host")
    projection = []
    for coalition in coalitions:
        location_visible = visible(host_basis, observation_host, coalition)
        for identifier in sorted(error_fields):
            projection.append(
                {
                    "coalition": coalition,
                    "errorFieldId": identifier,
                    "payloadVisible": location_visible
                    or visible(error_basis, identifier, coalition),
                }
            )
    if expected.get("payloadProjection") != projection:
        fail(
            "expectedSemantics.payloadProjection is not the independently derived "
            "LocVisible OR ErrorVisible projection"
        )
    if expected.get("errorStructuralFields") != [
        "tag",
        "site",
        "occurrence",
        "errorFieldId",
        "class",
    ]:
        fail("Error structural fields must remain present even when payload is concealed")

    schedules = abi["terminalOutputOrder"]
    if not isinstance(schedules, list):
        fail("terminalOutputOrder must be an array of map rows")
    schedule_by_class: dict[str, list[str]] = {}
    for index, row in enumerate(schedules):
        row = require_fields(
            row, TERMINAL_OUTPUT_ORDER_FIELDS, f"terminalOutputOrder[{index}]"
        )
        if row["entryId"] != entry_id:
            fail("terminalOutputOrder contains a foreign entry")
        return_class_key = class_key(row["returnClass"])
        if return_class_key not in allowed_keys:
            fail("terminalOutputOrder contains an out-of-class return schedule")
        if return_class_key in schedule_by_class:
            fail("terminalOutputOrder contains a duplicate return-class row")
        output_ids = require_sorted_unique_strings(
            row["outputIds"], f"terminalOutputOrder[{index}].outputIds"
        )
        unknown_outputs = sorted(set(output_ids) - set(outputs))
        if unknown_outputs:
            fail(
                "terminalOutputOrder references undeclared OutputId "
                f"{unknown_outputs[0]!r}"
            )
        schedule_by_class[return_class_key] = output_ids
    if set(schedule_by_class) != allowed_keys:
        fail("terminalOutputOrder domain must equal the allowed return-class domain")
    if any(output_ids != ["return.byte"] for output_ids in schedule_by_class.values()):
        fail("both return classes must emit the exact return.byte terminal schedule")
    if abi["contractEventOutputOrder"] != []:
        fail("this entry-only fixture must have an empty contractEventOutputOrder")
    declared_outputs = schedule_by_class[class_key(declared_class)]
    expected_declared_order = [
        {"tag": "Failure", "class": "DeclaredFailure"},
        {
            "tag": "Error",
            "errorFieldId": declared_id,
            "class": "DeclaredFailure",
        },
        {"tag": "Latency"},
        *({"tag": "Output", "outputId": output_id} for output_id in declared_outputs),
        {"tag": "Termination", "returnClass": declared_class},
    ]
    if expected.get("declaredFailureEventOrder") != expected_declared_order:
        fail(
            "declaredFailureEventOrder is not Failure -> Error -> Latency -> "
            "terminal outputs -> Termination (target: Unknown(OutputClosureMismatch))"
        )
    expected_ub_order = [
        {"tag": "UBRisk", "reasonClass": UB_REASON_CLASS},
        {
            "tag": "Failure",
            "class": "UBRisk",
            "reasonClass": UB_REASON_CLASS,
        },
        {
            "tag": "Error",
            "errorFieldId": ub_id,
            "class": "UBRisk",
            "payload": {"kind": 1, "reasonClass": UB_REASON_CLASS},
        },
        {
            "tag": "Termination",
            "returnClass": {"tag": "UBFailure", "args": [UB_REASON_CLASS]},
        },
    ]
    if expected.get("ubRiskEventOrder") != expected_ub_order:
        fail(
            "ubRiskEventOrder is not UBRisk -> Failure -> Error -> "
            "Termination(UBFailure), with no latency/output suffix"
        )

    expected_counterexample = {
        "tag": "Counterexample",
        "args": [{"tag": "FreshProtectedReceiptMatcherV2"}],
    }
    if expected.get("expectedModelStatus") != expected_counterexample:
        fail(
            "the observer-visible application error payload must expect a fresh-receipt "
            "Counterexample; this fixture cannot claim Proved"
        )
    if expected.get("expectedDeploymentStatus") != {
        "tag": "Open",
        "args": [{"tag": "P4EvidenceProfileUnavailable"}],
    }:
        fail("future error fixture must keep the base-profile deployment status Open")
    if expected.get("expectedPolicyReviewStatus") != {"tag": "Complete"}:
        fail("the release-free future fixture must expect policy review Complete")

    negatives = expected.get("negativeCases")
    if negatives != NEGATIVE_CASES:
        fail(
            "expectedSemantics.negativeCases must exactly match the ordered mutation/outcome set"
        )

    print(
        f"validated {contract['caseId']}: future ConformanceV2 error contract "
        f"({len(error_fields)} error fields)"
    )
    print(
        "checked contract: DeclaredFailure and verifier-UB bindings, payload visibility, "
        "exact constructor/output order"
    )
    print("claim boundary: CandidateOnly Pending; ModelStatus=NotComputed")
    return contract


def validate_materialized(
    root: Path,
    contract: dict[str, Any],
    bundle: Path,
    report_path: Path | None,
) -> None:
    missing = [
        name
        for name in contract["requiredMaterializedFiles"]
        if not (bundle / name).is_file()
    ]
    if missing:
        fail(f"materialized bundle is missing required ConformanceV2 file: {missing[0]}")
    report_path = report_path or bundle / "sps-report.sps.json"
    sys.path.insert(0, str(root / "tools"))
    import check_sps_v2_bundle
    import sps_interfaces

    try:
        check_sps_v2_bundle.check_bundle(bundle, report_path)
        run = sps_interfaces.require_canonical(report_path.read_bytes())
        registry = sps_interfaces.load_default_registry()
        registry.validate_root(run, "SPSRunReportV2")
    except (OSError, check_sps_v2_bundle.BoundaryError, sps_interfaces.InterfaceError) as error:
        fail(f"invalid Rev4.1 V2 materialized bundle/report: {error}")
    if not isinstance(run, dict) or run.get("tag") != "CompletedV2":
        actual = run.get("tag") if isinstance(run, dict) else type(run).__name__
        fail(f"future positive error fixture expected CompletedV2, got {actual!r}")
    expected = contract["expectedSemantics"]
    report = run["report"]
    expected_matcher = expected["expectedModelStatus"]
    if expected_matcher != {
        "tag": "Counterexample",
        "args": [{"tag": "FreshProtectedReceiptMatcherV2"}],
    }:
        fail("future error contract has a non-V2 model-status matcher")
    status = report.get("modelStatus")
    receipt = status.get("args", [None])[0] if isinstance(status, dict) else None
    if (
        not isinstance(status, dict)
        or status.get("tag") != "Counterexample"
        or not isinstance(status.get("args"), list)
        or len(status["args"]) != 1
        or not isinstance(receipt, str)
        or len(receipt) != 64
        or any(character not in "0123456789abcdef" for character in receipt)
    ):
        fail("materialized error fixture must report Counterexample(receiptId)")
    if report.get("deploymentStatus") != expected["expectedDeploymentStatus"]:
        fail("materialized error fixture DeploymentStatus disagrees with the future contract")
    if report.get("policyReviewStatus") != expected["expectedPolicyReviewStatus"]:
        fail("materialized error fixture PolicyReviewStatus disagrees with the future contract")
    print(f"checked exact-verifier report/status for configured future bundle: {bundle}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--materialized-bundle", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    contract_path = args.contract or (
        args.root
        / "integration"
        / "Inputs"
        / "sps-error-events"
        / "future-conformance-contract.json"
    )
    contract = validate_contract(args.root.resolve(), contract_path.resolve())
    if args.materialized_bundle is not None:
        validate_materialized(
            args.root.resolve(),
            contract,
            args.materialized_bundle.resolve(),
            args.report.resolve() if args.report else None,
        )
    elif args.report is not None:
        fail("--report requires --materialized-bundle")


if __name__ == "__main__":
    main()
