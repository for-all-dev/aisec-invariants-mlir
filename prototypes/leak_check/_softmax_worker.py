"""
Worker for the softmax codegen probe. Compile one activation from
corpus_activations with a specific SECRET class present and let
TORCH_LOGS=output_code dump the generated C++ to stderr (captured by the driver).

    TORCH_LOGS=output_code python _softmax_worker.py <act> <secret.npy>

Inductor caches are force-disabled so codegen actually runs rather than loading a
cached .so — otherwise the second class would silently reuse the first's kernel
and the diff would be vacuously identical.
"""
import os, sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("PYTHONHASHSEED", "0")

import numpy as np
import torch

torch.manual_seed(0)
torch.set_num_threads(1)

import corpus_activations as CA


def main():
    act, secret_path = sys.argv[1], sys.argv[2]

    import torch._inductor.config as ic
    ic.force_disable_caches = True

    w = np.load(secret_path).astype(np.float32)
    m = CA.build(act)
    with torch.no_grad():
        m.weight.copy_(torch.from_numpy(w))
    x = CA.example_input(act)

    fn = torch.compile(m, fullgraph=True)
    with torch.no_grad():
        for _ in range(2):
            out = fn(x)

    flat = out.reshape(-1)
    print(f"RESULT act={act} secret={os.path.basename(secret_path)} "
          f"out[0]={flat[0].item():.12g} sum={out.sum().item():.12g}")


if __name__ == "__main__":
    main()
