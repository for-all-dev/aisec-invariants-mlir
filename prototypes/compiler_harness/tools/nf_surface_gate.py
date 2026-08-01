#!/usr/bin/env python3
"""Syntactic surface gate for two Rev4 normal-form residue questions.

This is a harness-owned `PreflightV1` scanner. It answers two purely
*syntactic* questions about one textual LLVM module:

`--profile fp-closure`
    Does the module contain any opcode from the closed rejected floating-point
    set that `SPS_Rev4_LLVM_Normal_Form_and_Conformance_Profile.md` NF-A02 and
    `SPS_Rev4_Metatheory_and_Written_Proofs.md` Lemma R5.0N place outside the
    admitted surface --- FP arithmetic, FP-width conversion, and FP/integer
    numeric conversion? Loads, stores, same-width bitcasts, `phi`, `select`,
    `fneg`, and `fcmp` are the admitted bit-preserving movement forms.

`--profile vector-residue`
    How many vector-typed items and masked-memory intrinsic call sites remain,
    which is the quantitative shape NF-A05 ("zero vector items") and NF-CM02
    ("residual target-legal masked/vector operation") are stated over.

WHAT THIS TOOL DOES NOT DO. It does not compute `NFConforms`, a `ModelStatus`,
a `DeploymentStatus`, or a `PolicyReviewStatus`; it does not build a relational
product, a replay, or a receipt; it does not read an `ArtifactIdentityV1`; and
it has never seen LLVM 22.1.8. An empty rejected set is textual silence about
one opcode list in one file, not `NoAmbiguousNaNResult_e(T)` and not a proof.
The reason-class names it prints are *harness expectation* strings recording
which Rev4 disposition the fixture is a seed for. They are never a computed
result.

Exit status is 1 when the scanned profile finds at least one item, 0 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys

FORMAT_ID = "SPS-Harness-Surface-Gate-v1"

# NF-A02 / Lemma R5.0N rejected surface: FP arithmetic, FP-width conversion,
# and FP/integer numeric conversion. `fneg` is deliberately absent: R5.0N
# admits it because it preserves the exact input bits.
REJECTED_FP_OPCODES = (
    "fadd",
    "fsub",
    "fmul",
    "fdiv",
    "frem",
    "fptrunc",
    "fpext",
    "fptosi",
    "fptoui",
    "sitofp",
    "uitofp",
)

REJECTED_FP_KIND = {
    "fadd": "fp-arithmetic",
    "fsub": "fp-arithmetic",
    "fmul": "fp-arithmetic",
    "fdiv": "fp-arithmetic",
    "frem": "fp-arithmetic",
    "fptrunc": "fp-width-conversion",
    "fpext": "fp-width-conversion",
    "fptosi": "fp-integer-numeric-conversion",
    "fptoui": "fp-integer-numeric-conversion",
    "sitofp": "fp-integer-numeric-conversion",
    "uitofp": "fp-integer-numeric-conversion",
}

# Admitted bit-preserving movement forms, in the order R5.0N lists them.
ADMITTED_FP_OPCODES = ("load", "store", "bitcast", "phi", "select", "fneg", "fcmp")

FP_TYPE = re.compile(r"\b(half|bfloat|float|double|fp128|x86_fp80|ppc_fp128)\b")
VECTOR_TYPE = re.compile(r"<\s*(?:vscale\s+x\s+)?\d+\s+x\s+[^<>]*?>")
DEFINE_LINE = re.compile(r"^define\b.*?@([\w.$\-]+|\"[^\"]*\")")
DECLARE_LINE = re.compile(r"^declare\b.*?@([\w.$\-]+|\"[^\"]*\")")
OPCODE = re.compile(r"^(?:%(?:[\w.$\-]+|\"[^\"]*\")\s*=\s*)?([a-z][\w.]*)")
MASKED_CALLEE = re.compile(r"@(llvm\.masked\.[\w.]+)")


def strip_comment(line: str) -> str:
    """Remove a trailing LLVM `;` comment without cutting inside a string."""
    out = []
    in_string = False
    for index, char in enumerate(line):
        if char == '"' and (index == 0 or line[index - 1] != "\\"):
            in_string = not in_string
        if char == ";" and not in_string:
            break
        out.append(char)
    return "".join(out)


def scan(path):
    """Return (kind, line, function, opcode-or-form, text) for one module.

    `kind` is "signature" for a `define`/`declare` header line and "body" for a
    line inside a function body. Lines outside any body are dropped, so an
    intrinsic name that happens to contain a rejected opcode spelling cannot be
    mistaken for an instruction.
    """
    with open(path, encoding="utf-8") as stream:
        raw_lines = stream.read().splitlines()

    records = []
    function = None
    depth_in_body = False
    for number, raw in enumerate(raw_lines, start=1):
        text = strip_comment(raw).rstrip()
        stripped = text.strip()
        if not stripped:
            continue
        define = DEFINE_LINE.match(stripped)
        declare = DECLARE_LINE.match(stripped)
        if define:
            function = define.group(1)
            depth_in_body = stripped.endswith("{")
            records.append(("signature", number, function, "define", stripped))
            continue
        if declare:
            records.append(("signature", number, declare.group(1), "declare", stripped))
            continue
        if stripped == "}":
            depth_in_body = False
            function = None
            continue
        if not depth_in_body:
            continue
        match = OPCODE.match(stripped)
        opcode = match.group(1) if match else ""
        records.append(("body", number, function or "?", opcode, stripped))
    return records


def emit_header(profile: str, path: str) -> None:
    print(FORMAT_ID)
    print("profile: {}".format(profile))
    print("input: {}".format(path))


def emit_boundary() -> None:
    print(
        "SPS-Harness-Boundary: tier=PreflightV1 nf_conforms=NotEvaluated "
        "model_status=NotComputed deployment_status=NotComputed"
    )
    print(
        "SPS-Harness-Note: syntactic opcode/type scan of one textual module "
        "under LLVM 17.0.6; not the Rev4 normal-form audit and not a proof"
    )


def run_fp_closure(path: str) -> int:
    records = scan(path)
    admitted = {opcode: 0 for opcode in ADMITTED_FP_OPCODES}
    rejected = []
    for kind, number, function, opcode, text in records:
        if kind != "body":
            continue
        if opcode in REJECTED_FP_OPCODES:
            rejected.append((number, function, opcode, text))
            continue
        if opcode in admitted and (FP_TYPE.search(text) or opcode == "fneg"):
            admitted[opcode] += 1

    emit_header("fp-closure", path)
    print("admitted-bit-preserving-fp-items:")
    for opcode in ADMITTED_FP_OPCODES:
        print("  {} {}".format(opcode, admitted[opcode]))
    print("rejected-fp-items:")
    for number, function, opcode, text in rejected:
        print(
            "  line {} in @{}: {} ({}): {}".format(
                number, function, opcode, REJECTED_FP_KIND[opcode], text
            )
        )
    print("summary: rejected-fp-item-count={}".format(len(rejected)))
    if rejected:
        print(
            "SPS-Harness-Expectation: Unknown(PONFFPArithmeticUnsupported) "
            "-- NF-A02 admits no residual FP arithmetic, FP-width conversion, "
            "or FP/integer numeric conversion (Lemma R5.0N)"
        )
        emit_boundary()
        return 1
    print(
        "SPS-Harness-Expectation: NF-A02 rejected-FP surface is textually "
        "empty in this module; the NoAmbiguousNaNResult_e(T) gate is NOT "
        "thereby established"
    )
    emit_boundary()
    return 0


def run_vector_residue(path: str) -> int:
    records = scan(path)
    body_occurrences = []
    signature_occurrences = []
    masked_calls = []
    for kind, number, function, opcode, text in records:
        hits = VECTOR_TYPE.findall(text)
        if kind == "signature":
            if hits:
                signature_occurrences.append((number, function, opcode, len(hits)))
            continue
        if opcode == "alloca" and hits:
            body_occurrences.append((number, function, "alloca", len(hits)))
        elif hits:
            body_occurrences.append((number, function, opcode, len(hits)))
        if opcode in ("call", "invoke", "callbr"):
            callee = MASKED_CALLEE.search(text)
            if callee:
                masked_calls.append((number, function, callee.group(1)))

    body_total = sum(count for _, _, _, count in body_occurrences)
    signature_total = sum(count for _, _, _, count in signature_occurrences)
    total = body_total + signature_total + len(masked_calls)

    emit_header("vector-residue", path)
    print("residual-vector-typed-function-signatures:")
    for number, function, form, count in signature_occurrences:
        print("  line {}: {} @{} vector-type-occurrences={}".format(
            number, form, function, count
        ))
    print("residual-vector-typed-body-instructions:")
    for number, function, opcode, count in body_occurrences:
        print("  line {} in @{}: {} vector-type-occurrences={}".format(
            number, function, opcode, count
        ))
    print("residual-masked-memory-intrinsic-call-sites:")
    for number, function, callee in masked_calls:
        print("  line {} in @{}: {}".format(number, function, callee))
    print("summary: signature-vector-type-occurrences={}".format(signature_total))
    print("summary: body-vector-type-occurrences={}".format(body_total))
    print("summary: masked-memory-intrinsic-call-sites={}".format(len(masked_calls)))
    print("summary: residual-vector-item-count={}".format(total))
    if total:
        print(
            "SPS-Harness-Expectation: Unknown(ResidualVector) -- a nonzero "
            "residual vector inventory refutes the NF-A05 zero-item criterion "
            "and is the NF-CM02 case; running a scalarizer pass is not "
            "evidence of closure"
        )
        emit_boundary()
        return 1
    print(
        "SPS-Harness-Expectation: NF-A05 residual vector inventory is empty "
        "for this module; acceptance still requires the Rev4 audit, which "
        "this scan does not perform"
    )
    emit_boundary()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile", required=True, choices=("fp-closure", "vector-residue")
    )
    parser.add_argument("module", help="textual LLVM module (.ll)")
    arguments = parser.parse_args(argv)
    if arguments.profile == "fp-closure":
        return run_fp_closure(arguments.module)
    return run_vector_residue(arguments.module)


if __name__ == "__main__":
    sys.exit(main())
