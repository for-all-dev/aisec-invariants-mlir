#!/usr/bin/env python3
"""Dependency-free structural checks for the C/MLIR confidentiality corpus."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
C_DIR = ROOT / "c"
MLIR_DIR = ROOT / "mlir"

PROVENANCE_FIELDS = (
    "Case:",
    "Reduction classification:",
    "Relationship to upstream:",
    "Secret inputs:",
    "Public inputs:",
    "Canonical compiler command:",
    "License note:",
)

MLIR_FIELDS = (
    "// case:",
    "// classification:",
    "// c source:",
    "// upstream GitHub source:",
    "// upstream revision:",
    "// secret:",
    "// public:",
    "// expected outcome:",
    "// observer/model:",
    "// reason id:",
    "// outstanding obligations:",
    "// evidence boundary:",
)

OUTCOMES = frozenset({"verified", "unsafe", "unknown", "conditional"})
CLASSIFICATIONS = frozenset(
    {
        "compiler-generated-minimized",
        "modeled-from-verified-assembly",
        "modeled-fixed-target",
        "modeled-helper-call-without-contract",
        "modeled-test-profile",
        "seeded-semantic-harness",
        "reduced-runtime-model",
    }
)
IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
EVIDENCE_LEVEL = re.compile(r"\bL[0-4]\b")


@dataclass(frozen=True)
class ScenarioContract:
    outcome: str
    observer_model: str
    reason_id: str
    obligations: tuple[str, ...] = ()


# The corpus is intentionally small and curated. Pin the structured outcome,
# model, reason, and obligation fields so a valid-looking replacement cannot
# silently change what a regression fixture claims. Classification, evidence
# level, and provenance are validated separately below.
EXPECTED_SCENARIOS: dict[str, ScenarioContract] = {
    "breach_compressed_length.bad.mlir": ScenarioContract(
        "unsafe", "reduced-public-wire-length-output", "secret-to-public-sink"
    ),
    "breach_compressed_length.fixed.mlir": ScenarioContract(
        "verified", "reduced-public-wire-length-output", "public-sink-isolation"
    ),
    "ckks_unsafe_release.bad.mlir": ScenarioContract(
        "unsafe", "public-release-sink", "unauthorized-release"
    ),
    "ckks_unsafe_release.fixed.mlir": ScenarioContract(
        "conditional",
        "public-release-sink",
        "sanitized-release-requires-evidence",
        (
            "sanitizer-sufficiency",
            "certificate-soundness",
            "release-policy-integrity",
        ),
    ),
    "clangover_poly_frommsg.lowered_bad.mlir": ScenarioContract(
        "unsafe", "x86-control-flow-timing", "secret-dependent-branch"
    ),
    "clangover_poly_frommsg.lowered_fixed.mlir": ScenarioContract(
        "verified", "in-module-x86-control-flow-timing", "branchless-selection"
    ),
    "clangover_poly_frommsg.source.mlir": ScenarioContract(
        "verified", "source-operation-timing", "source-branchless-dataflow"
    ),
    "dynamic_kv_length.bad.mlir": ScenarioContract(
        "unsafe", "reduced-public-count-output", "secret-to-public-sink"
    ),
    "dynamic_kv_length.fixed.mlir": ScenarioContract(
        "verified", "reduced-public-count-output", "public-sink-isolation"
    ),
    "explicit_error_oracle.bad.mlir": ScenarioContract(
        "unsafe", "release-relative-padding-oracle", "residual-leak-beyond-release"
    ),
    "explicit_error_oracle.fixed.mlir": ScenarioContract(
        "verified", "release-relative-padding-oracle", "authorized-release-only"
    ),
    "kyberslash1_poly_tomsg.bad.mlir": ScenarioContract(
        "unsafe", "source-operation-timing", "secret-dependent-variable-latency-op"
    ),
    "kyberslash1_poly_tomsg.fixed.mlir": ScenarioContract(
        "verified", "source-operation-timing", "variable-latency-op-removed"
    ),
    "kyberslash2_compress.bad.mlir": ScenarioContract(
        "unsafe", "source-operation-timing", "secret-dependent-variable-latency-op"
    ),
    "kyberslash2_compress.fixed.mlir": ScenarioContract(
        "verified", "source-operation-timing", "variable-latency-op-removed"
    ),
    "leftoverlocals_scratch.bad.mlir": ScenarioContract(
        "unsafe", "reduced-sequential-cross-tenant-output", "cross-domain-stale-state"
    ),
    "leftoverlocals_scratch.fixed.mlir": ScenarioContract(
        "verified",
        "reduced-sequential-cross-tenant-output",
        "cross-domain-state-reinitialized",
    ),
    "redis_pool_reuse.bad.mlir": ScenarioContract(
        "unsafe", "reduced-sequential-cross-actor-response", "cross-domain-stale-state"
    ),
    "redis_pool_reuse.fixed.mlir": ScenarioContract(
        "verified",
        "reduced-sequential-cross-actor-response",
        "cross-domain-state-reinitialized",
    ),
    "secret_embedding_index.bad.mlir": ScenarioContract(
        "unsafe", "source-memory-address-trace", "secret-dependent-address"
    ),
    "secret_embedding_index.fixed.mlir": ScenarioContract(
        "verified", "source-memory-address-trace", "secret-independent-address-scan"
    ),
    "secret_logging_checkpoint.bad.mlir": ScenarioContract(
        "unsafe", "public-log-and-artifact-sinks", "secret-to-public-sink"
    ),
    "secret_logging_checkpoint.fixed.mlir": ScenarioContract(
        "verified", "public-log-and-artifact-sinks", "public-sink-isolation"
    ),
    "wolfssl_3579_mul.source.mlir": ScenarioContract(
        "unknown",
        "rv32i-helper-timing",
        "missing-target-timing",
        ("target-lowering-semantics", "helper-latency-contract"),
    ),
    "wolfssl_3579_mul.target_bad.mlir": ScenarioContract(
        "unsafe",
        "affected-rv32i-muldi3-v1",
        "secret-dependent-variable-latency-call",
    ),
    "wolfssl_3579_mul.target_constant_latency.mlir": ScenarioContract(
        "verified",
        "constant-latency-muldi3-test-v1",
        "constant-latency-helper-contract",
    ),
    "wolfssl_3579_mul.target_fixed.mlir": ScenarioContract(
        "conditional",
        "modeled-rv32i-timing",
        "fixed-loop-requires-target-evidence",
        ("base-operation-latency", "backend-trace-preservation"),
    ),
    "wolfssl_3579_mul.target_unknown.mlir": ScenarioContract(
        "unknown",
        "rv32i-helper-timing",
        "missing-helper-contract",
        ("helper-latency-contract",),
    ),
    "wolfssl_3580_mask.source.mlir": ScenarioContract(
        "verified", "source-operation-timing", "source-branchless-dataflow"
    ),
    "wolfssl_3580_mask.target_bad.mlir": ScenarioContract(
        "unsafe", "modeled-rv32i-control-flow-timing", "secret-dependent-branch"
    ),
    "wolfssl_3580_mask.target_fixed.mlir": ScenarioContract(
        "verified", "modeled-rv32i-control-flow-timing", "branchless-selection"
    ),
    "wrong_host_fhe_reveal.bad.mlir": ScenarioContract(
        "unsafe", "host-authorized-plaintext-sinks", "wrong-audience-or-host"
    ),
    "wrong_host_fhe_reveal.fixed.mlir": ScenarioContract(
        "verified", "host-authorized-plaintext-sinks", "authorized-sink-isolation"
    ),
    "wrong_party_plaintext.bad.mlir": ScenarioContract(
        "unsafe", "audience-authorized-mailbox-sinks", "wrong-audience-or-host"
    ),
    "wrong_party_plaintext.fixed.mlir": ScenarioContract(
        "verified", "audience-authorized-mailbox-sinks", "authorized-sink-isolation"
    ),
}

ERROR_BLOCK = re.compile(
    r"(?m)^\s*// CONFIDENTIALITY ERROR: .+\n"
    r"\s*// secret source: .+\n"
    r"\s*// observable effect: .+\n"
    r"\s*// reason: .+\n"
    r"\s*// detection boundary: .+\n"
    r"\s*// expected-error @\+1 \{\{[a-z][a-z0-9]*(?:-[a-z0-9]+)*\}\}\n"
    r"\s*(?!//)(?:[%^}]|[a-zA-Z]).+"
)

EXPECTED_ERROR_DIRECTIVE = re.compile(
    r"(?m)^\s*// expected-error @\+1 "
    r"\{\{([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\}\}\s*$"
)
DIAGNOSTIC_RUN = "// RUN: %mlir-opt %s --verify-diagnostics"

REPAIR_BLOCK = re.compile(
    r"(?m)^\s*// CONFIDENTIALITY REPAIR: .+\n"
    r"\s*// secret source: .+\n"
    r"\s*// (?:removed observable|safe effect): .+\n"
    r"\s*// reason: .+\n"
    r"\s*// detection boundary: .+\n"
    r"\s*(?!//)(?:[%^}]|[a-zA-Z]).+"
)


# These snippets pin the distinctions that previously made several fixtures
# misleading. They are structural regression checks, not an IFC proof.
FIXTURE_CONTRACT_SNIPPETS: dict[str, tuple[str, ...]] = {
    "explicit_error_oracle.bad.mlir": (
        "// SANCTIONED RELEASE:",
        '"sps.release_policy" = "padding_validity_v1"',
        "llvm.store %status, %public_status",
        "llvm.store %padding_error_detail, %public_error_detail",
    ),
    "explicit_error_oracle.fixed.mlir": (
        "// SANCTIONED RELEASE:",
        '"sps.release_policy" = "padding_validity_v1"',
        "llvm.store %status, %public_status",
        "llvm.store %zero, %public_error_detail",
    ),
    "ckks_unsafe_release.bad.mlir": (
        "// private result:",
        "llvm.store %raw_approximate_plaintext, %public_release",
    ),
    "ckks_unsafe_release.fixed.mlir": (
        "// private result:",
        '"sps.contract_kind" = "sanitizer"',
        '"sps.contract_status" = "requires_l4_evidence"',
        '"sps.release_function" = "(raw & public_mask) & certificate_mask"',
        '"sps.required_integrity" = "public_sanitizer_mask:trusted,certificate_ok:trusted"',
        "%masked_plaintext = llvm.and %raw_approximate_plaintext, %public_sanitizer_mask",
        "llvm.call @ckks_sanitize_model",
        '"sps.release_policy" = "ckks_masked_release_v1"',
        "llvm.store %sanitized, %public_release",
    ),
    "dynamic_kv_length.bad.mlir": (
        "// L4 extrapolation: no allocation, dynamic shape, loop, or scheduler event is encoded here",
    ),
    "dynamic_kv_length.fixed.mlir": (
        "// L4 extrapolation: actual fixed allocation and fixed work are not encoded here",
    ),
    "breach_compressed_length.bad.mlir": (
        "// L4 extrapolation: the match-to-length relation is already inlined; no compressor is encoded",
    ),
    "breach_compressed_length.fixed.mlir": (
        "// L4 extrapolation: no compressor, padding, or transport event is encoded here",
    ),
    "wolfssl_3579_mul.target_bad.mlir": (
        '"sps.contract_status" = "assumed_l0_target_fact"',
        '"sps.helper_latency" = "operand_dependent"',
        '"sps.real_target_applicability" = "requires_l4_evidence"',
        '"sps.relevant_operands" = array<i32: 0, 1>',
    ),
}

ORDERED_FIXTURE_SNIPPETS: dict[str, tuple[str, ...]] = {
    "explicit_error_oracle.bad.mlir": (
        "llvm.store %status, %public_status",
        "llvm.store %padding_error_detail, %public_error_detail",
    ),
    "explicit_error_oracle.fixed.mlir": (
        "llvm.store %status, %public_status",
        "llvm.store %zero, %public_error_detail",
    ),
    "ckks_unsafe_release.fixed.mlir": (
        "llvm.call @ckks_sanitize_model",
        "llvm.store %sanitized, %public_release",
    ),
}


def fail(errors: list[str], path: Path, message: str) -> None:
    errors.append(f"{path.relative_to(ROOT)}: {message}")


def c_sources() -> list[Path]:
    return sorted(
        path
        for path in C_DIR.glob("*.c")
        if path.name != "equivalence_driver.c"
    )


def check_provenance() -> list[str]:
    errors: list[str] = []
    mutable = re.compile(r"github\.com/[^/]+/[^/]+/(?:blob|tree)/(?:main|master)(?:/|$)")
    github_revision = re.compile(
        r"github\.com/[^/]+/[^/]+/(?:blob|tree)/([^/#?]+)(?:/|$)"
    )

    for path in c_sources():
        text = path.read_text()
        for field in PROVENANCE_FIELDS:
            if field not in text:
                fail(errors, path, f"missing provenance field {field!r}")

        has_original = "Original vulnerable code:" in text
        declares_none = re.search(
            r"Original C source:\s*\n\s*\*\s+none\b", text, re.IGNORECASE
        )
        if not has_original and not declares_none:
            fail(
                errors,
                path,
                "must link Original vulnerable code or declare Original C source: none",
            )

        for url in re.findall(r"https://[^\s*)]+", text):
            clean_url = url.rstrip(".,")
            if mutable.search(clean_url):
                fail(errors, path, f"mutable GitHub URL {clean_url}")
            match = github_revision.search(clean_url)
            if match and not re.fullmatch(r"[0-9a-f]{40}", match.group(1)):
                fail(errors, path, f"GitHub blob/tree URL lacks a full commit: {clean_url}")

        classification_match = re.search(
            r"Reduction classification:\s*\n\s*\*\s+([^\n]+)", text
        )
        classification = classification_match.group(1).strip() if classification_match else ""
        if declares_none and classification in {
            "faithful-minimal-reduction",
            "adapted-upstream-snippet",
        }:
            fail(errors, path, "claims an upstream-C reduction after declaring no C source")

    return errors


def is_bad(path: Path) -> bool:
    return any(marker in path.name for marker in (".bad.mlir", "_bad.mlir", "lowered_bad", "target_bad"))


def is_fixed(path: Path) -> bool:
    return any(marker in path.name for marker in (".fixed.mlir", "_fixed.mlir", "lowered_fixed", "target_fixed"))


def field_values(text: str, field: str) -> list[str]:
    """Return values for an exact, line-oriented MLIR metadata field."""
    return [
        match.group(1).strip()
        for match in re.finditer(
            rf"(?m)^\s*{re.escape(field)}\s*(.*?)\s*$", text
        )
    ]


def check_fixture_inventory(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    actual = {path.name for path in paths}
    expected = set(EXPECTED_SCENARIOS)
    for name in sorted(expected - actual):
        errors.append(f"mlir/{name}: expected fixture is missing")
    for name in sorted(actual - expected):
        errors.append(
            f"mlir/{name}: fixture has no scenario contract in check_harness.py"
        )
    return errors


def check_metadata(errors: list[str], path: Path, text: str) -> str | None:
    values: dict[str, str] = {}
    for field in MLIR_FIELDS:
        found = field_values(text, field)
        if not found:
            fail(errors, path, f"missing MLIR header field {field!r}")
            continue
        if len(found) != 1:
            fail(errors, path, f"MLIR header field {field!r} occurs {len(found)} times")
            continue
        if not found[0]:
            fail(errors, path, f"MLIR header field {field!r} is empty")
            continue
        values[field] = found[0]

    if field_values(text, "// expected verdict:"):
        fail(errors, path, "uses legacy '// expected verdict:' metadata")
    if field_values(text, "// exact incident boundary:"):
        fail(errors, path, "uses legacy '// exact incident boundary:' metadata")
    metadata_text = "\n".join(values.values())
    if re.search(r"\b(?:pass|reject)\b", metadata_text, re.IGNORECASE):
        fail(errors, path, "uses legacy pass/reject wording in MLIR metadata")

    classification = values.get("// classification:")
    if classification is not None and classification not in CLASSIFICATIONS:
        fail(
            errors,
            path,
            "classification must be one of: " + ", ".join(sorted(CLASSIFICATIONS)),
        )

    outcome = values.get("// expected outcome:")
    if outcome is not None and outcome not in OUTCOMES:
        fail(
            errors,
            path,
            "expected outcome must be exactly one of: " + ", ".join(sorted(OUTCOMES)),
        )

    expected = EXPECTED_SCENARIOS.get(path.name)
    if outcome in OUTCOMES and expected is not None and outcome != expected.outcome:
        fail(
            errors,
            path,
            f"expected outcome is {outcome!r}; scenario requires {expected.outcome!r}",
        )

    observer = values.get("// observer/model:")
    if observer is not None and not IDENTIFIER.fullmatch(observer):
        fail(errors, path, "observer/model must be one lower-kebab-case identifier")
    elif expected is not None and observer != expected.observer_model:
        fail(
            errors,
            path,
            f"observer/model is {observer!r}; scenario requires {expected.observer_model!r}",
        )

    reason = values.get("// reason id:")
    if reason is not None and not IDENTIFIER.fullmatch(reason):
        fail(errors, path, "reason id must be one lower-kebab-case identifier")
    elif expected is not None and reason != expected.reason_id:
        fail(
            errors,
            path,
            f"reason id is {reason!r}; scenario requires {expected.reason_id!r}",
        )

    obligations = values.get("// outstanding obligations:")
    if obligations is not None:
        if obligations == "none":
            parsed_obligations: list[str] = []
        else:
            parsed_obligations = obligations.split(",")
            if any(not IDENTIFIER.fullmatch(item) for item in parsed_obligations):
                fail(
                    errors,
                    path,
                    "outstanding obligations must be 'none' or a comma-separated "
                    "list of lower-kebab-case identifiers",
                )
            if len(set(parsed_obligations)) != len(parsed_obligations):
                fail(errors, path, "outstanding obligations contain a duplicate")

        if outcome in {"verified", "unsafe"} and parsed_obligations:
            fail(errors, path, f"{outcome} outcome cannot have outstanding obligations")
        if outcome in {"unknown", "conditional"} and not parsed_obligations:
            fail(errors, path, f"{outcome} outcome requires an outstanding obligation")
        if expected is not None and tuple(parsed_obligations) != expected.obligations:
            required = ",".join(expected.obligations) or "none"
            fail(
                errors,
                path,
                f"outstanding obligations are {obligations!r}; scenario requires {required!r}",
            )

    boundary = values.get("// evidence boundary:")
    if boundary is not None and not EVIDENCE_LEVEL.search(boundary):
        fail(errors, path, "evidence boundary must name at least one level L0 through L4")

    c_source = values.get("// c source:")
    if c_source is not None:
        candidate = (MLIR_DIR / c_source).resolve()
        try:
            candidate.relative_to(C_DIR.resolve())
        except ValueError:
            fail(errors, path, "c source must resolve inside the harness c/ directory")
        else:
            if candidate.suffix != ".c" or not candidate.is_file():
                fail(errors, path, f"c source does not name an existing C file: {c_source}")
            elif is_bad(path) and not candidate.stem.endswith(("_bad", "_vulnerable")):
                fail(errors, path, "bad fixture must cite its bad or vulnerable C provenance")
            elif is_fixed(path) and not candidate.stem.endswith("_fixed"):
                fail(errors, path, "fixed fixture must cite its fixed C provenance")

    return outcome


def check_annotations() -> list[str]:
    errors: list[str] = []
    paths = sorted(MLIR_DIR.glob("*.mlir"))
    errors.extend(check_fixture_inventory(paths))

    for path in paths:
        text = path.read_text()
        outcome = check_metadata(errors, path, text)

        if "CONFIDENTIALITY BREAK" in text:
            fail(errors, path, "uses obsolete CONFIDENTIALITY BREAK marker")

        error_count = text.count("CONFIDENTIALITY ERROR:")
        repair_count = text.count("CONFIDENTIALITY REPAIR:")
        expected_errors = EXPECTED_ERROR_DIRECTIVE.findall(text)
        diagnostic_run_count = text.count(DIAGNOSTIC_RUN)
        complete_errors = len(ERROR_BLOCK.findall(text))
        complete_repairs = len(REPAIR_BLOCK.findall(text))
        if complete_errors != error_count:
            fail(errors, path, "has an incomplete or non-adjacent confidentiality error block")
        if complete_repairs != repair_count:
            fail(errors, path, "has an incomplete or non-adjacent confidentiality repair block")

        if is_bad(path):
            if outcome != "unsafe":
                fail(errors, path, "bad fixture must have outcome 'unsafe'")
            if error_count == 0:
                fail(errors, path, "lacks a complete error block adjacent to an MLIR op")
            if repair_count:
                fail(errors, path, "bad fixture contains a confidentiality repair block")
            if diagnostic_run_count != 1:
                fail(
                    errors,
                    path,
                    "bad fixture must have exactly one active --verify-diagnostics RUN",
                )
            if len(expected_errors) != error_count:
                fail(
                    errors,
                    path,
                    "each confidentiality error must have one adjacent expected-error",
                )
            expected_reason = EXPECTED_SCENARIOS[path.name].reason_id
            for actual_reason in expected_errors:
                if actual_reason != expected_reason:
                    fail(
                        errors,
                        path,
                        f"expected-error reason is {actual_reason!r}; "
                        f"scenario requires {expected_reason!r}",
                    )
        elif error_count:
            fail(errors, path, "non-bad fixture contains a confidentiality error block")
        elif expected_errors or diagnostic_run_count:
            fail(errors, path, "non-bad fixture contains a bad-fixture diagnostic oracle")

        if is_fixed(path):
            if outcome not in {"verified", "conditional"}:
                fail(errors, path, "fixed fixture must have outcome 'verified' or 'conditional'")
            if error_count:
                fail(errors, path, "fixed fixture contains a confidentiality error")
            if repair_count == 0:
                fail(errors, path, "lacks a complete repair block adjacent to an MLIR op")
        elif repair_count:
            fail(errors, path, "non-fixed fixture contains a confidentiality repair block")

        if outcome == "unsafe" and not is_bad(path):
            fail(errors, path, "unsafe outcome requires a bad fixture filename")
        if outcome == "unknown" and (error_count or repair_count):
            fail(errors, path, "unknown fixture cannot claim a confidentiality error or repair")

        for snippet in FIXTURE_CONTRACT_SNIPPETS.get(path.name, ()):
            if snippet not in text:
                fail(errors, path, f"missing fixture-contract snippet {snippet!r}")

        ordered = ORDERED_FIXTURE_SNIPPETS.get(path.name, ())
        if ordered and all(snippet in text for snippet in ordered):
            positions = [text.index(snippet) for snippet in ordered]
            if positions != sorted(positions):
                fail(errors, path, "fixture-contract operations are out of order")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "check", choices=("provenance", "annotations", "all"), default="all", nargs="?"
    )
    args = parser.parse_args()

    errors: list[str] = []
    if args.check in ("provenance", "all"):
        errors.extend(check_provenance())
    if args.check in ("annotations", "all"):
        errors.extend(check_annotations())

    if errors:
        print("\n".join(f"error: {message}" for message in errors), file=sys.stderr)
        return 1

    print(f"{args.check} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
