#!/usr/bin/env python3
"""Cross-file identifier binding for case-local candidate bundles.

WHAT THIS CHECKS
----------------
Rev-4 spec section 3 defines `WFInputs(M,ABI,R,K,TE,FPT,I,T)`.  The candidate
bundles under ``fixtures/<family>/<case>/candidate/`` carry harness mirrors of
the policy, ABI, contract, and release-table interfaces. ``c/check_harness.py`` already
validates each sidecar in isolation plus its digest binding to ``artifact.bc``;
it does **not** check that identifiers mentioned in one sidecar resolve in
another.  This tool implements the resolvable-reference fragment of `WFInputs`
that is expressible against those mirrors, plus the explicit empty
`TimingEnvironmentContract` that spec section 2.5.1 requires.

WHAT THIS DOES NOT CHECK, AND CANNOT
------------------------------------
This is a ``CandidateOnly`` tool.  A clean run is *not*:

* `WFInputs` itself.  Items 4, 5, 9, 10, 12 and 14 quantify over the frozen
  reparsed module, the exact data layout, and a satisfiability obligation.
  None of those exists here.
* `NFConforms(T,I)`.  The normative boundary is LLVM 22.1.8; these bundles are
  LLVM 17.0.6 candidates.
* a `ModelStatus`, a `DeploymentStatus`, a `PolicyReviewStatus`, a verifier
  receipt, or a witness.  This tool never emits any of them.  Where the spec
  and the lecture notes name the disposition a real verifier would reach on a
  given failure, the diagnostic quotes that reason class as *text*, tagged
  ``would-be disposition reason class``.  Quoting a reason class is not
  computing a status, and silence from this tool proves nothing.

The three Rev-4 result axes (`ModelStatus`, `DeploymentStatus`,
`PolicyReviewStatus`) stay independent and stay uncomputed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import fixture_layout

ROOT = Path(__file__).resolve().parent.parent
SIDECARS = (
    "policy.json",
    "abi.json",
    "contracts.json",
    "release-table.json",
    "expected-report.json",
)

# Spec section 7 (SPS_Rev4_Normative_Specification.md:3094) fixes exactly one
# observation model for Rev-4; :3096 states that removing or coarsening an
# event kind or field is not configuration.  There is no second legal value.
FIXED_OBSERVATION_MODEL = "Theta_ct"

# Spec section 2.5.1 (:2255-2258): "An explicit empty contract - with an empty
# choice domain, occurrence map, latency table, and coupling map - is required
# when no ideal timing choice is modeled."  The six mirrored contract fields,
# per SPS_Lecture_Notes/artifacts/common/timing-environment.logical.yaml.
TIMING_ENVIRONMENT_FORMAT_ID = "SPS-Harness-Candidate-Timing-Environment-v2"
TIMING_ENVIRONMENT_FIELDS = (
    "choiceDomain",
    "occurrences",
    "latencyMeaning",
    "latencyClasses",
    "pairedChoiceCoupling",
    "versionAndObservationBoundary",
)

# Exact `PublicReasonClassesV2` spellings selected from the active specification.  A
# diagnostic may only quote a member of this closed set, and quoting one is
# reporting text, never computing a `ModelStatus`.  Inventing a plausible
# reason-class name would be indistinguishable from a normative claim, so
# checks whose true disposition the corpus does not state name no class at all.
QUOTABLE_REASON_CLASSES = frozenset({"ManifestMismatch"})

VISIBILITY_BASES = ("component_visibility", "output_visibility", "error_visibility")

COMPONENT_ROLE_TAGS = ("ComponentArgumentV2", "PublicConfigurationArgumentV2")
POINTER_ROLE_TAG = "PointerRootArgumentV2"


class Report:
    """Accumulates violations in ``bundle/file: path: message`` form."""

    def __init__(self) -> None:
        self.failures: list[str] = []

    def add(
        self,
        bundle: Path,
        filename: str,
        field_path: str,
        message: str,
        citation: str,
        reason_class: str | None = None,
    ) -> None:
        try:
            label = (bundle / filename).relative_to(ROOT)
        except ValueError:
            label = bundle / filename
        line = f"{label}: {field_path}: {message} ({citation})"
        if reason_class is not None:
            if reason_class not in QUOTABLE_REASON_CLASSES:
                raise AssertionError(
                    f"{reason_class!r} is not an active PublicReasonClassesV2 spelling"
                )
            line += f" (would-be disposition reason class: {reason_class})"
        self.failures.append(line)


def read_json(report: Report, bundle: Path, filename: str) -> dict[str, object] | None:
    path = bundle / filename
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        report.add(bundle, filename, "<file>", f"cannot parse JSON: {error}", "WFInputs item 1")
        return None
    if not isinstance(value, dict):
        report.add(bundle, filename, "<file>", "top-level JSON value must be an object", "WFInputs item 1")
        return None
    return value


def string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def check_envelope_digests(report: Report, bundle: Path, identity: dict[str, object]) -> None:
    """Harness-envelope binding.

    This is the candidate analogue of `WFInputs` item 13 (every digest in
    `ArtifactIdentity` equals the canonical serialization of the referenced
    object).  It is deliberately weaker: `artifact.json` is an
    `SPS-Harness-Candidate-Artifact-v2` envelope, not an `ArtifactIdentityV2`,
    and sha256-over-file-bytes is not canonical SPS serialization.
    """
    digests = identity.get("candidate_sidecar_sha256")
    if not isinstance(digests, dict):
        report.add(
            bundle,
            "artifact.json",
            "candidate_sidecar_sha256",
            "sidecar digest map is missing",
            "harness analogue of WFInputs item 13",
        )
        return
    for filename in SIDECARS:
        actual = hashlib.sha256((bundle / filename).read_bytes()).hexdigest()
        if digests.get(filename) != actual:
            report.add(
                bundle,
                "artifact.json",
                f"candidate_sidecar_sha256[{filename}]",
                f"recorded digest does not equal sha256 of {filename}",
                "harness analogue of WFInputs item 13",
            )


def check_observation_model(report: Report, bundle: Path, policy: dict[str, object]) -> None:
    """Spec section 7: Rev-4 has exactly one observation model."""
    model = policy.get("fixed_observation_model")
    if model != FIXED_OBSERVATION_MODEL:
        report.add(
            bundle,
            "policy.json",
            "fixed_observation_model",
            f"{model!r} is not the single Rev-4 observation model "
            f"{FIXED_OBSERVATION_MODEL!r}; coarsening or replacing an event kind is not configuration",
            "spec section 7 and WFInputs item 1",
        )


def check_release_binding_domains(
    report: Report,
    bundle: Path,
    policy: dict[str, object],
    entries: list[dict[str, object]],
) -> None:
    """`WFInputs` item 3: `dom(M.releaseBindings) = dom(R)`.

    Both inclusions are required.  A binding with no table entry, and a table
    entry with no binding, are equally fatal.  Per
    `SPS_Lecture_Notes/part5-soundness.tex:296-298`, a manifest whose release
    bindings no longer match `dom(R)` is `Unknown(ManifestMismatch)`.
    """
    bindings = policy.get("release_bindings")
    if not isinstance(bindings, list) or any(not isinstance(item, str) for item in bindings):
        report.add(
            bundle,
            "policy.json",
            "release_bindings",
            "release bindings must be an array of release identifiers",
            "WFInputs item 3",
            reason_class="ManifestMismatch",
        )
        return

    table_ids: list[str] = []
    for index, entry in enumerate(entries):
        entry_id = entry.get("id")
        if not isinstance(entry_id, str):
            report.add(
                bundle,
                "release-table.json",
                f"entries[{index}].id",
                "release entry id must be a stable identifier",
                "WFInputs item 3",
                reason_class="ManifestMismatch",
            )
            continue
        if entry_id in table_ids:
            report.add(
                bundle,
                "release-table.json",
                f"entries[{index}].id",
                f"release id {entry_id!r} is declared more than once, so dom(R) is ambiguous",
                "WFInputs items 1 and 3",
                reason_class="ManifestMismatch",
            )
        table_ids.append(entry_id)

    seen: set[str] = set()
    for index, binding in enumerate(bindings):
        if binding in seen:
            report.add(
                bundle,
                "policy.json",
                f"release_bindings[{index}]",
                f"release id {binding!r} is bound more than once",
                "WFInputs items 1 and 3",
                reason_class="ManifestMismatch",
            )
        seen.add(binding)
        if binding not in table_ids:
            report.add(
                bundle,
                "policy.json",
                f"release_bindings[{index}]",
                f"release id {binding!r} does not resolve to any release-table entries id; "
                "dom(M.releaseBindings) is not equal to dom(R)",
                "WFInputs item 3",
                reason_class="ManifestMismatch",
            )
    for index, entry_id in enumerate(table_ids):
        if entry_id not in seen:
            report.add(
                bundle,
                "release-table.json",
                f"entries[{index}].id",
                f"release id {entry_id!r} is not bound by policy release_bindings; "
                "dom(M.releaseBindings) is not equal to dom(R)",
                "WFInputs item 3",
                reason_class="ManifestMismatch",
            )


def check_release_entries(
    report: Report,
    bundle: Path,
    policy: dict[str, object],
    entries: list[dict[str, object]],
    contracts: dict[str, object],
) -> None:
    """`WFInputs` items 3, 4, 7 and 8 over each release entry's references."""
    principals = string_list(policy.get("principals"))
    components = string_list(policy.get("components"))
    mechanisms = contracts.get("mechanism_contracts")
    contract_callees = (
        {
            contract.get("callee")
            for contract in mechanisms
            if isinstance(contract, dict) and isinstance(contract.get("callee"), str)
        }
        if isinstance(mechanisms, list)
        else set()
    )

    for index, entry in enumerate(entries):
        # Item 3 (and item 8: audiences resolve uniquely).  Coalitions and all
        # derived audience relations are computed from M.principals; an
        # audience naming an undeclared principal is in no coalition at all.
        audience = entry.get("audience")
        if not isinstance(audience, list) or not audience:
            report.add(
                bundle,
                "release-table.json",
                f"entries[{index}].audience",
                "release audience must be a nonempty array of declared principals",
                "WFInputs items 3 and 8",
            )
        else:
            for position, principal in enumerate(audience):
                if principal not in principals:
                    report.add(
                        bundle,
                        "release-table.json",
                        f"entries[{index}].audience[{position}]",
                        f"principal {principal!r} is not declared in policy principals, "
                        "so it belongs to no coalition derived from the policy basis",
                        "WFInputs items 2, 3 and 8",
                    )

        # Items 3 and 4: the footprint must resolve to declared components.
        footprint = entry.get("footprint")
        if not isinstance(footprint, list):
            report.add(
                bundle,
                "release-table.json",
                f"entries[{index}].footprint",
                "release footprint must be an array of declared components",
                "WFInputs items 3 and 4",
            )
        else:
            for position, component in enumerate(footprint):
                if component not in components:
                    report.add(
                        bundle,
                        "release-table.json",
                        f"entries[{index}].footprint[{position}]",
                        f"component {component!r} is not declared in policy components",
                        "WFInputs items 3 and 4",
                    )

        # Items 3 and 7: every carrier is an external boundary that must have
        # one declared mechanism contract.
        carrier = entry.get("carrier")
        if not isinstance(carrier, dict) or not isinstance(carrier.get("callee"), str):
            report.add(
                bundle,
                "release-table.json",
                f"entries[{index}].carrier",
                "release carrier must name a mechanism callee",
                "WFInputs items 3 and 7",
            )
        elif carrier["callee"] not in contract_callees:
            report.add(
                bundle,
                "release-table.json",
                f"entries[{index}].carrier.callee",
                f"callee {carrier['callee']!r} does not resolve to a "
                "contracts mechanism_contracts callee",
                "WFInputs items 3 and 7",
            )


