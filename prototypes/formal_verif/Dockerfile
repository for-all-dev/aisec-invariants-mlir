# BINSEC/checkct formal-verification pipeline — reproducible image.
#
# Mirrors setup_binsec.sh (Debian/apt + opam) so kapedalex's scripts run
# verbatim inside the container. No host pollution: the 32-bit toolchain,
# opam switch, and binsec build all live in the image.
#
#   build:  docker build -t formal-verif prototypes/formal_verif
#   run:    docker run --rm formal-verif            # full reproduction
#   shell:  docker run --rm -it formal-verif bash   # poke around
#
# binsec -checkct decodes x86-32 ONLY, so every target is built -m32 -static;
# gcc-multilib supplies the 32-bit libc/crt that gcc *and* clang link against.
#
# Base is ubuntu:24.04 (not debian:bookworm-slim): the opam `z3` package builds
# z3 4.16 from source, which needs C++20 <format> — absent from bookworm's g++-12,
# present in 24.04's g++-13+. Mirrors the verified host env (setup_binsec.sh).
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    OPAMROOT=/root/.opam \
    OPAMYES=1

# System deps: opam + build toolchain, 32-bit multilib (gcc-multilib),
# clang for the differential arm, binutils (objdump/objcopy used by the
# scripts), z3 solver, and binsec's build deps (m4, pkg-config, libgmp).
RUN echo 'Acquire::Retries "8";' > /etc/apt/apt.conf.d/80retries && \
    apt-get update && \
    apt-get install -y --no-install-recommends --fix-missing \
        opam build-essential gcc-multilib clang binutils \
        m4 pkg-config libgmp-dev z3 python3 git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# opam init + OCaml switch + binsec. Sandboxing off = container-safe
# (bubblewrap can't nest in a plain container), exactly as setup_binsec.sh.
# bitwuzla is binsec's preferred CT solver but optional — never fail on it.
RUN opam init --disable-sandboxing --bare -y && \
    (opam switch create default 5.1.1 || opam switch create default) && \
    eval "$(opam env)" && \
    opam install -y binsec z3 && \
    (opam install -y bitwuzla bitwuzla-cxx || echo "bitwuzla optional: skipped") && \
    opam clean -a -c

# Put the switch bin (where `binsec` lives) on PATH so the scripts' own
# `eval "$(opam env)"` is belt-and-suspenders rather than load-bearing.
ENV PATH=/root/.opam/default/bin:$PATH

# uv for the ctverify package (layers A/B drive it). Pinned, pulled from the
# official image so no curl/pip is needed. UV_LINK_MODE=copy silences the
# hardlink warning across the /root and image layers.
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /usr/local/bin/
ENV UV_LINK_MODE=copy

# Self-contained: the prototype ships in the image, so `docker run` needs no
# mount. Bind-mount over /opt/formal_verif for live editing (see dockerize.sh).
COPY . /opt/formal_verif
WORKDIR /opt/formal_verif

# Provision the ctverify environment from its lockfile so `run.sh` (layers A/B)
# can drive the CLI offline at run time.
RUN cd ctverify && uv sync --locked

# Sanity: fail the build early if binsec or the 32-bit toolchain is broken.
# (binsec has no --version flag -- it exits 2 on unknown options; --help exits 0.)
RUN binsec --help >/dev/null && uv --version >/dev/null && \
    echo 'int main(){return 0;}' | gcc -m32 -static -x c - -o /tmp/m32ok && \
    echo 'int main(){return 0;}' | clang -m32 -static -x c - -o /tmp/m32okc && \
    rm -f /tmp/m32ok /tmp/m32okc

CMD ["bash", "run_all.sh"]
