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
#: Section-10 diagnostic dispositions. RelationalRequired is the one that makes
#: precision controls expressible: it says the diagnostic layer completed and
#: could not decide, so the product must. It is NOT silence, and coercing a
#: control to silence invites the StaticallyDischarged shortcut that cannot
#: establish safety.
DISPOSITIONS = frozenset(
    {
        "not-observable",
        "statically-discharged",
        "definite-violation",
        "relational-required",
        "unknown",
    }
)
#: A target tuple is triple/cpu/opt-level, each a lower-kebab or numeric token.
TARGET_TUPLE = re.compile(r"[a-z0-9_.-]+/[a-z0-9_.-]+/O[0-3sz]\Z")
#: A coalition is {} or {a} or {a,b}: lower-kebab members, comma separated.
COALITION = re.compile(r"\{(?:[a-z][a-z0-9-]*(?:,[a-z][a-z0-9-]*)*)?\}\Z")
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


#: A verdict is only ever a claim about one (entry, coalition) pair, evaluated
#: for one target tuple. There is exactly one representation: every fixture
#: carries rows, and a single-observer fixture carries one row keyed by the
#: empty coalition -- the world-visible observer.
@dataclass(frozen=True)
class ResultRow:
    coalition: str
    outcome: str
    reason_id: str
    obligations: tuple[str, ...] = ()


#: Aggregate a row set into the artifact-level outcome. Deliberately total and
#: order-independent: unsafe dominates, then unknown, then conditional. A row set
#: that is entirely verified aggregates to verified.
AGGREGATE_ORDER = ("unsafe", "unknown", "conditional", "verified")


def aggregate_outcome(rows: tuple[ResultRow, ...]) -> str:
    present = {row.outcome for row in rows}
    for candidate in AGGREGATE_ORDER:
        if candidate in present:
            return candidate
    return "verified"


@dataclass(frozen=True)
class ScenarioContract:
    """A verdict is a SET OF ROWS, one per (entry, coalition).

    There is deliberately no single-outcome form. A fixture with one observer
    has one row whose coalition is the empty set -- the world-visible observer --
    rather than a separate flatter representation. Two ways to say the same
    thing is what made the actor dimension unrepresentable for so long: the
    scalar form could not grow a second row, and nothing forced the question.

    outcome, reason_id and obligations are DERIVED from the rows. They are not
    stored, so they cannot disagree with them.
    """

    observer_model: str
    rows: tuple[ResultRow, ...]
    #: The target tuple a verdict is relative to. Empty means the fixture's
    #: conclusion is target-independent and must say so in its evidence
    #: boundary. Measured counterexample: one module emits a secret-dependent
    #: branch on x86-64 and a conditional select on aarch64, so a control-flow
    #: verdict without a target tuple is not a claim about anything runnable.
    target_tuple: str = ""
    #: Required first-layer disposition. Present only on precision controls,
    #: where the point is that the diagnostic layer is EXPECTED to lose
    #: precision; without this field a control cannot say "report imprecision
    #: here, but never silence", so the suite cannot catch an analysis that
    #: invents leaks.
    disposition: str = ""

    @property
    def outcome(self) -> str:
        return aggregate_outcome(self.rows)

    @property
    def reason_ids(self) -> frozenset[str]:
        """Every reason the rows carry.

        There is deliberately no single derived reason_id. With several rows
        carrying different reasons nothing picks one: audience_mismatch is
        unsafe at {} for raw-item-not-world-releasable and unsafe at {bob} for
        release-audience-mismatch, and neither is more the artifact's reason
        than the other. The header names whichever the diagnostic pins, and is
        checked for MEMBERSHIP rather than equality.
        """
        return frozenset(row.reason_id for row in self.rows)

    @property
    def obligations(self) -> tuple[str, ...]:
        """Union across rows, first-seen order, so it stays deterministic."""
        seen: list[str] = []
        for row in self.rows:
            for item in row.obligations:
                if item not in seen:
                    seen.append(item)
        return tuple(seen)


def one_row(outcome: str, reason: str, obligations: tuple[str, ...] = ()) -> tuple[ResultRow, ...]:
    """A single world-visible-observer row: the common case, stated once."""
    return (ResultRow("{}", outcome, reason, obligations),)


