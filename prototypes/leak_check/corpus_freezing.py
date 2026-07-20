"""
Corpus of constant-folding surfaces for the freezing probe (probe_freezing.py).

The empty quadrant of this project has been "compiler-INTRODUCED leak": structural
lowerings (relu/exp/matmul) key codegen on shape/dtype, so the weight is runtime
data the optimizer has nothing to specialize on. The lever this corpus pulls is
CONSTANT-FOLDING. `torch._inductor.config.freezing = True` treats the weight as a
compile-time constant; any secret-derived scalar the forward computes from it
(`w.abs().max()/127`, `w.max()`, `w.sum()`, `1/w.norm()`) becomes computable at
compile time, so Inductor may fold it and bake a secret-derived LITERAL into the
generated C++. That is a stronger violation than a side channel: the secret is now
part of the generated CODE.

Each surface is a model computing one folded scalar and multiplying the input by
it, plus a baited pair of secret classes that differ ONLY in that scalar (the
softmax lesson: the bait must differ in the exact statistic the compiler folds,
not arbitrarily). `stat(w)` returns the scalar the compiler should fold, so the
driver can check a recovered literal against the value it must equal.

  EAGER / non-frozen : the scalar is computed at runtime from weight data, so both
                       classes execute identical instructions -> OBLIVIOUS.
  FROZEN             : the scalar is folded to a literal, so codegen differs by
                       class -> the compiler-introduced leak.
"""

import numpy as np
import torch

DIM = 64  # scalar fold: tiny is plenty, and keeps each compile to seconds.


class ScaleModel(torch.nn.Module):
    """out = x * f(weight), where f collapses the secret weight to one scalar."""

    def __init__(self, surface):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.zeros(DIM, DIM))
        self._surface = surface

    def forward(self, x):
        w = self.weight
        if self._surface == "quant_scale":
            s = w.abs().max() / 127.0
        elif self._surface == "wmax":
            s = w.max()
        elif self._surface == "wsum":
            s = w.sum()
        elif self._surface == "wnorm":
            s = torch.reciprocal(w.norm())
        else:  # pragma: no cover - guarded by names()
            raise ValueError(self._surface)
        return x * s


_SURFACES = ("quant_scale", "wmax", "wsum", "wnorm")


def names():
    return list(_SURFACES)


def build(name):
    return ScaleModel(name)


def example_input(name):
    return torch.randn(1, DIM)


def stat(name, w):
    """The scalar the compiler is expected to fold, computed in numpy (float32 to
    match the graph). This is what a recovered literal must equal."""
    w = w.astype(np.float32)
    if name == "quant_scale":
        return float(np.max(np.abs(w)) / np.float32(127.0))
    if name == "wmax":
        return float(np.max(w))
    if name == "wsum":
        return float(np.sum(w))
    if name == "wnorm":
        return float(np.float32(1.0) / np.linalg.norm(w.reshape(-1)).astype(np.float32))
    raise ValueError(name)


# Baits. Each surface names the folded statistic and two target values for it,
# well clear of 1.0 so that `x * s` is never simplified to the identity `x`
# (which would make classes differ structurally rather than by the folded value).
# The primary surface keeps the task's max|w| = 1.0 vs 100.0 -> scale 1/127 vs
# 100/127, neither of which is 1.0.
_BAIT = {
    "quant_scale": ("maxabs", 1.0, 100.0),
    "wmax": ("max", 3.0, 100.0),
    "wsum": ("sum", 7.0, 100.0),
    "wnorm": ("norm", 2.0, 100.0),
}


def _draw(name, target, seed):
    """A [DIM, DIM] float32 draw whose folded statistic equals `target` exactly,
    with the same underlying random field otherwise so the classes differ only in
    the statistic the compiler folds."""
    base = np.random.default_rng(seed).standard_normal((DIM, DIM), dtype=np.float32)
    if name == "quant_scale":
        w = base / np.max(np.abs(base)) * np.float32(target)  # |w|.max() == target
    elif name == "wmax":
        w = base + np.float32(target - np.max(base))  # w.max() == target (shift)
    elif name == "wsum":
        w = base + np.float32((target - np.sum(base)) / base.size)  # w.sum() == target
    elif name == "wnorm":
        w = base / np.linalg.norm(base.reshape(-1)) * np.float32(target)  # norm == target
    else:
        raise ValueError(name)
    return w.astype(np.float32)


def secret_classes(name):
    """((labelA, arrA), (labelB, arrB), (labelCtl, arrCtl)).

    A and B differ in the folded statistic (the bait). Ctl is an INDEPENDENT draw
    with the SAME statistic as A: under a correct detector its frozen codegen must
    match A's exactly (MANDATORY same-class control, PRINCIPLES §5). If Ctl differs
    from A the detector/normalizer is broken, not the compiler."""
    stat_name, va, vb = _BAIT[name]
    a = _draw(name, va, seed=1)
    b = _draw(name, vb, seed=2)
    ctl = _draw(name, va, seed=3)  # same statistic as A, different random field
    return (
        (f"{stat_name}{va:g}", a),
        (f"{stat_name}{vb:g}", b),
        (f"{stat_name}{va:g}_ctl", ctl),
    )
