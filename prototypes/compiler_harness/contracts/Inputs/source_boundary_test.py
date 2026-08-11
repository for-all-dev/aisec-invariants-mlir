#!/usr/bin/env python3
"""Focused positive and fail-closed checks for source-boundary authoring."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


def run(command: list[str], *, environment: dict[str, str], ok: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if ok and completed.returncode != 0:
        raise AssertionError(f"command failed: {command}\n{completed.stderr}")
    if not ok and completed.returncode == 0:
        raise AssertionError(f"command unexpectedly passed: {command}")
    return completed


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: object) -> bool:
        return True


def dump(path: Path, value: object) -> None:
    path.write_text(
        yaml.dump(value, Dumper=NoAliasDumper, sort_keys=False), encoding="utf-8"
    )


def c_source(
    component: str = "logits",
    *,
    warning: bool = False,
    variadic: bool = False,
    calling_convention: bool = False,
    address_space: bool = False,
) -> str:
    unused = "  unsigned unused_local;\n" if warning else ""
    convention = "__attribute__((preserve_most))\n" if calling_convention else ""
    alice_type = (
        "unsigned __attribute__((address_space(1))) *" if address_space else "unsigned *"
    )
    variadic_tail = ", ...)" if variadic else ")"
    return f"""\
#include <stdint.h>
#include <sps/annotations.h>

SPS_HELPER("masked-class")
static uint32_t masked(uint32_t raw)
{{
  return raw & 0xffu;
}}