# The corpus is intentionally small and curated. Pin the structured outcome,
# model, reason, and obligation fields so a valid-looking replacement cannot
# silently change what a regression fixture claims. Classification, evidence
# level, and provenance are validated separately below.
EXPECTED_SCENARIOS: dict[str, ScenarioContract] = {
    # Metatheory countermodel encodings. Each refutes one invalid proof or
    # reporting principle the metatheory names as a required negative result.
    # MT-CM5: unproved ABI alias separation may not be assumed. Unknown rather
    # than unsafe, because no witness replayed by the exact semantics exists.
    "abi_alias_unproved.unknown.mlir": ScenarioContract(
        "public-sink-value",
        one_row("unknown", "alias-binding-mismatch", ("proved-disjoint-clause",)),
    ),
    # Allocation-size acceptance pair. The refusal and its twin differ only in the
    # label and binding on the size operand, so neither can be satisfied by
    # inspecting the allocation shape alone.
    "alloca_size_high_count.unknown.mlir": ScenarioContract(
        "allocation-size-trace",
        one_row("unknown", "alloca-size-not-world-structural", ("world-structural-size-expression",)),
    ),
    "alloca_size_public.control.mlir": ScenarioContract(
        "allocation-size-trace",
        one_row("verified", "world-structural-alloca-size"),
    ),
    # MT-CM2: bounded-run filtering is not a sound proof domain. First loop
    # fixture in the corpus. loop-remainder must never denote an engine cap.
    "bound_exhausted_loop.unknown.mlir": ScenarioContract(
        "operation-count-trace",
        one_row("unknown", "loop-remainder", ("bound-adequacy",)),
    ),
    # First fixture with per-(entry, coalition) rows. verified at {alice} and
    # unsafe at {bob} on byte-identical operations; the artifact outcome is the
    # projection of the rows, recomputed rather than trusted.
    "audience_mismatch.bad.mlir": ScenarioContract(
        "public-sink-value",
        (
            ResultRow("{}", "unsafe", "raw-item-not-world-releasable"),
            ResultRow("{alice}", "verified", "authorized-audience"),
            ResultRow("{bob}", "unsafe", "release-audience-mismatch"),
            ResultRow("{alice,bob}", "unsafe", "release-audience-mismatch"),
        ),
    ),
    "breach_compressed_length.bad.mlir": ScenarioContract(
        "reduced-public-wire-length-output",
        one_row("unsafe", "secret-to-public-sink"),
    ),
    "breach_compressed_length.fixed.mlir": ScenarioContract(
        "reduced-public-wire-length-output",
        one_row("verified", "public-sink-isolation"),
    ),
    "ckks_unsafe_release.bad.mlir": ScenarioContract(
        "public-release-sink",
        one_row("unsafe", "unauthorized-release"),
    ),
    "ckks_unsafe_release.fixed.mlir": ScenarioContract(
        "public-release-sink",
        one_row("conditional", "sanitized-release-requires-evidence", (
            "sanitizer-sufficiency",
            "certificate-soundness",
            "release-policy-integrity",
        )),
    ),
    "clangover_poly_frommsg.lowered_bad.mlir": ScenarioContract(
        "x86-control-flow-timing",
        one_row("unsafe", "secret-dependent-branch"),
    ),
    "clangover_poly_frommsg.lowered_fixed.mlir": ScenarioContract(
        "in-module-x86-control-flow-timing",
        one_row("verified", "branchless-selection"),
    ),
    "clangover_poly_frommsg.source.mlir": ScenarioContract(
        "source-operation-timing",
        one_row("verified", "source-branchless-dataflow"),
    ),
    "dynamic_kv_length.bad.mlir": ScenarioContract(
        "reduced-public-count-output",
        one_row("unsafe", "secret-to-public-sink"),
    ),
    "dynamic_kv_length.fixed.mlir": ScenarioContract(
        "reduced-public-count-output",
        one_row("verified", "public-sink-isolation"),
    ),
    "explicit_error_oracle.bad.mlir": ScenarioContract(
        "release-relative-padding-oracle",
        one_row("unsafe", "residual-leak-beyond-release"),
    ),
    "explicit_error_oracle.fixed.mlir": ScenarioContract(
        "release-relative-padding-oracle",
        one_row("verified", "authorized-release-only"),
    ),
    "kyberslash1_poly_tomsg.bad.mlir": ScenarioContract(
        "source-operation-timing",
        one_row("unsafe", "secret-dependent-variable-latency-op"),
    ),
    # Compiler-introduced leak. The only fixture whose obligations can be
    # discharged solely by evidence from a LOWER level: the module is branchless
    # and an IR-level analysis has nothing to object to, yet the x86 backend
    # converts the select to a conditional jump because it has a memory operand.
    # unknown rather than verified because the artifact that runs is not this
    # one; unknown rather than unsafe because no replayable counterexample
    # exists at this level. See integration/laundering-x86-codegen.test.
    "launder_scan.analyzed_clean.unknown.mlir": ScenarioContract(
        "target-control-flow-timing",
        one_row("unknown", "backend-may-reintroduce-branch", ("backend-trace-preservation", "target-tuple-binding")),
        target_tuple="x86_64-unknown-linux-gnu/generic/O2",
    ),
    "kyberslash1_poly_tomsg.fixed.mlir": ScenarioContract(
        "source-operation-timing",
        one_row("verified", "variable-latency-op-removed"),
    ),
    "kyberslash2_compress.bad.mlir": ScenarioContract(
        "source-operation-timing",
        one_row("unsafe", "secret-dependent-variable-latency-op"),
    ),
    "kyberslash2_compress.fixed.mlir": ScenarioContract(
        "source-operation-timing",
        one_row("verified", "variable-latency-op-removed"),
    ),
    "leftoverlocals_scratch.bad.mlir": ScenarioContract(
        "reduced-sequential-cross-tenant-output",
        one_row("unsafe", "cross-domain-stale-state"),
    ),
    "leftoverlocals_scratch.fixed.mlir": ScenarioContract(
        "reduced-sequential-cross-tenant-output",
        one_row("verified", "cross-domain-state-reinitialized"),
    ),
    # Diagnostic-precision negative controls. Each is release-relative
    # noninterferent, so a reported violation is imprecision, not a finding.
    # Section 10 gives the diagnostic analysis no proof-authoritative strong
    # update, no summaries, and no slice selection, so each site below is
    # RelationalRequired at L1 and is decided by the exact product at L2.
    # These carry no diagnostic RUN: the required disposition is
    # RelationalRequired, not silence, and coercing them to silence invites the
    # StaticallyDischarged shortcut that section 10 forbids.
    "precision_identical_successor.control.mlir": ScenarioContract(
        "source-control-location-trace",
        one_row("verified", "identical-successor-control-location"),
        disposition="relational-required",
    ),
    "precision_offset_disjoint.control.mlir": ScenarioContract(
        "public-sink-value",
        one_row("verified", "offset-disjoint-public-reload"),
        disposition="relational-required",
    ),
    "precision_overwritten_slot.control.mlir": ScenarioContract(
        "public-sink-value",
        one_row("verified", "public-overwrite-before-observation"),
        disposition="relational-required",
    ),
    "precision_xor_cancellation.control.mlir": ScenarioContract(
        "public-sink-value",
        one_row("verified", "lane-equal-value-after-cancellation"),
        disposition="relational-required",
    ),
    # Anti-control for precision_identical_successor: same single-successor
    # branch shape, differing only in block-argument operands. Satisfying that
    # control by the rule "identical successors imply no control leak" silently
    # accepts this counterexample.
    "predecessor_choice_blockarg.bad.mlir": ScenarioContract(
        "public-sink-value",
        one_row("unsafe", "secret-selected-block-argument"),
    ),
    # MT-CM3: a future release may not condition an earlier observation.
    "prefix_causal_release.bad.mlir": ScenarioContract(
        "release-relative-public-channel",
        one_row("unsafe", "pre-release-observation"),
    ),
    "redis_pool_reuse.bad.mlir": ScenarioContract(
        "reduced-sequential-cross-actor-response",
        one_row("unsafe", "cross-domain-stale-state"),
    ),
    "redis_pool_reuse.fixed.mlir": ScenarioContract(
        "reduced-sequential-cross-actor-response",
        one_row("verified", "cross-domain-state-reinitialized"),
    ),
    "secret_embedding_index.bad.mlir": ScenarioContract(
        "source-memory-address-trace",
        one_row("unsafe", "secret-dependent-address"),
    ),
    "secret_embedding_index.fixed.mlir": ScenarioContract(
        "source-memory-address-trace",
        one_row("verified", "secret-independent-address-scan"),
    ),
    "secret_logging_checkpoint.bad.mlir": ScenarioContract(
        "public-log-and-artifact-sinks",
        one_row("unsafe", "secret-to-public-sink"),
    ),
    "secret_logging_checkpoint.fixed.mlir": ScenarioContract(
        "public-log-and-artifact-sinks",
        one_row("verified", "public-sink-isolation"),
    ),
    "wolfssl_3579_mul.source.mlir": ScenarioContract(
        "rv32i-helper-timing",
        one_row("unknown", "missing-target-timing", ("target-lowering-semantics", "helper-latency-contract")),
    ),
    "wolfssl_3579_mul.target_bad.mlir": ScenarioContract(
        "affected-rv32i-muldi3-v1",
        one_row("unsafe", "secret-dependent-variable-latency-call"),
    ),
    "wolfssl_3579_mul.target_constant_latency.mlir": ScenarioContract(
        "constant-latency-muldi3-test-v1",
        one_row("verified", "constant-latency-helper-contract"),
    ),
    "wolfssl_3579_mul.target_fixed.mlir": ScenarioContract(
        "modeled-rv32i-timing",
        one_row("conditional", "fixed-loop-requires-target-evidence", ("base-operation-latency", "backend-trace-preservation")),
    ),
    "wolfssl_3579_mul.target_unknown.mlir": ScenarioContract(
        "rv32i-helper-timing",
        one_row("unknown", "missing-helper-contract", ("helper-latency-contract",)),
    ),
    "wolfssl_3580_mask.source.mlir": ScenarioContract(
        "source-operation-timing",
        one_row("verified", "source-branchless-dataflow"),
    ),
    "wolfssl_3580_mask.target_bad.mlir": ScenarioContract(
        "modeled-rv32i-control-flow-timing",
        one_row("unsafe", "secret-dependent-branch"),
    ),
    "wolfssl_3580_mask.target_fixed.mlir": ScenarioContract(
        "modeled-rv32i-control-flow-timing",
        one_row("verified", "branchless-selection"),
    ),
    "wrong_host_fhe_reveal.bad.mlir": ScenarioContract(
        "host-authorized-plaintext-sinks",
        one_row("unsafe", "wrong-audience-or-host"),
    ),
    "wrong_host_fhe_reveal.fixed.mlir": ScenarioContract(
        "host-authorized-plaintext-sinks",
        one_row("verified", "authorized-sink-isolation"),
    ),
    "wrong_party_plaintext.bad.mlir": ScenarioContract(
        "audience-authorized-mailbox-sinks",
        one_row("unsafe", "wrong-audience-or-host"),
    ),
    "wrong_party_plaintext.fixed.mlir": ScenarioContract(
        "audience-authorized-mailbox-sinks",
        one_row("verified", "authorized-sink-isolation"),
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


#: A result-row block looks like:
#:
#:   // result rows:
#:   //   {}          verified  world-visible-observer          none
#:   //   {alice}     unsafe    release-audience-mismatch       none
#:   //   {bob}       unknown   missing-helper-contract         helper-latency-contract
#:
#: Columns are coalition, outcome, reason id, obligations. Whitespace separated,
#: obligations comma separated or the literal 'none'.
RESULT_ROW = re.compile(
    r"(?m)^\s*//\s+(\{[^}]*\})\s+(\w+)\s+([a-z][a-z0-9-]*)\s+(\S+)\s*$"
)


def parse_result_rows(errors: list[str], path: Path, text: str) -> tuple[ResultRow, ...]:
    """Parse an optional '// result rows:' block. Absent block means no rows."""
    if not field_values(text, "// result rows:"):
        return ()

    block = text.split("// result rows:", 1)[1]
    #: Stop at the first line that is not a row, so a following metadata field
    #: or prose comment ends the block rather than being silently swallowed.
    lines: list[str] = []
    for line in block.splitlines()[1:]:
        if RESULT_ROW.fullmatch(line):
            lines.append(line)
        elif line.strip().startswith("//") and not line.strip("/ \t"):
            continue
        else:
            break

    rows: list[ResultRow] = []
    seen: set[str] = set()
    for line in lines:
        coalition, outcome, reason, obligations = RESULT_ROW.fullmatch(line).groups()
        if not COALITION.fullmatch(coalition):
            fail(errors, path, f"malformed coalition {coalition!r} in result rows")
            continue
        if coalition in seen:
            fail(errors, path, f"duplicate coalition {coalition!r} in result rows")
            continue
        seen.add(coalition)
        if outcome not in OUTCOMES:
            fail(errors, path, f"result row {coalition} has invalid outcome {outcome!r}")
            continue
        parsed = () if obligations == "none" else tuple(obligations.split(","))
        if any(not IDENTIFIER.fullmatch(item) for item in parsed):
            fail(errors, path, f"result row {coalition} has a malformed obligation")
            continue
        #: The same invariant as the artifact level, enforced per row: a row that
        #: claims to be finished may not carry an obligation, and a row that is
        #: not finished must say what would finish it.
        if outcome in {"verified", "unsafe"} and parsed:
            fail(errors, path, f"result row {coalition} is {outcome} but has obligations")
        if outcome in {"unknown", "conditional"} and not parsed:
            fail(errors, path, f"result row {coalition} is {outcome} with no obligation")
        rows.append(ResultRow(coalition, outcome, reason, parsed))

    if not rows:
        fail(errors, path, "'// result rows:' block declared but no valid rows parsed")
    return tuple(rows)


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
    elif expected is not None and reason not in expected.reason_ids:
        fail(
            errors,
            path,
            f"reason id is {reason!r}; scenario rows carry "
            f"{sorted(expected.reason_ids)}",
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

    # ---- optional record extensions -------------------------------------
    # All three are optional so the original corpus needs no re-recording, but
    # once present they are checked as strictly as the mandatory fields.

    rows = parse_result_rows(errors, path, text)
    if rows:
        derived = aggregate_outcome(rows)
        if outcome is not None and outcome != derived:
            fail(
                errors,
                path,
                f"expected outcome is {outcome!r} but the result rows aggregate "
                f"to {derived!r}; the artifact outcome is a projection of the "
                f"rows, not an independent claim",
            )
        if expected is not None and expected.rows and rows != expected.rows:
            fail(errors, path, "result rows do not match the scenario contract")

    targets = field_values(text, "// target tuple:")
    if targets:
        if len(targets) != 1:
            fail(errors, path, "'// target tuple:' occurs more than once")
        elif not TARGET_TUPLE.fullmatch(targets[0]):
            fail(
                errors,
                path,
                "target tuple must be <triple>/<cpu>/<opt-level>, "
                "for example x86_64-unknown-linux-gnu/generic/O2",
            )
        elif expected is not None and expected.target_tuple and targets[0] != expected.target_tuple:
            fail(
                errors,
                path,
                f"target tuple is {targets[0]!r}; scenario requires "
                f"{expected.target_tuple!r}",
            )

    dispositions = field_values(text, "// l1 disposition:")
    if dispositions:
        if len(dispositions) != 1:
            fail(errors, path, "'// l1 disposition:' occurs more than once")
        elif dispositions[0] not in DISPOSITIONS:
            fail(
                errors,
                path,
                "l1 disposition must be one of: " + ", ".join(sorted(DISPOSITIONS)),
            )
        elif expected is not None and expected.disposition and dispositions[0] != expected.disposition:
            fail(
                errors,
                path,
                f"l1 disposition is {dispositions[0]!r}; scenario requires "
                f"{expected.disposition!r}",
            )
    elif expected is not None and expected.disposition:
        fail(errors, path, "scenario requires an '// l1 disposition:' field")

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
            allowed = EXPECTED_SCENARIOS[path.name].reason_ids
            for actual_reason in expected_errors:
                if actual_reason not in allowed:
                    fail(
                        errors,
                        path,
                        f"expected-error reason is {actual_reason!r}; "
                        f"scenario rows carry {sorted(allowed)}",
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
