#!/usr/bin/env python3
"""Versioned structural fact extractors for Snapshot V3 endpoints.

The extractors expose small typed registries.  Snapshot matchers select facts;
they never provide regular expressions or executable parsing rules.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


class ExtractorError(ValueError):
    pass


EXTRACTORS = {
    "mlir-structure-v1": "mlir",
    "llvm-ir-structure-v1": "llvm-ir",
    "mir-structure-v1": "mir",
    "assembly-structure-v1": "assembly",
    "object-inventory-v1": "object-inventory",
}

COMMON_FUNCTION_FACTS = frozenset({"function.names"})
MLIR_FACTS = COMMON_FUNCTION_FACTS | frozenset(
    {
        "function.signatures",
        "function.argument_names",
        "function.attribute_keys",
        "function.attributes",
        "argument.attribute_keys",
        "argument.attributes",
        "operation.names",
        "operation.argument_dependencies",
        "operation.annotations",
        "constant.values",
        "conversion.shapes",
        "call.callees",
        "branch.conditional",
        "branch.condition_roots",
        "branch.successor_shapes",
        "memory.store_edges",
        "memory.store_accesses",
        "memory.load_roots",
        "memory.load_accesses",
        "memory.alloca_counts",
        "return.roots",
        "return.access_roots",
        "gep.offsets",
        "gep.accesses",
        "def_use.edges",
    }
)
LLVM_FACTS = COMMON_FUNCTION_FACTS | frozenset(
    {
        "operation.names",
        "call.callees",
        "branch.conditional",
        "branch.condition_roots",
        "branch.successor_shapes",
        "memory.store_edges",
        "memory.load_roots",
        "return.roots",
        "gep.offsets",
        "constant.values",
        "def_use.edges",
    }
)
ASSEMBLY_FACTS = COMMON_FUNCTION_FACTS | frozenset(
    {"instruction.mnemonics", "branch.conditional", "call.callees"}
)
MIR_FACTS = COMMON_FUNCTION_FACTS | frozenset(
    {"machine.opcodes", "stack.objects"}
)
OBJECT_FACTS = frozenset(
    {"object.symbols", "object.relocations", "object.sections"}
)

STATIC_FACTS = {
    "mlir-structure-v1": MLIR_FACTS,
    "llvm-ir-structure-v1": LLVM_FACTS,
    "assembly-structure-v1": ASSEMBLY_FACTS,
    "mir-structure-v1": MIR_FACTS,
    "object-inventory-v1": OBJECT_FACTS,
}
DYNAMIC_FACTS = {
    "mlir-structure-v1": ("operation.occurrences.", "call.occurrences."),
    "llvm-ir-structure-v1": ("operation.occurrences.", "call.occurrences."),
    "assembly-structure-v1": ("instruction.occurrences.",),
    "mir-structure-v1": ("machine.occurrences.",),
    "object-inventory-v1": (),
}
FACT_SUFFIX = re.compile(r"[A-Za-z_.$][A-Za-z0-9_.$@+-]*\Z")


def _fact_is_known(extractor: str, fact: str) -> bool:
    if fact in STATIC_FACTS[extractor]:
        return True
    for prefix in DYNAMIC_FACTS[extractor]:
        if fact.startswith(prefix) and FACT_SUFFIX.fullmatch(fact[len(prefix) :]):
            return True
    return False


def validate_properties(
    representation: str, extractor: str, properties: Mapping[str, Any]
) -> None:
    expected = EXTRACTORS.get(extractor)
    if expected is None:
        raise ExtractorError(f"unknown structural extractor {extractor!r}")
    if representation != expected:
        raise ExtractorError(
            f"extractor {extractor!r} requires representation {expected!r}"
        )
    unknown = sorted(fact for fact in properties if not _fact_is_known(extractor, fact))
    if unknown:
        raise ExtractorError(f"unknown {extractor} facts {unknown}")


def _json_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    try:
        return json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(
            right, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError):
        return left == right


def _contains(items: Sequence[Any], expected: Any) -> bool:
    return any(_json_equal(item, expected) for item in items)


def _ordered_subsequence(items: Sequence[Any], expected: Sequence[Any]) -> bool:
    position = 0
    for wanted in expected:
        while position < len(items) and not _json_equal(items[position], wanted):
            position += 1
        if position == len(items):
            return False
        position += 1
    return True


def match_properties(
    properties: Mapping[str, Any], facts: Mapping[str, Any]
) -> list[str]:
    """Return focused mismatch descriptions; an empty result is a match."""

    mismatches: list[str] = []
    for fact, matcher_value in properties.items():
        if fact not in facts:
            mismatches.append(f"{fact}: extractor did not emit the requested fact")
            continue
        actual = facts[fact]
        matcher = dict(matcher_value)
        if "equals" in matcher and not _json_equal(actual, matcher["equals"]):
            mismatches.append(
                f"{fact}: expected equals {matcher['equals']!r}, got {actual!r}"
            )
        for operator, should_be_present in (
            ("contains_all", True),
            ("not_contains_any", False),
        ):
            if operator not in matcher:
                continue
            if not isinstance(actual, list):
                mismatches.append(f"{fact}: {operator} requires a list fact")
                continue
            offending = [
                item
                for item in matcher[operator]
                if _contains(actual, item) is not should_be_present
            ]
            if offending:
                description = "missing" if should_be_present else "unexpected"
                mismatches.append(f"{fact}: {description} values {offending!r}")
        if "ordered_subsequence" in matcher:
            expected = matcher["ordered_subsequence"]
            if not isinstance(actual, list):
                mismatches.append(f"{fact}: ordered_subsequence requires a list fact")
            elif not _ordered_subsequence(actual, expected):
                mismatches.append(
                    f"{fact}: {expected!r} is not an ordered subsequence of {actual!r}"
                )
        if "count" in matcher:
            if not isinstance(actual, list):
                mismatches.append(f"{fact}: count requires a list fact")
                continue
            count = len(actual)
            bounds = matcher["count"]
            if "eq" in bounds and count != bounds["eq"]:
                mismatches.append(f"{fact}: expected count {bounds['eq']}, got {count}")
            if "min" in bounds and count < bounds["min"]:
                mismatches.append(
                    f"{fact}: expected count >= {bounds['min']}, got {count}"
                )
            if "max" in bounds and count > bounds["max"]:
                mismatches.append(
                    f"{fact}: expected count <= {bounds['max']}, got {count}"
                )
    return mismatches


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _split_top_level(value: str, delimiter: str = ",") -> list[str]:
    parts: list[str] = []
    start = 0
    stack: list[str] = []
    quoted = False
    escaped = False
    pairs = {")": "(", "]": "[", "}": "{", ">": "<"}
    for index, character in enumerate(value):
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character in "([{<":
            stack.append(character)
        elif character in pairs:
            if stack and stack[-1] == pairs[character]:
                stack.pop()
        elif character == delimiter and not stack:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return [part for part in parts if part]


def _matching(text: str, opening: int, left: str, right: str) -> int:
    depth = 0
    quoted = False
    escaped = False
    for index in range(opening, len(text)):
        character = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character == left:
            depth += 1
        elif character == right:
            depth -= 1
            if depth == 0:
                return index
    raise ExtractorError(f"unterminated {left}{right} region")


def _braced_segments(text: str) -> list[str]:
    result: list[str] = []
    index = 0
    while True:
        opening = text.find("{", index)
        if opening < 0:
            return result
        closing = _matching(text, opening, "{", "}")
        result.append(text[opening + 1 : closing])
        index = closing + 1


def _attributes(text: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for item in _split_top_level(text):
        match = re.match(
            r'(?:"([A-Za-z_][A-Za-z0-9_.-]*)"|([A-Za-z_][A-Za-z0-9_.-]*))'
            r"\s*=\s*(.+)\Z",
            item,
            re.S,
        )
        if match:
            result.append((match.group(1) or match.group(2), _compact(match.group(3))))
    return result


def _mlir_signature(
    text: str, symbol: str
) -> tuple[str, str, tuple[int, int] | None]:
    pattern = re.compile(
        rf"(?m)^\s*llvm\.func\b[^@\n]*@{re.escape(symbol)}\s*\("
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ExtractorError(
            f"MLIR symbol {symbol!r} must name exactly one llvm.func"
        )
    start = matches[0].start()
    paren = text.find("(", matches[0].start(), matches[0].end())
    close_paren = _matching(text, paren, "(", ")")
    cursor = close_paren + 1
    next_function = re.search(r"(?m)^\s*llvm\.func\b", text[cursor:])
    limit = cursor + next_function.start() if next_function else len(text)
    header_end = text.find("\n", close_paren, limit)
    if header_end < 0:
        header_end = limit
    body_region: tuple[int, int] | None = None
    opening = text.find("{", cursor, limit)
    if opening >= 0:
        prefix = text[cursor:opening].rstrip()
        if prefix.endswith("attributes"):
            attribute_close = _matching(text, opening, "{", "}")
            header_end = attribute_close + 1
            candidate = attribute_close + 1
            while candidate < limit and text[candidate].isspace():
                candidate += 1
            if candidate < limit and text[candidate] == "{":
                body_region = (candidate, _matching(text, candidate, "{", "}"))
        else:
            body_region = (opening, _matching(text, opening, "{", "}"))
            header_end = opening
    return text[start:header_end], text[paren + 1 : close_paren], body_region


def _mlir_type(value: str) -> str:
    """Canonicalize only insignificant layout in an MLIR type spelling."""

    compact = _compact(value)
    return re.sub(r"\s*([,()<>])\s*", r"\1", compact)


def _mlir_argument_type(argument: str) -> str:
    value = argument.split(":", 1)[1].strip() if ":" in argument else argument.strip()
    stack: list[str] = []
    quoted = False
    escaped = False
    pairs = {")": "(", "]": "[", ">": "<"}
    for index, character in enumerate(value):
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character in "([<":
            stack.append(character)
        elif character in pairs:
            if stack and stack[-1] == pairs[character]:
                stack.pop()
        elif character == "{" and not stack:
            value = value[:index]
            break
    return _mlir_type(value)


def _mlir_function_signature(header: str, arguments: str, symbol: str) -> str:
    argument_types = [_mlir_argument_type(item) for item in _split_top_level(arguments)]
    opening = header.find("(")
    if opening < 0:
        raise ExtractorError(f"MLIR function {symbol!r} has no argument list")
    closing = _matching(header, opening, "(", ")")
    suffix = header[closing + 1 :]
    attributes = re.search(r"\battributes\s*\{", suffix)
    if attributes:
        suffix = suffix[: attributes.start()]
    suffix = suffix.strip()
    if suffix:
        result = re.match(r"->\s*(.+)\Z", suffix, re.S)
        if not result:
            raise ExtractorError(f"malformed MLIR result type for {symbol!r}")
        result_type = _mlir_type(result.group(1))
    else:
        result_type = "()"
    return f"{symbol}|({','.join(argument_types)})->{result_type}"


def _mlir_function(text: str, symbol: str) -> tuple[str, str, str]:
    header, arguments, body_region = _mlir_signature(text, symbol)
    if body_region is None:
        raise ExtractorError(f"MLIR function {symbol!r} has no body")
    body_open, body_close = body_region
    return header, arguments, text[body_open + 1 : body_close]


def _mlir_statements(body: str) -> list[str]:
    statements: list[str] = []
    pending = ""
    depth = 0
    for raw_line in body.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line or line.startswith("^") or line == "}":
            continue
        pending = (pending + " " + line).strip()
        depth += sum(line.count(char) for char in "([{<")
        depth -= sum(line.count(char) for char in ")]}>")
        # Most MLIR operations are line-complete.  Continue only while delimiters
        # are unbalanced; this preserves branch successor argument lists.
        if depth <= 0:
            statements.append(pending)
            pending = ""
            depth = 0
    if pending:
        statements.append(pending)
    return statements


def _operation_name(statement: str) -> str | None:
    match = re.search(r"\b(llvm\.[A-Za-z_.$][A-Za-z0-9_.$-]*)\b", statement)
    return match.group(1) if match else None


def _ssa_result(statement: str) -> str | None:
    match = re.match(r"%([A-Za-z0-9_.$-]+)(?:\s*:[^=]+)?\s*=", statement)
    return match.group(1) if match else None


def _ssa_operands(statement: str) -> list[str]:
    assignment = re.match(
        r"%[A-Za-z0-9_.$-]+(?:\s*:[^=]+)?\s*=\s*(.*)\Z", statement, re.S
    )
    rhs = assignment.group(1) if assignment else statement
    return re.findall(r"%([A-Za-z0-9_.$-]+)", rhs)


def _root(roots: Mapping[str, str], name: str) -> str:
    return roots.get(name, f"ssa:{name}")


def _constant_fact(statement: str, symbol: str) -> tuple[str, str] | None:
    match = re.search(
        r"llvm\.mlir\.constant\((.*?)\)\s*:\s*([^\s,}\)]+)", statement
    )
    if not match:
        return None
    literal = _compact(match.group(1))
    result_type = _compact(match.group(2))
    return f"{symbol}|{result_type}|{literal}", f"constant:{result_type}:{literal}"


def _mlir_gep_access(
    statement: str, roots: Mapping[str, str]
) -> tuple[str, list[str]] | None:
    match = re.search(
        r"\bllvm\.getelementptr\s+%([A-Za-z0-9_.$-]+)\s*\[(.*?)\]",
        statement,
        re.S,
    )
    if not match:
        return None
    base = _root(roots, match.group(1))
    offsets: list[str] = []
    for item in _split_top_level(match.group(2)):
        ssa = re.fullmatch(r"%([A-Za-z0-9_.$-]+)", item.strip())
        if ssa:
            offset = _root(roots, ssa.group(1))
            constant = re.fullmatch(r"constant:[^:]+:(-?[0-9]+)(?:\s*:\s*[^:]+)?", offset)
            offsets.append(constant.group(1) if constant else offset)
            continue
        literal = re.match(r"\s*(-?[0-9]+)(?:\s*:\s*[^,]+)?\s*\Z", item)
        offsets.append(literal.group(1) if literal else _compact(item))
    return base, offsets


def _mlir_alloca_shape(
    statement: str, roots: Mapping[str, str]
) -> tuple[str, str] | None:
    match = re.search(
        r"\bllvm\.alloca\s+(%[A-Za-z0-9_.$-]+|-?[0-9]+)\s+x\s+(.+?)\s*:",
        statement,
        re.S,
    )
    if not match:
        return None
    raw_count = match.group(1)
    if raw_count.startswith("%"):
        count = _root(roots, raw_count[1:])
        constant = re.fullmatch(
            r"constant:[^:]+:(-?[0-9]+)(?:\s*:\s*[^:]+)?", count
        )
        if constant:
            count = constant.group(1)
    else:
        count = raw_count
    element_type = match.group(2).split("{", 1)[0]
    return count, _mlir_type(element_type)


def _mlir_conversion_shape(statement: str, function: str) -> str | None:
    match = re.search(
        r"\b(llvm\.(?:trunc|zext|sext))\s+%[A-Za-z0-9_.$-]+"
        r"\s*:\s*([^\s]+)\s+to\s+([^\s,}\)]+)",
        statement,
    )
    if not match:
        return None
    return (
        f"{function}|op={match.group(1)}|from={_mlir_type(match.group(2))}"
        f"|to={_mlir_type(match.group(3))}"
    )


def _mlir_argument_origins(
    arguments_text: str, body: str, statements: Sequence[str]
) -> dict[str, frozenset[int]]:
    """Compute entry-argument provenance for SSA values.

    This is deliberately a structural data-flow fact, not a secrecy judgment.
    Equations are solved to a fixed point so block arguments and loop-carried
    values retain their entry-argument origins even when their definitions are
    not in simple textual order.
    """

    origins: dict[str, set[int]] = {}
    for index, argument in enumerate(_split_top_level(arguments_text)):
        match = re.match(r"\s*%([A-Za-z0-9_.$-]+)\s*:", argument)
        if match:
            origins[match.group(1)] = {index}

    equations: list[tuple[str, tuple[str, ...]]] = []
    for statement in statements:
        result = _ssa_result(statement)
        if result is not None:
            equations.append((result, tuple(_ssa_operands(statement))))

    block_arguments: dict[str, tuple[str, ...]] = {}
    for match in re.finditer(
        r"(?m)^\s*\^([A-Za-z0-9_.$-]+)\s*(?:\(([^\n]*)\))?\s*:", body
    ):
        parameters = tuple(
            name.group(1)
            for item in _split_top_level(match.group(2) or "")
            if (name := re.match(r"\s*%([A-Za-z0-9_.$-]+)\s*:", item))
        )
        block_arguments[match.group(1)] = parameters

    for statement in statements:
        operation = _operation_name(statement)
        if operation not in {"llvm.br", "llvm.cond_br"}:
            continue
        for successor in re.finditer(
            r"\^([A-Za-z0-9_.$-]+)(?:\((.*?)\))?", statement
        ):
            parameters = block_arguments.get(successor.group(1), ())
            actuals = tuple(
                re.findall(r"%([A-Za-z0-9_.$-]+)", successor.group(2) or "")
            )
            equations.extend(
                (parameter, (actual,))
                for parameter, actual in zip(parameters, actuals)
            )

    changed = True
    while changed:
        changed = False
        for result, operands in equations:
            propagated: set[int] = set()
            for operand in operands:
                propagated.update(origins.get(operand, ()))
            destination = origins.setdefault(result, set())
            before = len(destination)
            destination.update(propagated)
            changed |= len(destination) != before

    return {name: frozenset(indices) for name, indices in origins.items()}


def _extract_mlir(text: str, function: str) -> dict[str, Any]:
    header, arguments_text, body = _mlir_function(text, function)
    function_names = re.findall(
        r"(?m)^\s*llvm\.func\b[^@\n]*@([A-Za-z_.$][A-Za-z0-9_.$-]*)", text
    )
    facts: dict[str, Any] = {
        "function.names": function_names,
        "function.signatures": [],
        "function.argument_names": [],
        "function.attribute_keys": [],
        "function.attributes": [],
        "argument.attribute_keys": [],
        "argument.attributes": [],
        "operation.names": [],
        "operation.argument_dependencies": [],
        "operation.annotations": [],
        "constant.values": [],
        "conversion.shapes": [],
        "call.callees": [],
        "branch.conditional": [],
        "branch.condition_roots": [],
        "branch.successor_shapes": [],
        "memory.store_edges": [],
        "memory.store_accesses": [],
        "memory.load_roots": [],
        "memory.load_accesses": [],
        "memory.alloca_counts": [],
        "return.roots": [],
        "return.access_roots": [],
        "gep.offsets": [],
        "gep.accesses": [],
        "def_use.edges": [],
    }

    roots: dict[str, str] = {}
    access_roots: dict[str, str] = {}
    # Function and argument attributes are module inventory facts.  This lets a
    # scoped entry endpoint retain contract facts on a helper without making the
    # helper's operation stream part of the entry's structural scope.
    for inventory_function in function_names:
        try:
            inventory_header, inventory_arguments, _ = _mlir_signature(
                text, inventory_function
            )
        except ExtractorError:
            continue
        facts["function.signatures"].append(
            _mlir_function_signature(
                inventory_header, inventory_arguments, inventory_function
            )
        )
        attributes_match = re.search(
            r"\battributes\s*\{(.*?)\}\s*\Z", inventory_header, re.S
        )
        if attributes_match:
            for key, value in _attributes(attributes_match.group(1)):
                facts["function.attribute_keys"].append(
                    f"{inventory_function}|{key}"
                )
                facts["function.attributes"].append(
                    f"{inventory_function}|{key}|{value}"
                )
        for index, argument in enumerate(_split_top_level(inventory_arguments)):
            for segment in _braced_segments(argument):
                for key, value in _attributes(segment):
                    facts["argument.attribute_keys"].append(
                        f"{inventory_function}|{index}|{key}"
                    )
                    facts["argument.attributes"].append(
                        f"{inventory_function}|{index}|{key}|{value}"
                    )

    for index, argument in enumerate(_split_top_level(arguments_text)):
        match = re.match(r"\s*%([A-Za-z0-9_.$-]+)\s*:", argument)
        if not match:
            continue
        name = match.group(1)
        roots[name] = f"arg:{index}"
        access_roots[name] = f"arg:{index}"
        facts["function.argument_names"].append(f"{function}|{index}|{name}")

    statements = _mlir_statements(body)
    argument_origins = _mlir_argument_origins(arguments_text, body, statements)
    occurrences: dict[str, list[str]] = {}
    call_occurrences: dict[str, list[str]] = {}
    transparent = {
        "llvm.bitcast",
        "llvm.addrspacecast",
        "llvm.inttoptr",
        "llvm.ptrtoint",
        "llvm.getelementptr",
    }
    access_transparent = {
        "llvm.bitcast",
        "llvm.addrspacecast",
        "llvm.inttoptr",
        "llvm.ptrtoint",
        "llvm.trunc",
        "llvm.zext",
        "llvm.sext",
    }
    for ordinal, statement in enumerate(statements):
        operation = _operation_name(statement)
        if operation is None:
            continue
        facts["operation.names"].append(operation)
        occurrence = f"{function}|{ordinal}"
        occurrences.setdefault(operation, []).append(occurrence)
        operands = _ssa_operands(statement)
        for index, operand in enumerate(operands):
            facts["def_use.edges"].append(
                f"{function}|user={ordinal}|op={operation}|operand={index}|root={_root(roots, operand)}"
            )
            dependencies = sorted(argument_origins.get(operand, ()))
            if dependencies:
                facts["operation.argument_dependencies"].append(
                    f"{function}|{operation}|operand={index}|args="
                    + ",".join(str(item) for item in dependencies)
                )
        for segment in _braced_segments(statement):
            for key, value in _attributes(segment):
                facts["operation.annotations"].append(
                    f"{function}|{ordinal}|{operation}|{key}|{value}"
                )

        constant = _constant_fact(statement, function)
        conversion = _mlir_conversion_shape(statement, function)
        result = _ssa_result(statement)
        if constant is not None:
            facts["constant.values"].append(constant[0])
            if result:
                roots[result] = constant[1]
                access_roots[result] = constant[1]
        if conversion is not None:
            facts["conversion.shapes"].append(conversion)

        callee_match = re.search(
            r"\bllvm\.call\b[^@\n]*@([A-Za-z_.$][A-Za-z0-9_.$-]*)", statement
        )
        if callee_match:
            callee = callee_match.group(1)
            facts["call.callees"].append(callee)
            call_occurrences.setdefault(callee, []).append(occurrence)

        if operation == "llvm.cond_br":
            facts["branch.conditional"].append(occurrence)
            condition = _root(roots, operands[0]) if operands else "missing"
            facts["branch.condition_roots"].append(f"{function}|{condition}")
            successors: list[tuple[str, list[str]]] = []
            for successor in re.finditer(
                r"\^([A-Za-z0-9_.$-]+)(?:\((.*?)\))?", statement
            ):
                argument_roots = [
                    _root(roots, name)
                    for name in re.findall(r"%([A-Za-z0-9_.$-]+)", successor.group(2) or "")
                ]
                successors.append((successor.group(1), argument_roots))
            targets = [item[0] for item in successors]
            encoded_args = ";".join(
                ",".join(argument_roots) for _, argument_roots in successors
            )
            facts["branch.successor_shapes"].append(
                f"{function}|targets={','.join(targets)}|same-target="
                f"{str(len(set(targets)) == 1).lower()}|args={encoded_args}"
            )
        elif operation == "llvm.alloca":
            shape = _mlir_alloca_shape(statement, access_roots)
            if shape is not None:
                count, element_type = shape
                facts["memory.alloca_counts"].append(
                    f"{function}|count={count}|element={element_type}"
                )
                if result:
                    access_roots[result] = (
                        f"alloca(count={count};element={element_type})"
                    )
        elif operation == "llvm.store" and len(operands) >= 2:
            facts["memory.store_edges"].append(
                f"{function}|value={_root(roots, operands[0])}"
                f"|address={_root(roots, operands[1])}"
            )
            facts["memory.store_accesses"].append(
                f"{function}|value={_root(access_roots, operands[0])}"
                f"|address={_root(access_roots, operands[1])}"
            )
        elif operation == "llvm.load" and operands:
            facts["memory.load_roots"].append(
                f"{function}|{_root(roots, operands[0])}"
            )
            facts["memory.load_accesses"].append(
                f"{function}|address={_root(access_roots, operands[0])}"
            )
        elif operation == "llvm.return":
            facts["return.roots"].extend(
                f"{function}|{_root(roots, operand)}" for operand in operands
            )
            facts["return.access_roots"].extend(
                f"{function}|{_root(access_roots, operand)}" for operand in operands
            )
        elif operation == "llvm.getelementptr" and operands:
            facts["gep.offsets"].append(
                f"{function}|base={_root(roots, operands[0])}|offsets="
                + ",".join(_root(roots, item) for item in operands[1:])
            )
            access = _mlir_gep_access(statement, access_roots)
            if access is not None:
                base, offsets = access
                facts["gep.accesses"].append(
                    f"{function}|base={base}|offsets={','.join(offsets)}"
                )
                if result:
                    access_roots[result] = (
                        f"gep(base={base};offsets={','.join(offsets)})"
                    )

        if result and result not in roots:
            if operation in transparent and operands:
                roots[result] = _root(roots, operands[0])
            elif callee_match:
                roots[result] = f"call:{callee_match.group(1)}"
            else:
                roots[result] = f"op:{operation}:{ordinal}"
        if result and result not in access_roots:
            if operation in access_transparent and operands:
                access_roots[result] = _root(access_roots, operands[0])
            elif callee_match:
                access_roots[result] = f"call:{callee_match.group(1)}"
            else:
                access_roots[result] = f"op:{operation}:{ordinal}"

    for operation, rows in occurrences.items():
        facts[f"operation.occurrences.{operation}"] = rows
    for callee, rows in call_occurrences.items():
        facts[f"call.occurrences.{callee}"] = rows
    return facts


def _llvm_function(text: str, symbol: str) -> tuple[str, str]:
    pattern = re.compile(
        rf"(?m)^define\b[^@\n]*@{re.escape(symbol)}\s*\((.*?)\)[^\n]*\{{"
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ExtractorError(
            f"LLVM IR scope {symbol!r} must name exactly one function definition"
        )
    opening = text.find("{", matches[0].start(), matches[0].end())
    closing = _matching(text, opening, "{", "}")
    return matches[0].group(1), text[opening + 1 : closing]


def _llvm_opcode(statement: str) -> str | None:
    rhs = statement.split("=", 1)[1].strip() if "=" in statement else statement.strip()
    rhs = re.sub(r"^(?:tail|musttail|notail)\s+", "", rhs)
    match = re.match(r"([A-Za-z][A-Za-z0-9_.-]*)\b", rhs)
    return match.group(1) if match else None


def _extract_llvm(text: str, function: str) -> dict[str, Any]:
    arguments_text, body = _llvm_function(text, function)
    names = re.findall(
        r"(?m)^(?:define|declare)\b[^@\n]*@([A-Za-z_.$][A-Za-z0-9_.$-]*)", text
    )
    facts: dict[str, Any] = {
        "function.names": names,
        "operation.names": [],
        "call.callees": [],
        "branch.conditional": [],
        "branch.condition_roots": [],
        "branch.successor_shapes": [],
        "memory.store_edges": [],
        "memory.load_roots": [],
        "return.roots": [],
        "gep.offsets": [],
        "constant.values": [],
        "def_use.edges": [],
    }
    roots: dict[str, str] = {}
    for index, argument in enumerate(_split_top_level(arguments_text)):
        names_in_argument = re.findall(r"%([A-Za-z0-9_.$-]+)", argument)
        if names_in_argument:
            roots[names_in_argument[-1]] = f"arg:{index}"
    occurrences: dict[str, list[str]] = {}
    call_occurrences: dict[str, list[str]] = {}
    statements = [
        line.split(";", 1)[0].strip()
        for line in body.splitlines()
        if line.split(";", 1)[0].strip()
        and not line.split(";", 1)[0].strip().endswith(":")
    ]
    for ordinal, statement in enumerate(statements):
        opcode = _llvm_opcode(statement)
        if opcode is None:
            continue
        facts["operation.names"].append(opcode)
        occurrence = f"{function}|{ordinal}"
        occurrences.setdefault(opcode, []).append(occurrence)
        operands = _ssa_operands(statement)
        for index, operand in enumerate(operands):
            facts["def_use.edges"].append(
                f"{function}|user={ordinal}|op={opcode}|operand={index}|root={_root(roots, operand)}"
            )
        result = _ssa_result(statement)
        call = re.search(r"\bcall\b[^@\n]*@([A-Za-z_.$][A-Za-z0-9_.$-]*)", statement)
        if call:
            callee = call.group(1)
            facts["call.callees"].append(callee)
            call_occurrences.setdefault(callee, []).append(occurrence)
        if opcode == "br" and re.search(r"\bbr\s+i1\b", statement):
            facts["branch.conditional"].append(occurrence)
            facts["branch.condition_roots"].append(
                f"{function}|{_root(roots, operands[0]) if operands else 'missing'}"
            )
            targets = re.findall(r"label\s+%([A-Za-z0-9_.$-]+)", statement)
            facts["branch.successor_shapes"].append(
                f"{function}|targets={','.join(targets)}|same-target="
                f"{str(len(set(targets)) == 1).lower()}|args="
            )
        elif opcode == "store" and len(operands) >= 2:
            facts["memory.store_edges"].append(
                f"{function}|value={_root(roots, operands[0])}|address={_root(roots, operands[1])}"
            )
        elif opcode == "load" and operands:
            facts["memory.load_roots"].append(f"{function}|{_root(roots, operands[0])}")
        elif opcode == "ret":
            facts["return.roots"].extend(
                f"{function}|{_root(roots, operand)}" for operand in operands
            )
        elif opcode == "getelementptr" and operands:
            facts["gep.offsets"].append(
                f"{function}|base={_root(roots, operands[0])}|offsets="
                + ",".join(_root(roots, item) for item in operands[1:])
            )
        constants = re.findall(r"\b(i[0-9]+)\s+(-?[0-9]+)\b", statement)
        facts["constant.values"].extend(
            f"{function}|{kind}|{literal}" for kind, literal in constants
        )
        if result:
            if opcode in {"bitcast", "addrspacecast", "getelementptr"} and operands:
                roots[result] = _root(roots, operands[0])
            elif call:
                roots[result] = f"call:{call.group(1)}"
            else:
                roots[result] = f"op:{opcode}:{ordinal}"
    for opcode, rows in occurrences.items():
        facts[f"operation.occurrences.{opcode}"] = rows
    for callee, rows in call_occurrences.items():
        facts[f"call.occurrences.{callee}"] = rows
    return facts


def _assembly_functions(text: str) -> list[str]:
    result: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^([A-Za-z_.$][A-Za-z0-9_.$-]*):\s*(?:[#;].*)?$", line.strip())
        if match and not match.group(1).startswith(".L"):
            result.append(match.group(1))
    return result


def _assembly_body(text: str, function: str) -> list[str]:
    lines = text.splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if re.match(rf"^\s*{re.escape(function)}:\s*(?:[#;].*)?$", line)
    ]
    if len(starts) != 1:
        raise ExtractorError(
            f"assembly scope {function!r} must name exactly one function label"
        )
    result: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if re.match(rf"^\s*\.size\s+{re.escape(function)}\b", line):
            break
        label = re.match(r"^([A-Za-z_.$][A-Za-z0-9_.$-]*):\s*$", line.strip())
        if label and not label.group(1).startswith(".L"):
            break
        result.append(line)
    return result


def _is_conditional_branch(mnemonic: str) -> bool:
    lower = mnemonic.lower()
    if lower.startswith("j"):
        return lower not in {"j", "jmp", "jmpq"}
    if lower in {
        "beq",
        "bne",
        "blt",
        "bge",
        "bltu",
        "bgeu",
        "beqz",
        "bnez",
        "bltz",
        "bgez",
        "cbz",
        "cbnz",
        "tbz",
        "tbnz",
    }:
        return True
    return lower.startswith("b.")


def _extract_assembly(text: str, function: str) -> dict[str, Any]:
    body = _assembly_body(text, function)
    facts: dict[str, Any] = {
        "function.names": _assembly_functions(text),
        "instruction.mnemonics": [],
        "branch.conditional": [],
        "call.callees": [],
    }
    occurrences: dict[str, list[str]] = {}
    for line in body:
        stripped = line.strip()
        if not stripped or stripped.startswith((".", "#", ";")) or stripped.endswith(":"):
            continue
        match = re.match(r"([A-Za-z][A-Za-z0-9_.]*)\b\s*(.*)", stripped)
        if not match:
            continue
        mnemonic = match.group(1).lower()
        ordinal = len(facts["instruction.mnemonics"])
        occurrence = f"{function}|{ordinal}"
        facts["instruction.mnemonics"].append(mnemonic)
        occurrences.setdefault(mnemonic, []).append(occurrence)
        if _is_conditional_branch(mnemonic):
            facts["branch.conditional"].append(occurrence)
        if mnemonic in {"call", "callq", "bl", "jal"}:
            operand = match.group(2).split(",")[-1].strip()
            operand = operand.split("@", 1)[0]
            if operand:
                facts["call.callees"].append(operand)
    for mnemonic, rows in occurrences.items():
        facts[f"instruction.occurrences.{mnemonic}"] = rows
    return facts


def _extract_mir(text: str, function: str) -> dict[str, Any]:
    names = re.findall(r"(?m)^name:\s*([A-Za-z_.$][A-Za-z0-9_.$-]*)\s*$", text)
    matches = list(re.finditer(rf"(?m)^name:\s*{re.escape(function)}\s*$", text))
    if len(matches) != 1:
        raise ExtractorError(f"MIR scope {function!r} must name exactly one body")
    next_match = re.search(r"(?m)^name:\s*", text[matches[0].end() :])
    end = matches[0].end() + next_match.start() if next_match else len(text)
    body = text[matches[0].end() : end]
    opcodes: list[str] = []
    occurrences: dict[str, list[str]] = {}
    for line in body.splitlines():
        match = re.search(r"(?:=\s*)?([A-Z][A-Z0-9_]+)(?:\s|$)", line)
        if not match:
            continue
        opcode = match.group(1)
        ordinal = len(opcodes)
        opcodes.append(opcode)
        occurrences.setdefault(opcode, []).append(f"{function}|{ordinal}")
    stack_objects = [
        _compact(line)
        for line in body.splitlines()
        if re.search(r"\btype:\s*(?:spill-slot|variable-sized)\b", line)
    ]
    facts: dict[str, Any] = {
        "function.names": names,
        "machine.opcodes": opcodes,
        "stack.objects": stack_objects,
    }
    for opcode, rows in occurrences.items():
        facts[f"machine.occurrences.{opcode}"] = rows
    return facts


def _extract_object_inventory(text: str) -> dict[str, Any]:
    symbols: list[str] = []
    sections: list[str] = []
    relocations: list[str] = []
    context = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Symbols ["):
            context = "symbols"
        elif stripped.startswith("Sections ["):
            context = "sections"
        elif stripped.startswith("Relocations ["):
            context = "relocations"
        name = re.match(r"Name:\s*(\S+)", stripped)
        if name and context == "symbols":
            symbols.append(name.group(1))
        elif name and context == "sections":
            sections.append(name.group(1))
        elif context == "relocations" and re.match(r"0x[0-9A-Fa-f]+\s+", stripped):
            relocations.append(_compact(stripped))
    return {
        "object.symbols": symbols,
        "object.relocations": relocations,
        "object.sections": sections,
    }


def extract(
    representation: str,
    extractor: str,
    endpoint_bytes: bytes,
    scope: Mapping[str, Any],
) -> dict[str, Any]:
    expected = EXTRACTORS.get(extractor)
    if expected is None or expected != representation:
        validate_properties(representation, extractor, {})
        raise AssertionError("unreachable")
    try:
        text = endpoint_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ExtractorError(f"{extractor} endpoint is not UTF-8") from error
    function = scope.get("function") if isinstance(scope, Mapping) else None
    if representation != "object-inventory" and not isinstance(function, str):
        raise ExtractorError(f"{extractor} requires a function scope")
    if representation == "mlir":
        return _extract_mlir(text, function)
    if representation == "llvm-ir":
        return _extract_llvm(text, function)
    if representation == "assembly":
        return _extract_assembly(text, function)
    if representation == "mir":
        return _extract_mir(text, function)
    return _extract_object_inventory(text)
