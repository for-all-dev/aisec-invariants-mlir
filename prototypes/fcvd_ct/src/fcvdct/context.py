"""The MLIR context and semantics registration shared by the tools here."""

from __future__ import annotations

from xdsl.context import Context
from xdsl.dialects.affine import Affine
from xdsl.dialects.arith import Arith
from xdsl.dialects.builtin import Builtin
from xdsl.dialects.cf import Cf
from xdsl.dialects.comb import Comb
from xdsl.dialects.func import Func
from xdsl.dialects.memref import MemRef
from xdsl.dialects.pdl import PDL
from xdsl.dialects.scf import Scf
from xdsl.dialects.tensor import Tensor
from xdsl.ir import Dialect
from xdsl_smt.dialects.effects.effect import EffectDialect
from xdsl_smt.dialects.effects.ub_effect import UBEffectDialect
from xdsl_smt.dialects.hw_dialect import HW
from xdsl_smt.dialects.index_dialect import Index
from xdsl_smt.dialects.llvm_dialect import LLVM
from xdsl_smt.dialects.pdl_dataflow import PDLDataflowDialect
from xdsl_smt.dialects.smt_bitvector_dialect import SMTBitVectorDialect
from xdsl_smt.dialects.smt_dialect import SMTDialect
from xdsl_smt.dialects.smt_utils_dialect import SMTUtilsDialect
from xdsl_smt.dialects.transfer import Transfer
from xdsl_smt.passes.lower_to_smt.smt_lowerer_loaders import load_vanilla_semantics

from .affine_ops import install_affine_syntax
from .dialect import FCVD
from .hw_ops import HWConstant, load_hw_semantics
from .index_ops import load_index_semantics
from .tensor_ops import load_tensor_semantics


def make_context() -> Context:
    """A context with the dialects a PDL constant-time query can mention."""
    ctx = Context()
    pdl_with_dataflow = Dialect(
        "pdl",
        [*PDL.operations, *PDLDataflowDialect.operations],
        [*PDL.attributes, *PDLDataflowDialect.attributes],
    )
    # xdsl-smt declares `hw` but gives `hw.constant` neither syntax nor semantics; ours
    # supplies both, and the rest of upstream's dialect is kept as it is.
    hw_with_constant = Dialect(
        "hw",
        [
            *(op for op in HW.operations if op.name not in {o.name for o in HWConstant.operations}),
            *HWConstant.operations,
        ],
        [*HW.attributes],
    )
    smt_collection = Dialect(
        "smt",
        [
            *SMTDialect.operations,
            *SMTBitVectorDialect.operations,
            *SMTUtilsDialect.operations,
        ],
        [
            *SMTDialect.attributes,
            *SMTBitVectorDialect.attributes,
            *SMTUtilsDialect.attributes,
        ],
    )
    for dialect in (
        Builtin,
        Func,
        Arith,
        Affine,
        Tensor,
        Cf,
        Scf,
        FCVD,
        Comb,
        hw_with_constant,
        LLVM,
        MemRef,
        Index,
        Transfer,
        EffectDialect,
        UBEffectDialect,
        pdl_with_dataflow,
        smt_collection,
    ):
        ctx.register_dialect(dialect.name, lambda d=dialect: d)  # type: ignore[misc]

    load_vanilla_semantics()
    load_index_semantics()
    install_affine_syntax()
    load_hw_semantics()
    load_tensor_semantics()
    return ctx
