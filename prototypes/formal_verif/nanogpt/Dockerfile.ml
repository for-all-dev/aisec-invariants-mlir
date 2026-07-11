# nanoGPT weight-confidentiality probe — the ML-compiler-IR view (CPU only).
#
# Kept SEPARATE from the binsec image on purpose: different toolchain
# (python+torch vs opam+binsec), and the binsec build is the long pole, so we
# don't want an ML tweak to rebuild OCaml. Everything happens IN the container:
# the nanoGPT clone is self-bootstrapped at a pinned commit and the CPU-only
# torch wheel is resolved at build time -> `docker run` needs no host clone and
# no network.
#
#   build+run:  ../dockerize.sh ml       (from prototypes/formal_verif)
#   or:         docker build -f Dockerfile.ml -t formal-verif-ml . && docker run --rm formal-verif-ml
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/nanogpt
COPY realgpt_probe.py .

# Pre-warm at build: self-bootstrap the pinned nanoGPT clone and cache the CPU
# torch wheel, so the image is self-contained and `docker run` is instant.
RUN uv run realgpt_probe.py || true

CMD ["uv", "run", "realgpt_probe.py"]