def check_argument_roles(
    report: Report,
    bundle: Path,
    policy: dict[str, object],
    abi: dict[str, object],
) -> None:
    """`WFInputs` item 3: every component and root reference resolves."""
    components = string_list(policy.get("components"))
    arguments = abi.get("arguments")
    arguments = arguments if isinstance(arguments, list) else []
    root_ids = {
        argument.get("root_id")
        for argument in arguments
        if isinstance(argument, dict) and isinstance(argument.get("root_id"), str)
    }
    output_ids = {
        argument.get("output")
        for argument in arguments
        if isinstance(argument, dict) and isinstance(argument.get("output"), str)
    }

    roles = policy.get("argument_roles")
    if not isinstance(roles, list):
        report.add(
            bundle,
            "policy.json",
            "argument_roles",
            "argument roles must be an array",
            "WFInputs item 3",
        )
        return
    for index, record in enumerate(roles):
        if not isinstance(record, dict):
            report.add(bundle, "policy.json", f"argument_roles[{index}]", "role record must be an object", "WFInputs item 3")
            continue
        role = record.get("role")
        if not isinstance(role, dict):
            report.add(bundle, "policy.json", f"argument_roles[{index}].role", "role must be a tagged object", "WFInputs item 3")
            continue
        tag = role.get("tag")
        args = role.get("args")
        if not isinstance(args, list) or len(args) != 1 or not isinstance(args[0], str):
            report.add(
                bundle,
                "policy.json",
                f"argument_roles[{index}].role.args",
                "role must carry exactly one stable identifier",
                "WFInputs items 1 and 3",
            )
            continue
        identifier = args[0]
        if tag in COMPONENT_ROLE_TAGS and identifier not in components:
            report.add(
                bundle,
                "policy.json",
                f"argument_roles[{index}].role.args[0]",
                f"{tag} component {identifier!r} is not declared in policy components",
                "WFInputs item 3",
            )
        elif tag == POINTER_ROLE_TAG and identifier not in (root_ids | output_ids):
            report.add(
                bundle,
                "policy.json",
                f"argument_roles[{index}].role.args[0]",
                f"pointer root {identifier!r} does not resolve to an abi root_id or output channel",
                "WFInputs item 3",
            )


