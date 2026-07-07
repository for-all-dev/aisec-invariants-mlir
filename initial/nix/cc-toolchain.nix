# Custom C++ toolchain for phase-2 nixification (#22).
#
# rules_nixpkgs's nixpkgs_cc_configure takes a nix expression that produces
# a wrapped cc derivation. The default `(import <nixpkgs> {}).gcc14` works
# for vanilla C++ code but fails for LLVM/MLIR because LLVM's Bazel build
# does `#include <zlib.h>`, `#include <zstd.h>`, etc. directly from the
# system — and Bazel rejects absolute-path includes unless the paths are
# declared in the toolchain's builtin_include_directories.
#
# Fix: wrap gcc14 with wrapCCWith and append -isystem/-L lines for the
# libraries LLVM expects. rules_nixpkgs reads these out of
# `nix-support/cc-cflags` and `nix-support/cc-ldflags` and surfaces them
# to Bazel as part of the toolchain's include/library dirs, so Bazel's
# absolute-path check passes.
let
  pkgs = import <nixpkgs> { };

  extraLibs = with pkgs; [
    zlib
    zstd
    libxml2
    ncurses
  ];

  # Join each lib's `.dev` output and `$out/lib` into flag fragments.
  extraCflags = builtins.concatStringsSep " " (map
    (lib: "-isystem ${lib.dev}/include")
    extraLibs);

  extraLdflags = builtins.concatStringsSep " " (map
    (lib: "-L${lib}/lib -rpath ${lib}/lib")
    extraLibs);
in
pkgs.wrapCCWith {
  cc = pkgs.gcc14.cc;
  bintools = pkgs.gcc14.bintools;
  extraBuildCommands = ''
    echo "${extraCflags}" >> $out/nix-support/cc-cflags
    echo "${extraLdflags}" >> $out/nix-support/cc-ldflags
    # Embed an rpath pointing at gcc14's libstdc++ so Bazel-built binaries
    # (FileCheck, llvm-min-tblgen, aisec-opt, etc.) can find libstdc++.so.6
    # at runtime. Without this, tests fail with
    # "libstdc++.so.6: cannot open shared object file" when Bazel executes
    # them in a sandbox with no LD_LIBRARY_PATH and no system libstdc++.
    echo "-rpath ${pkgs.gcc14.cc.lib}/lib" >> $out/nix-support/cc-ldflags
  '';
}