SPS_ENTRY("audience-mismatch")
{convention}\
void boundary(unsigned logits SPS_COMPONENT("{component}"),
              {alice_type}alice SPS_ROOT("alice-channel"),
              unsigned *bob SPS_ROOT("bob-channel"){variadic_tail}
{{
{unused}  unsigned released = masked(logits);
  *alice = released;
  *bob = released;
}}
"""


def renamed_symbol_source() -> str:
    return """\
#include <sps/annotations.h>

SPS_HELPER("masked-class")
static unsigned masked(unsigned raw)
{
  return raw & 0xffu;
}

SPS_ENTRY("audience-mismatch")
void boundary(unsigned logits SPS_COMPONENT("logits"),
              unsigned *alice SPS_ROOT("alice-channel"),
              unsigned *bob SPS_ROOT("bob-channel")) __asm__("renamed_boundary");

void boundary(unsigned logits, unsigned *alice, unsigned *bob)
{
  unsigned released = masked(logits);
  *alice = released;
  *bob = released;
}
"""


def three_root_source() -> str:
    return """\
#include <sps/annotations.h>

SPS_HELPER("masked-class")
static unsigned masked(unsigned raw)
{
  return raw & 0xffu;
}

SPS_ENTRY("audience-mismatch")
void boundary(unsigned logits SPS_COMPONENT("logits"),
              unsigned *alice SPS_ROOT("alice-channel"),
              unsigned *bob SPS_ROOT("bob-channel"),
              unsigned *charlie SPS_ROOT("charlie-channel"))
{
  unsigned released = masked(logits);
  *alice = released;
  *bob = released;
  *charlie = released;
}
"""


def namespace_collision_source() -> str:
    return """\
#include <sps/annotations.h>

namespace intended {
SPS_HELPER("masked-class")
unsigned masked(unsigned raw)
{
  return raw & 0xffu;
}
}

namespace wrong {
unsigned masked(unsigned raw)
{
  return raw;
}
}

extern "C" {
SPS_ENTRY("namespace-collision")
void boundary(unsigned value SPS_COMPONENT("value"))
{
  (void)wrong::masked(value);
}
}
"""


def buffer_source() -> str:
    return """\
#include <sps/annotations.h>

SPS_ENTRY("buffer-entry")
void boundary(unsigned char *buffer SPS_ROOT("buffer"))
{
  unsigned char observed = buffer[0];
  (void)observed;
}
"""


def buffer_policy() -> dict[str, object]:
    return {
        "entry": "buffer-entry",
        "observation-model": "constant-time",
        "principals": ["attacker"],
        "adversaries": {"maximal": [["attacker"]]},
        "hosts": {
            "compute": {"visibility": "secret"},
            "memory": {"visibility": "secret"},
        },
        "components": {
            "payload": {
                "lifecycle": "entry-input",
                "type": "bytes",
                "visibility": "secret",
            }
        },
        "outputs": {},
        "releases": {},
    }


def buffer_abi() -> dict[str, object]:
    return {
        "source": "boundary.c",
        "relation": "provenance-only",
        "entry": {
            "id": "buffer-entry",
            "symbol": "boundary",
            "host": "compute",
            "function-type": "void (ptr)",
            "return": "void",
        },
        "carriers": {},
        "roots": {
            "buffer": {
                "argument": 0,
                "host": "memory",
                "extent-bytes": 1,
                "alignment": 1,
                "permission": "read-only",
                "initialization": "initialized",
                "ownership": "caller",
                "input": "payload",
            }
        },
        "aliases": {"complete": True, "relations": []},
        "terminal-output-order": {"normal-void": []},
    }


def policy() -> dict[str, object]:
    alice = {"world": False, "members": ["alice"], "joint": []}
    bob = {"world": False, "members": ["bob"], "joint": []}
    return {
        "entry": "audience-mismatch",
        "observation-model": "constant-time",
        "principals": ["alice", "bob"],
        "adversaries": {"maximal": [["alice", "bob"]]},
        "hosts": {
            "compute": {"visibility": "secret"},
            "alice-endpoint": {"visibility": alice},
            "bob-endpoint": {"visibility": bob},
        },
        "components": {
            "logits": {"lifecycle": "entry-input", "type": "bv32", "visibility": "secret"}
        },
        "outputs": {
            "alice-channel": {"visibility": alice},
            "bob-channel": {"visibility": bob},
        },
        "releases": {
            "masked-class": {
                "locator": {"helper": "masked-class", "call-ordinal": 0},
                "audience": alice,
                "type": {"kind": "bv", "width": 32, "byte-order": "little"},
                "expression": {
                    "bit-and": {
                        "left": {"component": "logits"},
                        "right": {"constant": 255},
                    }
                },
                "guard": True,
                "payload-footprint": [0],
                "multiplicity": 1,
            }
        },
    }


def abi() -> dict[str, object]:
    return {
        "source": "boundary.c",
        "relation": "provenance-only",
        "entry": {
            "id": "audience-mismatch",
            "symbol": "boundary",
            "host": "compute",
            "function-type": "void (i32, ptr, ptr)",
            "return": "void",
        },
        "carriers": {"logits": {"argument": 0, "llvm-type": "i32", "bit-width": 32}},
        "roots": {
            "alice-channel": {
                "argument": 1,
                "host": "alice-endpoint",
                "extent-bytes": 4,
                "alignment": 4,
                "permission": "write-only",
                "initialization": "uninitialized",
                "ownership": "caller",
                "output": "alice-channel",
            },
            "bob-channel": {
                "argument": 2,
                "host": "bob-endpoint",
                "extent-bytes": 4,
                "alignment": 4,
                "permission": "write-only",
                "initialization": "uninitialized",
                "ownership": "caller",
                "output": "bob-channel",
            },
        },
        "aliases": {
            "complete": True,
            "relations": [
                {"relation": "disjoint", "roots": ["alice-channel", "bob-channel"]}
            ],
        },
        "terminal-output-order": {"normal-void": ["alice-channel", "bob-channel"]},
    }


def inconsistent_alias_policy() -> dict[str, object]:
    value = copy.deepcopy(policy())
    value["hosts"]["charlie-endpoint"] = {"visibility": "secret"}
    value["outputs"]["charlie-channel"] = {"visibility": "secret"}
    return value


def inconsistent_alias_abi() -> dict[str, object]:
    value = copy.deepcopy(abi())
    value["entry"]["function-type"] = "void (i32, ptr, ptr, ptr)"
    value["roots"]["bob-channel"]["host"] = "alice-endpoint"
    value["roots"]["charlie-channel"] = {
        "argument": 3,
        "host": "alice-endpoint",
        "extent-bytes": 4,
        "alignment": 4,
        "permission": "write-only",
        "initialization": "uninitialized",
        "ownership": "caller",
        "output": "charlie-channel",
    }
    value["aliases"]["relations"] = [
        {
            "relation": "same-allocation",
            "roots": ["alice-channel", "bob-channel"],
        },
        {
            "relation": "same-allocation",
            "roots": ["bob-channel", "charlie-channel"],
        },
        {
            "relation": "disjoint",
            "roots": ["alice-channel", "charlie-channel"],
        },
    ]
    value["terminal-output-order"]["normal-void"].append("charlie-channel")
    return value


def namespace_collision_policy() -> dict[str, object]:
    return {
        "entry": "namespace-collision",
        "observation-model": "constant-time",
        "principals": ["attacker"],
        "adversaries": {"maximal": [["attacker"]]},
        "hosts": {"compute": {"visibility": "secret"}},
        "components": {
            "value": {"lifecycle": "entry-input", "type": "bv32", "visibility": "secret"}
        },
        "outputs": {},
        "releases": {
            "masked-class": {
                "locator": {"helper": "masked-class", "call-ordinal": 0},
                "audience": "public",
                "type": {"kind": "bv", "width": 32, "byte-order": "little"},
                "expression": {"component": "value"},
                "guard": True,
                "payload-footprint": [0],
                "multiplicity": 1,
            }
        },
    }


def namespace_collision_abi() -> dict[str, object]:
    return {
        "source": "boundary.cpp",
        "relation": "provenance-only",
        "entry": {
            "id": "namespace-collision",
            "symbol": "boundary",
            "host": "compute",
            "function-type": "void (i32)",
            "return": "void",
        },
        "carriers": {"value": {"argument": 0, "llvm-type": "i32", "bit-width": 32}},
        "roots": {},
        "aliases": {"complete": True, "relations": []},
        "terminal-output-order": {"normal-void": []},
    }


def contract_source(
    *,
    declaration: str = "extern void remote_transfer(uint32_t value);",
    definition: str = "",
) -> str:
    return f"""\
#include <stdint.h>
#include <sps/annotations.h>

{declaration}
{definition}
SPS_ENTRY("contract-entry")
void boundary(uint32_t value SPS_COMPONENT("value"))
{{
  remote_transfer(value);
}}
"""


def contract_policy() -> dict[str, object]:
    return {
        "entry": "contract-entry",
        "observation-model": "constant-time",
        "principals": ["observer"],
        "adversaries": {"maximal": [["observer"]]},
        "hosts": {
            "compute": {"visibility": "secret"},
            "remote": {"visibility": "public"},
        },
        "components": {
            "value": {
                "lifecycle": "entry-input",
                "type": "bv32",
                "visibility": "secret",
            }
        },
        "outputs": {},
        "releases": {},
    }


def contract_abi() -> dict[str, object]:
    return {
        "source": "boundary.c",
        "relation": "provenance-only",
        "entry": {
            "id": "contract-entry",
            "symbol": "boundary",
            "host": "compute",
            "function-type": "void (i32)",
            "return": "void",
        },
        "carriers": {"value": {"argument": 0, "llvm-type": "i32", "bit-width": 32}},
        "roots": {},
        "aliases": {"complete": True, "relations": []},
        "terminal-output-order": {"normal-void": []},
    }


def contract_authoring() -> dict[str, object]:
    return {
        "format-id": "SPS-Harness-Authoring-Contracts-v1",
        "claim-boundary": "NonClaimableAuthoringLocator",
        "contracts": [
            {
                "id": "remote-transfer",
                "locator": {"callee": "remote_transfer", "call-ordinal": 0},
                "source-host": "compute",
                "destination-host": "remote",
                "signature": {"arguments": ["i32"], "result": "void"},
                "memory-effects": [],
                "choice": "Unit",
                "total": True,
                "deterministic": True,
                "representation": "SPS-ContractWire-v2",
                "limitations": [
                    "NoFunctionSemantics",
                    "NotCanonicalContractTableV2",
                ],
            }
        ],
    }


def write_contract_case(
    case: Path,
    *,
    source_text: str | None = None,
    contracts_value: dict[str, object] | None = None,
) -> None:
    write_case(
        case,
        source_text=source_text or contract_source(),
        policy_value=contract_policy(),
        abi_value=contract_abi(),
    )
    dump(case / "contracts.sps.yaml", contracts_value or contract_authoring())


def write_case(
    case: Path,
    *,
    source_text: str | None = None,
    policy_value: dict[str, object] | None = None,
    abi_value: dict[str, object] | None = None,
) -> None:
    case.mkdir(parents=True, exist_ok=True)
    (case / "boundary.c").write_text(source_text or c_source(), encoding="utf-8")
    dump(case / "policy.sps.yaml", policy_value or policy())
    dump(case / "abi.sps.yaml", abi_value or abi())


def command(
    harness: Path,
    case: Path,
    extractor: Path,
    clang: Path,
    report: Path,
    resolved: Path,
    *,
    source_name: str = "boundary.c",
) -> list[str]:
    return [
        sys.executable,
        str(harness / "tools" / "sps_boundary.py"),
        "--source",
        str(case / source_name),
        "--policy",
        str(case / "policy.sps.yaml"),
        "--abi",
        str(case / "abi.sps.yaml"),
        "--extractor",
        str(extractor),
        "--clang",
        str(clang),
        "--report",
        str(report),
        "--resolved",
        str(resolved),
    ]


def case_command(
    harness: Path,
    case: Path,
    extractor: Path,
    clang: Path,
    report: Path,
    resolved: Path,
) -> list[str]:
    return [
        sys.executable,
        str(harness / "tools" / "sps_boundary.py"),
        "--case",
        str(case),
        "--extractor",
        str(extractor),
        "--clang",
        str(clang),
        "--report",
        str(report),
        "--resolved",
        str(resolved),
    ]


def expect_rejected(
    harness: Path,
    case: Path,
    extractor: Path,
    clang: Path,
    environment: dict[str, str],
    needle: str,
    *,
    source_name: str = "boundary.c",
) -> None:
    completed = run(
        command(
            harness,
            case,
            extractor,
            clang,
            case / "report.json",
            case / "resolved.json",
            source_name=source_name,
        ),
        environment=environment,
        ok=False,
    )
    if needle not in completed.stderr:
        raise AssertionError(f"missing diagnostic {needle!r}: {completed.stderr}")


def cpp_return_case(case: Path) -> None:
    case.mkdir(parents=True)
    (case / "return.cpp").write_text(
        """\
#include <sps/annotations.h>
extern "C" {
SPS_ENTRY("return-demo")
SPS_RETURN_OUTPUT("selected")
unsigned return_demo(unsigned value SPS_COMPONENT("value"))
{
  return value;
}
}
""",
        encoding="utf-8",
    )
    dump(
        case / "policy.sps.yaml",
        {
            "entry": "return-demo",
            "observation-model": "constant-time",
            "principals": ["attacker"],
            "adversaries": {"maximal": [["attacker"]]},
            "hosts": {"compute": {"visibility": "secret"}},
            "components": {
                "value": {"lifecycle": "entry-input", "type": "bv32", "visibility": "public"}
            },
            "outputs": {"selected": {"visibility": "public"}},
            "releases": {},
        },
    )
    dump(
        case / "abi.sps.yaml",
        {
            "source": "return.cpp",
            "relation": "provenance-only",
            "entry": {
                "id": "return-demo",
                "symbol": "return_demo",
                "host": "compute",
                "function-type": "i32 (i32)",
                "return": {"llvm-type": "i32", "bit-width": 32, "output": "selected"},
            },
            "carriers": {"value": {"argument": 0, "llvm-type": "i32", "bit-width": 32}},
            "roots": {},
            "aliases": {"complete": True, "relations": []},
            "terminal-output-order": {"normal-value": ["selected"]},
        },
    )


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: source_boundary_test.py HARNESS LLVM_BIN")
    harness = Path(sys.argv[1]).resolve()
    llvm_bin = Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(harness / "tools"))
    from source_boundary.build_extractor import ensure_extractor

    environment = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="source-boundary-") as temporary:
        root = Path(temporary)
        environment["LIT_BUILD_ROOT"] = str(root / "lit")
        extractor = ensure_extractor(
            root / "sps-ast-extract", llvm_config=llvm_bin / "llvm-config"
        )
        clang = llvm_bin / "clang"
        case = root / "positive"
        write_case(case)
        report_path = root / "report.json"
        resolved_path = root / "resolved.json"
        run(
            command(harness, case, extractor, clang, report_path, resolved_path),
            environment=environment,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        resolved = json.loads(resolved_path.read_text(encoding="utf-8"))
        assert report["blockers"] == ["ReleaseCarrierMismatch"]
        assert report["modelStatus"] == {"tag": "NotComputed"}
        assert "NormalLLVMAnnotationResidueAbsent" in report["completedChecks"]
        # This is the canonical-JSON-byte ordering used by SPS's derived closure.
        assert [row["members"] for row in resolved["coalitions"]] == [
            ["alice", "bob"],
            ["alice"],
            ["bob"],
            [],
        ]
        assert resolved["coalitions"][2]["visible-outputs"] == ["bob-channel"]
        assert resolved["coalitions"][2]["authorized-releases"] == []
        print("resolved temporary audience boundary and canonical coalition closure")

        contract_case = root / "contract-locator"
        write_contract_case(contract_case)
        contract_report = root / "contract-report.json"
        contract_resolved = root / "contract-resolved.json"
        run(
            command(
                harness,
                contract_case,
                extractor,
                clang,
                contract_report,
                contract_resolved,
            ),
            environment=environment,
        )
        contract_report_value = json.loads(
            contract_report.read_text(encoding="utf-8")
        )
        contract_resolved_value = json.loads(
            contract_resolved.read_text(encoding="utf-8")
        )
        assert contract_report_value["blockers"] == ["OpenModelObligations"]
        assert "ContractLocatorsResolved" in contract_report_value["completedChecks"]
        assert contract_resolved_value["contracts"][0]["claim-boundary"] == (
            "NonClaimableAuthoringLocator"
        )
        assert contract_resolved_value["contracts"][0]["signature"] == "void (i32)"

        local_definition = contract_source(
            declaration="static void remote_transfer(uint32_t value);",
            definition="static void remote_transfer(uint32_t value) { (void)value; }",
        )
        write_contract_case(contract_case, source_text=local_definition)
        expect_rejected(
            harness,
            contract_case,
            extractor,
            clang,
            environment,
            "external declarations for contract callee",
        )

        wrong_ordinal = contract_authoring()
        wrong_ordinal["contracts"][0]["locator"]["call-ordinal"] = 1
        write_contract_case(contract_case, contracts_value=wrong_ordinal)
        expect_rejected(
            harness,
            contract_case,
            extractor,
            clang,
            environment,
            "call ordinal 1 is out of range",
        )

        pointer_source = contract_source(
            declaration="extern void remote_transfer(uint32_t *value);"
        ).replace("remote_transfer(value);", "remote_transfer(&value);")
        write_contract_case(contract_case, source_text=pointer_source)
        expect_rejected(
            harness,
            contract_case,
            extractor,
            clang,
            environment,
            "must have a scalar, non-variadic signature",
        )

        float_contract = contract_authoring()
        float_contract["contracts"][0]["signature"] = {
            "arguments": ["float"],
            "result": "void",
        }
        float_source = contract_source(
            declaration="extern void remote_transfer(float value);"
        ).replace("remote_transfer(value);", "remote_transfer((float)value);")
        write_contract_case(
            contract_case,
            source_text=float_source,
            contracts_value=float_contract,
        )
        expect_rejected(
            harness,
            contract_case,
            extractor,
            clang,
            environment,
            "string does not match '^i[1-9][0-9]*$'",
        )
        print("resolved and fail-closed checked nonclaimable contract locators")

        incomplete_aliases = copy.deepcopy(abi())
        incomplete_aliases["aliases"] = {"complete": False, "relations": []}
        write_case(case, abi_value=incomplete_aliases)
        run(
            command(harness, case, extractor, clang, report_path, resolved_path),
            environment=environment,
        )
        assert json.loads(report_path.read_text(encoding="utf-8"))["blockers"] == [
            "AliasBindingMismatch",
            "ReleaseCarrierMismatch",
        ]

        may_alias = copy.deepcopy(abi())
        may_alias["aliases"]["relations"][0]["relation"] = "may-alias"
        write_case(case, abi_value=may_alias)
        run(
            command(harness, case, extractor, clang, report_path, resolved_path),
            environment=environment,
        )
        assert "AliasBindingMismatch" in json.loads(
            report_path.read_text(encoding="utf-8")
        )["blockers"]

        missing_complete_pair = copy.deepcopy(abi())
        missing_complete_pair["aliases"]["relations"] = []
        write_case(case, abi_value=missing_complete_pair)
        expect_rejected(
            harness,
            case,
            extractor,
            clang,
            environment,
            "complete alias table is missing root pairs",
        )

        initialized_write_only = copy.deepcopy(abi())
        initialized_write_only["roots"]["alice-channel"]["initialization"] = "initialized"
        write_case(case, abi_value=initialized_write_only)
        run(
            command(harness, case, extractor, clang, report_path, resolved_path),
            environment=environment,
        )

        read_write_output_only = copy.deepcopy(abi())
        read_write_output_only["roots"]["alice-channel"]["permission"] = "read-write"
        write_case(case, abi_value=read_write_output_only)
        run(
            command(harness, case, extractor, clang, report_path, resolved_path),
            environment=environment,
        )

        uninitialized_read_write_input = copy.deepcopy(abi())
        uninitialized_read_write_input["roots"]["alice-channel"].update(
            {"permission": "read-write", "input": "alice-initial"}
        )
        input_policy = copy.deepcopy(policy())
        input_policy["components"]["alice-initial"] = {
            "lifecycle": "entry-input",
            "type": "bytes",
            "visibility": "secret",
        }
        write_case(
            case,
            abi_value=uninitialized_read_write_input,
            policy_value=input_policy,
        )
        expect_rejected(
            harness,
            case,
            extractor,
            clang,
            environment,
            "read-write root 'alice-channel' with input must be initialized",
        )

        buffer_case = root / "buffer-input"
        write_case(
            buffer_case,
            source_text=buffer_source(),
            policy_value=buffer_policy(),
            abi_value=buffer_abi(),
        )
        buffer_report = root / "buffer-report.json"
        buffer_resolved = root / "buffer-resolved.json"
        run(
            command(
                harness,
                buffer_case,
                extractor,
                clang,
                buffer_report,
                buffer_resolved,
            ),
            environment=environment,
        )
        buffer_value = json.loads(buffer_resolved.read_text(encoding="utf-8"))
        assert buffer_value["arguments"][0]["input"] == "payload"
        assert buffer_value["terminal-output-order"] == []

        missing_root_input = copy.deepcopy(buffer_abi())
        missing_root_input["roots"]["buffer"].pop("input")
        write_case(
            buffer_case,
            source_text=buffer_source(),
            policy_value=buffer_policy(),
            abi_value=missing_root_input,
        )
        expect_rejected(
            harness,
            buffer_case,
            extractor,
            clang,
            environment,
            "read-only root 'buffer' requires input and forbids output",
        )

        uninitialized_root_input = copy.deepcopy(buffer_abi())
        uninitialized_root_input["roots"]["buffer"]["initialization"] = "uninitialized"
        write_case(
            buffer_case,
            source_text=buffer_source(),
            policy_value=buffer_policy(),
            abi_value=uninitialized_root_input,
        )
        expect_rejected(
            harness,
            buffer_case,
            extractor,
            clang,
            environment,
            "read-only root 'buffer' must be initialized",
        )

        duplicate_component = copy.deepcopy(abi())
        duplicate_component["roots"]["alice-channel"].update(
            {"permission": "read-write", "initialization": "initialized", "input": "logits"}
        )
        write_case(case, abi_value=duplicate_component)
        expect_rejected(
            harness,
            case,
            extractor,
            clang,
            environment,
            "scalar carriers and root inputs repeat logical component IDs",
        )

        byte_release_policy = copy.deepcopy(policy())
        byte_release_policy["components"]["payload"] = {
            "lifecycle": "entry-input",
            "type": "bytes",
            "visibility": "secret",
        }
        byte_release_policy["releases"]["masked-class"]["expression"] = {
            "component": "payload"
        }
        byte_release_abi = copy.deepcopy(abi())
        byte_release_abi["roots"]["alice-channel"].update(
            {"permission": "read-write", "initialization": "initialized", "input": "payload"}
        )
        write_case(
            case, policy_value=byte_release_policy, abi_value=byte_release_abi
        )
        expect_rejected(
            harness,
            case,
            extractor,
            clang,
            environment,
            "byte expressions are not supported yet",
        )

        recursive_expression = copy.deepcopy(policy())
        recursive_expression["releases"]["masked-class"]["expression"] = {
            "bit-xor": {
                "left": {"component": "logits"},
                "right": {"negate": {"constant": 1}},
            }
        }
        write_case(case, policy_value=recursive_expression)
        run(
            command(harness, case, extractor, clang, report_path, resolved_path),
            environment=environment,
        )

        oversized_constant = copy.deepcopy(policy())
        oversized_constant["releases"]["masked-class"]["expression"] = {
            "constant": 1 << 32
        }
        write_case(case, policy_value=oversized_constant)
        expect_rejected(
            harness,
            case,
            extractor,
            clang,
            environment,
            "does not fit in BV32",
        )

        support_case = root / "support-tu"
        write_case(support_case)
        (support_case / "support.cc").write_text(
            'extern "C" unsigned support_identity(unsigned value) { return value; }\n',
            encoding="utf-8",
        )
        support_report = root / "support-report.json"
        support_resolved = root / "support-resolved.json"
        run(
            case_command(
                harness,
                support_case,
                extractor,
                clang,
                support_report,
                support_resolved,
            ),
            environment=environment,
        )
        assert json.loads(support_resolved.read_text(encoding="utf-8"))[
            "support-sources"
        ] == ["support.cc"]

        (support_case / "support.cc").write_text(
            '#include <sps/annotations.h>\nextern "C" {\n'
            'SPS_ENTRY("support-entry")\nvoid support_entry(void) {}\n}\n',
            encoding="utf-8",
        )
        expect_rejected(
            harness,
            support_case,
            extractor,
            clang,
            environment,
            "support source 'support.cc' must not define SPS_ENTRY",
        )

        (support_case / "support.cc").write_text(
            'extern "C" unsigned support_identity(unsigned value) { return value; }\n',
            encoding="utf-8",
        )
        support_abi = abi()
        support_abi["source"] = "support.cc"
        dump(support_case / "abi.sps.yaml", support_abi)
        completed = run(
            case_command(
                harness,
                support_case,
                extractor,
                clang,
                support_report,
                support_resolved,
            ),
            environment=environment,
            ok=False,
        )
        assert "primary source 'support.cc' must define exactly one SPS entry" in completed.stderr

        bad_source = copy.deepcopy(abi())
        bad_source["source"] = "../boundary.c"
        write_case(case, abi_value=bad_source)
        expect_rejected(harness, case, extractor, clang, environment, "does not match")
        print("rejected non-case-local ABI source path")

        bad_visibility = copy.deepcopy(abi())
        bad_visibility["roots"]["alice-channel"]["visibility"] = "public"
        write_case(case, abi_value=bad_visibility)
        expect_rejected(harness, case, extractor, clang, environment, "unknown field 'visibility'")
        print("rejected visibility in ABI authoring data")

        write_case(case)
        policy_path = case / "policy.sps.yaml"
        policy_path.write_text(
            policy_path.read_text(encoding="utf-8") + "entry: duplicate\n",
            encoding="utf-8",
        )
        expect_rejected(harness, case, extractor, clang, environment, "duplicate key 'entry'")
        print("rejected duplicate policy YAML keys")

        write_case(case, source_text=c_source("stale-logits"))
        expect_rejected(harness, case, extractor, clang, environment, "do not exactly cover")
        print("rejected source/policy annotation drift")

        bad_ordinal = policy()
        bad_ordinal["releases"]["masked-class"]["locator"]["call-ordinal"] = 1
        write_case(case, policy_value=bad_ordinal)
        expect_rejected(harness, case, extractor, clang, environment, "out of range")
        print("rejected missing helper call ordinal")

        bad_multiplicity = policy()
        bad_multiplicity["releases"]["masked-class"]["multiplicity"] = 2
        write_case(case, policy_value=bad_multiplicity)
        expect_rejected(harness, case, extractor, clang, environment, "multiplicity must be 1")
        print("rejected unproved release multiplicity")

        write_case(case, source_text=c_source(variadic=True))
        expect_rejected(
            harness, case, extractor, clang, environment, "variadic entries are unsupported"
        )

        write_case(case, source_text=c_source(calling_convention=True))
        expect_rejected(
            harness,
            case,
            extractor,
            clang,
            environment,
            "non-default calling conventions are unsupported",
        )

        write_case(case, source_text=c_source(address_space=True))
        expect_rejected(
            harness,
            case,
            extractor,
            clang,
            environment,
            "non-default pointer address spaces are unsupported",
        )

        write_case(case, source_text=renamed_symbol_source())
        expect_rejected(
            harness,
            case,
            extractor,
            clang,
            environment,
            "definitions for ABI symbol 'boundary'",
        )

        write_case(
            case,
            source_text=three_root_source(),
            policy_value=inconsistent_alias_policy(),
            abi_value=inconsistent_alias_abi(),
        )
        expect_rejected(
            harness,
            case,
            extractor,
            clang,
            environment,
            "disjoint inside one same-allocation class",
        )

        mismatched_allocation = inconsistent_alias_abi()
        mismatched_allocation["aliases"]["relations"] = [
            {
                "relation": "same-allocation",
                "roots": ["alice-channel", "bob-channel", "charlie-channel"],
            }
        ]
        mismatched_allocation["roots"]["charlie-channel"]["extent-bytes"] = 8
        write_case(
            case,
            source_text=three_root_source(),
            policy_value=inconsistent_alias_policy(),
            abi_value=mismatched_allocation,
        )
        expect_rejected(
            harness,
            case,
            extractor,
            clang,
            environment,
            "same-allocation roots must agree on concrete root metadata",
        )

        namespace_case = root / "namespace-collision"
        namespace_case.mkdir()
        (namespace_case / "boundary.cpp").write_text(
            namespace_collision_source(), encoding="utf-8"
        )
        dump(namespace_case / "policy.sps.yaml", namespace_collision_policy())
        dump(namespace_case / "abi.sps.yaml", namespace_collision_abi())
        expect_rejected(
            harness,
            namespace_case,
            extractor,
            clang,
            environment,
            "call ordinal 0 is out of range",
            source_name="boundary.cpp",
        )

        write_case(case, source_text=c_source(warning=True))
        expect_rejected(harness, case, extractor, clang, environment, "normal source compilation failed")
        print("normal no-residue compilation treats warnings as errors")

        cpp_case = root / "cpp-return"
        cpp_return_case(cpp_case)
        cpp_report = root / "cpp-report.json"
        cpp_resolved = root / "cpp-resolved.json"
        cpp_command = command(
            harness,
            cpp_case,
            extractor,
            clang,
            cpp_report,
            cpp_resolved,
            source_name="return.cpp",
        )
        run(cpp_command, environment=environment)
        cpp_value = json.loads(cpp_resolved.read_text(encoding="utf-8"))
        assert cpp_value["return"] == {"bit-width": 32, "llvm-type": "i32", "output": "selected"}
        assert json.loads(cpp_report.read_text(encoding="utf-8"))["blockers"] == []
        print("resolved inert C++ extern-C return annotation")


if __name__ == "__main__":
    main()
