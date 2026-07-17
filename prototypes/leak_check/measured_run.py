"""
One measured forward pass with a *fixed, secret-independent code path*.

The whole point: everything except the contents of model.weight is identical
across invocations, so any difference an instrument sees is attributable to the
secret bytes. All compilation, warmup, and allocation happen OUTSIDE the
instrumented region (between cg_start/cg_stop, or before the taint mark).

Usage:
  python measured_run.py <model> <secret.npy> [--compile] [--taint]

Instruments wrap this script:
  * callgrind counts instructions between cg_start()/cg_stop()
  * memcheck reports any control-flow/address dependence on the tainted weights
"""

import argparse
import ctypes
import os

# Determinism knobs BEFORE importing torch.
os.environ.setdefault("PYTHONHASHSEED", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np
import torch

torch.manual_seed(0)
torch.set_num_threads(1)

# Optional Inductor vectorization cap. Mainline Valgrind's VEX decoder has no
# AVX-512 EVEX support (verified through 3.25.1, the latest release: it SIGILLs on
# the same vpternlogd bytes as 3.22), so on an AVX-512 host Inductor's generated
# kernels die under callgrind/memcheck. LEAKCHECK_SIMDLEN=8 forces 256-bit (AVX2)
# codegen the decoder can handle. This changes the measured ISA config point --
# note it in any verdict. No effect on eager or on an absent/empty value.
_simd = os.environ.get("LEAKCHECK_SIMDLEN")
if _simd:
    import torch._inductor.config as _icfg

    _icfg.cpp.simdlen = int(_simd)

import corpus  # noqa: E402  (must follow the determinism setup above)
import corpus_activations  # noqa: E402


def _resolve(name):
    """Dispatch a model name to whichever corpus module defines it."""
    return corpus_activations if name in corpus_activations.names() else corpus


def load_shim(path):
    shim = ctypes.CDLL(path)
    shim.vg_make_undefined.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    shim.vg_make_defined.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    shim.vg_marker.argtypes = [ctypes.c_char_p]
    shim.vg_running.restype = ctypes.c_int
    return shim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", choices=corpus.names() + corpus_activations.names())
    ap.add_argument("secret", help="path to float32 .npy of shape [DIM, DIM]")
    ap.add_argument("--compile", action="store_true")
    ap.add_argument("--taint", action="store_true")
    ap.add_argument("--shim", default=os.path.join(os.path.dirname(__file__), "vgshim.so"))
    args = ap.parse_args()

    shim = load_shim(args.shim)

    src = _resolve(args.model)
    w = np.load(args.secret).astype(np.float32)
    model = src.build(args.model)
    with torch.no_grad():
        model.weight.copy_(torch.from_numpy(w))
    x = src.example_input(args.model)

    fn = model
    if args.compile:
        fn = torch.compile(model, fullgraph=True)

    # --- Warm EVERYTHING outside the measured region: compile, autotune,
    #     allocator caches, dispatch caches. Two passes for good measure. ---
    with torch.no_grad():
        for _ in range(2):
            _ = fn(x)

    nbytes = model.weight.numel() * model.weight.element_size()
    wptr = model.weight.data_ptr()

    if args.taint:
        # Mark the secret bytes UNDEFINED. Their real values stay in memory; only
        # memcheck's definedness shadow flips, so any branch/address computed from
        # them is reported at the exact leaking instruction.
        shim.vg_marker(b"### LEAKCHECK taint region begin ###")
        shim.vg_make_undefined(ctypes.c_void_p(wptr), ctypes.c_size_t(nbytes))
        with torch.no_grad():
            out = fn(x)
        # Re-define the derived output so our own teardown (dealloc, exit) can't
        # raise spurious reports.
        shim.vg_make_defined(
            ctypes.c_void_p(out.data_ptr()), ctypes.c_size_t(out.numel() * out.element_size())
        )
        shim.vg_make_defined(ctypes.c_void_p(wptr), ctypes.c_size_t(nbytes))
        shim.vg_marker(b"### LEAKCHECK taint region end ###")
    else:
        # Counting mode: gate callgrind to just the forward pass.
        # The sink forces materialization so nothing is optimized away. The
        # original sink `float(out.reshape(-1)[0])` READ an output value inside
        # the measured region, and float()/scalar-extract takes a data-dependent
        # CPython path on an all-zero vs a random output -- injecting a
        # secret-VALUE-dependent count that is the harness's, not the kernel's
        # (measured: ~194 of a 303-instruction zero-vs-random gap on branchless).
        # Default "none" keeps `out` alive to block DCE with NO value read, so the
        # count reflects only the kernel. Set LEAKCHECK_SINK=elem for the old sink.
        sink_mode = os.environ.get("LEAKCHECK_SINK", "none")
        _keep = []
        shim.cg_start()
        with torch.no_grad():
            out = fn(x)
            if sink_mode == "elem":
                sink = float(out.reshape(-1)[0])  # force materialization
            else:
                _keep.append(out)  # reference-only; no value read
                sink = 0.0
        shim.cg_stop()
        # keep `sink`/`out` observable so nothing is optimized away
        if sink == 123456789.0 or (_keep and _keep[0].numel() < 0):
            print("unreachable", sink)


if __name__ == "__main__":
    main()
