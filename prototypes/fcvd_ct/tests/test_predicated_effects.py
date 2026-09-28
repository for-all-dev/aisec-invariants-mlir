"""Memory effects on untaken paths: the flattener must not let them fire.

If-conversion runs both arms of every branch, so an effect sitting in the arm that is
not taken has to be predicated or refused. `memref.store` always was; `llvm.store` used
to be emitted as-is, so a store that never runs still wrote memory, and a later load
saw the secret it would have written. The pair below differs only in whether the arm
is taken, so a flattener that ignored the guard would answer `insecure` for both.
"""

from __future__ import annotations

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.parser import Parser

from fcvdct.context import make_context
from fcvdct.selfcomp import check_module

# The secret is stored only when %taken holds, then read back and branched on.
GUARDED_LLVM_STORE = """
func.func @k(%p: !llvm.ptr, %s: i8 {{fcvdct.secret}}) -> i8 {{
  %taken = arith.constant {taken}
  %c0 = arith.constant 0 : i64
  %g = "llvm.getelementptr"(%p, %c0) <{{rawConstantIndices = array<i32: -1>, elem_type = i8}}>
      : (!llvm.ptr, i64) -> !llvm.ptr
  scf.if %taken {{
    "llvm.store"(%s, %g) <{{ordering = 0 : i64}}> : (i8, !llvm.ptr) -> ()
  }}
  %v = "llvm.load"(%g) <{{ordering = 0 : i64}}> : (!llvm.ptr) -> i8
  %z = arith.constant 0 : i8
  %b = arith.cmpi eq, %v, %z : i8
  %r = scf.if %b -> (i8) {{
    scf.yield %z : i8
  }} else {{
    scf.yield %v : i8
  }}
  func.return %r : i8
}}
"""


def load(name: str, source: str) -> tuple[Context, ModuleOp]:
    ctx = make_context()
    return ctx, Parser(ctx, source, name).parse_module()


@pytest.mark.parametrize(
    ("taken", "verdict", "violated"),
    [
        ("false", "secure", None),
        ("true", "insecure", "control"),
    ],
)
def test_llvm_store_only_fires_on_its_path(taken: str, verdict: str, violated: str | None):
    ctx, module = load("guarded_llvm_store", GUARDED_LLVM_STORE.format(taken=taken))
    result = check_module(ctx, module)
    assert result.verdict == verdict, result.reason
    insecure = {o.kind for o in result.obligations if o.verdict == "insecure"}
    assert insecure == ({violated} if violated else set())


def test_dealloc_under_a_branch_is_refused_not_run():
    """A `dealloc` cannot be predicated by a select; it must come back `unknown`."""
    ctx, module = load(
        "guarded_dealloc",
        """
        func.func @k(%c: i1, %s: i8 {fcvdct.secret}) -> i8 {
          %m = memref.alloc() : memref<4xi8>
          scf.if %c {
            memref.dealloc %m : memref<4xi8>
          }
          func.return %s : i8
        }
        """,
    )
    result = check_module(ctx, module)
    assert result.verdict == "unknown"
    assert "dealloc" in result.reason
