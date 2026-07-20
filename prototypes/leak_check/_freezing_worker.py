"""
Worker for the freezing codegen probe. Compile ONE folding surface from
corpus_freezing with ONE secret class present, under a chosen mode, and let
TORCH_LOGS=output_code dump the generated C++ to stderr (captured by the driver).

    TORCH_LOGS=output_code python _freezing_worker.py <surface> <secret.npy> <frozen|nonfrozen>

Mode is the ONLY difference between the two arms of the 2x2:

  nonfrozen : torch.compile with freezing OFF. The weight stays a runtime input,
              so the scalar f(weight) is computed by the kernel at run time --
              identical instructions for every class (the oblivious column).
  frozen    : torch._inductor.config.freezing = True. The weight becomes a
              compile-time constant, so f(weight) is constant-folded and may be
              baked into the generated code as a literal (the leak column).

MANDATORY controls (PRINCIPLES §5, burned twice before):
  * A private, unique TORCHINDUCTOR_CACHE_DIR per invocation AND
    force_disable_caches -- otherwise class B silently reuses class A's cached
    kernel and every codegen diff is vacuously identical (a false-NEGATIVE
    generator). Both are set here; the cache dir also avoids colliding with
    sibling jobs.
"""

import os
import sys
import tempfile

# Determinism knobs + a private inductor cache BEFORE importing torch, so nothing
# is keyed on a shared or leftover cache.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("PYTHONHASHSEED", "0")
os.environ["TORCHINDUCTOR_CACHE_DIR"] = tempfile.mkdtemp(prefix="ic_freeze_")

import numpy as np  # noqa: E402  (must follow the determinism/cache setup above)
import torch  # noqa: E402

torch.manual_seed(0)
torch.set_num_threads(1)

import corpus_freezing as CF  # noqa: E402


def main():
    surface, secret_path, mode = sys.argv[1], sys.argv[2], sys.argv[3]
    assert mode in ("frozen", "nonfrozen"), mode

    import torch._inductor.config as ic

    ic.force_disable_caches = True  # force real codegen, never a cache hit
    ic.freezing = mode == "frozen"

    w = np.load(secret_path).astype(np.float32)
    m = CF.build(surface).eval()
    with torch.no_grad():
        m.weight.copy_(torch.from_numpy(w))
    x = CF.example_input(surface)

    fn = torch.compile(m, fullgraph=True)
    with torch.no_grad():
        for _ in range(2):
            out = fn(x)

    flat = out.reshape(-1)
    print(
        f"RESULT surface={surface} mode={mode} secret={os.path.basename(secret_path)} "
        f"out[0]={flat[0].item():.12g} expected_stat={CF.stat(surface, w):.12g}"
    )


if __name__ == "__main__":
    main()
