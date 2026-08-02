"""Z3 and independent exhaustive backends for reference obligations."""

from __future__ import annotations

import itertools
import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from .errors import SolverUnavailableError
from .product import ReferenceProduct
from .smt import SMTArtifact
from .terms import Term, collect_variables, equal, var


@dataclass(frozen=True)
class SolverResult:
    backend: str
    status: str
    witness: dict[str, int] | None
    detail: str


def run_z3(artifact: SMTArtifact) -> SolverResult:
    configured = os.environ.get("Z3", "")
    binary = shutil.which(configured or "z3")
    if binary is None:
        if configured:
            raise SolverUnavailableError(
                f"configured Z3 executable is unavailable: {configured}"
            )
        raise SolverUnavailableError("z3 is not installed")
    return _run_solver(artifact, "z3", [binary, "-in", "-smt2"])


def run_cvc5(artifact: SMTArtifact) -> SolverResult:
    binary = shutil.which("cvc5")
    if binary is None:
        raise SolverUnavailableError("cvc5 is not installed")
    return _run_solver(artifact, "cvc5", [binary, "--lang=smt2"])


def _run_solver(
    artifact: SMTArtifact, backend: str, command: list[str]
) -> SolverResult:
    try:
        completed = subprocess.run(
            command,
            input=artifact.text,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return SolverResult(backend, "unknown", None, "status query timed out")
    except OSError as exc:
        return SolverResult(backend, "error", None, f"status launch failed: {exc}")
    lines = completed.stdout.strip().splitlines()
    status = lines[0].strip() if lines else "unknown"
    if completed.returncode != 0 or status not in {"sat", "unsat", "unknown"}:
        return SolverResult(
            backend,
            "error",
            None,
            f"exit={completed.returncode}; stdout={completed.stdout}; "
            f"stderr={completed.stderr}",
        )
    if status == "sat":
        if not artifact.variables:
            return SolverResult(backend, status, {}, completed.stderr.strip())
        symbols = " ".join(
            _quote_model_symbol(name) for name, _ in artifact.variables
        )
        request = f"(get-value ({symbols}))\n"
        try:
            model_run = subprocess.run(
                command,
                input=artifact.text + request,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return SolverResult(
                backend, "error", None, "model retrieval timed out after SAT"
            )
        except OSError as exc:
            return SolverResult(
                backend, "error", None, f"model retrieval launch failed: {exc}"
            )
        model_lines = model_run.stdout.strip().splitlines()
        model_status = model_lines[0].strip() if model_lines else "unknown"
        if model_run.returncode != 0 or model_status != "sat":
            return SolverResult(
                backend,
                "error",
                None,
                "model query disagreed with the status query: "
                f"exit={model_run.returncode}; stdout={model_run.stdout}; "
                f"stderr={model_run.stderr}",
            )
        try:
            witness = _parse_model_response(
                "\n".join(model_lines[1:]), artifact.variables
            )
        except ValueError as exc:
            return SolverResult(backend, "error", None, f"invalid model: {exc}")
        detail = "\n".join(
            part for part in (completed.stderr.strip(), model_run.stderr.strip()) if part
        )
        return SolverResult(backend, status, witness, detail)
    return SolverResult(backend, status, None, completed.stderr.strip())


def run_exhaustive(
    product: ReferenceProduct, max_assignments: int = 1_000_000
) -> SolverResult:
    if (
        not isinstance(max_assignments, int)
        or isinstance(max_assignments, bool)
        or max_assignments <= 0
    ):
        raise ValueError("max_assignments must be a positive integer")
    variables = product_variables(product)
    low_pairs = _validated_low_pairs(product, variables)
    low_right_to_left = {right: left for left, right, _ in low_pairs}
    total = 1
    ordered = [
        (name, width)
        for name, width in sorted(variables.items())
        if name not in low_right_to_left
    ]
    for _, width in ordered:
        total *= 1 << width
    if total > max_assignments:
        return SolverResult(
            "exhaustive",
            "unknown",
            None,
            f"domain has {total} assignments, cap is {max_assignments}",
        )
    domains = [range(1 << width) for _, width in ordered]
    for values in itertools.product(*domains):
        environment = {
            name: value for (name, _), value in zip(ordered, values, strict=True)
        }
        for right, left in low_right_to_left.items():
            environment[right] = environment[left]
        if all(bool(term.evaluate(environment)) for term in product.low_constraints):
            if bool(product.bad.evaluate(environment)):
                return SolverResult("exhaustive", "sat", environment, "")
    return SolverResult("exhaustive", "unsat", None, "")


def _validated_low_pairs(
    product: ReferenceProduct, variables: dict[str, int]
) -> tuple[tuple[str, str, int], ...]:
    seen: set[str] = set()
    expected_constraints: list[Term] = []
    for left, right, width in product.low_input_pairs:
        if (
            left in seen
            or right in seen
            or left == right
            or variables.get(left) != width
            or variables.get(right) != width
        ):
            raise ValueError("invalid reference product LowEq input pair")
        seen.update({left, right})
        expected_constraints.append(equal(var(left, width), var(right, width)))
    if product.low_constraints != tuple(expected_constraints):
        raise ValueError("reference product LowEq table disagrees with constraints")
    return product.low_input_pairs


def product_variables(product: ReferenceProduct) -> dict[str, int]:
    result = dict(product.input_variables)
    if len(result) != len(product.input_variables):
        raise ValueError("duplicate reference product input symbol")
    referenced = collect_variables([*product.low_constraints, product.bad])
    for name, width in referenced.items():
        if result.get(name) != width:
            raise ValueError(f"formula symbol {name} is absent or has the wrong width")
    return result


def _quote_model_symbol(name: str) -> str:
    return "|" + name.replace("\\", "\\\\").replace("|", "\\|") + "|"


def _parse_model_response(
    raw: str, expected: tuple[tuple[str, int], ...]
) -> dict[str, int]:
    if not expected:
        if raw.strip():
            raise ValueError("unexpected model response for empty request")
        return {}
    tokens = _tokenize_sexpr(raw)
    position = 0

    def parse() -> object:
        nonlocal position
        if position >= len(tokens):
            raise ValueError("truncated S-expression")
        token = tokens[position]
        position += 1
        if token != "(":
            if token == ")":
                raise ValueError("unexpected close parenthesis")
            return token
        result: list[object] = []
        while True:
            if position >= len(tokens):
                raise ValueError("unterminated S-expression")
            if tokens[position] == ")":
                position += 1
                return result
            result.append(parse())

    tree = parse()
    if position != len(tokens):
        raise ValueError("trailing model response")
    if not isinstance(tree, list) or len(tree) != len(expected):
        raise ValueError("model pair count mismatch")
    result: dict[str, int] = {}
    for pair, (name, width) in zip(tree, expected, strict=True):
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("model entry is not a pair")
        symbol = pair[0]
        if symbol != f"|{name}|":
            raise ValueError(f"model symbol order mismatch for {name}")
        value = _parse_ground_bv(pair[1], width)
        result[name] = value
    return result


def parse_model_response(
    raw: str, expected: tuple[tuple[str, int], ...]
) -> dict[str, int]:
    """Validate and normalize one ordered ground-value response."""

    return _parse_model_response(raw, expected)


def _tokenize_sexpr(raw: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char.isspace():
            index += 1
            continue
        if char in "()":
            tokens.append(char)
            index += 1
            continue
        if char == "|":
            end = index + 1
            escaped = False
            while end < len(raw):
                current = raw[end]
                if current == "|" and not escaped:
                    break
                escaped = current == "\\" and not escaped
                if current != "\\":
                    escaped = False
                end += 1
            if end >= len(raw):
                raise ValueError("unterminated quoted symbol")
            tokens.append(raw[index : end + 1])
            index = end + 1
            continue
        end = index
        while end < len(raw) and not raw[end].isspace() and raw[end] not in "()":
            end += 1
        tokens.append(raw[index:end])
        index = end
    if not tokens:
        raise ValueError("empty model response")
    return tokens


def _parse_ground_bv(value: object, width: int) -> int:
    if isinstance(value, str):
        if value.startswith("#b"):
            bits = value[2:]
            if len(bits) != width or not bits or set(bits) - {"0", "1"}:
                raise ValueError("binary literal width mismatch")
            return int(bits, 2)
        if value.startswith("#x"):
            digits = value[2:]
            if width % 4 != 0 or len(digits) * 4 != width:
                raise ValueError("hex literal width mismatch")
            if not re.fullmatch(r"[0-9A-Fa-f]+", digits):
                raise ValueError("invalid hex literal")
            return int(digits, 16)
    if (
        isinstance(value, list)
        and len(value) == 3
        and value[0] == "_"
        and isinstance(value[1], str)
        and value[1].startswith("bv")
        and isinstance(value[2], str)
        and value[2].isdigit()
    ):
        literal_width = int(value[2])
        digits = value[1][2:]
        if literal_width != width or not digits.isdigit():
            raise ValueError("decimal bitvector literal mismatch")
        parsed = int(digits)
        if parsed >= 1 << width:
            raise ValueError("decimal bitvector literal overflow")
        return parsed
    raise ValueError("unsupported ground bitvector literal")
