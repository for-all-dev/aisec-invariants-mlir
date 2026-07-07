"""Module extension that wires a nix-provided C++ toolchain into Bazel.

Phase 2 of the nixification (#22). Replaces the env-var forwarding hack in
.bazelrc — instead of letting the devshell's CC/CXX/NIX_CFLAGS_COMPILE leak
into Bazel actions, rules_nixpkgs actually configures a proper Bazel C++
toolchain whose tools come from a pinned nix derivation. Bazel then resolves
it via toolchain resolution like any other registered toolchain.

Uses `gcc14` from the nixpkgs pinned in flake.lock (via nixpkgs.nix). gcc14
is required because gcc15's libstdc++ breaks HEIR's pinned LLVM with a
strict ranges-concept check in GenericDomTreeConstruction.h — see #10.
"""

load("@rules_nixpkgs_cc//:cc.bzl", "nixpkgs_cc_configure")

def _cc_configure_impl(_module_ctx):
    nixpkgs_cc_configure(
        name = "nixpkgs_config_cc",
        # Use a custom wrapped gcc14 that bakes in zlib/zstd/libxml2/ncurses
        # headers and libraries so LLVM's Support/CRC.cpp and friends can
        # `#include <zlib.h>` without tripping Bazel's absolute-path-include
        # check. See cc-toolchain.nix for details.
        nix_file = "//nix:cc-toolchain.nix",
        nix_file_deps = ["//nix:nixpkgs.nix", "//:flake.lock"],
        repository = "@nixpkgs",
        register = False,
        # HEIR's LLVM uses <string_view>, <concepts>, etc. — c++20 is also
        # what the top-level .bazelrc sets via --cxxopt, but the toolchain
        # has its own baked-in default (c++0x/c++11) that takes precedence
        # during toolchain construction.
        cc_lang = "c++",
        cc_std = "c++20",
    )

cc_configure = module_extension(
    implementation = _cc_configure_impl,
)