def check_entry_bound_tables(
    report: Report,
    bundle: Path,
    policy: dict[str, object],
    abi: dict[str, object],
) -> None:
    """`WFInputs` items 3, 6 and 9: entry-keyed tables name the ABI entry."""
    entry = abi.get("entry")
    placements = policy.get("placement")
    if not isinstance(placements, list):
        report.add(bundle, "policy.json", "placement", "placement must be an array", "WFInputs items 3 and 6")
        placements = []
    matching = 0
    for index, placement in enumerate(placements):
        if not isinstance(placement, dict):
            report.add(bundle, "policy.json", f"placement[{index}]", "placement record must be an object", "WFInputs items 3 and 6")
            continue
        named = placement.get("entry")
        if named != entry:
            report.add(
                bundle,
                "policy.json",
                f"placement[{index}].entry",
                f"placement names {named!r}, which is not the abi entry {entry!r}",
                "WFInputs items 3 and 6",
            )
            continue
        matching += 1
    if matching != 1:
        report.add(
            bundle,
            "policy.json",
            "placement",
            f"abi entry {entry!r} must have exactly one placement, found {matching}",
            "WFInputs items 3 and 6",
        )

    bounds = policy.get("execution_bounds", [])
    if not isinstance(bounds, list):
        report.add(bundle, "policy.json", "execution_bounds", "execution bounds must be an array", "WFInputs items 3 and 9")
        return
    for index, bound in enumerate(bounds):
        if not isinstance(bound, dict) or bound.get("entry") != entry:
            report.add(
                bundle,
                "policy.json",
                f"execution_bounds[{index}].entry",
                f"bound does not resolve to the abi entry {entry!r}",
                "WFInputs items 3 and 9",
            )
            continue
        limit = bound.get("backedge_limit")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            report.add(
                bundle,
                "policy.json",
                f"execution_bounds[{index}].backedge_limit",
                "public bounds must be finite and nonnegative",
                "WFInputs item 9",
            )


