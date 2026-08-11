#!/usr/bin/env python3
"""Check executable CandidateOnly seeds for selected Rev4 NF cases.

The checker deliberately owns only small, reproducible LLVM-17 shape facts:

* ``a06`` counts the guards, lane addresses, accesses, alignments, and
  passthrough PHIs produced by masked-memory scalarization;
* ``a07`` derives direct-call closure, recursion/indirection, maximum call
  depth, expanded CFG path count, and expanded instruction count, then checks
  a CandidateOnly case table;
* ``a09`` derives the original loop trip range, separates engine-cap shortfall
  from aligned and High-controlled public-bound remainder shapes, and checks
  that rows differing only in ``K_loop`` carry byte-identical canonical
  expectations;
* ``a14`` computes entry reachability from the literal CFG without using a
  solver or folding a constant branch, and inventories pinned cleanup sites;
* ``cm03`` inventories definition/call-site Class-A ABI spellings and rejects
  every stripping mutation used by the paired countermodel test.

This is not the SPS verifier. It does not establish normal-form conformance or
issue a model result. All input bitcode used by the lit tests is temporary and
all checked-in records are preflight observations or reason-class seeds.

CLI (kept open for additional cases):

    check_rev4_nf_seeds.py --case CASE INPUT [--cases TABLE.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


FORMAT_ID = "SPS-Harness-Rev4-NF-Seed-Check-v1"
LLVM_VERSION = "17.0.6"


class SeedError(ValueError):
    """A deterministic fixture-contract failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SeedError(message)


