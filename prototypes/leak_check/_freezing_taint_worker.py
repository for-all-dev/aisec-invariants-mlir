"""
Worker for the COMPILE-TIME taint escalation of the freezing constant-fold leak
(probe_freezing_taint.py).

The established finding (leak_check.freezing.agents.md) is at the codegen-diff
level: `torch._inductor.config.freezing = True` folds a secret-derived scalar
(quant_scale = max|w|/127) into a `static_cast<float>` literal in the generated
C++. This worker escalates it toward an instruction-level proof via the taint
channel.

THE CRITICAL INSIGHT: the fold happens at COMPILE time. In the FROZEN model the
executed kernel reads the folded LITERAL, not the weight buffer -- so the classic
runtime taint (mark weights undefined, run the forward under memcheck) reads CLEAN
on a frozen model. The secret was already baked into the code during compilation.
Therefore we must taint the COMPILE step, not the forward pass:

    frozen    : ConstantFolder evaluates max|w|/127 on the (tainted) weight tensor
                DURING compilation, then formats the result into the C++ source.
                memcheck should fire at compile time with origin = the weight
                buffer (a Valgrind client request).
    nonfrozen : the weight stays a runtime input; compilation never reads it, so no
                fold-site report. Any report is the ordinary runtime read inside the
                generated kernel .so -- the negative control that isolates freezing
                as the cause.

    python _freezing_taint_worker.py <surface> <secret.npy> <frozen|nonfrozen> [shim.so]

MANDATORY controls (PRINCIPLES §5): a private, unique TORCHINDUCTOR_CACHE_DIR per
invocation AND force_disable_caches, so a class never reuses a sibling's cached
kernel (a false-negative generator this project was burned by twice).
"""

import ctypes
import os
import sys
import tempfile

# Determinism knobs + a private inductor cache BEFORE importing torch.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("PYTHONHASHSEED", "0")
os.environ["TORCHINDUCTOR_CACHE_DIR"] = tempfile.mkdtemp(prefix="ic_freeze_taint_")
# Compile IN-PROCESS: the async-compile pool forks worker subprocesses that stay
# under Valgrind and clobber a shared --log-file. Serializing keeps the tainted
# fold + literal formatting (both in the main process) in one clean memcheck log.
os.environ["TORCHINDUCTOR_COMPILE_THREADS"] = "1"

import numpy as np  # noqa: E402  (must follow the determinism/cache setup above)
import torch  # noqa: E402

torch.manual_seed(0)
torch.set_num_threads(1)

import corpus_freezing as CF  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def load_shim(path):
    shim = ctypes.CDLL(path)
    shim.vg_make_undefined.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    shim.vg_make_defined.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    shim.vg_marker.argtypes = [ctypes.c_char_p]
    shim.vg_running.restype = ctypes.c_int
    return shim


def main():
    surface, secret_path, mode = sys.argv[1], sys.argv[2], sys.argv[3]
    shim_path = sys.argv[4] if len(sys.argv) > 4 else os.path.join(HERE, "vgshim.so")
    assert mode in ("frozen", "nonfrozen"), mode

    shim = load_shim(shim_path)

    import torch._inductor.config as ic

    ic.force_disable_caches = True  # force real codegen, never a cache hit
    ic.freezing = mode == "frozen"

    w = np.load(secret_path).astype(np.float32)
    m = CF.build(surface).eval()
    with torch.no_grad():
        m.weight.copy_(torch.from_numpy(w))
    x = CF.example_input(surface)

    fn = torch.compile(m, fullgraph=True)

    nbytes = m.weight.numel() * m.weight.element_size()
    wptr = m.weight.data_ptr()

    # --- Taint the COMPILE step. Mark the secret weight bytes UNDEFINED, then
    #     trigger compilation (first forward). In frozen mode the constant-folding
    #     pass reads these bytes to compute max|w|/127 and formats the result into
    #     the generated C++; memcheck reports the use with origin = this client
    #     request. In nonfrozen mode compilation never reads the weight. ---
    shim.vg_marker(b"### LEAKCHECK taint region begin ###")
    shim.vg_make_undefined(ctypes.c_void_p(wptr), ctypes.c_size_t(nbytes))
    with torch.no_grad():
        out = fn(x)
    # Re-define derived buffers so our own teardown can't raise spurious reports.
    shim.vg_make_defined(
        ctypes.c_void_p(out.data_ptr()), ctypes.c_size_t(out.numel() * out.element_size())
    )
    shim.vg_make_defined(ctypes.c_void_p(wptr), ctypes.c_size_t(nbytes))
    shim.vg_marker(b"### LEAKCHECK taint region end ###")

    flat = out.reshape(-1)
    print(
        f"RESULT surface={surface} mode={mode} secret={os.path.basename(secret_path)} "
        f"vg_running={shim.vg_running()} out[0]={flat[0].item():.12g} "
        f"expected_stat={CF.stat(surface, w):.12g}"
    )


if __name__ == "__main__":
    main()
