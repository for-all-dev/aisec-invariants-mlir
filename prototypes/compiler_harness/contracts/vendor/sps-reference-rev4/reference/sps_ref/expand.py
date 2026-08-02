"""Deterministic structured expansion for the reference-only IR."""

from __future__ import annotations

from typing import Any

from .canonical import canonical_digest
from .errors import SchemaError
from .model import parse_program


def expand_program(program: dict[str, Any]) -> dict[str, Any]:
    """Expand branches and canonical fixed-bound loops into a flat table.

    This is intentionally named `SPS-Reference-ExpandedCFG-v2`; it is not the
    complete normative `ExpandedCFGTableV2`.
    """

    parse_program(program)
    nodes: list[dict[str, Any]] = []
    ordinal = 0

    def add(kind: str, site: str, path: list[dict[str, Any]], detail: dict[str, Any]) -> None:
        nonlocal ordinal
        node = {
            "nodeOrdinal": ordinal,
            "kind": kind,
            "site": site,
            "expansionPath": list(path),
            "detail": detail,
        }
        nodes.append(node)
        ordinal += 1

    def visit(statements: list[dict[str, Any]], path: list[dict[str, Any]]) -> None:
        for statement in statements:
            op = statement["op"]
            site = statement["site"]
            if op == "if":
                add("Branch", site, path, {"armOrder": ["then", "else"]})
                visit(statement["then"], path + [{"tag": "BranchArm", "site": site, "arm": "then"}])
                visit(statement["else"], path + [{"tag": "BranchArm", "site": site, "arm": "else"}])
            elif op == "loop":
                maximum = statement["boundMaximum"]
                add(
                    "LoopEntry",
                    site,
                    path,
                    {"boundId": statement["boundId"], "boundMaximum": maximum},
                )
                for copy_index in range(maximum):
                    copy_path = path + [
                        {"tag": "LoopFrameV2", "site": site, "copyIndex": copy_index}
                    ]
                    add(
                        "LoopCopyGuard",
                        site,
                        copy_path,
                        {"boundId": statement["boundId"], "copyIndex": copy_index},
                    )
                    visit(statement["body"], copy_path)
                add(
                    "BoundRemainder",
                    site,
                    path + [{"tag": "BoundRemainderV2", "site": site}],
                    {"boundId": statement["boundId"], "afterCopies": maximum},
                )
                add(
                    "LoopExit",
                    site,
                    path,
                    {"boundId": statement["boundId"], "afterCopies": maximum},
                )
            else:
                add("Transition", site, path, {"op": op})

    visit(program["statements"], [])
    table = {
        "formatId": "SPS-Reference-ExpandedCFG-v2",
        "entryId": program["entryId"],
        "nodes": nodes,
        "horizon": len(nodes),
    }
    table["expandedCFGTableDigest"] = canonical_digest(table)
    return table


def width_for(maximum: int) -> int:
    if maximum < 0:
        raise SchemaError("width_for expects a natural")
    return max(1, maximum.bit_length())