def check_visibility_domains(
    report: Report,
    bundle: Path,
    policy: dict[str, object],
    abi: dict[str, object],
) -> None:
    """`WFInputs` items 2, 3 and 10.

    Every visibility basis is total in the declared principals: item 1 requires
    totality, item 2 forbids authored overrides outside the basis, and item 10
    requires a mandatory visibility basis per reachable event.
    """
    principals = string_list(policy.get("principals"))
    components = set(string_list(policy.get("components")))
    arguments = abi.get("arguments")
    arguments = arguments if isinstance(arguments, list) else []
    outputs = {
        argument.get("output")
        for argument in arguments
        if isinstance(argument, dict) and isinstance(argument.get("output"), str)
    }
    allowed = {
        "component_visibility": components,
        "output_visibility": outputs,
        "error_visibility": set(),
    }

    for name in VISIBILITY_BASES:
        basis = policy.get(name)
        if not isinstance(basis, dict):
            report.add(bundle, "policy.json", name, "visibility basis must be an object", "WFInputs items 1 and 10")
            continue
        members = basis.get("member_visible")
        if not isinstance(members, dict):
            report.add(bundle, "policy.json", f"{name}.member_visible", "member visibility must be an object", "WFInputs items 1 and 10")
            continue
        if list(members) != principals:
            report.add(
                bundle,
                "policy.json",
                f"{name}.member_visible",
                f"member visibility keys {sorted(members)} are not exactly the declared "
                f"principals {principals}",
                "WFInputs items 1, 2 and 10",
            )
        for principal, identifiers in members.items():
            for position, identifier in enumerate(string_list(identifiers)):
                if identifier not in allowed[name]:
                    report.add(
                        bundle,
                        "policy.json",
                        f"{name}.member_visible[{principal}][{position}]",
                        f"identifier {identifier!r} is not declared for this basis",
                        "WFInputs item 3",
                    )
        for position, identifier in enumerate(string_list(basis.get("world_visible"))):
            if identifier not in allowed[name]:
                report.add(
                    bundle,
                    "policy.json",
                    f"{name}.world_visible[{position}]",
                    f"identifier {identifier!r} is not declared for this basis",
                    "WFInputs item 3",
                )