def require_key_order(value: Any, keys: tuple[str, ...], where: str) -> None:
    require(isinstance(value, dict), f"{where}: expected object")
    actual = tuple(value)
    require(
        actual == keys,
        f"{where}: expected fields {list(keys)}, found {list(actual)}",
    )


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SeedError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream, object_pairs_hook=strict_object)
    except (OSError, json.JSONDecodeError) as error:
        raise SeedError(f"{path}: cannot read strict JSON: {error}") from error
    require(isinstance(value, dict), f"{path}: top-level JSON value must be an object")
    reject_authoritative_claims(value, str(path))
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def reject_authoritative_claims(value: Any, where: str) -> None:
    """Keep preflight tables structurally unable to carry final verdicts."""
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            require(
                normalized not in {"nfconforms", "modelstatus", "expectedmodelstatus"},
                f"{where}: authoritative claim field is forbidden in CandidateOnly data: {key}",
            )
            reject_authoritative_claims(child, f"{where}.{key}")
        if value.get("tag") in {"Proved", "Counterexample", "Unknown"}:
            raise SeedError(
                f"{where}: final status tag {value['tag']} is forbidden in CandidateOnly data"
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_authoritative_claims(child, f"{where}[{index}]")


def validate_table_header(
    table: dict[str, Any], expected_format: str, path: Path
) -> list[dict[str, Any]]:
    require_key_order(
        table, ("formatId", "fixtureTier", "llvmVersion", "cases"), str(path)
    )
    require(table["formatId"] == expected_format, f"{path}: wrong formatId")
    require_key_order(table["fixtureTier"], ("tag",), f"{path}.fixtureTier")
    require(
        table["fixtureTier"]["tag"] == "CandidateOnly",
        f"{path}: fixtureTier must be CandidateOnly",
    )
    require(
        table["llvmVersion"] == LLVM_VERSION,
        f"{path}: llvmVersion must be {LLVM_VERSION}",
    )
    cases = table["cases"]
    require(isinstance(cases, list) and cases, f"{path}: cases must be nonempty")
    require(
        all(isinstance(case, dict) for case in cases),
        f"{path}: every case must be an object",
    )
    return cases


def strip_llvm_comment(line: str) -> str:
    out: list[str] = []
    in_string = False
    for index, character in enumerate(line):
        if character == '"' and (index == 0 or line[index - 1] != "\\"):
            in_string = not in_string
        if character == ";" and not in_string:
            break
        out.append(character)
    return "".join(out).strip()


@dataclass(frozen=True)
class Function:
    name: str
    signature: str
    body: tuple[str, ...]


FUNCTION_HEADER = re.compile(
    r"^define\b.*?@(?P<name>[-A-Za-z$._0-9]+)\((?P<args>.*)\).*\{\s*$"
)
DIRECT_CALL = re.compile(r"\bcall\b[^;]*?@([-A-Za-z$._0-9]+)\s*\(")
INDIRECT_CALL = re.compile(r"\bcall\b[^;]*?%[-A-Za-z$._0-9]+\s*\(")
BLOCK_LABEL = re.compile(r"^([-A-Za-z$._0-9]+):$")
COND_BRANCH = re.compile(
    r"^br i1 .+?, label %([-A-Za-z$._0-9]+), label %([-A-Za-z$._0-9]+)$"
)
UNCOND_BRANCH = re.compile(r"^br label %([-A-Za-z$._0-9]+)$")


def parse_functions(path: Path) -> dict[str, Function]:
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SeedError(f"{path}: cannot read LLVM input: {error}") from error

    functions: dict[str, Function] = {}
    current_name: str | None = None
    current_signature = ""
    body: list[str] = []
    for raw in raw_lines:
        line = strip_llvm_comment(raw)
        if current_name is None:
            match = FUNCTION_HEADER.match(line)
            if match:
                current_name = match.group("name")
                current_signature = line
                body = []
            continue
        if line == "}":
            require(current_name not in functions, f"{path}: duplicate @{current_name}")
            functions[current_name] = Function(
                current_name, current_signature, tuple(item for item in body if item)
            )
            current_name = None
            current_signature = ""
            body = []
            continue
        if line:
            body.append(line)

    require(current_name is None, f"{path}: unterminated function @{current_name}")
    require(functions, f"{path}: no LLVM function definitions found")
    return functions


def function_calls(function: Function) -> tuple[list[str], int]:
    direct: list[str] = []
    indirect = 0
    for line in function.body:
        direct.extend(DIRECT_CALL.findall(line))
        if INDIRECT_CALL.search(line):
            indirect += 1
    return direct, indirect


def reachable_functions(
    entry: str, functions: dict[str, Function]
) -> tuple[set[str], bool]:
    require(entry in functions, f"missing entry function @{entry}")
    seen: set[str] = set()
    pending = [entry]
    has_indirect_or_unresolved = False
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        direct, indirect = function_calls(functions[name])
        has_indirect_or_unresolved |= indirect != 0
        for callee in direct:
            if callee not in functions:
                has_indirect_or_unresolved = True
            elif callee not in seen:
                pending.append(callee)
    return seen, has_indirect_or_unresolved


def call_graph_has_cycle(closure: set[str], functions: dict[str, Function]) -> bool:
    state: dict[str, int] = {}

    def visit(name: str) -> bool:
        prior = state.get(name, 0)
        if prior == 1:
            return True
        if prior == 2:
            return False
        state[name] = 1
        direct, _ = function_calls(functions[name])
        for callee in direct:
            if callee in closure and visit(callee):
                return True
        state[name] = 2
        return False

    return any(visit(name) for name in sorted(closure) if state.get(name, 0) == 0)


def maximum_call_depth(
    entry: str, closure: set[str], functions: dict[str, Function]
) -> int:
    memo: dict[str, int] = {}

    def depth(name: str) -> int:
        if name in memo:
            return memo[name]
        direct, _ = function_calls(functions[name])
        children = [callee for callee in direct if callee in closure]
        value = max((1 + depth(callee) for callee in children), default=0)
        memo[name] = value
        return value

    return depth(entry)


def split_blocks(function: Function) -> tuple[str, dict[str, list[str]]]:
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    first: str | None = None
    for line in function.body:
        label = BLOCK_LABEL.match(line)
        if label:
            current = label.group(1)
            require(current not in blocks, f"@{function.name}: duplicate %{current}")
            blocks[current] = []
            if first is None:
                first = current
            continue
        require(current is not None, f"@{function.name}: instruction before first block")
        blocks[current].append(line)
    require(first is not None, f"@{function.name}: no basic blocks")
    return first, blocks


def expanded_path_count(
    entry: str, closure: set[str], functions: dict[str, Function]
) -> int:
    function_memo: dict[str, int] = {}

    def paths_for_function(name: str) -> int:
        if name in function_memo:
            return function_memo[name]
        first, blocks = split_blocks(functions[name])
        block_memo: dict[str, int] = {}
        active: set[str] = set()

        def paths_for_block(block_name: str) -> int:
            require(block_name in blocks, f"@{name}: branch to missing %{block_name}")
            if block_name in block_memo:
                return block_memo[block_name]
            require(block_name not in active, f"@{name}: loop in A07 expansion seed")
            active.add(block_name)
            lines = blocks[block_name]
            require(lines, f"@{name} %{block_name}: empty block")

            call_factor = 1
            for line in lines:
                for callee in DIRECT_CALL.findall(line):
                    if callee in closure:
                        call_factor *= paths_for_function(callee)

            terminator = lines[-1]
            conditional = COND_BRANCH.match(terminator)
            unconditional = UNCOND_BRANCH.match(terminator)
            if conditional:
                suffix = paths_for_block(conditional.group(1)) + paths_for_block(
                    conditional.group(2)
                )
            elif unconditional:
                suffix = paths_for_block(unconditional.group(1))
            elif terminator.startswith("ret ") or terminator == "ret void":
                suffix = 1
            else:
                raise SeedError(f"@{name} %{block_name}: unsupported terminator: {terminator}")

            active.remove(block_name)
            block_memo[block_name] = call_factor * suffix
            return block_memo[block_name]

        result = paths_for_block(first)
        function_memo[name] = result
        return result

    return paths_for_function(entry)


def maximum_expanded_instruction_count(
    entry: str, closure: set[str], functions: dict[str, Function]
) -> int:
    """Count the longest expanded path in this small acyclic seed.

    The count includes the direct-call instruction as the stable call boundary
    and adds the callee path expanded beneath it. It is a harness metric used
    only to make the zero-resource contrast executable.
    """
    function_memo: dict[str, int] = {}

    def count_function(name: str) -> int:
        if name in function_memo:
            return function_memo[name]
        first, blocks = split_blocks(functions[name])
        block_memo: dict[str, int] = {}
        active: set[str] = set()

        def count_block(block_name: str) -> int:
            require(block_name in blocks, f"@{name}: branch to missing %{block_name}")
            if block_name in block_memo:
                return block_memo[block_name]
            require(block_name not in active, f"@{name}: loop in A07 expansion seed")
            active.add(block_name)
            lines = blocks[block_name]
            require(lines, f"@{name} %{block_name}: empty block")

            call_expansion = 0
            for line in lines:
                for callee in DIRECT_CALL.findall(line):
                    if callee in closure:
                        call_expansion += count_function(callee)

            terminator = lines[-1]
            conditional = COND_BRANCH.match(terminator)
            unconditional = UNCOND_BRANCH.match(terminator)
            if conditional:
                suffix = max(
                    count_block(conditional.group(1)),
                    count_block(conditional.group(2)),
                )
            elif unconditional:
                suffix = count_block(unconditional.group(1))
            elif terminator.startswith("ret ") or terminator == "ret void":
                suffix = 0
            else:
                raise SeedError(f"@{name} %{block_name}: unsupported terminator: {terminator}")

            active.remove(block_name)
            block_memo[block_name] = len(lines) + call_expansion + suffix
            return block_memo[block_name]

        result = count_block(first)
        function_memo[name] = result
        return result

    return count_function(entry)


def reason_seed(reason: str) -> dict[str, str]:
    return {"tag": "ReasonClassSeed", "reasonClassId": reason}


A07_POSITIVE_OBSERVATION: dict[str, str] = {
    "tag": "AnalysisExpansionCandidateShape",
    "artifactMutation": "Forbidden",
    "memoryAndEvents": "Preserved",
}

A09_POSITIVE_OBSERVATION: dict[str, str] = {
    "tag": "BoundAdequacyCandidateShape",
    "boundaryEvent": "BoundExhausted",
    "boundaryTermination": "BoundFailure",
    "requiredReachability": "Unreachable",
}

A09_HIGH_MISMATCH_OBSERVATION: dict[str, str] = {
    "tag": "BoundExhaustedLaneMismatchSeed",
    "controlClass": "High",
    "boundaryEvent": "BoundExhausted",
    "boundaryTermination": "BoundFailure",
}


def a09_observation(
    template: dict[str, str], loop_site: str, bound_id: str
) -> dict[str, str]:
    items = iter(template.items())
    tag, value = next(items)
    require(tag == "tag", "a09: observation template must begin with tag")
    return {
        "tag": value,
        "loopSite": loop_site,
        "boundId": bound_id,
        **dict(items),
    }


def a09_reason_seed(reason: str, loop_site: str, bound_id: str) -> dict[str, str]:
    return {
        "tag": "ReasonClassSeed",
        "loopSite": loop_site,
        "boundId": bound_id,
        "reasonClassId": reason,
    }


def expectation_label(observation: dict[str, Any]) -> str:
    if observation["tag"] == "ReasonClassSeed":
        return f"reason-seed={observation['reasonClassId']}"
    return f"candidate={observation['tag']}"


def check_a06(input_path: Path, cases_path: Path | None) -> list[str]:
    require(cases_path is None, "a06: --cases is not used")
    functions = parse_functions(input_path)

    def arm(name: str) -> tuple[list[int], list[int]]:
        require(name in functions, f"a06: missing @{name}")
        function = functions[name]
        require(
            "<" not in function.signature and "..." not in function.signature,
            f"a06: @{name} must retain a scalar/pointer ABI",
        )
        body = function.body
        masked_calls = [
            line
            for line in body
            if re.search(r"\bcall\b.*@llvm\.masked\.(load|store)", line)
        ]
        conditional_branches = [line for line in body if line.startswith("br i1 ")]
        loads = [line for line in body if re.search(r"(?:^|= )load i32,", line)]
        stores = [line for line in body if line.startswith("store i32 ")]
        addresses = [line for line in body if "getelementptr" in line and " i32," in line]
        passthrough_phis = [line for line in body if " = phi <4 x i32> " in line]

        require(
            not masked_calls,
            f"a06: @{name} expected zero residual masked-memory call sites, "
            f"found {len(masked_calls)}",
        )
        require(
            len(conditional_branches) == 8,
            f"a06: @{name} expected eight introduced conditional lane guards, "
            f"found {len(conditional_branches)}",
        )
        require(len(loads) == 4, f"a06: @{name} expected four lane loads, found {len(loads)}")
        require(len(stores) == 4, f"a06: @{name} expected four lane stores, found {len(stores)}")
        require(
            len(addresses) == 8,
            f"a06: @{name} expected eight lane addresses, found {len(addresses)}",
        )
        require(
            len(passthrough_phis) == 4,
            f"a06: @{name} expected four inactive-lane passthrough PHIs, "
            f"found {len(passthrough_phis)}",
        )

        first, blocks = split_blocks(function)
        require(first == "entry", f"a06: @{name} must begin at %entry")
        load_guards = ("entry", "else", "else2", "else5")
        load_blocks = ("cond.load", "cond.load1", "cond.load4", "cond.load7")
        load_merges = ("else", "else2", "else5", "else8")
        store_guards = ("else8", "else11", "else13", "else15")
        store_blocks = ("cond.store", "cond.store12", "cond.store14", "cond.store16")
        store_merges = ("else11", "else13", "else15", "else17")
        expected_blocks = {
            "entry",
            *load_blocks,
            *load_merges,
            *store_blocks,
            *store_merges,
        }
        require(
            set(blocks) == expected_blocks,
            f"a06: @{name} guarded-lane CFG block inventory differs: "
            f"{sorted(blocks)}",
        )

        ssa = r"%[-A-Za-z$._0-9]+"
        bitcasts = [
            match.group(1)
            for line in function.body
            if (
                match := re.fullmatch(
                    rf"^({ssa}) = bitcast <4 x i1> %mask\.3 to i4$", line
                )
            )
        ]
        require(
            len(bitcasts) == 2,
            f"a06: @{name} must derive one load mask and one store mask from %mask.3",
        )

        def unique_match(
            block_name: str, pattern: str, description: str
        ) -> re.Match[str]:
            matches = [
                match
                for line in blocks[block_name]
                if (match := re.fullmatch(pattern, line))
            ]
            require(
                len(matches) == 1,
                f"a06: @{name} %{block_name} must contain exactly one {description}",
            )
            return matches[0]

        def validate_guard(
            block_name: str,
            scalar_mask: str,
            lane_mask: str,
            active_block: str,
            inactive_block: str,
        ) -> None:
            masked = unique_match(
                block_name,
                rf"^({ssa}) = and i4 {re.escape(scalar_mask)}, {lane_mask}$",
                f"lane-mask extraction for bit {lane_mask}",
            ).group(1)
            condition = unique_match(
                block_name,
                rf"^({ssa}) = icmp ne i4 {re.escape(masked)}, 0$",
                "lane-mask comparison",
            ).group(1)
            require(
                blocks[block_name][-1]
                == f"br i1 {condition}, label %{active_block}, label %{inactive_block}",
                f"a06: @{name} %{block_name} guard must branch on derived mask "
                "condition to the active access and inactive bypass",
            )

        prior_vector = "%passthrough.3"
        lane_masks = ("1", "2", "4", "-8")
        active_memory_blocks: set[str] = set()
        for lane, (guard, active, merge, lane_mask) in enumerate(
            zip(load_guards, load_blocks, load_merges, lane_masks, strict=True)
        ):
            validate_guard(guard, bitcasts[0], lane_mask, active, merge)
            address = unique_match(
                active,
                rf"^({ssa}) = getelementptr inbounds i32, ptr %source, i32 {lane}$",
                f"source lane-{lane} address",
            ).group(1)
            loaded = unique_match(
                active,
                rf"^({ssa}) = load i32, ptr {re.escape(address)}, align [0-9]+$",
                f"source lane-{lane} load",
            ).group(1)
            inserted = unique_match(
                active,
                rf"^({ssa}) = insertelement <4 x i32> {re.escape(prior_vector)}, "
                rf"i32 {re.escape(loaded)}, i64 {lane}$",
                f"loaded lane-{lane} insertion",
            ).group(1)
            require(
                blocks[active][-1] == f"br label %{merge}",
                f"a06: @{name} %{active} must rejoin %{merge}",
            )
            phi = unique_match(
                merge,
                rf"^({ssa}) = phi <4 x i32> \[ {re.escape(inserted)}, %{active} \], "
                rf"\[ {re.escape(prior_vector)}, %{guard} \]$",
                f"lane-{lane} active/passthrough PHI",
            ).group(1)
            prior_vector = phi
            active_memory_blocks.add(active)

        for lane, (guard, active, merge, lane_mask) in enumerate(
            zip(store_guards, store_blocks, store_merges, lane_masks, strict=True)
        ):
            validate_guard(guard, bitcasts[1], lane_mask, active, merge)
            extracted = unique_match(
                active,
                rf"^({ssa}) = extractelement <4 x i32> {re.escape(prior_vector)}, i64 {lane}$",
                f"destination lane-{lane} extraction",
            ).group(1)
            address = unique_match(
                active,
                rf"^({ssa}) = getelementptr inbounds i32, ptr %destination, i32 {lane}$",
                f"destination lane-{lane} address",
            ).group(1)
            unique_match(
                active,
                rf"^store i32 {re.escape(extracted)}, ptr {re.escape(address)}, align [0-9]+$",
                f"destination lane-{lane} store",
            )
            require(
                blocks[active][-1] == f"br label %{merge}",
                f"a06: @{name} %{active} must rejoin %{merge}",
            )
            active_memory_blocks.add(active)

        require(
            blocks["else17"] == ["ret void"],
            f"a06: @{name} final inactive/active merge must return",
        )
        memory_sites = [
            (block_name, line)
            for block_name, lines in blocks.items()
            for line in lines
            if re.search(r"(?:^|= )(?:load|store|atomicrmw|cmpxchg)\b|^fence\b", line)
        ]
        require(
            len(memory_sites) == 8
            and all(block_name in active_memory_blocks for block_name, _ in memory_sites),
            f"a06: @{name} memory access escaped a mask-true lane block",
        )

        def alignments(lines: list[str]) -> list[int]:
            result: list[int] = []
            for line in lines:
                match = re.search(r", align ([0-9]+)$", line)
                require(match is not None, f"a06: lane access has no alignment: {line}")
                result.append(int(match.group(1)))
            return result

        return alignments(loads), alignments(stores)

    align4_loads, align4_stores = arm("a06_masked_roundtrip_align4")
    align16_loads, align16_stores = arm("a06_masked_roundtrip_align16")
    required_align4 = [4, 4, 4, 4]
    required_align16 = [16, 4, 8, 4]
    require(
        align4_loads == required_align4 and align4_stores == required_align4,
        f"a06: align-4 arm disagrees with commonAlignment: {align4_loads}/{align4_stores}",
    )
    require(
        align16_loads == [4, 4, 4, 4] and align16_stores == [4, 4, 4, 4],
        "a06: LLVM-17 align-16 contrast no longer exhibits copied element alignment 4",
    )

    return [
        "case: a06",
        f"input: {input_path}",
        "align4 scalar-abi=yes residual-masked-calls=0 lane-guards=8 "
        "lane-addresses=8 passthrough-phis=4",
        "align4 load-alignments=4,4,4,4 store-alignments=4,4,4,4 "
        "required-commonAlignment=4,4,4,4 match=yes",
        "align16 scalar-abi=yes residual-masked-calls=0 lane-guards=8 "
        "lane-addresses=8 passthrough-phis=4",
        "align16 load-alignments=4,4,4,4 store-alignments=4,4,4,4 "
        "required-commonAlignment=16,4,8,4 match=no",
        "llvm17-alignment-contrast=copied-element-alignment-4",
        "candidate-observation=MaskedMemoryGuardedLaneShapeWithAlignmentLimitation",
    ]


def check_a07(input_path: Path, cases_path: Path | None) -> list[str]:
    require(cases_path is not None, "a07: --cases TABLE.json is required")
    table = load_json(cases_path)
    cases = validate_table_header(table, "SPS-Harness-NF-A07-Seeds-v1", cases_path)
    functions = parse_functions(input_path)
    for function in functions.values():
        for line in function.body:
            require(
                re.search(r"\b(?:musttail|tail|notail)\s+call\b", line) is None,
                f"a07: @{function.name} uses a forbidden tail/notail call form: {line}",
            )

    output = ["case: a07", f"input: {input_path}", f"cases: {cases_path}"]
    seen_ids: set[str] = set()
    category_counts: dict[str, int] = {}
    for index, case in enumerate(cases):
        where = f"{cases_path}.cases[{index}]"
        require_key_order(
            case,
            ("caseId", "entryFunction", "engineCaps", "expectedObservation"),
            where,
        )
        case_id = case["caseId"]
        entry = case["entryFunction"]
        require(isinstance(case_id, str) and case_id, f"{where}.caseId: expected string")
        require(case_id not in seen_ids, f"{where}: duplicate caseId {case_id}")
        seen_ids.add(case_id)
        require(isinstance(entry, str) and entry, f"{where}.entryFunction: expected string")
        require_key_order(
            case["engineCaps"],
            ("K_call", "K_paths", "K_expanded_instructions"),
            f"{where}.engineCaps",
        )
        call_cap = case["engineCaps"]["K_call"]
        path_cap = case["engineCaps"]["K_paths"]
        instruction_cap = case["engineCaps"]["K_expanded_instructions"]
        require(
            isinstance(call_cap, int) and not isinstance(call_cap, bool) and call_cap >= 0,
            f"{where}.engineCaps.K_call: expected nonnegative integer",
        )
        require(
            isinstance(path_cap, int) and not isinstance(path_cap, bool) and path_cap >= 0,
            f"{where}.engineCaps.K_paths: expected nonnegative integer",
        )
        require(
            isinstance(instruction_cap, int)
            and not isinstance(instruction_cap, bool)
            and instruction_cap >= 0,
            f"{where}.engineCaps.K_expanded_instructions: expected nonnegative integer",
        )

        closure, unclosed = reachable_functions(entry, functions)
        recursive = call_graph_has_cycle(closure, functions)
        depth: int | None = None
        paths: int | None = None
        instructions: int | None = None
        if unclosed:
            derived = reason_seed("IndirectCall")
        elif recursive:
            derived = reason_seed("Recursion")
        else:
            require(
                all(
                    "<" not in functions[name].signature
                    and "..." not in functions[name].signature
                    for name in closure
                ),
                f"{where}: eligible closure must use only scalar/pointer non-vararg ABI",
            )
            depth = maximum_call_depth(entry, closure, functions)
            paths = expanded_path_count(entry, closure, functions)
            instructions = maximum_expanded_instruction_count(entry, closure, functions)
            if (
                depth > call_cap
                or paths > path_cap
                or instructions > instruction_cap
            ):
                derived = reason_seed("ResourceLimit")
            else:
                derived = A07_POSITIVE_OBSERVATION

        expected = case["expectedObservation"]
        require(isinstance(expected, dict), f"{where}.expectedObservation: expected object")
        require(
            canonical_bytes(expected) == canonical_bytes(derived),
            f"{where}: expectation disagrees with derived call-closure observation; "
            f"expected {expected}, derived {derived}",
        )
        category = expectation_label(derived)
        category_counts[category] = category_counts.get(category, 0) + 1
        output.append(
            f"{case_id} entry=@{entry} direct-call-depth={depth if depth is not None else '-'} "
            f"expanded-path-count={paths if paths is not None else '-'} "
            f"expanded-instruction-count={instructions if instructions is not None else '-'} "
            f"K_call={call_cap} K_paths={path_cap} "
            f"K_expanded_instructions={instruction_cap} {category}"
        )

    require(
        category_counts == {
            "candidate=AnalysisExpansionCandidateShape": 1,
            "reason-seed=ResourceLimit": 3,
            "reason-seed=Recursion": 1,
            "reason-seed=IndirectCall": 1,
        },
        f"a07: incomplete positive/negative coverage: {category_counts}",
    )
    output.append(
        "verified a07: 6 CandidateOnly cases; direct-acyclic=1; "
        "zero-resource-contrast=3; recursion=1; indirect=1; temporary-bitcode-ready"
    )
    return output


@dataclass(frozen=True)
class LoopTripRange:
    minimum: int
    maximum: int
    high_controlled: bool


def loop_trip_range(function: Function) -> LoopTripRange:
    first, blocks = split_blocks(function)
    require(first == "entry", f"@{function.name}: expected %entry as first block")
    require(
        set(blocks) == {"entry", "zero", "preheader", "loop", "exit"},
        f"@{function.name}: expected exact guarded CanonicalSingleBlockLoopV2 "
        f"block inventory, found {sorted(blocks)}",
    )
    require(
        blocks["entry"][-1] == "br i1 %enter, label %preheader, label %zero",
        f"@{function.name}: entry guard must enter %preheader on true and %zero on false",
    )
    require(
        blocks["zero"] == ["ret i32 0"],
        f"@{function.name}: zero-trip bypass must return without entering the loop",
    )
    require(
        blocks["preheader"] == ["br label %loop"],
        f"@{function.name}: canonical preheader must have %loop as its sole successor",
    )
    require(
        blocks["loop"][0]
        == "%index = phi i32 [ 0, %preheader ], [ %next, %loop ]",
        f"@{function.name}: expected canonical induction PHI",
    )
    require(
        sum(1 for line in function.body if re.search(r" = add i32 %index, 1$", line)) == 1,
        f"@{function.name}: expected unit induction step",
    )
    require(
        sum(
            1
            for line in function.body
            if line == "br i1 %continue, label %loop, label %exit"
        )
        == 1,
        f"@{function.name}: expected original guarded backedge",
    )
    require(
        blocks["loop"][-1] == "br i1 %continue, label %loop, label %exit",
        f"@{function.name}: canonical loop must have one backedge and one dedicated exit",
    )
    require(
        blocks["exit"]
        == ["%result = phi i32 [ %next, %loop ]", "ret i32 %result"],
        f"@{function.name}: dedicated exit must carry the loop value through its leading PHI",
    )
    require(
        not any("getelementptr inbounds" in line for line in function.body),
        f"@{function.name}: loop seed must not introduce an inbounds GEP",
    )

    high_selects = [
        (int(match.group(1)), int(match.group(2)))
        for line in function.body
        if (
            match := re.search(
                r"^%limit = select i1 %high, i32 ([0-9]+), i32 ([0-9]+)$",
                line,
            )
        )
    ]
    if high_selects:
        require(len(high_selects) == 1, f"@{function.name}: duplicate High loop limit")
        require(
            sum(1 for line in function.body if line == "%enter = icmp ult i32 0, %limit") == 1,
            f"@{function.name}: missing High-controlled entry guard",
        )
        require(
            sum(
                1
                for line in function.body
                if line == "%continue = icmp ult i32 %next, %limit"
            )
            == 1,
            f"@{function.name}: missing High-controlled backedge guard",
        )
        left, right = high_selects[0]
        return LoopTripRange(min(left, right), max(left, right), True)

    entry_limits = [
        int(match.group(1))
        for line in function.body
        if (match := re.search(r"^%enter = icmp ult i32 0, ([0-9]+)$", line))
    ]
    backedge_limits = [
        int(match.group(1))
        for line in function.body
        if (
            match := re.search(
                r"^%continue = icmp ult i32 %next, ([0-9]+)$", line
            )
        )
    ]
    require(
        len(entry_limits) == 1 and len(backedge_limits) == 1,
        f"@{function.name}: expected literal entry and backedge guards",
    )
    require(
        entry_limits[0] == backedge_limits[0],
        f"@{function.name}: entry/backedge limit mismatch",
    )
    return LoopTripRange(entry_limits[0], entry_limits[0], False)


def check_a09(input_path: Path, cases_path: Path | None) -> list[str]:
    require(cases_path is not None, "a09: --cases TABLE.json is required")
    table = load_json(cases_path)
    cases = validate_table_header(table, "SPS-Harness-NF-A09-Seeds-v1", cases_path)
    functions = parse_functions(input_path)

    output = ["case: a09", f"input: {input_path}", f"cases: {cases_path}"]
    seen_ids: set[str] = set()
    category_counts: dict[str, int] = {}
    independence_groups: dict[str, list[dict[str, Any]]] = {}
    public_bound_maxima: set[int] = set()
    engine_caps: set[int] = set()
    for index, case in enumerate(cases):
        where = f"{cases_path}.cases[{index}]"
        require_key_order(
            case,
            (
                "caseId",
                "entryFunction",
                "publicBound",
                "engineCap",
                "capIndependenceGroup",
                "expectedObservation",
            ),
            where,
        )
        case_id = case["caseId"]
        entry = case["entryFunction"]
        require(isinstance(case_id, str) and case_id, f"{where}.caseId: expected string")
        require(case_id not in seen_ids, f"{where}: duplicate caseId {case_id}")
        seen_ids.add(case_id)
        require(isinstance(entry, str) and entry in functions, f"{where}: missing @{entry}")
        require_key_order(case["publicBound"], ("boundId", "maximum"), f"{where}.publicBound")
        bound_id = case["publicBound"]["boundId"]
        bound_maximum = case["publicBound"]["maximum"]
        engine_cap = case["engineCap"]
        require(
            isinstance(bound_id, str) and bound_id,
            f"{where}.publicBound.boundId: expected string",
        )
        require(
            isinstance(bound_maximum, int)
            and not isinstance(bound_maximum, bool)
            and bound_maximum >= 0,
            f"{where}.publicBound.maximum: expected nonnegative integer",
        )
        require(
            isinstance(engine_cap, int) and not isinstance(engine_cap, bool) and engine_cap >= 0,
            f"{where}.engineCap: expected nonnegative integer",
        )
        public_bound_maxima.add(bound_maximum)
        engine_caps.add(engine_cap)
        group = case["capIndependenceGroup"]
        require(
            group is None or isinstance(group, str),
            f"{where}.capIndependenceGroup: expected string or null",
        )
        if group is not None:
            independence_groups.setdefault(group, []).append(case)

        trip_range = loop_trip_range(functions[entry])
        loop_site = f"{entry}:loop"
        if engine_cap < bound_maximum + 1:
            derived = a09_reason_seed("ResourceLimit", loop_site, bound_id)
            relation = "cap-shortfall"
        elif trip_range.high_controlled and trip_range.maximum > bound_maximum:
            derived = a09_observation(
                A09_HIGH_MISMATCH_OBSERVATION, loop_site, bound_id
            )
            relation = "high-one-lane-mismatch"
        elif trip_range.maximum > bound_maximum:
            derived = a09_reason_seed("LoopRemainder", loop_site, bound_id)
            relation = "aligned-reachable-exhaustion"
        else:
            derived = a09_observation(A09_POSITIVE_OBSERVATION, loop_site, bound_id)
            relation = "boundary-unreachable"

        expected = case["expectedObservation"]
        require(isinstance(expected, dict), f"{where}.expectedObservation: expected object")
        require(
            canonical_bytes(expected) == canonical_bytes(derived),
            f"{where}: expectation disagrees with public-bound/cap observation; "
            f"expected {expected}, derived {derived}",
        )
        category = expectation_label(derived)
        category_counts[category] = category_counts.get(category, 0) + 1
        trip_text = (
            str(trip_range.minimum)
            if trip_range.minimum == trip_range.maximum
            else f"{trip_range.minimum}..{trip_range.maximum}"
        )
        output.append(
            f"{case_id} entry=@{entry} bound-id={bound_id} bound-maximum={bound_maximum} "
            f"original-trip-count={trip_text} K_loop={engine_cap} relation={relation} "
            f"{category} "
            f"canonical-expectation-sha256={digest(expected)}"
        )

    require(independence_groups, "a09: no cap-independence pair")
    for group, members in independence_groups.items():
        require(len(members) == 2, f"a09: cap-independence group {group} must have two rows")
        first, second = members
        first_context = {
            key: value
            for key, value in first.items()
            if key not in {"caseId", "engineCap", "expectedObservation"}
        }
        second_context = {
            key: value
            for key, value in second.items()
            if key not in {"caseId", "engineCap", "expectedObservation"}
        }
        require(
            canonical_bytes(first_context) == canonical_bytes(second_context),
            f"a09: group {group} differs in a field other than caseId/K_loop/expectation",
        )
        require(
            first["engineCap"] != second["engineCap"],
            f"a09: group {group} must use two distinct K_loop values",
        )
        first_expectation = canonical_bytes(first["expectedObservation"])
        second_expectation = canonical_bytes(second["expectedObservation"])
        require(
            first_expectation == second_expectation,
            f"a09: group {group} expectations are not byte-identical after canonical encoding",
        )
        output.append(
            f"cap-independence group={group} cases={first['caseId']},{second['caseId']} "
            f"K_loop={first['engineCap']},{second['engineCap']} "
            f"canonical-expectation-sha256={hashlib.sha256(first_expectation).hexdigest()}"
        )

    require(
        public_bound_maxima == {0, 1, 16},
        f"a09: expected public-bound maxima 0, 1, and 16; found {sorted(public_bound_maxima)}",
    )
    require(
        {15, 16, 17, 32} <= engine_caps,
        "a09: missing below/equal-public-maximum and exact/above-capacity "
        f"K_loop values 15/16/17/32: {sorted(engine_caps)}",
    )
    require(
        category_counts == {
            "candidate=BoundAdequacyCandidateShape": 4,
            "reason-seed=ResourceLimit": 2,
            "reason-seed=LoopRemainder": 1,
            "candidate=BoundExhaustedLaneMismatchSeed": 1,
        },
        f"a09: incomplete positive/negative coverage: {category_counts}",
    )
    output.append(
        "verified a09: 8 CandidateOnly cases; public-bounds=0,1,16; "
        "K_loop-15-16-17-32=below-max-equal-max-exact-cap-above-cap; aligned-remainder=1; "
        "high-lane-mismatch=1; temporary-bitcode-ready"
    )
    return output


def reachable_blocks(function: Function) -> tuple[dict[str, list[str]], set[str]]:
    first, blocks = split_blocks(function)
    reachable: set[str] = set()
    pending = [first]
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        require(name in blocks, f"@{function.name}: branch to missing %{name}")
        reachable.add(name)
        lines = blocks[name]
        require(lines, f"@{function.name} %{name}: empty block")
        terminator = lines[-1]
        conditional = COND_BRANCH.match(terminator)
        unconditional = UNCOND_BRANCH.match(terminator)
        if conditional:
            # Both successors are graph-reachable even when the condition is
            # literal false. NF-A14 forbids semantic or policy infeasibility
            # from becoming a cleanup premise.
            pending.extend((conditional.group(1), conditional.group(2)))
        elif unconditional:
            pending.append(unconditional.group(1))
        else:
            require(
                terminator.startswith("ret ") or terminator == "ret void",
                f"@{function.name} %{name}: unsupported terminator: {terminator}",
            )
    return blocks, reachable


def check_a14(input_path: Path, cases_path: Path | None) -> list[str]:
    require(cases_path is None, "a14: --cases is not used")
    functions = parse_functions(input_path)
    required = {
        "a14_dead_cleanup",
        "a14_literal_false_edge",
        "a14_runtime_reachable",
    }
    require(
        required <= set(functions),
        f"a14: missing functions {sorted(required - set(functions))}",
    )

    dead_function = functions["a14_dead_cleanup"]
    dead_blocks, dead_reachable = reachable_blocks(dead_function)
    require(
        set(dead_blocks) - dead_reachable == {"dead"},
        "a14_dead_cleanup: the exact unreachable-block inventory must be ['dead']",
    )
    require(
        "%dead.freeze = freeze i32 poison" in dead_blocks["dead"],
        "a14_dead_cleanup:dead must contain freeze i32 poison",
    )
    require(
        dead_blocks["dead"][-1] == "br label %join",
        "a14_dead_cleanup:dead must retain its outgoing PHI edge",
    )
    require(
        any(
            line.startswith("%value = phi i32 ")
            and "[ %dead.freeze, %dead ]" in line
            for line in dead_blocks["join"]
        ),
        "a14_dead_cleanup:join must retain the dead predecessor PHI incoming",
    )
    require(
        sum(line.count("%unused") for line in dead_function.body) == 1,
        "a14_dead_cleanup:%unused must have zero uses",
    )
    require(
        "%unused = add i32 %value, 7" in dead_blocks["join"],
        "a14_dead_cleanup:%unused must be the pinned side-effect-free add seed; "
        "the LLVM-22.1.8 and SPS removability classifiers are not inferred from use count",
    )

    false_function = functions["a14_literal_false_edge"]
    false_blocks, false_reachable = reachable_blocks(false_function)
    require(
        "syntactically_reachable" in false_reachable,
        "a14_literal_false_edge: syntactically_reachable must be CFG-reachable",
    )
    require(
        "%edge.freeze = freeze i32 poison"
        in false_blocks["syntactically_reachable"],
        "a14_literal_false_edge: reachable edge must retain freeze i32 poison",
    )

    runtime_function = functions["a14_runtime_reachable"]
    runtime_blocks, runtime_reachable = reachable_blocks(runtime_function)
    require(
        "choice" in runtime_reachable,
        "a14_runtime_reachable: choice must be CFG-reachable",
    )
    require(
        "%live.freeze = freeze i32 poison" in runtime_blocks["choice"],
        "a14_runtime_reachable: choice must retain freeze i32 poison",
    )

    return [
        "case=NF-A14",
        "unreachable-block=@a14_dead_cleanup:dead",
        "reachable-freeze-block=@a14_literal_false_edge:syntactically_reachable",
        "reachable-freeze-block=@a14_runtime_reachable:choice",
        "zero-use-removal-seed=@a14_dead_cleanup:%unused opcode=add "
        "classifier-result=NotComputed",
        "SPS-Harness-Expectation: Unknown(FreezeMayChoose) -- CFG-reachable "
        "unsupported freeze material must not be removed by policy or solver reasoning",
    ]


CM03_ATTRIBUTE_COUNTS: tuple[tuple[str, int], ...] = (
    ("signext", 4),
    ("zeroext", 4),
    ("sret", 2),
    ("byval", 2),
    ("inreg", 2),
    ("fastcc", 2),
)


def check_cm03(input_path: Path, cases_path: Path | None) -> list[str]:
    require(cases_path is None, "cm03: --cases is not used")
    try:
        text = "\n".join(
            strip_llvm_comment(line)
            for line in input_path.read_text(encoding="utf-8").splitlines()
        )
    except OSError as error:
        raise SeedError(f"{input_path}: cannot read LLVM input: {error}") from error

    patterns = {
        "signext": r"\bsignext\b",
        "zeroext": r"\bzeroext\b",
        "sret": r"\bsret\(",
        "byval": r"\bbyval\(",
        "inreg": r"\binreg\b",
        "fastcc": r"\bfastcc\b",
    }
    counts: dict[str, int] = {}
    for attribute, expected in CM03_ATTRIBUTE_COUNTS:
        actual = len(re.findall(patterns[attribute], text))
        require(
            actual == expected,
            f"NF-CM03 attribute inventory mismatch for {attribute}: "
            f"expected {expected}, found {actual}",
        )
        counts[attribute] = actual

    functions = parse_functions(input_path)
    required = {
        "cm03_signext",
        "cm03_zeroext",
        "cm03_aggregate",
        "cm03_fastcc",
        "cm03_ccc",
        "cm03_call_sites",
    }
    require(
        required <= set(functions),
        f"cm03: missing functions {sorted(required - set(functions))}",
    )

    expected_signatures = {
        "cm03_signext": "define signext i8 @cm03_signext(i8 signext %value) {",
        "cm03_zeroext": "define zeroext i8 @cm03_zeroext(i8 zeroext %value) {",
        "cm03_aggregate": (
            "define void @cm03_aggregate(ptr sret(%Pair) %out, "
            "ptr byval(%Pair) align 8 %input) {"
        ),
        "cm03_fastcc": "define fastcc i32 @cm03_fastcc(i32 inreg %value) {",
        "cm03_ccc": "define i32 @cm03_ccc(i32 %value) {",
        "cm03_call_sites": (
            "define i32 @cm03_call_sites(ptr %out, ptr %input, i8 %signed_value, "
            "i8 %unsigned_value, i32 %register_value) {"
        ),
    }
    for name, expected in expected_signatures.items():
        require(
            functions[name].signature == expected,
            f"cm03: @{name} definition ABI spelling mismatch: "
            f"{functions[name].signature}",
        )

    required_calls = {
        "%signed_result = call signext i8 @cm03_signext(i8 signext %signed_value)",
        "%unsigned_result = call zeroext i8 @cm03_zeroext(i8 zeroext %unsigned_value)",
        "call void @cm03_aggregate(ptr sret(%Pair) %out, "
        "ptr byval(%Pair) align 8 %input)",
        "%fast_result = call fastcc i32 @cm03_fastcc(i32 inreg %register_value)",
        "%ccc_result = call i32 @cm03_ccc(i32 %fast_result)",
    }
    actual_call_lines = {
        line for line in functions["cm03_call_sites"].body if " call " in f" {line} "
    }
    require(
        actual_call_lines == required_calls,
        "cm03: call-site ABI spelling inventory differs: "
        f"{sorted(actual_call_lines)}",
    )

    output = ["case=NF-CM03"]
    output.extend(
        f"attribute-count {attribute}={counts[attribute]}"
        for attribute, _ in CM03_ATTRIBUTE_COUNTS
    )
    output.extend(
        (
            "SPS-Harness-Expectation: Unknown(UnsupportedType) -- preserved "
            "sret/byval/inreg/fastcc remain out of the accepted top-level ABI",
            "SPS-Harness-Expectation: Unknown(NormalizerMismatch) -- stripping "
            "any Class-A spelling is forbidden",
        )
    )
    return output


Handler = Callable[[Path, Path | None], list[str]]
HANDLERS: dict[str, Handler] = {
    "a06": check_a06,
    "a07": check_a07,
    "a09": check_a09,
    "a14": check_a14,
    "cm03": check_cm03,
}


def emit_boundary() -> None:
    print(
        "SPS-Harness-Note: temporary bitcode and harness expectation records; "
        "no authoritative verifier result is issued"
    )
    print("tier=CandidateOnly")
    print("nf_conforms=NotEvaluated")
    print("model_status=NotComputed")
    print("deployment_status=NotComputed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, help="case handler (for example a06)")
    parser.add_argument("input", type=Path, help="textual LLVM input")
    parser.add_argument("--cases", type=Path, help="CandidateOnly JSON case table")
    arguments = parser.parse_args(argv)

    handler = HANDLERS.get(arguments.case)
    if handler is None:
        parser.error(
            "unsupported --case {!r}; available handlers: {}".format(
                arguments.case, ", ".join(sorted(HANDLERS))
            )
        )
    try:
        lines = handler(arguments.input, arguments.cases)
    except SeedError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(FORMAT_ID)
    for line in lines:
        print(line)
    emit_boundary()
    return 0


if __name__ == "__main__":
    sys.exit(main())
