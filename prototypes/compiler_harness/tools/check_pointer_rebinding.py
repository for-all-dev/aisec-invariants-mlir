#!/usr/bin/env python3
"""Cross-layer consistency checks for the pointer-rebinding fixture family.

This is deliberately a fixture validator, not a symbolic executor.  It derives
the expected projection result from the authoring policy and ABI, checks that
the snapshot and CandidateOnly matcher describe that result, and pins the
unsupported pointer-spill boundary without constructing an SMT query.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import checkpoint_extractors
import checkpoint_model
import counterexample_pair


ROOT = Path(__file__).resolve().parent.parent
FAMILY = Path("fixtures/pointer-rebinding")
ROOT_IDS = ("left", "private-result", "right")
SELECTED_ROOTS = ("left", "right")
OBSERVER = frozenset({"observer"})


class PointerRebindingError(ValueError):
    """A pointer-rebinding acceptance fixture is internally inconsistent."""


@dataclass(frozen=True)
class CaseSpec:
    directory: str
    entry: str
    mlir: str
    pointer_spill: bool
    selected_relation: str


CASES = (
    CaseSpec(
        "disjoint-select-bad",
        "pointer_rebinding_disjoint_select_bad",
        "pointer_rebinding_disjoint_select.bad.mlir",
        False,
        "Disjoint",
    ),
    CaseSpec(
        "same-allocation-control",
        "pointer_rebinding_same_allocation_control",
        "pointer_rebinding_same_allocation.control.mlir",
        False,
        "SameAllocation",
    ),
    CaseSpec(
        "pointer-spill-unsupported",
        "pointer_rebinding_pointer_spill_unsupported",
        "pointer_rebinding_pointer_spill.unknown.mlir",
        True,
        "Disjoint",
    ),
)


@dataclass(frozen=True)
class Topology:
    pairwise: Mapping[tuple[str, str], str]
    allocation_class: Mapping[str, int]

    def relation(self, left: str, right: str) -> str:
        return self.pairwise[tuple(sorted((left, right)))]


def _fail(where: str | Path, message: str) -> PointerRebindingError:
    return PointerRebindingError(f"{where}: {message}")


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail(where, "expected mapping")
    return value


def _sequence(value: Any, where: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise _fail(where, "expected list")
    return value


def _equal(actual: Any, expected: Any, where: str) -> None:
    if actual != expected:
        raise _fail(where, f"expected {expected!r}, got {actual!r}")


def _yaml(path: Path) -> dict[str, Any]:
    try:
        return checkpoint_model.strict_yaml_load(path.read_bytes(), source=str(path))
    except (OSError, checkpoint_model.CheckpointError) as error:
        raise _fail(path, str(error)) from error


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(), object_pairs_hook=_unique_json_object)
    except (OSError, UnicodeError, json.JSONDecodeError, PointerRebindingError) as error:
        raise _fail(path, f"invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise _fail(path, "top-level JSON value must be an object")
    return value


def _unique_json_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise PointerRebindingError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _visible(value: Any, coalition: frozenset[str], where: str) -> bool:
    if value == "public":
        return True
    if value == "secret":
        return False
    visibility = _mapping(value, where)
    if set(visibility) != {"world", "members", "joint"}:
        raise _fail(where, "visibility must have exactly world, members, and joint")
    if not isinstance(visibility["world"], bool):
        raise _fail(f"{where}.world", "expected boolean")
    members = _sequence(visibility["members"], f"{where}.members")
    joint = _sequence(visibility["joint"], f"{where}.joint")
    if any(not isinstance(item, str) for item in members):
        raise _fail(f"{where}.members", "expected principal identifiers")
    groups: list[set[str]] = []
    for index, raw_group in enumerate(joint):
        group = _sequence(raw_group, f"{where}.joint[{index}]")
        if any(not isinstance(item, str) for item in group):
            raise _fail(f"{where}.joint[{index}]", "expected principal identifiers")
        groups.append(set(group))
    return bool(
        visibility["world"]
        or coalition.intersection(members)
        or any(group <= coalition for group in groups)
    )


def _authoring_topology(abi: Mapping[str, Any], where: str) -> Topology:
    roots = _mapping(abi.get("roots"), f"{where}.roots")
    _equal(sorted(roots), list(ROOT_IDS), f"{where}.roots")
    aliases = _mapping(abi.get("aliases"), f"{where}.aliases")
    _equal(aliases.get("complete"), True, f"{where}.aliases.complete")
    rows = _sequence(aliases.get("relations"), f"{where}.aliases.relations")
    pairwise: dict[tuple[str, str], str] = {}
    for index, raw_row in enumerate(rows):
        row_where = f"{where}.aliases.relations[{index}]"
        row = _mapping(raw_row, row_where)
        if set(row) != {"relation", "roots"}:
            raise _fail(row_where, "expected exactly relation and roots")
        raw_roots = _sequence(row["roots"], f"{row_where}.roots")
        if len(raw_roots) != 2 or any(root not in roots for root in raw_roots):
            raise _fail(f"{row_where}.roots", "must name two declared roots")
        if raw_roots[0] == raw_roots[1]:
            raise _fail(f"{row_where}.roots", "self-relations are forbidden")
        relation = {"same-allocation": "SameAllocation", "disjoint": "Disjoint"}.get(
            row["relation"]
        )
        if relation is None:
            raise _fail(f"{row_where}.relation", "expected same-allocation or disjoint")
        pair = tuple(sorted((raw_roots[0], raw_roots[1])))
        if pair in pairwise:
            raise _fail(row_where, f"duplicate relation for root pair {pair}")
        pairwise[pair] = relation

    expected_pairs = {
        (left, right)
        for index, left in enumerate(ROOT_IDS)
        for right in ROOT_IDS[index + 1 :]
    }
    if set(pairwise) != expected_pairs:
        raise _fail(
            f"{where}.aliases.relations",
            "complete topology must cover every root pair exactly once; "
            f"missing={sorted(expected_pairs - set(pairwise))}, "
            f"extra={sorted(set(pairwise) - expected_pairs)}",
        )

    parent = {root: root for root in roots}

    def find(root: str) -> str:
        while parent[root] != root:
            parent[root] = parent[parent[root]]
            root = parent[root]
        return root

    def union(left: str, right: str) -> None:
        left_parent, right_parent = find(left), find(right)
        if left_parent != right_parent:
            parent[max(left_parent, right_parent)] = min(left_parent, right_parent)

    for (left, right), relation in pairwise.items():
        if relation == "SameAllocation":
            union(left, right)
    for (left, right), relation in pairwise.items():
        derived = "SameAllocation" if find(left) == find(right) else "Disjoint"
        if relation != derived:
            raise _fail(
                f"{where}.aliases.relations",
                f"inconsistent equivalence partition for {left!r} and {right!r}",
            )

    classes: dict[str, list[str]] = {}
    for root in sorted(roots):
        classes.setdefault(find(root), []).append(root)
    sorted_classes = sorted(tuple(members) for members in classes.values())
    ordinal = {
        root: index
        for index, members in enumerate(sorted_classes)
        for root in members
    }

    metadata_fields = (
        "extent-bytes",
        "host",
        "permission",
        "initialization",
        "address-space",
    )
    for members in sorted_classes:
        if len(members) < 2:
            continue
        baseline = roots[members[0]]
        for root_id in members[1:]:
            current = roots[root_id]
            for field in metadata_fields:
                default = 0 if field == "address-space" else None
                if baseline.get(field, default) != current.get(field, default):
                    raise _fail(
                        f"{where}.roots.{root_id}.{field}",
                        f"same-allocation roots {members!r} require identical {field}",
                    )
    return Topology(pairwise, ordinal)


def _candidate_topology(abi: Mapping[str, Any], where: str) -> Topology:
    arguments = _sequence(abi.get("arguments"), f"{where}.arguments")
    roots = {
        row.get("root_id")
        for row in arguments
        if isinstance(row, Mapping) and row.get("kind") == "root"
    }
    _equal(sorted(roots), list(ROOT_IDS), f"{where}.arguments root IDs")
    topology = _mapping(abi.get("alias_topology"), f"{where}.alias_topology")
    _equal(topology.get("complete"), True, f"{where}.alias_topology.complete")
    rows = _sequence(topology.get("relations"), f"{where}.alias_topology.relations")
    pairwise: dict[tuple[str, str], str] = {}
    for index, raw_row in enumerate(rows):
        row_where = f"{where}.alias_topology.relations[{index}]"
        row = _mapping(raw_row, row_where)
        if set(row) != {"left", "right", "relation"}:
            raise _fail(row_where, "expected exactly left, right, and relation")
        left, right, relation = row["left"], row["right"], row["relation"]
        if left not in roots or right not in roots or left == right:
            raise _fail(row_where, "must relate two distinct declared roots")
        if relation not in {"SameAllocation", "Disjoint"}:
            raise _fail(f"{row_where}.relation", "unknown candidate alias relation")
        pair = tuple(sorted((left, right)))
        if pair in pairwise:
            raise _fail(row_where, f"duplicate relation for root pair {pair}")
        pairwise[pair] = relation
    expected_pairs = {
        (left, right)
        for index, left in enumerate(ROOT_IDS)
        for right in ROOT_IDS[index + 1 :]
    }
    if set(pairwise) != expected_pairs:
        raise _fail(f"{where}.alias_topology", "must cover every root pair exactly once")

    # Candidate topology must itself be an equivalence partition.  Reuse the
    # already validated pair map to derive canonical class ordinals.
    parent = {root: root for root in roots}

    def find(root: str) -> str:
        while parent[root] != root:
            parent[root] = parent[parent[root]]
            root = parent[root]
        return root

    for (left, right), relation in pairwise.items():
        if relation == "SameAllocation":
            lp, rp = find(left), find(right)
            if lp != rp:
                parent[max(lp, rp)] = min(lp, rp)
    for (left, right), relation in pairwise.items():
        derived = "SameAllocation" if find(left) == find(right) else "Disjoint"
        if derived != relation:
            raise _fail(f"{where}.alias_topology", "relations do not form a partition")
    classes = sorted({tuple(sorted(root for root in roots if find(root) == find(seed))) for seed in roots})
    ordinal = {root: index for index, members in enumerate(classes) for root in members}
    return Topology(pairwise, ordinal)


def _validate_snapshot(
    root: Path, case: CaseSpec, raw: Mapping[str, Any], status: str, reason: str | None
) -> checkpoint_model.SnapshotV3:
    path = root / FAMILY / case.directory / "snapshot.yaml"
    _equal(raw.get("entry"), case.entry, f"{path}.entry")
    _equal(
        raw.get("secret"),
        [{"arg": 0, "name": "secret_selector"}],
        f"{path}.secret",
    )
    _equal(
        raw.get("public"),
        [
            {"memory_at_arg": 1, "name": "left"},
            {"memory_at_arg": 2, "name": "right"},
            {"observable": "address"},
        ],
        f"{path}.public",
    )
    final = _mapping(_mapping(raw.get("expect"), f"{path}.expect").get("final"), f"{path}.expect.final")
    model = _mapping(final.get("model"), f"{path}.expect.final.model")
    _equal(model.get("status"), status, f"{path}.expect.final.model.status")
    if status == "Counterexample":
        _equal(model.get("bad_state"), "address-trace-mismatch", f"{path}.expect.final.model.bad_state")
        expected_events = [{"kind": "Memory", "field": "allocationClass", "first_bad": True}]
    elif status == "Proved":
        expected_events = [{"kind": "Memory", "field": "allocationClass"}]
    else:
        _equal(model.get("reason"), reason, f"{path}.expect.final.model.reason")
        expected_events = []
    _equal(final.get("events", []), expected_events, f"{path}.expect.final.events")
    _equal(final.get("reference"), "candidate/expected-report.json", f"{path}.expect.final.reference")
    _equal(final.get("deployment"), "Open", f"{path}.expect.final.deployment")
    _equal(final.get("policy"), "Complete", f"{path}.expect.final.policy")

    pipelines = _mapping(_mapping(raw["expect"], f"{path}.expect").get("pipelines"), f"{path}.expect.pipelines")
    shape_ids = ("modeled-shape",) if case.pointer_spill else ("modeled-shape", "canonicalized-shape")
    for shape_id in shape_ids:
        properties = _mapping(
            _mapping(pipelines.get(shape_id), f"{path}.expect.pipelines.{shape_id}").get("properties"),
            f"{path}.expect.pipelines.{shape_id}.properties",
        )
        _equal(
            properties.get("branch.conditional"),
            {"count": {"eq": 0}},
            f"{path}.expect.pipelines.{shape_id}.properties.branch.conditional",
        )
        counts = {"llvm.select": 1, "llvm.load": 2 if case.pointer_spill else 1, "llvm.store": 2 if case.pointer_spill else 1}
        for operation, count in counts.items():
            _equal(
                properties.get(f"operation.occurrences.{operation}"),
                {"count": {"eq": count}},
                f"{path}.expect.pipelines.{shape_id}.properties.operation.occurrences.{operation}",
            )

    events = tuple(
        checkpoint_model.EventExpectation(
            event["kind"], event["field"], event.get("id"), event.get("first_bad", False)
        )
        for event in expected_events
    )
    final_value = checkpoint_model.FinalExpectation(
        status=status,
        deployment="Open",
        policy="Complete",
        because=str(final.get("because", "")),
        bad_state="address-trace-mismatch" if status == "Counterexample" else None,
        reason=reason,
        events=events,
        reference="candidate/expected-report.json",
    )
    return checkpoint_model.SnapshotV3(
        path=path.resolve(),
        root=root.resolve(),
        case=f"pointer-rebinding/{case.directory}",
        entry=case.entry,
        c_evidence=tuple(raw.get("c_evidence", [])),
        secret=tuple(raw.get("secret", [])),
        public=tuple(raw.get("public", [])),
        allowed=tuple(raw.get("allowed", [])),
        final=final_value,
        pipelines={},
        raw=raw,
    )


def _validate_policy(policy: Mapping[str, Any], abi: Mapping[str, Any], case: CaseSpec, where: str) -> tuple[bool, bool]:
    _equal(policy.get("entry"), case.entry, f"{where}.entry")
    _equal(policy.get("observation-model"), "constant-time", f"{where}.observation-model")
    _equal(policy.get("principals"), ["observer"], f"{where}.principals")
    _equal(_mapping(policy.get("adversaries"), f"{where}.adversaries").get("maximal"), [["observer"]], f"{where}.adversaries.maximal")
    components = _mapping(policy.get("components"), f"{where}.components")
    _equal(sorted(components), ["left-input", "right-input", "secret-selector"], f"{where}.components")
    for identifier, expected_type in (("left-input", "bytes"), ("right-input", "bytes"), ("secret-selector", "bv32")):
        component = _mapping(components[identifier], f"{where}.components.{identifier}")
        _equal(component.get("lifecycle"), "entry-input", f"{where}.components.{identifier}.lifecycle")
        _equal(component.get("type"), expected_type, f"{where}.components.{identifier}.type")
    left_visible = _visible(components["left-input"].get("visibility"), OBSERVER, f"{where}.components.left-input.visibility")
    right_visible = _visible(components["right-input"].get("visibility"), OBSERVER, f"{where}.components.right-input.visibility")
    selector_visible = _visible(components["secret-selector"].get("visibility"), OBSERVER, f"{where}.components.secret-selector.visibility")
    if not left_visible or not right_visible:
        raise _fail(where, "left-input and right-input must be Low for observer")
    if selector_visible:
        raise _fail(where, "secret-selector must remain High for observer")
    outputs = _mapping(policy.get("outputs"), f"{where}.outputs")
    result = _mapping(outputs.get("private-result"), f"{where}.outputs.private-result")
    if _visible(result.get("visibility"), OBSERVER, f"{where}.outputs.private-result.visibility"):
        raise _fail(where, "private-result must remain hidden from observer")
    entry = _mapping(abi.get("entry"), f"{where}.abi.entry")
    host_id = entry.get("host")
    hosts = _mapping(policy.get("hosts"), f"{where}.hosts")
    host = _mapping(hosts.get(host_id), f"{where}.hosts.{host_id}")
    host_visible = _visible(host.get("visibility"), OBSERVER, f"{where}.hosts.{host_id}.visibility")
    if not host_visible:
        raise _fail(where, f"allocation host {host_id!r} must be visible to observer in harness acceptance fixtures")
    return not selector_visible, host_visible


def _validate_abi_roles(abi: Mapping[str, Any], case: CaseSpec, where: str) -> None:
    entry = _mapping(abi.get("entry"), f"{where}.entry")
    _equal(entry.get("id"), case.entry, f"{where}.entry.id")
    _equal(entry.get("symbol"), case.entry, f"{where}.entry.symbol")
    _equal(entry.get("host"), "compute", f"{where}.entry.host")
    carriers = _mapping(abi.get("carriers"), f"{where}.carriers")
    _equal(sorted(carriers), ["secret-selector"], f"{where}.carriers")
    selector = _mapping(carriers["secret-selector"], f"{where}.carriers.secret-selector")
    _equal(selector.get("argument"), 0, f"{where}.carriers.secret-selector.argument")
    _equal(selector.get("bit-width"), 32, f"{where}.carriers.secret-selector.bit-width")
    roots = _mapping(abi.get("roots"), f"{where}.roots")
    expected = {
        "left": (1, "read-only", "initialized", "left-input", None),
        "right": (2, "read-only", "initialized", "right-input", None),
        "private-result": (3, "write-only", "uninitialized", None, "private-result"),
    }
    for root_id, (argument, permission, initialization, input_id, output_id) in expected.items():
        root = _mapping(roots[root_id], f"{where}.roots.{root_id}")
        _equal(root.get("argument"), argument, f"{where}.roots.{root_id}.argument")
        _equal(root.get("host"), "compute", f"{where}.roots.{root_id}.host")
        _equal(root.get("extent-bytes"), 1, f"{where}.roots.{root_id}.extent-bytes")
        _equal(root.get("permission"), permission, f"{where}.roots.{root_id}.permission")
        _equal(root.get("initialization"), initialization, f"{where}.roots.{root_id}.initialization")
        if input_id is not None:
            _equal(root.get("input"), input_id, f"{where}.roots.{root_id}.input")
        if output_id is not None:
            _equal(root.get("output"), output_id, f"{where}.roots.{root_id}.output")


def _validate_mlir(path: Path, case: CaseSpec) -> None:
    try:
        raw = path.read_bytes()
        facts = checkpoint_extractors.extract("mlir", "mlir-structure-v1", raw, {"function": case.entry})
    except (OSError, checkpoint_extractors.ExtractorError) as error:
        raise _fail(path, str(error)) from error
    expected_arguments = [
        f"{case.entry}|0|secret_selector",
        f"{case.entry}|1|left",
        f"{case.entry}|2|right",
        f"{case.entry}|3|private_result",
    ]
    _equal(facts.get("function.argument_names"), expected_arguments, f"{path}: function arguments")
    if facts.get("branch.conditional"):
        raise _fail(path, "a conditional branch occurs before the decisive scalar load")
    expected_operations = (
        ["llvm.mlir.constant", "llvm.mlir.constant", "llvm.icmp", "llvm.select", "llvm.alloca", "llvm.store", "llvm.load", "llvm.load", "llvm.store", "llvm.return"]
        if case.pointer_spill
        else ["llvm.mlir.constant", "llvm.icmp", "llvm.select", "llvm.load", "llvm.store", "llvm.return"]
    )
    _equal(facts.get("operation.names"), expected_operations, f"{path}: operation order")
    dependencies = set(facts.get("operation.argument_dependencies", []))
    required_dependencies = {
        f"{case.entry}|llvm.select|operand=0|args=0",
        f"{case.entry}|llvm.select|operand=1|args=2",
        f"{case.entry}|llvm.select|operand=2|args=1",
    }
    if not required_dependencies <= dependencies:
        raise _fail(path, f"pointer select dependencies are incomplete: missing={sorted(required_dependencies - dependencies)}")
    if case.pointer_spill:
        _equal(facts.get("memory.alloca_counts"), [f"{case.entry}|count=1|element=!llvm.ptr"], f"{path}: pointer spill alloca")
        _equal(
            facts.get("memory.store_accesses"),
            [
                f"{case.entry}|value=op:llvm.select:3|address=alloca(count=1;element=!llvm.ptr)",
                f"{case.entry}|value=op:llvm.load:7|address=arg:3",
            ],
            f"{path}: pointer spill stores",
        )
        _equal(
            facts.get("memory.load_accesses"),
            [
                f"{case.entry}|address=alloca(count=1;element=!llvm.ptr)",
                f"{case.entry}|address=op:llvm.load:6",
            ],
            f"{path}: pointer spill loads",
        )
        text = raw.decode("utf-8")
        if not re.search(r"llvm\.store\s+%selected,\s*%slot\s*:\s*!llvm\.ptr,\s*!llvm\.ptr", text):
            raise _fail(path, "pointer-valued store did not survive in the modeled artifact")
        if not re.search(r"%reloaded\s*=\s*llvm\.load\s+%slot\s*:\s*!llvm\.ptr\s*->\s*!llvm\.ptr", text):
            raise _fail(path, "pointer-valued load did not survive in the modeled artifact")
    else:
        _equal(facts.get("memory.alloca_counts"), [], f"{path}: unexpected alloca")
        _equal(facts.get("memory.load_accesses"), [f"{case.entry}|address=op:llvm.select:2"], f"{path}: selected scalar load")
        _equal(facts.get("memory.store_accesses"), [f"{case.entry}|value=op:llvm.load:3|address=arg:3"], f"{path}: scalar result store")


def _llvm_function(text: str, entry: str, where: Path) -> str:
    match = re.search(rf"^define\b[^\n@]*@{re.escape(entry)}\([^\n]*\)[^\n]*\{{\n(?P<body>.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    if match is None:
        raise _fail(where, f"missing LLVM definition for {entry}")
    return match.group("body")


def _validate_llvm_artifact(path: Path, case: CaseSpec) -> None:
    try:
        text = path.read_text()
    except (OSError, UnicodeError) as error:
        raise _fail(path, f"cannot read candidate LLVM artifact: {error}") from error
    body = _llvm_function(text, case.entry, path)
    if re.search(r"^\s*br\s+i1\b", body, re.MULTILINE):
        raise _fail(path, "conditional branch masks or precedes the selected-address event")
    select = re.search(r"=\s*select\s+i1\b[^\n]*\bptr\b[^\n]*\bptr\b", body)
    scalar_load = re.search(r"=\s*load\s+i8\b", body)
    scalar_store = re.search(r"^\s*store\s+i8\b", body, re.MULTILINE)
    if select is None or scalar_load is None or scalar_store is None:
        raise _fail(path, "candidate must retain pointer select, scalar load, and scalar store")
    pointer_store = re.search(r"^\s*store\s+ptr\b", body, re.MULTILINE)
    pointer_load = re.search(r"=\s*load\s+ptr\b", body)
    if case.pointer_spill:
        if pointer_store is None:
            raise _fail(path, "pointer-valued store did not survive in candidate artifact")
        if pointer_load is None:
            raise _fail(path, "pointer-valued load did not survive in candidate artifact")
        positions = (select.start(), pointer_store.start(), pointer_load.start(), scalar_load.start(), scalar_store.start())
    else:
        if pointer_store is not None or pointer_load is not None:
            raise _fail(path, "supported case unexpectedly contains pointer-valued memory access")
        positions = (select.start(), scalar_load.start(), scalar_store.start())
    if tuple(sorted(positions)) != positions:
        raise _fail(path, "pointer selection and memory operations are not in the required order")


def _expected_audit_rows(status: str) -> list[dict[str, Any]]:
    coalitions = ([], ["observer"])
    rows: list[dict[str, Any]] = []
    for coalition in coalitions:
        if status == "Unknown":
            rows.append(
                {
                    "coalition": coalition,
                    "query_outcome": {"tag": "NotConstructedResultMatcherV2", "reason": {"reasonClassId": "UnsupportedType"}},
                    "replay_expectation": {"tag": "NotAvailableV2", "reason": {"reasonClassId": "UnsupportedType"}},
                }
            )
        elif status == "Counterexample" and coalition:
            rows.append(
                {
                    "coalition": coalition,
                    "query_outcome": {"tag": "ConstructedResultMatcherV2", "raw_solver_result": "SAT", "query_disposition": {"tag": "CandidateOnly"}},
                    "replay_expectation": {"tag": "AcceptedBadStateRequiredV2", "bad_state_class": "address-trace-mismatch"},
                }
            )
        else:
            rows.append(
                {
                    "coalition": coalition,
                    "query_outcome": {"tag": "ConstructedResultMatcherV2", "raw_solver_result": "UNSAT", "query_disposition": {"tag": "Discharged"}},
                    "replay_expectation": {"tag": "NotApplicableV2"},
                }
            )
    return rows


def _validate_candidate(spec: Mapping[str, Any], authoring: Topology, case: CaseSpec, status: str, where: str) -> None:
    _equal(spec.get("catalog_authority"), {"tag": "CandidatePreflightCatalogV2", "claimable": False}, f"{where}.catalog_authority")
    candidate_policy = _mapping(spec.get("policy"), f"{where}.policy")
    _equal(candidate_policy.get("principals"), ["observer"], f"{where}.policy.principals")
    _equal(candidate_policy.get("maximal_adversary_coalitions"), [["observer"]], f"{where}.policy.maximal_adversary_coalitions")
    component_visibility = _mapping(candidate_policy.get("component_visibility"), f"{where}.policy.component_visibility")
    _equal(component_visibility.get("world_visible"), ["left-input", "right-input"], f"{where}.policy.component_visibility.world_visible")
    _equal(component_visibility.get("member_visible"), {"observer": []}, f"{where}.policy.component_visibility.member_visible")
    output_visibility = _mapping(candidate_policy.get("output_visibility"), f"{where}.policy.output_visibility")
    _equal(output_visibility.get("world_visible"), [], f"{where}.policy.output_visibility.world_visible")
    _equal(output_visibility.get("member_visible"), {"observer": []}, f"{where}.policy.output_visibility.member_visible")
    roles = _sequence(candidate_policy.get("argument_roles"), f"{where}.policy.argument_roles")
    expected_roles = [
        (0, "ComponentArgumentV2", "secret-selector"),
        (1, "PointerRootArgumentV2", "left"),
        (2, "PointerRootArgumentV2", "right"),
        (3, "PointerRootArgumentV2", "private-result"),
    ]
    actual_roles = []
    for row in roles:
        role_row = _mapping(row, f"{where}.policy.argument_roles")
        role = _mapping(role_row.get("role"), f"{where}.policy.argument_roles.role")
        actual_roles.append((role_row.get("argument_index"), role.get("tag"), (role.get("args") or [None])[0]))
        _equal(role_row.get("entry"), case.entry, f"{where}.policy.argument_roles.entry")
    _equal(actual_roles, expected_roles, f"{where}.policy.argument_roles")

    candidate_abi = _mapping(spec.get("abi"), f"{where}.abi")
    _equal(candidate_abi.get("entry"), case.entry, f"{where}.abi.entry")
    candidate_topology = _candidate_topology(candidate_abi, f"{where}.abi")
    _equal(candidate_topology.pairwise, authoring.pairwise, f"{where}.abi.alias_topology cross-layer binding")

    report = _mapping(spec.get("expected_report"), f"{where}.expected_report")
    _equal(report.get("fixture_tier"), {"tag": "CandidateOnly"}, f"{where}.expected_report.fixture_tier")
    _equal(report.get("claimable_from_checked_in_pair"), False, f"{where}.expected_report.claimable_from_checked_in_pair")
    _equal(report.get("current_harness_status"), {"tag": "PendingV2", "reasons": ["sps-verifier-not-implemented", "llvm-22.1.8-nf-recapture-required"]}, f"{where}.expected_report.current_harness_status")
    expected = _mapping(report.get("expected"), f"{where}.expected_report.expected")
    _equal(expected.get("entry"), case.entry, f"{where}.expected_report.expected.entry")
    _equal(expected.get("audit_all_expectations"), _expected_audit_rows(status), f"{where}.expected_report.expected.audit_all_expectations")
    _equal(expected.get("expected_deployment_status"), {"tag": "Open", "args": [{"tag": "P4EvidenceProfileUnavailable"}]}, f"{where}.expected_report.expected.expected_deployment_status")
    _equal(expected.get("expected_policy_review_status"), {"tag": "Complete"}, f"{where}.expected_report.expected.expected_policy_review_status")
    model = (
        {"tag": "Counterexample", "receipt_matcher": {"tag": "FreshProtectedReceiptMatcherV2"}}
        if status == "Counterexample"
        else {"tag": "Proved"}
        if status == "Proved"
        else {"tag": "Unknown", "args": [{"reasonClassId": "UnsupportedType"}]}
    )
    _equal(expected.get("expected_model_status"), model, f"{where}.expected_report.expected.expected_model_status")


def _validate_pair(snapshot: checkpoint_model.SnapshotV3, status: str) -> None:
    try:
        pair = counterexample_pair.load_fixture_pair(snapshot)
    except counterexample_pair.CounterexamplePairError as error:
        raise _fail(snapshot.path, str(error)) from error
    if status != "Counterexample":
        _equal(pair, None, f"{snapshot.path}: counterexample pair")
        return
    if pair is None:
        raise AssertionError("load_fixture_pair must return the required pair")
    _equal(pair.coalition, ("observer",), f"{pair.path}.coalition")
    _equal(sorted(pair.inputs.low_equal), ["left-input", "right-input"], f"{pair.path}.inputs.low_equal")
    left = pair.inputs.low_equal["left-input"]
    right = pair.inputs.low_equal["right-input"]
    if not isinstance(left, counterexample_pair.BytesValue) or not isinstance(right, counterexample_pair.BytesValue):
        raise _fail(pair.path, "isolation roots must be concrete byte strings")
    if left != right:
        raise _fail(pair.path, "equal-byte isolation requires identical left and right bytes")
    selector_left = pair.inputs.high_left.get("secret-selector")
    selector_right = pair.inputs.high_right.get("secret-selector")
    expected_left = counterexample_pair.BitVectorValue(32, "00000000")
    expected_right = counterexample_pair.BitVectorValue(32, "00000001")
    _equal(selector_left, expected_left, f"{pair.path}.inputs.high_left.secret-selector")
    _equal(selector_right, expected_right, f"{pair.path}.inputs.high_right.secret-selector")


def validate(root: Path) -> None:
    root = Path(root).resolve()
    family = root / FAMILY
    actual_cases = sorted(path.name for path in family.iterdir() if path.is_dir()) if family.is_dir() else []
    _equal(actual_cases, sorted(case.directory for case in CASES), family)

    for case in CASES:
        directory = family / case.directory
        snapshot_raw = _yaml(directory / "snapshot.yaml")
        policy = _yaml(directory / "policy.sps.yaml")
        abi = _yaml(directory / "abi.sps.yaml")
        _validate_abi_roles(abi, case, str(directory / "abi.sps.yaml"))
        topology = _authoring_topology(abi, str(directory / "abi.sps.yaml"))
        _equal(topology.relation(*SELECTED_ROOTS), case.selected_relation, f"{directory / 'abi.sps.yaml'}: selected-root relation")
        if topology.allocation_class["private-result"] in {topology.allocation_class[root] for root in SELECTED_ROOTS}:
            raise _fail(directory / "abi.sps.yaml", "private-result must be disjoint from both selected roots")
        selector_high, location_visible = _validate_policy(policy, abi, case, str(directory / "policy.sps.yaml"))

        _validate_mlir(directory / case.mlir, case)
        _validate_llvm_artifact(directory / "candidate" / "artifact.ll", case)

        if case.pointer_spill:
            status, reason = "Unknown", "UnsupportedType"
        else:
            mismatch = selector_high and location_visible and topology.relation(*SELECTED_ROOTS) == "Disjoint"
            status, reason = ("Counterexample" if mismatch else "Proved"), None

        snapshot = _validate_snapshot(root, case, snapshot_raw, status, reason)
        _validate_pair(snapshot, status)
        spec_path = directory / "candidate" / "bundle-spec.json"
        _validate_candidate(_json(spec_path), topology, case, status, str(spec_path))

    print("pointer-rebinding consistency checks passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        validate(args.root)
    except (PointerRebindingError, KeyError, IndexError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
