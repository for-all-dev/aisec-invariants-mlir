#!/usr/bin/env python3
"""Validate and run the eight case-local relation-reference checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


TEST = "integration/relation-reference-fixtures.test"
PIPELINE = "relation-reference"
EXPECTED_CASES = 8
FILE_ROLES = ("abi", "c", "mlir", "policy", "referenceFixture", "snapshot")


class BindingError(ValueError):
    """A reduced relation fixture is inconsistent with its harness case."""


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BindingError(f"{where}: expected an object")
    return value


def _list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise BindingError(f"{where}: expected a list")
    return value


def _expect(actual: Any, expected: Any, where: str) -> None:
    if actual != expected:
        raise BindingError(f"{where}: expected {expected!r}, got {actual!r}")


def _security_class(visibility: Any, where: str) -> str:
    if visibility == "secret":
        return "High"
    if visibility == "public":
        return "Low"
    raise BindingError(f"{where}: expected secret or public visibility")


def _logical_name(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise BindingError(f"{where}: expected a nonempty name")
    return value.replace("_", "-")


def _load_yaml(path: Path, checkpoint_model: Any) -> Mapping[str, Any]:
    try:
        return _mapping(
            checkpoint_model.strict_yaml_load(path.read_bytes(), source=str(path)),
            str(path),
        )
    except OSError as error:
        raise BindingError(f"cannot read {path}: {error}") from error


def _reference_api(root: Path) -> tuple[Any, Any]:
    reference = (
        root
        / "contracts"
        / "vendor"
        / "sps-reference-rev4"
        / "reference"
    )
    sys.path.insert(0, str(reference))
    try:
        from sps_ref import canonical, evidence
    except ImportError as error:
        raise BindingError(f"vendored relation-reference API is unavailable: {error}") from error
    for module in (canonical, evidence):
        try:
            Path(module.__file__).resolve().relative_to(reference.resolve())
        except ValueError as error:
            raise BindingError(
                f"relation-reference module escaped the vendor: {module.__file__}"
            ) from error
    return canonical, evidence


def _file_bindings(
    case: Path, binding: Mapping[str, Any]
) -> dict[str, Path]:
    rows = _list(binding.get("files"), "binding.files")
    roles = [row.get("role") for row in rows if isinstance(row, Mapping)]
    _expect(roles, list(FILE_ROLES), "binding file-role order")
    result: dict[str, Path] = {}
    for index, raw_row in enumerate(rows):
        row = _mapping(raw_row, f"binding.files[{index}]")
        if set(row) != {"role", "path", "sha256"}:
            raise BindingError(f"binding.files[{index}]: wrong fields")
        role = row["role"]
        relative = row["path"]
        digest = row["sha256"]
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise BindingError(f"binding file {role}: path must be case-relative")
        path = (case / relative).resolve()
        try:
            path.relative_to(case.resolve())
        except ValueError as error:
            raise BindingError(f"binding file {role}: path escapes the case") from error
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise BindingError(f"binding file {role}: cannot read {relative}: {error}") from error
        if actual != digest:
            raise BindingError(f"binding file {role}: SHA-256 mismatch")
        result[str(role)] = path
    return result


def _abi_signature(function_type: Any, symbol: str) -> str:
    if not isinstance(function_type, str):
        raise BindingError("ABI entry.function-type must be a string")
    match = re.fullmatch(r"\s*(.*?)\s*\((.*?)\)\s*", function_type)
    if not match:
        raise BindingError("ABI entry.function-type is malformed")

    def lower(value: str) -> str:
        value = re.sub(r"\s+", " ", value.strip())
        return "!llvm.ptr" if value == "ptr" else value

    arguments = [] if not match.group(2).strip() else [
        lower(item) for item in match.group(2).split(",")
    ]
    result = "()" if lower(match.group(1)) == "void" else lower(match.group(1))
    return f"{symbol}|({','.join(arguments)})->{result}"


def _snapshot_argument_rows(snapshot: Any) -> tuple[dict[int, str], dict[int, str]]:
    secret: dict[int, str] = {}
    public: dict[int, str] = {}
    for destination, rows, field in (
        (secret, snapshot.secret, "arg"),
        (public, snapshot.public, "arg"),
    ):
        for row in rows:
            if field not in row:
                continue
            index = row[field]
            if not isinstance(index, int) or isinstance(index, bool) or index < 0:
                raise BindingError(f"snapshot {field} index is invalid")
            if index in destination:
                raise BindingError(f"snapshot repeats argument {index}")
            destination[index] = _logical_name(row.get("name"), "snapshot argument name")
    if set(secret) & set(public):
        raise BindingError("snapshot classifies one argument as both secret and public")
    return secret, public


def _statement_offsets(program: Mapping[str, Any]) -> dict[str, set[int]]:
    result = {
        str(root["id"]): set()
        for root in _list(_mapping(program["abi"], "program.abi")["roots"], "program roots")
    }

    def expression(value: Any) -> None:
        if isinstance(value, Mapping):
            if set(value) == {"load"}:
                load = _mapping(value["load"], "load expression")
                root = load.get("root")
                if root not in result:
                    raise BindingError(f"load references unknown root {root!r}")
                result[str(root)].add(load.get("offset"))
            for child in value.values():
                expression(child)
        elif isinstance(value, list):
            for child in value:
                expression(child)

    def statements(rows: Any) -> None:
        for raw in _list(rows, "program statements"):
            row = _mapping(raw, "program statement")
            if row.get("op") == "store":
                root = row.get("root")
                if root not in result:
                    raise BindingError(f"store references unknown root {root!r}")
                result[str(root)].add(row.get("offset"))
            for field in ("condition", "value", "guard", "iterations"):
                if field in row:
                    expression(row[field])
            for field in ("then", "else", "body"):
                if field in row:
                    statements(row[field])

    expression(program.get("admission"))
    statements(program.get("statements"))
    if any(
        not isinstance(offset, int) or isinstance(offset, bool) or offset < 0
        for offsets in result.values()
        for offset in offsets
    ):
        raise BindingError("reduced program contains an invalid root offset")
    return result


def _memory_operations(
    program: Mapping[str, Any],
) -> tuple[list[tuple[str, int, str]], list[tuple[str, int]]]:
    stores: list[tuple[str, int, str]] = []
    loads: list[tuple[str, int]] = []

    def expression(value: Any) -> None:
        if isinstance(value, Mapping):
            if set(value) == {"load"}:
                load = _mapping(value["load"], "load expression")
                loads.append((str(load.get("root")), load.get("offset")))
            for child in value.values():
                expression(child)
        elif isinstance(value, list):
            for child in value:
                expression(child)

    def statements(rows: Any) -> None:
        for raw in _list(rows, "program statements"):
            row = _mapping(raw, "program statement")
            if row.get("op") == "store":
                value = _mapping(row.get("value"), "store value")
                if set(value) != {"var"} or not isinstance(value["var"], str):
                    raise BindingError("reduced store value must map directly to an input")
                stores.append((str(row.get("root")), row.get("offset"), value["var"]))
            for field in ("condition", "value", "guard", "iterations"):
                if field in row:
                    expression(row[field])
            for field in ("then", "else", "body"):
                if field in row:
                    statements(row[field])

    statements(program.get("statements"))
    return stores, loads


def _validate_memory_mapping(
    entry: str,
    binding: Mapping[str, Any],
    abi: Mapping[str, Any],
    program: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> None:
    stores, loads = _memory_operations(program)
    root_rows = {
        row["referenceRoot"]: row
        for row in _list(binding.get("roots"), "binding roots")
        if isinstance(row, Mapping)
    }
    argument_rows = {
        row["referenceInput"]: row
        for row in _list(binding.get("arguments"), "binding arguments")
        if isinstance(row, Mapping)
    }
    carriers = _mapping(abi.get("carriers"), "ABI carriers")
    abi_roots = _mapping(abi.get("roots"), "ABI roots")

    def address(reference_root: str, offset: int) -> str:
        row = _mapping(root_rows.get(reference_root), f"binding root {reference_root!r}")
        if row.get("storageKind") == "InternalAlloca":
            allocas = _list(facts.get("memory.alloca_counts"), "MLIR alloca facts")
            if len(allocas) != 1 or not str(allocas[0]).startswith(f"{entry}|"):
                raise BindingError("internal reduction root requires exactly one MLIR alloca")
            shape = str(allocas[0]).split("|", 1)[1].replace("|", ";")
            base = f"alloca({shape})"
            if offset != 0:
                return f"gep(base={base};offsets={offset})"
            return base
        abi_root = _mapping(
            abi_roots.get(row.get("abiRoot")), f"ABI root {row.get('abiRoot')!r}"
        )
        base = f"arg:{abi_root.get('argument')}"
        return base if offset == 0 else f"gep(base={base};offsets={offset})"

    expected_stores: list[str] = []
    for root, offset, reference_input in stores:
        argument = _mapping(
            argument_rows.get(reference_input),
            f"binding argument {reference_input!r}",
        )
        carrier = _mapping(
            carriers.get(argument.get("component")),
            f"ABI carrier {argument.get('component')!r}",
        )
        expected_stores.append(
            f"{entry}|value=arg:{carrier.get('argument')}|address={address(root, offset)}"
        )
    expected_loads = [
        f"{entry}|address={address(root, offset)}" for root, offset in loads
    ]
    _expect(facts.get("memory.store_accesses"), expected_stores, "MLIR/reduction stores")
    _expect(facts.get("memory.load_accesses"), expected_loads, "MLIR/reduction loads")


def _validate_control_mapping(
    entry: str,
    binding: Mapping[str, Any],
    program: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> None:
    reduced: list[bool] = []
    reduced_dependencies: list[list[int]] = []
    arguments = {
        row["referenceInput"]: row
        for row in _list(binding.get("arguments"), "binding arguments")
        if isinstance(row, Mapping)
    }

    def variables(value: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(value, Mapping):
            if set(value) == {"var"} and isinstance(value["var"], str):
                found.add(value["var"])
            for child in value.values():
                found.update(variables(child))
        elif isinstance(value, list):
            for child in value:
                found.update(variables(child))
        return found

    def statements(rows: Any) -> None:
        for raw in _list(rows, "program statements"):
            row = _mapping(raw, "program statement")
            if row.get("op") == "if":
                reduced.append(row.get("thenSuccessor") == row.get("elseSuccessor"))
                condition_inputs = variables(row.get("condition"))
                try:
                    reduced_dependencies.append(
                        sorted(arguments[name]["argumentIndex"] for name in condition_inputs)
                    )
                except KeyError as error:
                    raise BindingError(
                        f"reference condition uses an unbound input {error.args[0]!r}"
                    ) from error
            for field in ("then", "else", "body"):
                if field in row:
                    statements(row[field])

    statements(program.get("statements"))
    shapes = _list(facts.get("branch.successor_shapes"), "MLIR branch facts")
    mlir = ["|same-target=true|" in f"|{row}|" for row in shapes]
    _expect(mlir, reduced, f"{entry} MLIR/reduction successor identity")
    dependency_prefix = f"{entry}|llvm.cond_br|operand=0|args="
    mlir_dependencies = [
        [int(value) for value in str(row)[len(dependency_prefix) :].split(",")]
        for row in _list(
            facts.get("operation.argument_dependencies"),
            "MLIR argument-dependency facts",
        )
        if str(row).startswith(dependency_prefix)
    ]
    _expect(
        mlir_dependencies,
        reduced_dependencies,
        f"{entry} MLIR/reduction branch dependencies",
    )


def _validate_return_expression(
    entry: str,
    binding: Mapping[str, Any],
    program: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> None:
    returns: list[Mapping[str, Any]] = []

    def statements(rows: Any) -> None:
        for raw in _list(rows, "program statements"):
            row = _mapping(raw, "program statement")
            if row.get("op") == "return":
                returns.append(row)
            for field in ("then", "else", "body"):
                if field in row:
                    statements(row[field])

    statements(program.get("statements"))
    if len(returns) != 1:
        raise BindingError("exact-eight reduction requires one return statement")
    expression = _mapping(returns[0].get("value"), "reference return value")
    arguments = {
        row["referenceInput"]: row
        for row in _list(binding.get("arguments"), "binding arguments")
        if isinstance(row, Mapping)
    }
    operation_names = _list(facts.get("operation.names"), "MLIR operations")
    return_roots = _list(facts.get("return.access_roots"), "MLIR return access roots")

    def argument_root(input_id: Any) -> str:
        row = _mapping(arguments.get(input_id), f"binding argument {input_id!r}")
        return f"arg:{row.get('argumentIndex')}"

    if set(expression) == {"var"}:
        expected_root = argument_root(expression["var"])
    elif set(expression) == {"xor"}:
        operands = _list(expression["xor"], "reference XOR operands")
        if len(operands) != 2:
            raise BindingError("exact-eight XOR reduction requires two operands")
        ordinals = [
            ordinal
            for ordinal, operation in enumerate(operation_names)
            if operation == "llvm.xor"
        ]
        if len(ordinals) != 1:
            raise BindingError("reference XOR requires exactly one MLIR llvm.xor")
        ordinal = ordinals[0]
        expected_root = f"op:llvm.xor:{ordinal}"
        prefix = f"{entry}|user={ordinal}|op=llvm.xor|operand="
        actual_operands: dict[int, str] = {}
        for raw in _list(facts.get("def_use.edges"), "MLIR def-use facts"):
            row = str(raw)
            if not row.startswith(prefix):
                continue
            match = re.fullmatch(re.escape(prefix) + r"([0-9]+)\|root=(.*)", row)
            if match:
                actual_operands[int(match.group(1))] = match.group(2)
        if set(actual_operands) != {0, 1}:
            raise BindingError("MLIR XOR does not expose exactly two operand roots")
        for index, raw_operand in enumerate(operands):
            operand = _mapping(raw_operand, f"reference XOR operand {index}")
            actual = actual_operands[index]
            if set(operand) == {"var"}:
                _expect(actual, argument_root(operand["var"]), "MLIR/reduction XOR operands")
            elif set(operand) == {"const"}:
                constant = _mapping(operand["const"], "reference XOR constant")
                match = re.fullmatch(r"constant:i[0-9]+:(-?[0-9]+)(?:\s*:.*)?", actual)
                if not match or int(match.group(1)) != constant.get("value"):
                    raise BindingError("MLIR/reduction XOR operands: constant differs")
            else:
                raise BindingError("exact-eight XOR operand is neither var nor const")
    elif set(expression) == {"extract"}:
        extract = _mapping(expression["extract"], "reference return extract")
        value = _mapping(extract.get("value"), "reference extracted value")
        if set(value) != {"load"}:
            raise BindingError("exact-eight extracted return must wrap one load")
        ordinals = [
            ordinal
            for ordinal, operation in enumerate(operation_names)
            if operation == "llvm.load"
        ]
        if len(ordinals) != 1:
            raise BindingError("reference loaded return requires exactly one MLIR llvm.load")
        expected_root = f"op:llvm.load:{ordinals[0]}"
    else:
        raise BindingError("unsupported exact-eight reference return expression")
    _expect(return_roots, [f"{entry}|{expected_root}"], "MLIR/reduction return value")


def _validate_arguments(
    snapshot: Any,
    binding: Mapping[str, Any],
    policy: Mapping[str, Any],
    abi: Mapping[str, Any],
    program: Mapping[str, Any],
    mlir_arguments: list[str],
) -> None:
    components = _mapping(policy.get("components"), "policy.components")
    carriers = _mapping(abi.get("carriers"), "ABI carriers")
    inputs = {
        row["id"]: row
        for row in _list(program.get("inputs"), "reference program inputs")
        if isinstance(row, Mapping)
    }
    rows = _list(binding.get("arguments"), "binding.arguments")
    by_component: dict[str, Mapping[str, Any]] = {}
    secret, public = _snapshot_argument_rows(snapshot)
    for index, raw_row in enumerate(rows):
        row = _mapping(raw_row, f"binding.arguments[{index}]")
        component = row.get("component")
        if not isinstance(component, str) or component in by_component:
            raise BindingError("binding arguments repeat or omit a component ID")
        by_component[component] = row
        carrier = _mapping(carriers.get(component), f"ABI carrier {component!r}")
        authored = _mapping(components.get(component), f"policy component {component!r}")
        reference = _mapping(
            inputs.get(row.get("referenceInput")),
            f"reference input {row.get('referenceInput')!r}",
        )
        argument_index = carrier.get("argument")
        if (
            not isinstance(argument_index, int)
            or isinstance(argument_index, bool)
            or argument_index < 0
            or argument_index >= len(mlir_arguments)
        ):
            raise BindingError(f"ABI carrier {component!r} has an invalid argument index")
        _expect(row.get("argumentIndex"), argument_index, "binding/ABI argument index")
        argument_name = row.get("argumentName")
        _expect(argument_name, mlir_arguments[argument_index], "binding/MLIR argument name")
        full_width = carrier.get("bit-width")
        reduced_width = reference.get("width")
        _expect(row.get("fullWidth"), full_width, "binding/ABI full width")
        _expect(row.get("reducedWidth"), reduced_width, "binding/reference width")
        if (
            not isinstance(full_width, int)
            or isinstance(full_width, bool)
            or not isinstance(reduced_width, int)
            or isinstance(reduced_width, bool)
            or not 1 <= reduced_width <= 2
            or reduced_width > full_width
        ):
            raise BindingError("exact-eight reduction widths must be 1 or 2 bits")
        classification = _security_class(
            authored.get("visibility"), f"policy component {component!r}"
        )
        _expect(row.get("classification"), classification, "binding/policy classification")
        _expect(reference.get("classification"), classification, "reference/policy classification")
        snapshot_rows = secret if classification == "High" else public
        _expect(
            snapshot_rows.get(argument_index),
            _logical_name(argument_name, "binding argument name"),
            "snapshot/binding argument",
        )
        if _logical_name(component, "component") != _logical_name(
            argument_name, "binding argument"
        ):
            raise BindingError(f"component {component!r} and argument {argument_name!r} drift")
    if set(by_component) != set(carriers):
        raise BindingError("binding arguments do not exactly cover ABI scalar carriers")


def _validate_roots(
    snapshot: Any,
    binding: Mapping[str, Any],
    policy: Mapping[str, Any],
    abi: Mapping[str, Any],
    program: Mapping[str, Any],
    mlir_arguments: list[str],
    mlir_text: str,
) -> None:
    abi_roots = _mapping(abi.get("roots"), "ABI roots")
    components = _mapping(policy.get("components"), "policy components")
    outputs = _mapping(policy.get("outputs"), "policy outputs")
    reference_roots = {
        row["id"]: row
        for row in _list(_mapping(program["abi"], "program.abi")["roots"], "program roots")
        if isinstance(row, Mapping)
    }
    offsets = _statement_offsets(program)
    rows = _list(binding.get("roots"), "binding.roots")
    seen: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _mapping(raw_row, f"binding.roots[{index}]")
        reference_id = row.get("referenceRoot")
        if not isinstance(reference_id, str) or reference_id in seen:
            raise BindingError("binding roots repeat or omit a reference root")
        seen.add(reference_id)
        reference = _mapping(
            reference_roots.get(reference_id), f"reference root {reference_id!r}"
        )
        _expect(row.get("byteLength"), reference.get("byteLength"), "binding/reference root length")
        _expect(row.get("offsets"), sorted(offsets[reference_id]), "binding/program root offsets")
        storage = row.get("storageKind")
        if storage == "ABIArgument":
            abi_id = row.get("abiRoot")
            authored = _mapping(abi_roots.get(abi_id), f"ABI root {abi_id!r}")
            argument_index = authored.get("argument")
            if (
                not isinstance(argument_index, int)
                or isinstance(argument_index, bool)
                or argument_index < 0
                or argument_index >= len(mlir_arguments)
            ):
                raise BindingError(f"ABI root {abi_id!r} has an invalid argument index")
            _expect(
                row.get("argumentIndex"),
                argument_index,
                "binding/ABI root argument index",
            )
            _expect(
                row.get("argumentName"),
                mlir_arguments[argument_index],
                "binding/MLIR root argument name",
            )
            if _logical_name(mlir_arguments[argument_index], "MLIR root argument") != _logical_name(
                abi_id, "ABI root ID"
            ):
                raise BindingError("MLIR root argument name differs from the ABI root ID")
            _expect(row.get("byteLength"), authored.get("extent-bytes"), "binding/ABI root length")
            initialized = authored.get("initialization") == "initialized"
            _expect(
                reference.get("initialized"),
                [initialized] * reference["byteLength"],
                "reference/ABI initialization",
            )
            input_id = authored.get("input")
            if input_id is not None:
                initial = _security_class(
                    _mapping(components.get(input_id), f"root input {input_id!r}").get("visibility"),
                    f"root input {input_id!r}",
                )
                _expect(row.get("initialClassification"), initial, "binding root input classification")
                expected_snapshot = {
                    item.get("memory_at_arg"): _logical_name(item.get("name"), "snapshot root name")
                    for item in snapshot.public
                    if "memory_at_arg" in item
                }
                if initial == "Low":
                    snapshot_name = expected_snapshot.get(argument_index)
                    allowed_names = {
                        _logical_name(input_id, "ABI root input"),
                        _logical_name(abi_id, "ABI root ID"),
                    }
                    if snapshot_name not in allowed_names:
                        raise BindingError(
                            "snapshot/ABI public root input: expected one of "
                            f"{sorted(allowed_names)!r}, got {snapshot_name!r}"
                        )
            output_id = authored.get("output")
            terminal = output_id is not None
            _expect(reference.get("terminalOutput"), terminal, "reference/ABI terminal root")
            _expect(reference.get("outputId"), output_id, "reference/ABI root output ID")
            if terminal:
                terminal_class = _security_class(
                    _mapping(outputs.get(output_id), f"policy output {output_id!r}").get("visibility"),
                    f"policy output {output_id!r}",
                )
                _expect(row.get("terminalVisibility"), terminal_class, "binding root output visibility")
        elif storage == "InternalAlloca":
            if abi_roots:
                # Internal roots may coexist with ABI roots, but never impersonate one.
                if row.get("abiRoot") in abi_roots:
                    raise BindingError("internal alloca aliases an ABI root in the binding")
            _expect(reference.get("terminalOutput"), False, "internal root terminalOutput")
            _expect(reference.get("outputId"), None, "internal root outputId")
            _expect(reference.get("initialized"), [False] * reference["byteLength"], "internal root initialization")
            _expect(
                row.get("initialClassification"),
                "Uninitialized",
                "internal root classification",
            )
            _expect(
                row.get("terminalVisibility"),
                "NotTerminalOutput",
                "internal root visibility",
            )
            site = row.get("allocationSite")
            if not isinstance(site, str) or not re.search(
                rf"\bllvm\.alloca\b[^\n]*\{{[^}}]*\bsps\.site_alias\s*=\s*\"{re.escape(site)}\"",
                mlir_text,
                re.S,
            ):
                raise BindingError(f"MLIR does not bind internal allocation site {site!r}")
        else:
            raise BindingError(f"unknown binding root storageKind {storage!r}")
    if seen != set(reference_roots):
        raise BindingError("binding roots do not exactly cover reduced program roots")


def _validate_return(
    snapshot: Any,
    policy: Mapping[str, Any],
    abi: Mapping[str, Any],
    program: Mapping[str, Any],
) -> None:
    abi_entry = _mapping(abi.get("entry"), "ABI entry")
    abi_return = abi_entry.get("return")
    reference_return = _mapping(program.get("abi"), "program.abi").get("return")
    if abi_return == "void":
        _expect(reference_return, None, "reference/ABI void return")
        return
    authored = _mapping(abi_return, "ABI return")
    reference = _mapping(reference_return, "reference return")
    _expect(reference.get("outputId"), authored.get("output"), "reference/ABI return output")
    width = reference.get("width")
    full_width = authored.get("bit-width")
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(full_width, int)
        or isinstance(full_width, bool)
        or width <= 0
        or width > full_width
    ):
        raise BindingError("reference return width is not a valid ABI reduction")
    _expect(reference.get("byteOrder"), "LittleEndian", "reference return byte order")
    output = _mapping(
        _mapping(policy.get("outputs"), "policy outputs").get(authored.get("output")),
        "policy return output",
    )
    visibility = _security_class(output.get("visibility"), "policy return output")
    observable_return = any(
        row.get("observable") == "return" for row in snapshot.public
    )
    _expect(observable_return, visibility == "Low", "snapshot/policy return visibility")


def _validate_terminal_output_order(
    abi: Mapping[str, Any], program: Mapping[str, Any]
) -> None:
    schedules = _mapping(abi.get("terminal-output-order"), "ABI terminal-output-order")
    authored = _list(schedules.get("normal-value"), "ABI normal-value output order")
    program_abi = _mapping(program.get("abi"), "program.abi")
    reduced = _list(
        program_abi.get("terminalOutputOrder"),
        "reference terminal-output order",
    )
    _expect(reduced, authored, "reference/ABI terminal output order")


def _validate_coalition(
    binding: Mapping[str, Any],
    fixture: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> None:
    authored = _mapping(binding.get("coalition"), "binding coalition")
    adversary_id = authored.get("policyAdversaryId")
    adversaries = _mapping(policy.get("adversaries"), "policy adversaries")
    rows = _list(adversaries.get(adversary_id), f"policy adversary {adversary_id!r}")
    index = authored.get("policyAdversaryIndex")
    if (
        not isinstance(index, int)
        or isinstance(index, bool)
        or index < 0
        or index >= len(rows)
    ):
        raise BindingError("binding coalition requires policy adversary maximal[0]")
    principals = sorted(_list(rows[index], "policy adversary coalition"))
    _expect(authored.get("principals"), principals, "binding/policy coalition principals")

    fixture_coalition = _mapping(
        _mapping(fixture.get("input"), "fixture.input").get("coalition"),
        "fixture coalition",
    )
    _expect(
        authored.get("referenceCoalitionId"),
        fixture_coalition.get("id"),
        "binding/reference coalition ID",
    )
    _expect(
        authored.get("controlledHosts"),
        sorted(fixture_coalition.get("controlledHosts", [])),
        "binding/reference controlled hosts",
    )

    mappings = _list(authored.get("hostMappings"), "binding coalition hostMappings")
    _expect(
        [row.get("referenceHost") for row in mappings if isinstance(row, Mapping)],
        authored.get("controlledHosts"),
        "binding controlled-host coverage",
    )
    if any(
        row.get("policyHost") is not None
        or row.get("boundaryClass") != "PublicObservationEndpoint"
        for row in mappings
        if isinstance(row, Mapping)
    ):
        raise BindingError("reference observation hosts must map to a public endpoint")

    program = _mapping(_mapping(fixture["input"], "fixture.input")["program"], "program")
    program_abi = _mapping(program.get("abi"), "program.abi")
    outputs = _mapping(policy.get("outputs"), "policy outputs")
    public_hosts: set[str] = set()
    reference_return = program_abi.get("return")
    if isinstance(reference_return, Mapping):
        output = _mapping(outputs.get(reference_return.get("outputId")), "return output")
        if output.get("visibility") == "public":
            public_hosts.add(str(reference_return.get("host")))
    for root in _list(program_abi.get("roots"), "program roots"):
        if not isinstance(root, Mapping) or not root.get("terminalOutput"):
            continue
        output = _mapping(outputs.get(root.get("outputId")), "root output")
        if output.get("visibility") == "public":
            public_hosts.add(str(root.get("host")))
    if not public_hosts:
        raise BindingError("public observation endpoint lacks a public program output")
    if public_hosts != set(authored.get("controlledHosts", [])):
        raise BindingError(
            "bound controlled hosts must exactly equal public reference output hosts"
        )


def _validate_case(
    root: Path,
    snapshot: Any,
    pipeline: Any,
    checkpoint_model: Any,
    checkpoint_extractors: Any,
    canonical: Any,
    evidence: Any,
) -> tuple[Path, Path]:
    case = snapshot.path.parent.resolve()
    fixture_path = case / "relation-reference" / "fixture.json"
    binding_path = case / "relation-reference" / "binding.json"
    try:
        fixture_value = canonical.load_json_bytes(fixture_path.read_bytes())
        binding_value = canonical.load_json_bytes(binding_path.read_bytes())
        fixture = evidence.validate_relation_fixture(fixture_value)
        binding = evidence.validate_reduction_binding(
            binding_value,
            fixture,
            binding_path=binding_path,
            fixture_path=fixture_path,
        )
    except Exception as error:
        raise BindingError(f"{snapshot.case}: invalid relation reduction: {error}") from error

    _expect(binding.get("harnessCase"), snapshot.case, "binding/snapshot case")
    _expect(binding.get("entry"), snapshot.entry, "binding/snapshot entry")
    files = _file_bindings(case, binding)
    expected_files = {
        "abi": case / "abi.sps.yaml",
        "mlir": files["mlir"],
        "policy": case / "policy.sps.yaml",
        "referenceFixture": fixture_path,
        "snapshot": snapshot.path,
    }
    for role in ("abi", "policy", "referenceFixture", "snapshot"):
        _expect(files[role], expected_files[role].resolve(), f"binding {role} path")

    policy = _load_yaml(files["policy"], checkpoint_model)
    abi = _load_yaml(files["abi"], checkpoint_model)
    source = abi.get("source")
    if not isinstance(source, str) or Path(source).name != source:
        raise BindingError("ABI source must name a case-local translation unit")
    _expect(files["c"], (case / source).resolve(), "binding/ABI C source")
    c_evidence = {
        root.joinpath(*relative.split("/")).resolve()
        for relative in snapshot.c_evidence
    }
    if files["c"] not in c_evidence:
        raise BindingError("snapshot C evidence does not bind the ABI source")
    if files["mlir"].parent != case or files["mlir"].suffix != ".mlir":
        raise BindingError("binding MLIR must be a case-local .mlir file")

    abi_entry = _mapping(abi.get("entry"), "ABI entry")
    for actual, where in (
        (policy.get("entry"), "policy entry"),
        (abi_entry.get("id"), "ABI entry ID"),
        (abi_entry.get("symbol"), "ABI entry symbol"),
        (_mapping(fixture["input"], "fixture.input")["program"]["entryId"], "reference entry"),
    ):
        _expect(actual, snapshot.entry, where)

    mlir_raw = files["mlir"].read_bytes()
    facts = checkpoint_extractors.extract(
        "mlir",
        "mlir-structure-v1",
        mlir_raw,
        {"function": snapshot.entry},
    )
    signature = _abi_signature(abi_entry.get("function-type"), snapshot.entry)
    _expect(facts["function.signatures"], [signature], "MLIR/ABI signature")
    prefix = f"{snapshot.entry}|"
    mlir_arguments = [
        row.split("|", 2)[2]
        for row in facts["function.argument_names"]
        if row.startswith(prefix)
    ]
    program = _mapping(_mapping(fixture["input"], "fixture.input")["program"], "program")
    _validate_arguments(snapshot, binding, policy, abi, program, mlir_arguments)
    _validate_roots(
        snapshot,
        binding,
        policy,
        abi,
        program,
        mlir_arguments,
        mlir_raw.decode("utf-8"),
    )
    _validate_memory_mapping(snapshot.entry, binding, abi, program, facts)
    _validate_control_mapping(snapshot.entry, binding, program, facts)
    _validate_return_expression(snapshot.entry, binding, program, facts)
    _validate_return(snapshot, policy, abi, program)
    _validate_terminal_output_order(abi, program)
    _validate_coalition(binding, fixture, policy)

    root_inputs = {
        row.get("input")
        for row in _mapping(abi.get("roots"), "ABI roots").values()
        if isinstance(row, Mapping) and row.get("input") is not None
    }
    expected_components = set(_mapping(abi.get("carriers"), "ABI carriers")) | root_inputs
    _expect(
        set(_mapping(policy.get("components"), "policy components")),
        expected_components,
        "policy/ABI input components",
    )

    observations = sorted(
        {("kind", event.kind, "field", event.field) for event in snapshot.final.events}
    )
    expected_observations = [
        {kind_key: kind, field_key: field}
        for kind_key, kind, field_key, field in observations
    ]
    _expect(binding.get("observations"), expected_observations, "binding/snapshot observations")
    audit = _mapping(_mapping(fixture.get("expected"), "fixture.expected").get("auditAll"), "auditAll")
    expected_audit = pipeline.properties["query.audit-all"].get("equals")
    _expect(audit.get("status"), expected_audit, "fixture/snapshot AuditAll expectation")
    high_ids = [
        row["componentId"]
        for row in _list(
            _mapping(fixture.get("expected"), "fixture.expected").get("highVariation"),
            "fixture highVariation",
        )
    ]
    _expect(
        pipeline.properties["query.high-variation"].get("contains_all"),
        high_ids,
        "fixture/snapshot High-variation components",
    )
    _expect(
        pipeline.properties["query.admission-nonempty"].get("equals"),
        fixture["expected"]["admissionNonempty"],
        "fixture/snapshot admission expectation",
    )
    _expect(
        pipeline.properties["query.terminal-output-surface"].get("equals"),
        fixture["expected"]["terminalOutputSurface"],
        "fixture/snapshot terminal-output expectation",
    )
    _expect(
        pipeline.properties["backend.agreement"].get("equals"),
        True,
        "snapshot backend agreement expectation",
    )
    first_bad = [event for event in snapshot.final.events if event.first_bad]
    expected_difference = (
        {"kind": first_bad[0].kind, "field": first_bad[0].field}
        if first_bad
        else None
    )
    _expect(audit.get("firstDifference"), expected_difference, "fixture/snapshot first difference")
    if expected_difference is not None:
        matcher = pipeline.properties.get("query.audit-all-first-difference", {})
        _expect(matcher.get("equals"), expected_difference, "pipeline first difference")
    return fixture_path, binding_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-pipeline", required=True, choices=[PIPELINE])
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--outputs", required=True, type=Path)
    parser.add_argument("--z3", required=True, type=Path)
    arguments = parser.parse_args()

    root = arguments.root.resolve()
    sys.path.insert(0, str(root / "tools"))
    import checkpoint_extractors
    import checkpoint_model

    canonical, evidence = _reference_api(root)
    runner = root / "tools" / "checkpoint_runner.py"
    reference_runner = (
        root
        / "contracts"
        / "vendor"
        / "sps-reference-rev4"
        / "reference"
        / "run_reference_checks.py"
    )
    z3 = arguments.z3.resolve()
    if not z3.is_file() or not os.access(z3, os.X_OK):
        raise SystemExit(f"configured Z3 is not executable: {z3}")
    arguments.outputs.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["Z3"] = str(z3)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    owned = 0
    inventory = checkpoint_model.build_inventory(root)
    for snapshot in inventory.snapshots:
        pipeline = snapshot.pipelines.get(PIPELINE)
        if pipeline is None or pipeline.test != TEST:
            continue
        fixture, binding = _validate_case(
            root,
            snapshot,
            pipeline,
            checkpoint_model,
            checkpoint_extractors,
            canonical,
            evidence,
        )
        endpoint = arguments.outputs / f"{snapshot.case.replace('/', '--')}.json"
        command = [
            sys.executable,
            str(runner),
            "run",
            "--root",
            str(root),
            "--snapshot",
            str(snapshot.path.relative_to(root)),
            "--pipeline",
            PIPELINE,
            "--endpoint",
            str(endpoint),
            "--records",
            str(arguments.records),
            "--",
            sys.executable,
            str(reference_runner),
            "--relation-fixture",
            str(fixture),
            "--binding",
            str(binding),
            "--output",
            str(endpoint),
        ]
        subprocess.run(command, check=True, env=environment)
        owned += 1
    if owned != EXPECTED_CASES:
        raise SystemExit(
            f"expected exactly {EXPECTED_CASES} {PIPELINE!r} checkpoints owned by "
            f"{TEST}, got {owned}"
        )
    print(f"ran {owned} case-local relation-reference checkpoints")


if __name__ == "__main__":
    main()