def check_timing_environment(report: Report, bundle: Path, contracts: dict[str, object]) -> None:
    """Spec section 2.5.1 (:2255-2258) and `WFInputs` item 11.

    An explicit empty `TimingEnvironmentContract` - empty choice domain,
    occurrence map, latency table and coupling map - is REQUIRED when no ideal
    timing choice is modeled.  `"timing_contracts": []` is the *absence* of
    that object, not an instance of it, so its presence does not satisfy this.
    """
    environment = contracts.get("timing_environment")
    if not isinstance(environment, dict):
        report.add(
            bundle,
            "contracts.json",
            "timing_environment",
            "the explicit empty TimingEnvironmentContract is absent; an empty "
            "timing_contracts array is the absence of the required object, not an instance of it",
            "spec section 2.5.1 and WFInputs item 11",
        )
        return
    if environment.get("format_id") != TIMING_ENVIRONMENT_FORMAT_ID:
        report.add(
            bundle,
            "contracts.json",
            "timing_environment.format_id",
            f"harness timing environment must declare {TIMING_ENVIRONMENT_FORMAT_ID}",
            "harness naming rule for SPS-Harness-* records",
        )
    if environment.get("claimable") is not False:
        report.add(
            bundle,
            "contracts.json",
            "timing_environment.claimable",
            "candidate timing environment must remain explicitly non-claimable",
            "CandidateOnly tier rule",
        )
    for field in TIMING_ENVIRONMENT_FIELDS:
        if field not in environment:
            report.add(
                bundle,
                "contracts.json",
                f"timing_environment.{field}",
                "required TimingEnvironmentContract field is missing",
                "spec section 2.5.1 and WFInputs item 11",
            )
    empty_required = {
        "choiceDomain": [],
        "occurrences": {},
        "latencyMeaning": [],
        "pairedChoiceCoupling": {},
    }
    for field, value in empty_required.items():
        if field in environment and environment[field] != value:
            report.add(
                bundle,
                "contracts.json",
                f"timing_environment.{field}",
                "an explicit empty timing-choice contract must leave this empty; "
                "a nonempty value declares a timing choice this harness cannot type",
                "spec section 2.5.1 and WFInputs item 11",
            )
    classes = environment.get("latencyClasses")
    if not isinstance(classes, list) or not classes:
        report.add(
            bundle,
            "contracts.json",
            "timing_environment.latencyClasses",
            "latencyClasses must be a nonempty finite set even when the choice domain is empty",
            "spec section 2.5.1 and WFInputs item 11",
        )
    elif any(
        not isinstance(item, dict) or not isinstance(item.get("latencyClassId"), str)
        for item in classes
    ):
        report.add(
            bundle,
            "contracts.json",
            "timing_environment.latencyClasses",
            "every latency class must carry a stable latencyClassId",
            "spec section 2.5.1",
        )


