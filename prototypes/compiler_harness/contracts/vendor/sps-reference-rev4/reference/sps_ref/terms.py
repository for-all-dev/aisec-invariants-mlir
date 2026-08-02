"""Small typed Boolean/bitvector term language used by the reference slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .errors import SchemaError


@dataclass(frozen=True)
class Term:
    sort: str
    width: int | None
    op: str
    args: tuple["Term", ...] = ()
    value: int | bool | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        if self.sort not in {"Bool", "BV"}:
            raise SchemaError(f"unsupported term sort {self.sort!r}")
        if self.sort == "Bool" and self.width is not None:
            raise SchemaError("Bool term cannot have a width")
        if self.sort == "BV" and (self.width is None or self.width <= 0):
            raise SchemaError("BV term requires a positive width")

    def to_obj(self) -> dict[str, Any]:
        obj: dict[str, Any] = {"op": self.op, "sort": self.sort}
        if self.width is not None:
            obj["width"] = self.width
        if self.name is not None:
            obj["name"] = self.name
        if self.value is not None:
            obj["value"] = self.value
        if self.args:
            obj["args"] = [arg.to_obj() for arg in self.args]
        return obj

    def evaluate(self, environment: Mapping[str, int | bool]) -> int | bool:
        if self.op == "var":
            if self.name not in environment:
                raise SchemaError(f"missing value for {self.name}")
            raw = environment[self.name]
            if self.sort == "Bool":
                return bool(raw)
            return int(raw) & mask(self.width)
        if self.op == "bool":
            return bool(self.value)
        if self.op == "bv":
            return int(self.value) & mask(self.width)

        values = [arg.evaluate(environment) for arg in self.args]
        if self.op == "not":
            return not bool(values[0])
        if self.op == "and":
            return all(bool(value) for value in values)
        if self.op == "or":
            return any(bool(value) for value in values)
        if self.op == "xor_bool":
            return bool(values[0]) ^ bool(values[1])
        if self.op == "eq":
            return values[0] == values[1]
        if self.op == "ite":
            return values[1] if bool(values[0]) else values[2]
        if self.op == "bvadd":
            return (int(values[0]) + int(values[1])) & mask(self.width)
        if self.op == "bvxor":
            return (int(values[0]) ^ int(values[1])) & mask(self.width)
        if self.op == "bvand":
            return (int(values[0]) & int(values[1])) & mask(self.width)
        if self.op == "bvor":
            return (int(values[0]) | int(values[1])) & mask(self.width)
        if self.op == "bvult":
            return int(values[0]) < int(values[1])
        if self.op == "extract":
            low = int(self.value)
            return (int(values[0]) >> low) & mask(self.width)
        if self.op == "concat":
            result = 0
            for arg, value in zip(self.args, values, strict=True):
                result = (result << int(arg.width)) | int(value)
            return result & mask(self.width)
        raise SchemaError(f"cannot evaluate term operator {self.op!r}")

    def to_smt(self) -> str:
        if self.op == "var":
            return quote_symbol(self.name)
        if self.op == "bool":
            return "true" if self.value else "false"
        if self.op == "bv":
            return f"(_ bv{int(self.value) & mask(self.width)} {self.width})"
        if self.op == "not":
            return f"(not {self.args[0].to_smt()})"
        if self.op in {"and", "or"}:
            if not self.args:
                return "true" if self.op == "and" else "false"
            if len(self.args) == 1:
                return self.args[0].to_smt()
            return f"({self.op} {' '.join(arg.to_smt() for arg in self.args)})"
        if self.op == "xor_bool":
            return f"(xor {self.args[0].to_smt()} {self.args[1].to_smt()})"
        if self.op == "eq":
            return f"(= {self.args[0].to_smt()} {self.args[1].to_smt()})"
        if self.op == "ite":
            return (
                f"(ite {self.args[0].to_smt()} "
                f"{self.args[1].to_smt()} {self.args[2].to_smt()})"
            )
        smt_ops = {
            "bvadd": "bvadd",
            "bvxor": "bvxor",
            "bvand": "bvand",
            "bvor": "bvor",
            "bvult": "bvult",
        }
        if self.op in smt_ops:
            return (
                f"({smt_ops[self.op]} "
                f"{' '.join(arg.to_smt() for arg in self.args)})"
            )
        if self.op == "extract":
            high = int(self.value) + int(self.width) - 1
            return f"((_ extract {high} {self.value}) {self.args[0].to_smt()})"
        if self.op == "concat":
            return f"(concat {' '.join(arg.to_smt() for arg in self.args)})"
        raise SchemaError(f"cannot lower term operator {self.op!r}")


def mask(width: int | None) -> int:
    if width is None or width <= 0:
        raise SchemaError("bitvector mask requires a positive width")
    return (1 << width) - 1


def quote_symbol(name: str | None) -> str:
    if not name:
        raise SchemaError("empty SMT symbol")
    escaped = name.replace("\\", "\\\\").replace("|", "\\|")
    return f"|{escaped}|"


def term_from_obj(value: Any) -> Term:
    """Strictly decode one canonical reference term object."""

    if not isinstance(value, dict):
        raise SchemaError("term must be an object")
    op = value.get("op")
    sort = value.get("sort")
    width = value.get("width")
    if "width" in value and (
        not isinstance(width, int) or isinstance(width, bool) or width <= 0
    ):
        raise SchemaError("term width must be a positive integer")
    raw_args = value.get("args", [])
    if not isinstance(raw_args, list):
        raise SchemaError("term args must be a list")
    args = tuple(term_from_obj(item) for item in raw_args)

    if op == "var":
        expected = {"op", "sort", "name"}
        if sort == "BV":
            expected.add("width")
        if set(value) != expected or not isinstance(value.get("name"), str):
            raise SchemaError("malformed variable term")
        term = var(value["name"], width if sort == "BV" else None)
    elif op == "bool":
        if (
            set(value) != {"op", "sort", "value"}
            or sort != "Bool"
            or not isinstance(value.get("value"), bool)
        ):
            raise SchemaError("malformed Boolean literal")
        term = bool_lit(value["value"])
    elif op == "bv":
        literal = value.get("value")
        if (
            set(value) != {"op", "sort", "width", "value"}
            or sort != "BV"
            or not isinstance(width, int)
            or isinstance(width, bool)
            or width <= 0
            or not isinstance(literal, int)
            or isinstance(literal, bool)
            or literal < 0
            or literal >= 1 << width
        ):
            raise SchemaError("malformed bitvector literal")
        term = bv_lit(width, literal)
    elif op == "not":
        _require_term_shape(value, {"op", "sort", "args"}, "not")
        if sort != "Bool" or len(args) != 1:
            raise SchemaError("malformed not term")
        term = bool_not(args[0])
    elif op in {"and", "or"}:
        _require_term_shape(value, {"op", "sort", "args"}, op)
        if sort != "Bool":
            raise SchemaError(f"malformed {op} term")
        term = bool_and(*args) if op == "and" else bool_or(*args)
    elif op == "xor_bool":
        _require_term_shape(value, {"op", "sort", "args"}, op)
        if sort != "Bool" or len(args) != 2:
            raise SchemaError("malformed Boolean xor term")
        term = bool_xor(args[0], args[1])
    elif op == "eq":
        _require_term_shape(value, {"op", "sort", "args"}, op)
        if sort != "Bool" or len(args) != 2:
            raise SchemaError("malformed equality term")
        term = equal(args[0], args[1])
    elif op == "ite":
        expected = {"op", "sort", "args"}
        if sort == "BV":
            expected.add("width")
        _require_term_shape(value, expected, op)
        if len(args) != 3:
            raise SchemaError("malformed ite term")
        term = ite(args[0], args[1], args[2])
    elif op in {"bvadd", "bvxor", "bvand", "bvor"}:
        _require_term_shape(value, {"op", "sort", "width", "args"}, op)
        if sort != "BV" or len(args) != 2:
            raise SchemaError(f"malformed {op} term")
        term = bv_binary(op, args[0], args[1])
    elif op == "bvult":
        _require_term_shape(value, {"op", "sort", "args"}, op)
        if sort != "Bool" or len(args) != 2:
            raise SchemaError("malformed bvult term")
        term = bv_ult(args[0], args[1])
    elif op == "extract":
        _require_term_shape(
            value, {"op", "sort", "width", "value", "args"}, op
        )
        if sort != "BV" or len(args) != 1:
            raise SchemaError("malformed extract term")
        term = extract(args[0], value["value"], width)
    elif op == "concat":
        _require_term_shape(value, {"op", "sort", "width", "args"}, op)
        if (
            sort != "BV"
            or not args
            or any(arg.sort != "BV" for arg in args)
            or sum(int(arg.width) for arg in args) != width
        ):
            raise SchemaError("malformed concat term")
        term = Term("BV", width, "concat", args)
    else:
        raise SchemaError(f"unsupported term operator {op!r}")

    if term.to_obj() != value:
        raise SchemaError("term object is not in canonical form")
    return term


def _require_term_shape(
    value: dict[str, Any], expected: set[str], context: str
) -> None:
    if set(value) != expected:
        raise SchemaError(f"{context} term field mismatch")


def collect_variables(terms: Iterable[Term]) -> dict[str, int]:
    """Collect the exact bitvector leaf inventory from canonical terms."""

    result: dict[str, int] = {}

    def visit(term: Term) -> None:
        if term.op == "var":
            if term.name is None or term.width is None:
                raise SchemaError("reference formulas require bitvector input leaves")
            previous = result.setdefault(term.name, term.width)
            if previous != term.width:
                raise SchemaError(
                    f"formula symbol {term.name} has inconsistent widths"
                )
        for child in term.args:
            visit(child)

    for term in terms:
        visit(term)
    return result


def bool_lit(value: bool) -> Term:
    return Term("Bool", None, "bool", value=value)


def bv_lit(width: int, value: int) -> Term:
    return Term("BV", width, "bv", value=value & mask(width))


def var(name: str, width: int | None = None) -> Term:
    return Term("Bool" if width is None else "BV", width, "var", name=name)


def bool_not(value: Term) -> Term:
    require_sort(value, "Bool")
    return Term("Bool", None, "not", (value,))


def bool_and(*values: Term) -> Term:
    for value in values:
        require_sort(value, "Bool")
    if not values:
        return bool_lit(True)
    return Term("Bool", None, "and", tuple(values))


def bool_or(*values: Term) -> Term:
    for value in values:
        require_sort(value, "Bool")
    if not values:
        return bool_lit(False)
    return Term("Bool", None, "or", tuple(values))


def bool_xor(left: Term, right: Term) -> Term:
    require_sort(left, "Bool")
    require_sort(right, "Bool")
    return Term("Bool", None, "xor_bool", (left, right))


def equal(left: Term, right: Term) -> Term:
    require_same_sort(left, right)
    return Term("Bool", None, "eq", (left, right))


def ite(condition: Term, when_true: Term, when_false: Term) -> Term:
    require_sort(condition, "Bool")
    require_same_sort(when_true, when_false)
    return Term(when_true.sort, when_true.width, "ite", (condition, when_true, when_false))


def bv_binary(op: str, left: Term, right: Term) -> Term:
    require_same_sort(left, right)
    require_sort(left, "BV")
    return Term("BV", left.width, op, (left, right))


def bv_ult(left: Term, right: Term) -> Term:
    require_same_sort(left, right)
    require_sort(left, "BV")
    return Term("Bool", None, "bvult", (left, right))


def extract(value: Term, low: int, width: int) -> Term:
    require_sort(value, "BV")
    if (
        not isinstance(low, int)
        or isinstance(low, bool)
        or not isinstance(width, int)
        or isinstance(width, bool)
        or low < 0
        or width <= 0
        or low + width > int(value.width)
    ):
        raise SchemaError("invalid bitvector extraction")
    return Term("BV", width, "extract", (value,), value=low)


def require_sort(term: Term, sort: str) -> None:
    if term.sort != sort:
        raise SchemaError(f"expected {sort}, got {term.sort}")


def require_same_sort(left: Term, right: Term) -> None:
    if left.sort != right.sort or left.width != right.width:
        raise SchemaError(
            f"sort mismatch: {left.sort}/{left.width} vs {right.sort}/{right.width}"
        )
