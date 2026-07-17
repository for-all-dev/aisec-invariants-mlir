"""Worker for probe_autotune_select. Compile a frozen linear (x @ w) under
max-autotune with a specific SECRET weight baked in as a constant, forcing a
fresh (uncached) autotune so the secret could in principle steer which GEMM
kernel the tuner benchmarks-and-picks.

    TORCHINDUCTOR_CACHE_DIR=<private> \
    TORCH_LOGS="output_code,+torch._inductor.select_algorithm" \
    python _autotune_select_worker.py <bait> <seed> <w0.npy> <out.npy>

`freezing=True` turns the weight into a prepacked constant, which is what makes
Inductor register a real *multi-choice* GEMM autotune on CPU (cpp micro-gemm vs
the mkl extern kernel) instead of a single foregone choice. The autotune
DECISION (which candidates, which won) is emitted to stderr by the
select_algorithm logger and parsed by the driver. Afterwards we time the
compiled artifact as a corroborating channel.
"""

import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np  # noqa: E402  (thread caps must be set before torch/numpy BLAS init)
import torch  # noqa: E402

torch.manual_seed(0)
torch.set_num_threads(1)

DIM = 512
ITERS = 100
WARMUP = 20


def make_weight(bait: str, seed: int) -> np.ndarray:
    """Bait pairs share shape+dtype (float32 DIM×DIM) and differ in ONE
    tuner-relevant property. Two draws of the same `bait` with different `seed`
    are the same class (the same-class control)."""
    rng = np.random.default_rng(seed)
    if bait == "dense":
        w = rng.standard_normal((DIM, DIM), dtype=np.float32)
    elif bait == "denormal":
        # ~1e-40: subnormal float32 (smallest normal ~1.18e-38). A property with
        # a known ~25x penalty in scalar/vector loops (see probe_fastmath).
        w = (rng.standard_normal((DIM, DIM)) * 1e-40).astype(np.float32)
    elif bait == "sparse":
        w = rng.standard_normal((DIM, DIM), dtype=np.float32)
        w[rng.random((DIM, DIM)) < 0.9] = 0.0  # 90% exact zeros
    elif bait == "small":
        w = (rng.standard_normal((DIM, DIM)) * 1e-4).astype(np.float32)
    elif bait == "large":
        w = (rng.standard_normal((DIM, DIM)) * 1e4).astype(np.float32)
    elif bait == "lowrank":
        a = rng.standard_normal((DIM, 4)).astype(np.float32)
        b = rng.standard_normal((4, DIM)).astype(np.float32)
        w = (a @ b).astype(np.float32)  # rank-4 structure
    else:
        raise SystemExit(f"unknown bait {bait!r}")
    return np.ascontiguousarray(w, dtype=np.float32)


class Linear(torch.nn.Module):
    def __init__(self, w: np.ndarray):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.from_numpy(w))

    def forward(self, x):
        return torch.matmul(x, self.weight)


def main():
    bait, seed, out_path = sys.argv[1], int(sys.argv[2]), sys.argv[3]

    import torch._inductor.config as ic

    ic.force_disable_caches = True  # a real, fresh autotune every time
    ic.max_autotune = True
    ic.max_autotune_gemm = True
    ic.freezing = True  # bake the weight in as a prepacked constant

    m = Linear(make_weight(bait, seed)).eval()
    x = torch.randn(DIM, DIM)
    with torch.no_grad():
        fn = torch.compile(m, mode="max-autotune", fullgraph=True)
        # Compile + autotune happen here, with the secret sitting in the constant.
        fn(x)
        for _ in range(WARMUP):
            fn(x)
        t = np.empty(ITERS)
        for i in range(ITERS):
            t0 = time.perf_counter()
            fn(x)
            t[i] = time.perf_counter() - t0
    np.save(out_path, t)
    print(f"RESULT bait={bait} seed={seed} median_us={np.median(t) * 1e6:.2f}")


if __name__ == "__main__":
    main()
