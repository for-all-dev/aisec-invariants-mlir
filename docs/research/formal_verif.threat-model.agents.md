# Threat model: who can exploit a compiler-preserved weight leak

**Prototype:** [`prototypes/formal_verif/`](../../prototypes/formal_verif/) (kapedalex),
weight-confidentiality corpus [`prototypes/formal_verif/nanogpt/`](../../prototypes/formal_verif/nanogpt/).
**Status:** AI-drafted; owner (kapedalex) reviews. **Date:** 2026-07-11.

Scopes the adversary for the specific leak the `nanogpt` corpus demonstrates:
[`cases.c::mm_codebook`](../../prototypes/formal_verif/nanogpt/cases.c) — an
on-the-fly codebook dequant `codebook[q]` whose **load address depends on the
secret quantized weight `q`** — flagged by `binsec -checkct` on the `-m32`
binary and mirrored in the real-nanoGPT aten IR (`aten.index.Tensor`) by
[`realgpt_probe.py`](../../prototypes/formal_verif/nanogpt/realgpt_probe.py).
"They want the weights" is the goal; this note is about the **capabilities**
required to get them.

## What the attacker actually observes

The observable is **which address / cache line** the dequant touches
(`base + q·stride`), *not* the codebook values. The attacker infers `q` from the
access pattern and combines it with the codebook (often public, or separately
recoverable) to reconstruct the weight. Required capability is therefore
**microarchitectural address observation**, not memory disclosure — a much lower
bar than "read the victim's memory."

## Minimum viable capability bundle

Turning "address depends on weight" into "weights recovered" needs three things,
and notably **no software vulnerability in the victim** (the code is correct and
benign):

1. **Co-observation of the victim's cache/address stream** — co-resident code on
   a shared cache hierarchy, or a privileged host observing an enclave.
2. **Repeated inference invocation** (query access). The decisive enabler:
   **weights are static across inferences.** A crypto key is used once and must
   be extracted from a one-shot noisy channel; a weight is dequantized on *every*
   forward pass, so a noisy channel is averaged over unlimited triggered
   inferences until clean. Time is on the attacker's side.
3. **A cache-line-resolution timing primitive** — Flush+Reload, Prime+Probe, or a
   fine-grained timer.

Explicitly **not** required: RCE / memory corruption, the ability to read values,
chosen inputs (on-the-fly dequant touches *all* of `W`'s indices every pass
regardless), or breaking any cryptography.

## Attacker profiles

| Profile | Capabilities | Why the weights leak to them |
|---|---|---|
| **Cloud co-tenant** (canonical) | VM/container on the same multi-tenant inference host; shares the LLC. API/query access. | Prime+Probe cross-VM (no shared memory), or Flush+Reload if the model file / runtime is a deduplicated shared page (KSM). Static weights + unlimited queries beat the noise. Goal: **model theft.** |
| **Malicious host vs. a TEE** (*most on-point*) | Controls OS/hypervisor; victim runs inference in an enclave (SGX/TDX/SEV-SNP or confidential GPU) *specifically to hide weights from the operator*. | Controlled-channel + single-stepping (SGX-Step) give **4 KB-page and per-instruction** observation — near-oracle. A secret-dependent gather **directly defeats the enclave's stated guarantee.** Weight confidentiality here is an *explicit* security goal, so the formal leak is a direct break. |
| **On-device co-process** | Unprivileged code execution on a device (phone, on-prem appliance) shipping a proprietary model. | Prime+Probe from a sandboxed app; timers suffice. The formal reason "protect the model on the client" (DRM-style) is a losing battle. |
| **Physical / edge** | Physical possession; EM or DRAM-bus snooping on an embedded NPU. | Address lines are directly observable off-chip. Relevant for edge accelerators. |

The **TEE / confidential-inference** profile is why this work matters most: that
deployment *exists* to keep weights secret from an untrusted, highly capable
observer — exactly the observer a secret-dependent address cannot survive.

## Why the bar is low

- **No exploit needed** — the leak is in correct, benign inference code, not a bug.
- **Only addresses, never values** — the attacker infers `q` from *which* line is
  touched; they never read the codebook.
- **Static weights** — the same secret is re-exposed every inference, so a weak,
  noisy channel plus query access suffices via signal averaging. This is the
  single biggest difference from classical constant-time crypto, where the secret
  is ephemeral.

## Honest caveat: formal model vs. real resolution

`binsec -checkct` flags the leak at **sub-cache-line** granularity (any address
dependence) — deliberately conservative. Real exploitability depends on **stride
vs. cache-line (64 B) granularity**:

- The corpus's **toy** 8-entry `int` codebook is 32 B — it fits in *one* cache
  line, so a pure cache attack learns almost nothing at that size. The formal
  verdict is "insecure"; the real cache attacker at this size is not. (The formal
  result is still correct — it is the *conservative* bound.)
- It becomes squarely exploitable when the stride crosses lines: realistic
  **per-group codebooks**, larger dtypes, or the **embedding-row gather**
  `wte[token]` (rows span many lines) — or when the observer is the **TEE host**,
  whose 4 KB-page / single-step resolution leaks even modest strides.

This gap is exactly why the prototype's roadmap does not stop at the formal layer:

- **A (formal, software)** — `binsec -checkct`: proves *a* secret-dependent access
  exists (what this corpus does).
- **B (leakage contract)** — pin the observation granularity to something real
  (cache-line, not bit); re-express the verdict as "program ⊨ contract."
- **C (Revizor / Scam-V)** — validate that contract against the actual silicon.
- **D (dudect / ct-fuzz)** — measure whether *this* attacker, on *this* CPU, can
  actually read the channel.

binsec answers *"is there a secret-dependent access?"*; B/C/D answer *"can this
adversary exploit it here?"*

## Corpus cross-reference

| Artifact | Role in this threat model |
|---|---|
| [`nanogpt/cases.c::mm_codebook`](../../prototypes/formal_verif/nanogpt/cases.c) | the leaking kernel (secret-dependent gather) |
| [`nanogpt/cases.c::mm_dense`](../../prototypes/formal_verif/nanogpt/cases.c) | oblivious baseline (weights → arithmetic only) — the attacker gets nothing |
| [`nanogpt/w.cfg`](../../prototypes/formal_verif/nanogpt/w.cfg) | declares `secret global W` — the confidential asset |
| [`nanogpt/realgpt_probe.py`](../../prototypes/formal_verif/nanogpt/realgpt_probe.py) | same leak on real nanoGPT weights, at the ML-compiler IR level |

## Background references

- Yarom & Falkner, *Flush+Reload* (USENIX Security 2014) — cache-line-resolution channel.
- Xu, Cui, Peinado, *Controlled-Channel Attacks* (IEEE S&P 2015) — a malicious OS reading enclave access patterns.
- Van Bulck et al., *SGX-Step* (SysTEX 2017) — single-stepping enclaves for per-instruction observation.
- Yan, Fletcher, Torrellas, *Cache Telepathy* (USENIX Security 2020) — GEMM cache side channels leak DNN structure.
- Hu et al., *DeepSniffer* (ASPLOS 2020) — model extraction via architectural side channels.
