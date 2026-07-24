"""
Information-theoretic leakage estimate from a timing sample — the core of
layers C and D.

Given, for many kernel invocations, the secret CLASS that drove each call and
the measured CYCLE count, we ask: *how many bits of the secret does the timing
reveal?* That is the mutual information ``I(S; T)`` between the class label ``S``
and the timing ``T``, in bits. ``0`` bits ⟹ the timing is independent of the
secret (no channel); ``H(S)`` bits ⟹ the timing determines the secret exactly.
For a 2-class test ``H(S) = 1`` bit, so ``I`` lands in ``[0, 1]``.

Why an information estimate rather than just "is there a difference":

  - It is a single, comparable, physically meaningful number: bits leaked per
    query. Combined with the threat-model fact that model weights are queried
    *unbounded* times (see formal_verif.threat-model.agents.md), bits/query is
    exactly what bounds how fast an attacker recovers the secret.
  - It catches distribution-shape leaks a difference-of-means test misses (e.g.
    same mean, different variance/multimodality).

The honest problem with plug-in MI: on finite samples it is **biased upward** —
even independent data gives ``I_hat > 0`` because empty/sparse histogram cells
look "informative". We correct this with a PERMUTATION NULL: shuffle the class
labels (which destroys any real dependence but preserves the sample sizes and
the timing distribution), recompute MI, and repeat. The mean of that null IS the
finite-sample bias; we subtract it, and the fraction of shuffles that beat the
observed MI is a distribution-free p-value. This is the same discipline the
leak_check prototype settled on — decide on a debiased effect size with a
calibrated null, not on a raw statistic (leak_check.lessons.agents.md).

Alongside MI we report the dudect / TVLA Welch t-statistic (the detection
primitive the roadmap names for layer D) as an independent corroborating signal.

Detection, never proof: a null here means "no channel above this harness's noise
floor on this CPU at this sample size", not "provably constant-time".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

# dudect's canonical decision threshold on |t| (≈ 1e-5 two-sided at large N).
DUDECT_T_THRESHOLD = 4.5
# Permutation p below this AND a debiased effect above the floor ⟹ we call a leak.
DEFAULT_P_THRESHOLD = 0.01
DEFAULT_BITS_FLOOR = 0.01  # bits; below this we treat MI as harness noise


@dataclass
class LeakEstimate:
    kernel: str
    n_samples: int
    class_counts: dict[int, int]
    mi_bits: float  # debiased I(S;T), clamped at 0 — the headline "bits leaked"
    mi_raw_bits: float  # plug-in MI before debiasing
    mi_null_mean: float  # mean MI under label permutation == the finite-sample bias
    mi_null_std: float
    mi_p_value: float  # P(shuffled MI >= observed) — distribution-free
    max_bits: float  # H(S): the most the timing could possibly reveal
    t_stat: float  # dudect / TVLA Welch t (cropped)
    t_leaks: bool  # |t| > DUDECT_T_THRESHOLD
    median_cycles: dict[int, float]
    bins: int
    permutations: int
    verdict: str  # "leak" | "no-detectable-leak"
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def _entropy_bits(counts: np.ndarray) -> float:
    p = counts[counts > 0].astype(float)
    p /= p.sum()
    return float(-(p * np.log2(p)).sum())


def _mi_bits_from_joint(joint: np.ndarray) -> float:
    """Plug-in mutual information (bits) from a joint count table [classes x bins]."""
    total = joint.sum()
    if total == 0:
        return 0.0
    p_sb = joint.astype(float) / total
    p_s = p_sb.sum(axis=1, keepdims=True)
    p_b = p_sb.sum(axis=0, keepdims=True)
    denom = p_s @ p_b  # outer product == independent joint
    mask = p_sb > 0
    return float((p_sb[mask] * np.log2(p_sb[mask] / denom[mask])).sum())


def _quantile_bin_edges(times: np.ndarray, bins: int) -> np.ndarray:
    """Equal-frequency (quantile) bin edges over the pooled timings, deduped."""
    qs = np.linspace(0.0, 1.0, bins + 1)
    edges = np.quantile(times, qs)
    edges = np.unique(edges)
    if edges.size < 2:  # degenerate: all times identical
        edges = np.array([times.min(), times.min() + 1.0])
    edges[-1] = np.nextafter(edges[-1], np.inf)  # include the max in the last bin
    return edges


def _welch_t(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or b.size < 2:
        return 0.0
    va, vb = a.var(ddof=1), b.var(ddof=1)
    denom = np.sqrt(va / a.size + vb / b.size)
    if denom == 0:
        return 0.0
    return float((a.mean() - b.mean()) / denom)


def _cropped_t(classes: np.ndarray, times: np.ndarray, crop_pct: float = 99.5) -> float:
    """dudect-style Welch t on tail-cropped data (kills interrupt/OS spikes)."""
    hi = np.percentile(times, crop_pct)
    keep = times <= hi
    c, t = classes[keep], times[keep]
    labels = np.unique(c)
    if labels.size != 2:
        return 0.0
    return _welch_t(t[c == labels[0]].astype(float), t[c == labels[1]].astype(float))


def estimate_leak(
    classes: np.ndarray,
    cycles: np.ndarray,
    *,
    kernel: str = "?",
    bins: int | None = None,
    permutations: int = 300,
    seed: int = 0,
    p_threshold: float = DEFAULT_P_THRESHOLD,
    bits_floor: float = DEFAULT_BITS_FLOOR,
) -> LeakEstimate:
    """Estimate ``I(S; T)`` in bits with a permutation-null debias + dudect t.

    ``classes`` and ``cycles`` are parallel 1-D arrays (one per measured call).
    """
    classes = np.asarray(classes)
    cycles = np.asarray(cycles, dtype=float)
    n = classes.size
    labels, inv = np.unique(classes, return_inverse=True)
    n_classes = labels.size

    counts = {int(lbl): int((classes == lbl).sum()) for lbl in labels}
    medians = {int(lbl): float(np.median(cycles[classes == lbl])) for lbl in labels}
    max_bits = _entropy_bits(np.array(list(counts.values())))

    if bins is None:
        # Enough bins to resolve shape, few enough that cells aren't starved;
        # the permutation null corrects whatever bias the choice induces.
        bins = int(min(50, max(4, n // 200)))

    edges = _quantile_bin_edges(cycles, bins)
    b_idx = np.clip(np.digitize(cycles, edges) - 1, 0, edges.size - 2)
    n_bins = edges.size - 1

    def joint_from(class_idx: np.ndarray) -> np.ndarray:
        j = np.zeros((n_classes, n_bins), dtype=np.int64)
        np.add.at(j, (class_idx, b_idx), 1)
        return j

    mi_raw = _mi_bits_from_joint(joint_from(inv))

    rng = np.random.default_rng(seed)
    null = np.empty(permutations)
    for r in range(permutations):
        null[r] = _mi_bits_from_joint(joint_from(rng.permutation(inv)))
    null_mean = float(null.mean())
    null_std = float(null.std(ddof=1)) if permutations > 1 else 0.0
    mi_debiased = max(0.0, mi_raw - null_mean)
    # +1 smoothing so a clean separation reports p = 1/(R+1), never 0.
    p_value = float((1 + int((null >= mi_raw).sum())) / (permutations + 1))

    t_stat = _cropped_t(classes, cycles) if n_classes == 2 else 0.0
    t_leaks = abs(t_stat) > DUDECT_T_THRESHOLD

    leak = (p_value < p_threshold) and (mi_debiased > bits_floor)
    if leak:
        detail = (
            f"timing reveals ~{mi_debiased:.3f} of {max_bits:.2f} secret bits/query "
            f"(perm p={p_value:.2g}, dudect t={t_stat:.1f})"
        )
    else:
        detail = (
            f"no channel above floor: MI {mi_debiased:.3f} bits "
            f"(raw {mi_raw:.3f} − bias {null_mean:.3f}), perm p={p_value:.2g}, "
            f"dudect t={t_stat:.1f} — detection null, not a proof of constant-time"
        )

    return LeakEstimate(
        kernel=kernel,
        n_samples=n,
        class_counts=counts,
        mi_bits=mi_debiased,
        mi_raw_bits=mi_raw,
        mi_null_mean=null_mean,
        mi_null_std=null_std,
        mi_p_value=p_value,
        max_bits=max_bits,
        t_stat=t_stat,
        t_leaks=t_leaks,
        median_cycles=medians,
        bins=n_bins,
        permutations=permutations,
        verdict="leak" if leak else "no-detectable-leak",
        detail=detail,
    )
