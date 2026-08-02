"""Resolve annotated C/C++ and unversioned SPS policy/ABI authoring files."""

from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import checkpoint_model

from source_boundary import schema as authoring_schema


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INCLUDE = ROOT / "include"
DEFAULT_SCHEMAS = ROOT / "source-annotations" / "schemas"
AUTHORING_CONTRACT_SCHEMA = Path(__file__).with_name("contracts.schema.json")
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")
ANNOTATIONS = {
    "sps.entry=": "entry",
    "sps.helper=": "helper",
    "sps.component=": "component",
    "sps.root=": "root",
    "sps.return-output=": "return-output",
}
FUNCTION_KINDS = frozenset({"entry", "helper", "return-output"})
PARAMETER_KINDS = frozenset({"component", "root"})
SOURCE_SUFFIXES = frozenset({".c", ".cc", ".cpp", ".cxx"})


class BoundaryError(ValueError):
    pass


def _load_yaml(path: Path, schema_path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise BoundaryError(f"cannot read {path}: {error}") from error
    try:
        value = checkpoint_model.strict_yaml_load(raw, source=str(path))
        schema = authoring_schema.load_schema(schema_path)
        authoring_schema.validate(value, schema, source=str(path))
    except (checkpoint_model.CheckpointError, authoring_schema.SchemaError) as error:
        raise BoundaryError(str(error)) from error
    return value


def case_primary_source(case: Path, schemas: Path = DEFAULT_SCHEMAS) -> Path:
    """Select a case's primary translation unit from its ABI authoring file."""
    case = case.resolve()
    abi_path = case / "abi.sps.yaml"
    abi = _load_yaml(abi_path, schemas / "abi.schema.json")
    source_name = abi["source"]
    if Path(source_name).name != source_name or Path(source_name).suffix not in SOURCE_SUFFIXES:
        raise BoundaryError("ABI source must be a local C/C++ basename")
    return case / source_name


def _strict_json(raw: str, source: str) -> dict[str, Any]:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise BoundaryError(f"{source}: duplicate JSON field {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=object_pairs)
    except json.JSONDecodeError as error:
        raise BoundaryError(f"{source}: invalid extractor JSON: {error.msg}") from error
    if not isinstance(value, dict):
        raise BoundaryError(f"{source}: extractor result must be an object")
    return value


def _resolve_tool(value: str | Path, name: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        found = shutil.which(str(path))
        if found:
            path = Path(found)
    path = path.resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise BoundaryError(f"{name} is not executable: {value}")
    return path


def _language(source: Path) -> tuple[str, str]:
    if source.suffix == ".c":
        return "c", "c11"
    if source.suffix in {".cc", ".cpp", ".cxx"}:
        return "c++", "c++17"
    raise BoundaryError(f"unsupported source suffix: {source.name}")


def _driver_query(command: list[str], what: str) -> str:
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise BoundaryError(f"cannot query {what}: {detail.strip()}") from error
    value = completed.stdout.strip()
    if not value or "\n" in value:
        raise BoundaryError(f"cannot query {what}: command returned no single path")
    path = Path(value).resolve()
    if not path.is_dir():
        raise BoundaryError(f"cannot query {what}: {path} is not a directory")
    return str(path)


def _extractor_toolchain_arguments(clang: Path) -> list[str]:
    resource_dir = _driver_query(
        [str(clang), "-print-resource-dir"], "Clang resource directory"
    )
    arguments = [f"-resource-dir={resource_dir}"]
    if sys.platform == "darwin":
        xcrun = shutil.which("xcrun")
        if xcrun is None:
            raise BoundaryError("cannot query macOS SDK path: xcrun is not executable")
        sdk = _driver_query([xcrun, "--show-sdk-path"], "macOS SDK path")
        arguments.extend(["-isysroot", sdk])
    return arguments


def _run_extractor(
    source: Path,
    extractor: Path,
    include: Path,
    toolchain_arguments: list[str],
) -> dict[str, Any]:
    language, standard = _language(source)
    command = [
        str(extractor),
        str(source),
        "--",
        "-x",
        language,
        f"-std={standard}",
        "-DSPS_EXTRACT_ANNOTATIONS",
        *toolchain_arguments,
        f"-I{include}",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise BoundaryError(f"Clang AST extraction failed: {detail.strip()}") from error
    return _strict_json(completed.stdout, "Clang AST extractor")


def _matching_parenthesis(value: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(value)):
        if value[index] == "(":
            depth += 1
        elif value[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    raise BoundaryError("generated LLVM function declaration has unbalanced parentheses")


def _split_llvm_parameters(value: str) -> list[str]:
    if not value.strip():
        return []
    result: list[str] = []
    start = 0
    depths = {"(": 0, "[": 0, "{": 0, "<": 0}
    closing = {")": "(", "]": "[", "}": "{", ">": "<"}
    for index, character in enumerate(value):
        if character in depths:
            depths[character] += 1
        elif character in closing:
            depths[closing[character]] -= 1
        elif character == "," and not any(depths.values()):
            result.append(value[start:index].strip())
            start = index + 1
    result.append(value[start:].strip())
    return result


def _llvm_parameter_type(value: str) -> str:
    if value == "...":
        return value
    match = re.match(
        r"^(ptr(?:\s+addrspace\([0-9]+\))?|i[1-9][0-9]*|float|double)(?:\s|$)",
        value,
    )
    if match is None:
        raise BoundaryError(f"generated LLVM uses an unsupported parameter shape: {value!r}")
    return match.group(1)


def _emitted_function_type(rendered: str, symbol: str) -> str:
    definitions: list[str] = []
    lines = iter(rendered.splitlines())
    for line in lines:
        declaration = line.strip()
        if not declaration.startswith("define "):
            continue
        while "{" not in declaration:
            try:
                declaration += " " + next(lines).strip()
            except StopIteration as error:
                raise BoundaryError("generated LLVM ended inside a function declaration") from error
        definitions.append(declaration)

    marker = f"@{symbol}("
    matches = [definition for definition in definitions if marker in definition]
    if len(matches) != 1:
        raise BoundaryError(
            f"generated LLVM has {len(matches)} definitions for ABI symbol {symbol!r}"
        )
    declaration = matches[0]
    symbol_offset = declaration.index(marker)
    return_match = re.search(
        rf"(?:^|\s)(void|i[1-9][0-9]*|float|double)\s+@{re.escape(symbol)}\($",
        declaration[: symbol_offset + len(marker)],
    )
    if return_match is None:
        raise BoundaryError(
            f"generated LLVM uses an unsupported return or symbol shape for {symbol!r}"
        )
    opening = symbol_offset + len(marker) - 1
    closing = _matching_parenthesis(declaration, opening)
    parameters = _split_llvm_parameters(declaration[opening + 1 : closing])
    parameter_types = [_llvm_parameter_type(parameter) for parameter in parameters]
    return "{} ({})".format(return_match.group(1), ", ".join(parameter_types))


def _emitted_contract_function_type(rendered: str, symbol: str) -> str:
    """Return the type of one external scalar contract declaration."""
    declarations: list[str] = []
    lines = iter(rendered.splitlines())
    for line in lines:
        declaration = line.strip()
        if not declaration.startswith("declare "):
            continue
        while ")" not in declaration:
            try:
                declaration += " " + next(lines).strip()
            except StopIteration as error:
                raise BoundaryError(
                    "generated LLVM ended inside a contract declaration"
                ) from error
        declarations.append(declaration)

    marker = f"@{symbol}("
    matches = [declaration for declaration in declarations if marker in declaration]
    if len(matches) != 1:
        raise BoundaryError(
            f"generated LLVM has {len(matches)} external declarations for "
            f"contract callee {symbol!r}"
        )
    declaration = matches[0]
    symbol_offset = declaration.index(marker)
    return_match = re.search(
        rf"(?:^|\s)(void|i[1-9][0-9]*|float|double)\s+@{re.escape(symbol)}\($",
        declaration[: symbol_offset + len(marker)],
    )
    if return_match is None:
        raise BoundaryError(
            f"contract callee {symbol!r} has an unsupported return or symbol shape"
        )
    opening = symbol_offset + len(marker) - 1
    closing = _matching_parenthesis(declaration, opening)
    parameters = _split_llvm_parameters(declaration[opening + 1 : closing])
    parameter_types = [_llvm_parameter_type(parameter) for parameter in parameters]
    if any(parameter == "..." or parameter.startswith("ptr") for parameter in parameter_types):
        raise BoundaryError(
            f"cross-host contract callee {symbol!r} must have a scalar, non-variadic signature"
        )
    return "{} ({})".format(return_match.group(1), ", ".join(parameter_types))


def _normal_llvm(
    source: Path, clang: Path, include: Path, symbol: str | None
) -> tuple[str | None, str]:
    language, standard = _language(source)
    with tempfile.TemporaryDirectory() as temporary:
        llvm_path = Path(temporary) / "normal.ll"
        command = [
            str(clang),
            "-x",
            language,
            f"-std={standard}",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-O0",
            "-S",
            "-emit-llvm",
            f"-I{include}",
            str(source),
            "-o",
            str(llvm_path),
        ]
        try:
            completed = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            detail = getattr(error, "stderr", "") or str(error)
            raise BoundaryError(f"normal source compilation failed: {detail.strip()}") from error
        try:
            rendered = llvm_path.read_text(encoding="utf-8")
        except OSError as error:
            raise BoundaryError(f"cannot read generated LLVM IR: {error}") from error
    forbidden = ("sps.", "llvm.global.annotations", "llvm.var.annotation")
    present = [item for item in forbidden if item in rendered]
    if present:
        raise BoundaryError(
            "normal LLVM contains source-annotation residue: " + ", ".join(present)
        )
    return (
        _emitted_function_type(rendered, symbol) if symbol is not None else None,
        rendered,
    )


def _annotation(value: Any, where: str) -> tuple[str, str] | None:
    if not isinstance(value, str):
        raise BoundaryError(f"{where}: annotation must be a string")
    if not value.startswith("sps."):
        return None
    for prefix, kind in ANNOTATIONS.items():
        if value.startswith(prefix):
            identifier = value[len(prefix) :]
            if not IDENTIFIER.fullmatch(identifier):
                raise BoundaryError(f"{where}: malformed SPS identifier {identifier!r}")
            return kind, identifier
    raise BoundaryError(f"{where}: unknown SPS annotation {value!r}")


def _annotation_sets(function: Mapping[str, Any]) -> tuple[dict[str, set[str]], list[dict[str, set[str]]]]:
    parameters = function.get("parameters")
    declarations = function.get("declarations")
    symbol = function.get("symbol", "<unknown>")
    if not isinstance(parameters, list) or not isinstance(declarations, list):
        raise BoundaryError(f"AST function {symbol}: malformed extractor record")
    function_values: dict[str, set[str]] = {kind: set() for kind in ANNOTATIONS.values()}
    parameter_values = [
        {kind: set() for kind in ANNOTATIONS.values()} for _ in parameters
    ]
    for declaration_index, declaration in enumerate(declarations):
        if not isinstance(declaration, Mapping):
            raise BoundaryError(f"AST function {symbol}: malformed declaration record")
        raw_annotations = declaration.get("annotations")
        raw_parameters = declaration.get("parameterAnnotations")
        if not isinstance(raw_annotations, list) or not isinstance(raw_parameters, list):
            raise BoundaryError(f"AST function {symbol}: malformed annotations")
        if len(raw_parameters) != len(parameters):
            raise BoundaryError(f"AST function {symbol}: redeclaration arity mismatch")
        for raw in raw_annotations:
            decoded = _annotation(raw, f"{symbol} declaration {declaration_index}")
            if decoded is not None:
                function_values[decoded[0]].add(decoded[1])
        for parameter_index, values in enumerate(raw_parameters):
            if not isinstance(values, list):
                raise BoundaryError(f"AST function {symbol}: malformed parameter annotations")
            for raw in values:
                decoded = _annotation(
                    raw, f"{symbol} parameter {parameter_index} declaration {declaration_index}"
                )
                if decoded is not None:
                    parameter_values[parameter_index][decoded[0]].add(decoded[1])
    return function_values, parameter_values


def _one(values: set[str], where: str) -> str | None:
    if len(values) > 1:
        raise BoundaryError(f"{where}: conflicting annotation identifiers {sorted(values)!r}")
    return next(iter(values), None)


def _decode_ast(
    ast: Mapping[str, Any], *, require_entry: bool, source: str
) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]]]:
    functions = ast.get("functions")
    cplusplus = ast.get("cplusplus")
    if not isinstance(functions, list) or not isinstance(cplusplus, bool):
        raise BoundaryError("Clang AST extractor returned a malformed root")
    entries: dict[str, dict[str, Any]] = {}
    helpers: dict[str, dict[str, Any]] = {}
    for function in functions:
        if not isinstance(function, dict):
            raise BoundaryError("Clang AST extractor returned a malformed function")
        symbol = function.get("symbol")
        if not isinstance(symbol, str):
            raise BoundaryError("Clang AST function has no symbol")
        function_values, parameter_values = _annotation_sets(function)
        for kind in PARAMETER_KINDS:
            if function_values[kind]:
                raise BoundaryError(f"{symbol}: SPS_{kind.upper()} is not a function annotation")
        for values in parameter_values:
            for kind in FUNCTION_KINDS:
                if values[kind]:
                    raise BoundaryError(f"{symbol}: SPS {kind} is not a parameter annotation")
        for kind, values in function_values.items():
            _one(values, f"{symbol} {kind}")
        for index, values in enumerate(parameter_values):
            for kind, identifiers in values.items():
                _one(identifiers, f"{symbol} parameter {index} {kind}")
            if values["component"] and values["root"]:
                raise BoundaryError(f"{symbol} parameter {index}: component and root conflict")

        entry_id = _one(function_values["entry"], f"{symbol} entry")
        helper_id = _one(function_values["helper"], f"{symbol} helper")
        return_output = _one(function_values["return-output"], f"{symbol} return output")
        if entry_id and helper_id:
            raise BoundaryError(f"{symbol}: a function cannot be both entry and helper")
        if return_output and not entry_id:
            raise BoundaryError(f"{symbol}: return output requires an entry annotation")
        if not entry_id and any(
            values["component"] or values["root"] for values in parameter_values
        ):
            raise BoundaryError(
                f"{symbol}: component/root annotations require an entry annotation"
            )
        if not function.get("isDefinition"):
            raise BoundaryError(f"{symbol}: annotated function has no case-local definition")
        if not isinstance(function.get("identity"), str) or not function["identity"]:
            raise BoundaryError(f"{symbol}: Clang did not provide a declaration identity")
        if function.get("isMethod") or function.get("isTemplate") or function.get("isOverloaded"):
            raise BoundaryError(f"{symbol}: methods, templates, and overloads are unsupported")
        if cplusplus and entry_id and not function.get("isExternC"):
            raise BoundaryError(f"{symbol}: a C++ entry must have extern \"C\" linkage")

        if helper_id:
            if any(values["component"] or values["root"] for values in parameter_values):
                raise BoundaryError(f"{symbol}: helper parameters cannot define entry boundary roles")
            if helper_id in helpers:
                raise BoundaryError(f"helper ID {helper_id!r} is defined more than once")
            helpers[helper_id] = function
        if entry_id:
            if function.get("isVariadic"):
                raise BoundaryError(f"{symbol}: variadic entries are unsupported")
            if function.get("usesDefaultCallingConvention") is not True:
                raise BoundaryError(f"{symbol}: non-default calling conventions are unsupported")
            if entry_id in entries:
                raise BoundaryError(f"entry ID {entry_id!r} is defined more than once")
            parameters = function["parameters"]
            for index, values in enumerate(parameter_values):
                component = _one(values["component"], f"{symbol} parameter {index}")
                root = _one(values["root"], f"{symbol} parameter {index}")
                if component is None and root is None:
                    raise BoundaryError(f"{symbol} parameter {index}: missing component/root annotation")
                if parameters[index].get("isPointer"):
                    if parameters[index].get("isFunctionPointer"):
                        raise BoundaryError(
                            f"{symbol} parameter {index}: function pointers cannot be ABI roots"
                        )
                    if parameters[index].get("usesDefaultAddressSpace") is not True:
                        raise BoundaryError(
                            f"{symbol} parameter {index}: non-default pointer address spaces are unsupported"
                        )
                parameters[index]["role"] = "component" if component else "root"
                parameters[index]["id"] = component or root
            function["entryId"] = entry_id
            function["returnOutput"] = return_output
            entries[entry_id] = function
    if require_entry:
        if len(entries) != 1:
            raise BoundaryError(
                f"primary source {source!r} must define exactly one SPS entry; "
                f"found {len(entries)}"
            )
        return next(iter(entries.values())), helpers
    if entries:
        raise BoundaryError(
            f"support source {source!r} must not define SPS_ENTRY; found {len(entries)}"
        )
    return None, helpers


def _llvm_scalar(value: Mapping[str, Any], where: str) -> str:
    width = value.get("bitWidth")
    if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
        raise BoundaryError(f"{where}: missing scalar width")
    if value.get("isInteger"):
        if value.get("type") in {"_Bool", "bool"}:
            raise BoundaryError(f"{where}: boolean ABI lowering is not supported yet")
        return f"i{width}"
    if value.get("isFloating"):
        if width == 32:
            return "float"
        if width == 64:
            return "double"
    raise BoundaryError(f"{where}: unsupported scalar C/C++ type {value.get('type')!r}")


def _return_llvm(entry: Mapping[str, Any]) -> str:
    if entry.get("returnIsVoid"):
        return "void"
    pseudo = {
        "bitWidth": entry.get("returnBitWidth"),
        "isInteger": entry.get("returnIsInteger"),
        "isFloating": entry.get("returnIsFloating"),
        "type": entry.get("returnType"),
    }
    return _llvm_scalar(pseudo, f"{entry.get('symbol')} return")


def _visibility(value: Any, principals: set[str], where: str) -> dict[str, Any]:
    if value == "public":
        return {"world": True, "members": [], "joint": []}
    if value == "secret":
        return {"world": False, "members": [], "joint": []}
    assert isinstance(value, Mapping)
    members = value["members"]
    joint = value["joint"]
    unknown = (set(members) | {item for group in joint for item in group}) - principals
    if unknown:
        raise BoundaryError(f"{where}: visibility references unknown principals {sorted(unknown)!r}")
    normalized_joint = {tuple(sorted(group)) for group in joint}
    if len(normalized_joint) != len(joint):
        raise BoundaryError(f"{where}: duplicate semantic joint coalition")
    return {
        "world": value["world"],
        "members": sorted(members),
        "joint": [list(group) for group in sorted(normalized_joint)],
    }


def _is_visible(visibility: Mapping[str, Any], coalition: frozenset[str]) -> bool:
    return bool(
        visibility["world"]
        or coalition.intersection(visibility["members"])
        or any(set(group) <= coalition for group in visibility["joint"])
    )


def _coalitions(policy: Mapping[str, Any]) -> list[frozenset[str]]:
    principals = set(policy["principals"])
    maxima: list[frozenset[str]] = []
    for index, raw in enumerate(policy["adversaries"]["maximal"]):
        coalition = frozenset(raw)
        unknown = coalition - principals
        if unknown:
            raise BoundaryError(
                f"adversaries.maximal[{index}] references unknown principals {sorted(unknown)!r}"
            )
        if coalition in maxima:
            raise BoundaryError("adversaries.maximal contains a duplicate semantic coalition")
        maxima.append(coalition)
    for left, right in itertools.permutations(maxima, 2):
        if left < right:
            raise BoundaryError("adversaries.maximal is not a maximal-coalition antichain")
    closure: set[frozenset[str]] = set()
    for maximum in maxima:
        ordered = sorted(maximum)
        for count in range(len(ordered) + 1):
            closure.update(frozenset(items) for items in itertools.combinations(ordered, count))
    return sorted(
        closure,
        key=lambda item: checkpoint_model.canonical_bytes(sorted(item)),
    )


def _expression_components(expression: Mapping[str, Any]) -> set[str]:
    if "component" in expression:
        return {expression["component"]}
    if "constant" in expression:
        return set()
    for operator in ("bit-and", "bit-xor"):
        if operator in expression:
            operation = expression[operator]
            return _expression_components(operation["left"]) | _expression_components(
                operation["right"]
            )
    if "negate" in expression:
        return _expression_components(expression["negate"])
    raise BoundaryError("policy release contains an unsupported expression")


def _validate_expression_width(
    expression: Mapping[str, Any],
    components: Mapping[str, Any],
    width: int,
    where: str,
) -> None:
    if "component" in expression:
        identifier = expression["component"]
        if identifier not in components:
            raise BoundaryError(f"{where} references unknown component {identifier!r}")
        component_type = components[identifier]["type"]
        if component_type == "bytes":
            raise BoundaryError(
                f"{where} uses byte-root component {identifier!r}; "
                "byte expressions are not supported yet"
            )
        if int(component_type[2:]) != width:
            raise BoundaryError(
                f"{where} width disagrees with component {identifier!r}"
            )
        return
    if "constant" in expression:
        constant = expression["constant"]
        if constant.bit_length() > width:
            raise BoundaryError(
                f"{where} constant {constant} does not fit in BV{width}"
            )
        return
    for operator in ("bit-and", "bit-xor"):
        if operator in expression:
            operation = expression[operator]
            _validate_expression_width(
                operation["left"], components, width, f"{where}.{operator}.left"
            )
            _validate_expression_width(
                operation["right"], components, width, f"{where}.{operator}.right"
            )
            return
    if "negate" in expression:
        _validate_expression_width(
            expression["negate"], components, width, f"{where}.negate"
        )
        return
    raise BoundaryError(f"{where} contains an unsupported expression")


def _validate_contracts(
    contracts: dict[str, Any] | None,
    *,
    entry: dict[str, Any],
    abi: dict[str, Any],
    policy: dict[str, Any],
    rendered_llvm: str,
) -> list[dict[str, Any]]:
    if contracts is None:
        return []

    rows = contracts["contracts"]
    identifiers = [row["id"] for row in rows]
    if identifiers != sorted(identifiers) or len(identifiers) != len(set(identifiers)):
        raise BoundaryError(
            "contract authoring rows must be sorted by unique stable contract ID"
        )

    entry_host = abi["entry"]["host"]
    declared_hosts = set(policy["hosts"])
    calls = sorted(entry.get("calls", []), key=lambda item: item.get("offset", -1))
    bound_sites: set[tuple[str, int]] = set()
    resolved: list[dict[str, Any]] = []
    for row in rows:
        contract_id = row["id"]
        source_host = row["source-host"]
        destination_host = row["destination-host"]
        if source_host != entry_host:
            raise BoundaryError(
                f"contract {contract_id!r} source host must equal entry host {entry_host!r}"
            )
        if destination_host == source_host:
            raise BoundaryError(
                f"contract {contract_id!r} must cross two distinct hosts"
            )
        unknown_hosts = {source_host, destination_host} - declared_hosts
        if unknown_hosts:
            raise BoundaryError(
                f"contract {contract_id!r} references undeclared hosts "
                f"{sorted(unknown_hosts)!r}"
            )

        locator = row["locator"]
        callee = locator["callee"]
        ordinal = locator["call-ordinal"]
        direct_calls = [
            call
            for call in calls
            if call.get("direct") is True and call.get("callee") == callee
        ]
        if ordinal >= len(direct_calls):
            raise BoundaryError(
                f"contract {contract_id!r} call ordinal {ordinal} is out of range "
                f"for callee {callee!r}"
            )
        site = (callee, ordinal)
        if site in bound_sites:
            raise BoundaryError(f"contract call site {site!r} is bound more than once")
        bound_sites.add(site)

        signature = row["signature"]
        scalar_types = [*signature["arguments"]]
        if signature["result"] != "void":
            scalar_types.append(signature["result"])
        if any(re.fullmatch(r"i[1-9][0-9]*", item) is None for item in scalar_types):
            raise BoundaryError(
                f"contract {contract_id!r} supports only integer Bool/BV scalar types"
            )
        expected_type = "{} ({})".format(
            signature["result"], ", ".join(signature["arguments"])
        )
        actual_type = _emitted_contract_function_type(rendered_llvm, callee)
        if actual_type != expected_type:
            raise BoundaryError(
                f"contract {contract_id!r} signature mismatch: authoring has "
                f"{expected_type!r}, emitted LLVM has {actual_type!r}"
            )
        resolved.append(
            {
                "id": contract_id,
                "callee": callee,
                "call-ordinal": ordinal,
                "source-host": source_host,
                "destination-host": destination_host,
                "signature": expected_type,
                "source-offset": direct_calls[ordinal].get("offset"),
                "claim-boundary": contracts["claim-boundary"],
            }
        )
    return resolved


def _validate_policy(
    policy: dict[str, Any],
    entry: dict[str, Any],
    abi: dict[str, Any],
    contracts: list[dict[str, Any]],
) -> dict[str, Any]:
    principals = set(policy["principals"])
    if len(principals) != len(policy["principals"]):
        raise BoundaryError("principals contain duplicates")
    entry_id = entry["entryId"]
    if policy["entry"] != entry_id:
        raise BoundaryError(
            f"policy entry {policy['entry']!r} does not match source entry {entry_id!r}"
        )
    expected_hosts = {
        abi["entry"]["host"],
        *(root["host"] for root in abi["roots"].values()),
        *(row["source-host"] for row in contracts),
        *(row["destination-host"] for row in contracts),
    }
    if set(policy["hosts"]) != expected_hosts:
        raise BoundaryError(
            f"policy hosts do not exactly cover ABI hosts; expected {sorted(expected_hosts)!r}"
        )
    visibilities: dict[str, dict[str, dict[str, Any]]] = {}
    for section in ("hosts", "components", "outputs"):
        visibilities[section] = {
            identifier: _visibility(item["visibility"], principals, f"{section}.{identifier}")
            for identifier, item in policy[section].items()
        }
    release_visibilities = {
        identifier: _visibility(item["audience"], principals, f"releases.{identifier}.audience")
        for identifier, item in policy["releases"].items()
    }
    coalitions = _coalitions(policy)
    rows = []
    for coalition in coalitions:
        rows.append(
            {
                "members": sorted(coalition),
                "visible-hosts": sorted(
                    key for key, value in visibilities["hosts"].items() if _is_visible(value, coalition)
                ),
                "visible-components": sorted(
                    key
                    for key, value in visibilities["components"].items()
                    if _is_visible(value, coalition)
                ),
                "visible-outputs": sorted(
                    key for key, value in visibilities["outputs"].items() if _is_visible(value, coalition)
                ),
                "authorized-releases": sorted(
                    key for key, value in release_visibilities.items() if _is_visible(value, coalition)
                ),
            }
        )
    return {"principals": sorted(principals), "coalitions": rows}


def _validate_abi(
    abi: dict[str, Any],
    entry: dict[str, Any],
    policy: dict[str, Any],
    emitted_function_type: str,
) -> tuple[dict[str, Any], set[str]]:
    abi_entry = abi["entry"]
    if abi_entry["id"] != entry["entryId"]:
        raise BoundaryError("ABI entry ID does not match the source annotation")
    if abi_entry["symbol"] != entry["symbol"]:
        raise BoundaryError("ABI entry symbol does not match the C/C++ definition")
    parameters = entry["parameters"]
    component_parameters = {item["id"]: item for item in parameters if item["role"] == "component"}
    root_parameters = {item["id"]: item for item in parameters if item["role"] == "root"}
    if len(component_parameters) + len(root_parameters) != len(parameters):
        raise BoundaryError("source entry repeats a component or root identifier")
    duplicate_boundary_ids = set(component_parameters).intersection(root_parameters)
    if duplicate_boundary_ids:
        raise BoundaryError(
            "source entry reuses logical IDs across components and roots: "
            f"{sorted(duplicate_boundary_ids)!r}"
        )
    if set(abi["carriers"]) != set(component_parameters):
        raise BoundaryError("ABI scalar carriers do not exactly cover source components")
    if set(abi["roots"]) != set(root_parameters):
        raise BoundaryError("ABI roots do not exactly cover source roots")

    used_arguments: dict[int, str] = {}
    argument_rows = []
    for identifier, carrier in abi["carriers"].items():
        parameter = component_parameters[identifier]
        index = carrier["argument"]
        if index != parameter["index"]:
            raise BoundaryError(f"carrier {identifier!r} binds the wrong argument")
        if parameter["isPointer"]:
            raise BoundaryError(f"component {identifier!r} is not a scalar parameter")
        llvm_type = _llvm_scalar(parameter, f"component {identifier}")
        if carrier["llvm-type"] != llvm_type or carrier["bit-width"] != parameter["bitWidth"]:
            raise BoundaryError(f"carrier {identifier!r} disagrees with the Clang AST type")
        component_type = policy["components"].get(identifier, {}).get("type")
        if not isinstance(component_type, str) or not component_type.startswith("bv"):
            raise BoundaryError(
                f"scalar component {identifier!r} requires a bit-vector policy type"
            )
        component_width = int(component_type[2:])
        if component_width != parameter["bitWidth"]:
            raise BoundaryError(f"policy component {identifier!r} width disagrees with the C type")
        used_arguments[index] = identifier
        argument_rows.append(
            {"argument": index, "id": identifier, "kind": "component", "llvm-type": llvm_type}
        )

    root_input_ids: list[str] = []
    output_ids: list[str] = []
    for identifier, root in abi["roots"].items():
        parameter = root_parameters[identifier]
        index = root["argument"]
        if index != parameter["index"]:
            raise BoundaryError(f"root {identifier!r} binds the wrong argument")
        if not parameter["isPointer"]:
            raise BoundaryError(f"root {identifier!r} is not a pointer parameter")
        if root["alignment"] & (root["alignment"] - 1):
            raise BoundaryError(f"root {identifier!r} alignment must be a power of two")
        if index in used_arguments:
            raise BoundaryError(f"argument {index} has more than one ABI binding")
        used_arguments[index] = identifier
        input_id = root.get("input")
        output_id = root.get("output")
        permission = root["permission"]
        initialization = root["initialization"]
        if permission == "read-only":
            if not isinstance(input_id, str) or output_id is not None:
                raise BoundaryError(
                    f"read-only root {identifier!r} requires input and forbids output"
                )
            if initialization != "initialized":
                raise BoundaryError(f"read-only root {identifier!r} must be initialized")
        elif permission == "write-only":
            if input_id is not None or not isinstance(output_id, str):
                raise BoundaryError(
                    f"write-only root {identifier!r} requires output and forbids input"
                )
        elif permission == "read-write":
            if not isinstance(output_id, str):
                raise BoundaryError(
                    f"read-write root {identifier!r} requires output"
                )
            if isinstance(input_id, str) and initialization != "initialized":
                raise BoundaryError(
                    f"read-write root {identifier!r} with input must be initialized"
                )
        else:
            raise BoundaryError(f"root {identifier!r} has an unsupported permission")

        row = {"argument": index, "id": identifier, "kind": "root", "llvm-type": "ptr"}
        if isinstance(input_id, str):
            root_input_ids.append(input_id)
            row["input"] = input_id
        if isinstance(output_id, str):
            output_ids.append(output_id)
            row["output"] = output_id
        argument_rows.append(row)
    if len(root_input_ids) != len(set(root_input_ids)):
        raise BoundaryError("ABI roots repeat a logical input component identifier")
    if len(output_ids) != len(set(output_ids)):
        raise BoundaryError("ABI roots repeat a logical output identifier")
    overlap = set(component_parameters).intersection(root_input_ids)
    if overlap:
        raise BoundaryError(
            "scalar carriers and root inputs repeat logical component IDs: "
            f"{sorted(overlap)!r}"
        )
    expected_policy_components = set(component_parameters).union(root_input_ids)
    if set(policy["components"]) != expected_policy_components:
        raise BoundaryError(
            "policy components do not exactly cover scalar carriers and root inputs"
        )
    for identifier in root_input_ids:
        if policy["components"][identifier]["type"] != "bytes":
            raise BoundaryError(
                f"root input component {identifier!r} requires policy type 'bytes'"
            )
    if set(used_arguments) != set(range(len(parameters))):
        raise BoundaryError("ABI bindings do not cover every source entry argument")

    return_binding = abi_entry["return"]
    return_output = entry["returnOutput"]
    return_type = _return_llvm(entry)
    terminal = abi["terminal-output-order"]
    if return_binding == "void":
        if return_type != "void" or return_output is not None:
            raise BoundaryError("void ABI return disagrees with the source return annotation/type")
        if set(terminal) != {"normal-void"}:
            raise BoundaryError("a void entry requires only terminal-output-order.normal-void")
        terminal_outputs = terminal["normal-void"]
        return_row: str | dict[str, Any] = "void"
    else:
        if return_type == "void" or return_output is None:
            raise BoundaryError("value ABI return requires a source return-output annotation")
        if return_binding["output"] != return_output:
            raise BoundaryError("ABI return output does not match SPS_RETURN_OUTPUT")
        if return_binding["llvm-type"] != return_type:
            raise BoundaryError("ABI return LLVM type disagrees with the Clang AST")
        if return_binding["bit-width"] != entry["returnBitWidth"]:
            raise BoundaryError("ABI return width disagrees with the Clang AST")
        if set(terminal) != {"normal-value"}:
            raise BoundaryError("a value entry requires only terminal-output-order.normal-value")
        output_ids.append(return_output)
        terminal_outputs = terminal["normal-value"]
        return_row = dict(return_binding)
    if len(output_ids) != len(set(output_ids)) or set(terminal_outputs) != set(output_ids):
        raise BoundaryError("terminal output order does not exactly cover logical outputs")
    if set(policy["outputs"]) != set(output_ids):
        raise BoundaryError("policy outputs do not exactly cover ABI terminal outputs")

    if abi_entry["function-type"] != emitted_function_type:
        raise BoundaryError(
            f"ABI function-type mismatch: emitted LLVM has {emitted_function_type!r}"
        )

    covered_pairs: dict[tuple[str, str], str] = {}
    for relation in abi["aliases"]["relations"]:
        unknown = set(relation["roots"]) - set(root_parameters)
        if unknown:
            raise BoundaryError(f"alias relation references unknown roots {sorted(unknown)!r}")
        for left, right in itertools.combinations(sorted(relation["roots"]), 2):
            pair = (left, right)
            if pair in covered_pairs:
                raise BoundaryError(f"alias pair {pair!r} is specified more than once")
            covered_pairs[pair] = relation["relation"]
    required_pairs = set(itertools.combinations(sorted(root_parameters), 2))
    complete_aliases = abi["aliases"]["complete"]
    if complete_aliases and set(covered_pairs) != required_pairs:
        missing = sorted(required_pairs - set(covered_pairs))
        raise BoundaryError(f"complete alias table is missing root pairs {missing!r}")

    parent = {identifier: identifier for identifier in root_parameters}

    def find(identifier: str) -> str:
        while parent[identifier] != identifier:
            parent[identifier] = parent[parent[identifier]]
            identifier = parent[identifier]
        return identifier

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for pair, relation in covered_pairs.items():
        if relation == "same-allocation":
            union(*pair)
    allocation_fields = (
        "extent-bytes",
        "alignment",
        "host",
        "permission",
        "initialization",
        "ownership",
    )
    allocation_classes: dict[str, list[str]] = {}
    for identifier in root_parameters:
        allocation_classes.setdefault(find(identifier), []).append(identifier)
    for members in allocation_classes.values():
        if len(members) < 2:
            continue
        baseline = abi["roots"][members[0]]
        for identifier in members[1:]:
            current = abi["roots"][identifier]
            differing = [
                field for field in allocation_fields if current[field] != baseline[field]
            ]
            if differing:
                raise BoundaryError(
                    "same-allocation roots must agree on concrete root metadata; "
                    f"{members[0]!r} and {identifier!r} differ in {differing!r}"
                )
    for pair, relation in covered_pairs.items():
        if relation == "disjoint" and find(pair[0]) == find(pair[1]):
            raise BoundaryError(
                f"alias pair {pair!r} is disjoint inside one same-allocation class"
            )

    blockers = set()
    if not complete_aliases or any(
        relation == "may-alias" for relation in covered_pairs.values()
    ):
        blockers.add("AliasBindingMismatch")

    return (
        {
            "arguments": sorted(argument_rows, key=lambda item: item["argument"]),
            "return": return_row,
            "terminal-output-order": list(terminal_outputs),
        },
        blockers,
    )


def _validate_releases(
    policy: dict[str, Any], entry: dict[str, Any], helpers: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    components = policy["components"]
    calls = sorted(entry.get("calls", []), key=lambda item: item.get("offset", -1))
    resolved: list[dict[str, Any]] = []
    bound_sites: set[tuple[str, int]] = set()
    for release_id, release in policy["releases"].items():
        helper_id = release["locator"]["helper"]
        if helper_id not in helpers:
            raise BoundaryError(f"release {release_id!r} references unknown helper {helper_id!r}")
        helper = helpers[helper_id]
        direct_calls = [
            item
            for item in calls
            if item.get("direct") is True
            and item.get("calleeIdentity") == helper["identity"]
        ]
        ordinal = release["locator"]["call-ordinal"]
        if ordinal >= len(direct_calls):
            raise BoundaryError(
                f"release {release_id!r} call ordinal {ordinal} is out of range for helper {helper_id!r}"
            )
        site = (helper_id, ordinal)
        if site in bound_sites:
            raise BoundaryError(f"release helper site {site!r} is bound more than once")
        bound_sites.add(site)
        width = release["type"]["width"]
        if release["multiplicity"] != 1:
            raise BoundaryError(
                f"release {release_id!r} multiplicity must be 1 for a single source call locator"
            )
        expression_components = _expression_components(release["expression"])
        unknown = expression_components - set(components)
        if unknown:
            raise BoundaryError(
                f"release {release_id!r} expression references unknown components {sorted(unknown)!r}"
            )
        _validate_expression_width(
            release["expression"], components, width, f"release {release_id!r}.expression"
        )
        footprint = release["payload-footprint"]
        if footprint != sorted(footprint):
            raise BoundaryError(f"release {release_id!r} payload footprint must be sorted")
        payload_bytes = (width + 7) // 8
        if any(index >= payload_bytes for index in footprint):
            raise BoundaryError(f"release {release_id!r} footprint is outside its payload")
        resolved.append(
            {
                "id": release_id,
                "helper": helper_id,
                "helper-symbol": helper["symbol"],
                "call-ordinal": ordinal,
                "source-offset": direct_calls[ordinal].get("offset"),
            }
        )
    return sorted(resolved, key=lambda item: item["id"])


def resolve(
    *,
    source: Path,
    support_sources: list[Path] | None = None,
    policy_path: Path,
    abi_path: Path,
    extractor: Path,
    clang: Path,
    include: Path = DEFAULT_INCLUDE,
    schemas: Path = DEFAULT_SCHEMAS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_input = source.absolute()
    policy_input = policy_path.absolute()
    abi_input = abi_path.absolute()
    for path, label in (
        (source_input, "primary source"),
        (policy_input, "policy sidecar"),
        (abi_input, "ABI sidecar"),
    ):
        if path.is_symlink():
            raise BoundaryError(f"{label} must not be a symlink: {path}")
    source = source_input.resolve()
    policy_path = policy_input.resolve()
    abi_path = abi_input.resolve()
    if source.parent != policy_path.parent or source.parent != abi_path.parent:
        raise BoundaryError("source, policy, and ABI must be siblings in one case directory")
    if policy_path.name != "policy.sps.yaml" or abi_path.name != "abi.sps.yaml":
        raise BoundaryError("case sidecars must be named policy.sps.yaml and abi.sps.yaml")
    case_sources = sorted(
        path
        for path in source.parent.iterdir()
        if path.suffix in SOURCE_SUFFIXES and (path.is_file() or path.is_symlink())
    )
    for path in case_sources:
        if path.is_symlink():
            raise BoundaryError(f"case-owned translation unit must not be a symlink: {path.name}")
    discovered_support = [path for path in case_sources if path != source]
    if support_sources is None:
        support_sources = discovered_support
    else:
        explicit_support: list[Path] = []
        for support_input in support_sources:
            absolute = support_input.absolute()
            if absolute.is_symlink():
                raise BoundaryError(
                    f"support source must not be a symlink: {support_input}"
                )
            support = absolute.resolve()
            if support.parent != source.parent or support.suffix not in SOURCE_SUFFIXES:
                raise BoundaryError(
                    f"support source must be a sibling C/C++ translation unit: {support_input}"
                )
            explicit_support.append(support)
        if len(set(explicit_support)) != len(explicit_support):
            raise BoundaryError("support sources must not be repeated")
        if set(explicit_support) != set(discovered_support):
            raise BoundaryError(
                "explicit support sources must exactly name every non-primary "
                "case translation unit"
            )
        support_sources = sorted(explicit_support)
    if not include.joinpath("sps", "annotations.h").is_file():
        raise BoundaryError(f"SPS annotation header is missing below {include}")

    policy = _load_yaml(policy_path, schemas / "policy.schema.json")
    abi = _load_yaml(abi_path, schemas / "abi.schema.json")
    contracts_path = source.parent / "contracts.sps.yaml"
    contracts: dict[str, Any] | None = None
    if os.path.lexists(contracts_path):
        if contracts_path.is_symlink() or not contracts_path.is_file():
            raise BoundaryError(
                "optional contracts.sps.yaml must be a case-local regular file"
            )
        contracts = _load_yaml(contracts_path, AUTHORING_CONTRACT_SCHEMA)
    if (
        Path(abi["source"]).name != abi["source"]
        or Path(abi["source"]).suffix not in SOURCE_SUFFIXES
        or abi["source"] != source.name
    ):
        raise BoundaryError("ABI source must be the case-local source basename")
    if source not in case_sources:
        raise BoundaryError("ABI primary source is not a local case translation unit")

    toolchain_arguments = _extractor_toolchain_arguments(clang)
    ast = _run_extractor(source, extractor, include, toolchain_arguments)
    entry, helpers = _decode_ast(ast, require_entry=True, source=source.name)
    assert entry is not None
    for support in support_sources:
        support_ast = _run_extractor(
            support, extractor, include, toolchain_arguments
        )
        _, support_helpers = _decode_ast(
            support_ast, require_entry=False, source=support.name
        )
        for helper_id, helper in support_helpers.items():
            if helper_id in helpers:
                raise BoundaryError(
                    f"helper ID {helper_id!r} is defined in more than one translation unit"
                )
            helpers[helper_id] = helper
        _normal_llvm(support, clang, include, None)
    emitted_function_type, rendered_llvm = _normal_llvm(
        source, clang, include, abi["entry"]["symbol"]
    )
    assert emitted_function_type is not None
    abi_resolution, abi_blockers = _validate_abi(
        abi, entry, policy, emitted_function_type
    )
    contract_resolution = _validate_contracts(
        contracts,
        entry=entry,
        abi=abi,
        policy=policy,
        rendered_llvm=rendered_llvm,
    )
    policy_resolution = _validate_policy(policy, entry, abi, contract_resolution)
    releases = _validate_releases(policy, entry, helpers)

    resolved = {
        "source": source.name,
        "support-sources": [path.name for path in support_sources],
        "entry": {
            "id": entry["entryId"],
            "symbol": entry["symbol"],
            "host": abi["entry"]["host"],
            "function-type": abi["entry"]["function-type"],
        },
        **abi_resolution,
        **policy_resolution,
        "releases": releases,
        "contracts": contract_resolution,
    }
    completed = sorted(
        {
            "ABICarriersResolved",
            "CoalitionClosureEnumerated",
            "NormalLLVMAnnotationResidueAbsent",
            "PolicyIdsResolved",
            "ReleaseLocatorResolved",
            "SourceAnnotationsMatched",
            "SupportTranslationUnitsValidated",
        }
    )
    blockers = set(abi_blockers)
    if releases:
        blockers.add("ReleaseCarrierMismatch")
    if contract_resolution:
        completed.append("ContractLocatorsResolved")
        completed.sort()
        blockers.add("OpenModelObligations")
    report = {
        "formatId": "SPS-Harness-Stage-Report-v2",
        "fixtureTier": {"tag": "CandidateOnly"},
        "stageId": "SourceBoundaryValidation",
        "completedChecks": completed,
        "findings": [],
        "blockers": sorted(blockers),
        "claimable": False,
        "modelStatus": {"tag": "NotComputed"},
    }
    return resolved, report


def describe(resolved: Mapping[str, Any], report: Mapping[str, Any]) -> str:
    lines = [
        f"ENTRY {resolved['entry']['id']}",
        f"  source: {resolved['source']}",
        f"  symbol: {resolved['entry']['symbol']}",
        f"  function type: {resolved['entry']['function-type']}",
    ]
    for argument in resolved["arguments"]:
        lines.append(
            f"  argument {argument['argument']}: {argument['kind']} "
            f"{argument['id']} ({argument['llvm-type']})"
        )
    for row in resolved["coalitions"]:
        label = "{" + ",".join(row["members"]) + "}"
        lines.extend(
            [
                f"COALITION {label}",
                "  visible outputs: " + (", ".join(row["visible-outputs"]) or "none"),
                "  authorized releases: "
                + (", ".join(row["authorized-releases"]) or "none"),
            ]
        )
    if report["blockers"]:
        lines.append("BLOCKERS " + ", ".join(report["blockers"]))
    return "\n".join(lines) + "\n"
