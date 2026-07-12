#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["torch>=2.2"]
#
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
#
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# ///
"""
The actual-nanoGPT weight-confidentiality step (CPU only).

Loads Karpathy's real `model.py` (cloned into ./nanoGPT), builds a tiny GPT,
runs a real forward pass, then analyzes how a *compiled* inference kernel leaks
the model WEIGHTS -- on a genuine nanoGPT weight matrix.

Threat model (same as the C corpus): weights are the confidential asset; a
kernel is oblivious iff weight VALUES never influence a branch or a memory
ADDRESS. We show, in a real aten-level IR graph:

  * dense  W @ x            -> `addmm`/`mm`     : weights -> arithmetic only  (OBLIVIOUS)
  * codebook dequant W_hat  -> `index`/`embedding` gather : address depends on
                               the secret quantized weight  (LEAKS)

The gather is exactly what `binsec -checkct` flags on the -m32 binary of
`mm_codebook` (cases.c). This script is the ML-compiler-level view of the same
phenomenon; binsec is the binary-level *proof*. We do NOT verify all of nanoGPT
-- SE is bounded -- we show the leak is present in the real architecture's
lowering and localize the responsible op.

Run:  uv run realgpt_probe.py      (first run downloads the CPU torch wheel)
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NANOGPT_DIR = os.path.join(HERE, "nanoGPT")
NANOGPT_URL = "https://github.com/karpathy/nanoGPT.git"
NANOGPT_PIN = "3adf61e154c3fe3fca428ad6bc3818b27a3b8291"


def ensure_nanogpt():
    """Fetch Karpathy's nanoGPT at a pinned commit if absent.

    Why not `uv add git+...` in the frontmatter? nanoGPT ships no packaging
    metadata (no pyproject.toml / setup.py), so uv/pip can't build it as a
    dependency. Its `model.py` is self-contained (stdlib + torch), so we vendor
    the repo at a pinned commit instead. Self-bootstrapping => no manual clone
    on the host, and the Docker image bakes this at build time.
    """
    if os.path.exists(os.path.join(NANOGPT_DIR, "model.py")):
        return
    print(f"[bootstrap] fetching nanoGPT @ {NANOGPT_PIN[:10]} ...", flush=True)
    os.makedirs(NANOGPT_DIR, exist_ok=True)
    def g(*a):
        subprocess.run(("git", *a), cwd=NANOGPT_DIR, check=True)
    g("init", "-q")
    g("remote", "add", "origin", NANOGPT_URL)
    try:  # GitHub allows fetching a reachable sha directly (shallow)
        g("fetch", "-q", "--depth", "1", "origin", NANOGPT_PIN)
        g("checkout", "-q", "FETCH_HEAD")
    except subprocess.CalledProcessError:
        g("fetch", "-q", "origin")
        g("checkout", "-q", NANOGPT_PIN)


ensure_nanogpt()
sys.path.insert(0, NANOGPT_DIR)

import torch
from torch.fx.experimental.proxy_tensor import make_fx
from model import GPT, GPTConfig  # Karpathy's real nanoGPT

torch.manual_seed(0)

GATHER_OPS = ("index", "embedding", "gather", "index_select", "take")
MATMUL_OPS = ("addmm", "mm", "matmul", "linear", "bmm", "mv", "dot")


def banner(s):
    print(f"\n\033[1m== {s} ==\033[0m")


# ---------------------------------------------------------------------------
# 1. Build a REAL (tiny) nanoGPT on CPU and run a real forward pass.
# ---------------------------------------------------------------------------
banner("real nanoGPT (tiny config, CPU)")
cfg = GPTConfig(block_size=16, vocab_size=32, n_layer=1, n_head=1,
                n_embd=8, dropout=0.0, bias=True)
model = GPT(cfg).eval()

idx = torch.randint(0, cfg.vocab_size, (1, 8))
with torch.no_grad():
    logits, _ = model(idx)
print(f"forward ok: tokens {tuple(idx.shape)} -> logits {tuple(logits.shape)}")

# The confidential assets: the weight tensors themselves.
banner("confidential assets (the weights an adversary must not recover)")
for name, p in list(model.named_parameters())[:6]:
    print(f"  {name:40s} {tuple(p.shape)}")
print("  ...")

# Pull a genuine weight matrix out of the model: the MLP up-projection.
W = model.transformer.h[0].mlp.c_fc.weight.detach()  # (4*n_embd, n_embd)
n_out, n_in = W.shape
print(f"\nanalyzing real weight: transformer.h[0].mlp.c_fc.weight  {tuple(W.shape)}")


# ---------------------------------------------------------------------------
# 2. Two inference kernels for  y = W @ x  on the SAME real weight.
# ---------------------------------------------------------------------------
def quantize_codebook(w, k=8):
    """GPTQ/AWQ-flavored: represent each weight by a k-entry codebook index.
    `codebook` is public; `q` (the indices) is the SECRET stored weight."""
    levels = torch.quantile(w.flatten(), torch.linspace(0, 1, k))
    q = (w.unsqueeze(-1) - levels).abs().argmin(dim=-1)  # (n_out, n_in) indices
    return levels, q                                     # dequant: levels[q] ~= w


class DenseLinear(torch.nn.Module):
    """Oblivious: weights enter only the matmul."""
    def __init__(self, w):
        super().__init__()
        self.weight = torch.nn.Parameter(w.clone(), requires_grad=False)

    def forward(self, x):
        return x @ self.weight.t()


class CodebookLinear(torch.nn.Module):
    """On-the-fly dequant: y = (codebook[q]) @ x. The gather codebook[q] is a
    load whose ADDRESS depends on the secret quantized weight q -> weight leak."""
    def __init__(self, codebook, q):
        super().__init__()
        self.register_buffer("codebook", codebook)
        self.register_buffer("q", q)

    def forward(self, x):
        w_hat = self.codebook[self.q]        # <-- secret-indexed gather
        return x @ w_hat.t()


codebook, q = quantize_codebook(W, k=8)
dense = DenseLinear(W).eval()
cbk = CodebookLinear(codebook, q).eval()

x = torch.randn(n_in)
# sanity: same function, different leakage (the orthogonality result, on real weights)
err = (dense(x) - cbk(x)).abs().max().item()
print(f"\nfunctional check: max|dense - codebook| = {err:.4f} "
      f"(≈quantization error; both compute the same layer)")


# ---------------------------------------------------------------------------
# 3. Lower each to an aten-level IR graph and localize the leak.
# ---------------------------------------------------------------------------
def analyze(mod, name):
    # real tracing (not fake): the module holds real weight Parameters, and the
    # toy dims make real execution instant. Captures the aten ops verbatim.
    gm = make_fx(mod)(torch.randn(n_in))
    code = gm.code
    gathers = [op for op in GATHER_OPS if op in code]
    matmuls = [op for op in MATMUL_OPS if op in code]
    leaks = bool(gathers)
    verdict = (f"LEAKS weights via {gathers}  (secret-dependent address)"
               if leaks else
               f"oblivious  (weights -> {matmuls} only)")
    print(f"\n  [{name}]  {verdict}")
    for line in code.splitlines():
        if any(op in line for op in GATHER_OPS + MATMUL_OPS):
            print(f"      {line.strip()}")
    return leaks


banner("aten-level lowering (make_fx) of each kernel on the real weight")
d_leak = analyze(dense, "dense")
c_leak = analyze(cbk, "codebook")

banner("verdict")
print(f"  dense      : {'LEAKS' if d_leak else 'oblivious'}   (expected: oblivious)")
print(f"  codebook   : {'LEAKS' if c_leak else 'oblivious'}   (expected: LEAKS)")
print("\n  -> the codebook gather is the transformer's AES S-box: a secret-")
print("     dependent load with no branch. `binsec -checkct` proves this on the")
print("     -m32 binary of nanogpt/cases.c::mm_codebook; here it is on real")
print("     nanoGPT weights, at the ML-compiler IR level.")