def check_bundle(report: Report, bundle: Path) -> bool:
    missing = [name for name in ("artifact.json", *SIDECARS) if not (bundle / name).is_file()]
    if missing:
        for name in missing:
            report.add(bundle, name, "<file>", "required bundle member is missing", "WFInputs item 1")
        return False
    identity = read_json(report, bundle, "artifact.json")
    policy = read_json(report, bundle, "policy.json")
    abi = read_json(report, bundle, "abi.json")
    contracts = read_json(report, bundle, "contracts.json")
    release_table = read_json(report, bundle, "release-table.json")
    if any(value is None for value in (identity, policy, abi, contracts, release_table)):
        return False

    check_envelope_digests(report, bundle, identity)
    check_observation_model(report, bundle, policy)

    entries = release_table.get("entries")
    if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
        report.add(bundle, "release-table.json", "entries", "release entries must be an array of objects", "WFInputs item 3")
        entries = []

    check_release_binding_domains(report, bundle, policy, entries)
    check_release_entries(report, bundle, policy, entries, contracts)
    check_argument_roles(report, bundle, policy, abi)
    check_entry_bound_tables(report, bundle, policy, abi)
    check_visibility_domains(report, bundle, policy, abi)
    check_timing_environment(report, bundle, contracts)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    bundles = fixture_layout.candidate_dirs(ROOT)
    if not bundles:
        print(f"{ROOT / 'fixtures'}: no candidate bundles were discovered", file=sys.stdout)
        return 1

    report = Report()
    for bundle in bundles:
        check_bundle(report, bundle)

    if report.failures:
        for failure in report.failures:
            print(failure)
        print(
            "wfinputs binding checks failed: the WFInputs fragment expressible "
            "against these candidate sidecars does not hold"
        )
        print(
            "no ModelStatus, DeploymentStatus, PolicyReviewStatus, receipt, or "
            "witness is computed or implied by this tool"
        )
        return 1

    print(f"wfinputs binding checks passed: {len(bundles)} candidate bundles")
    print(
        "checked: cross-file identifier resolution for release bindings, audiences, "
        "footprints, carriers, argument roles, placements, bounds, visibility bases, "
        "the fixed observation model, and the explicit empty TimingEnvironmentContract"
    )
    print(
        "not checked: WFInputs items 4, 5, 9, 10, 12, 14 over a frozen module; "
        "NFConforms; ModelStatus; DeploymentStatus; PolicyReviewStatus; "
        "this is CandidateOnly and silence here proves nothing"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
