{
  description = "aisec-invariants-mlir — MLIR non-interference verifier built on HEIR's secret dialect";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    parts.url = "github:hercules-ci/flake-parts";
  };

  outputs = inputs@{ parts, nixpkgs, ... }:
    parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];

      perSystem = { config, self', inputs', pkgs, system, ... }: {
        # The devshell's only job is to put bazelisk + nix on PATH. The C++
        # toolchain comes from rules_nixpkgs, via nix/cc-toolchain.nix, which
        # builds its own wrapped gcc14 derivation out of the nixpkgs pinned
        # in flake.lock. See MODULE.bazel + extension.bzl + .bazelrc for the
        # Bazel-side wiring (#22 phase 2).
        #
        # We don't export CC/CXX or forward NIX_CFLAGS_COMPILE from here —
        # rules_nixpkgs's cc toolchain is declared properly in
        # MODULE.bazel and selected via toolchain resolution, independent
        # of the shell's environment. Nix just needs to be callable.
        devShells.default = pkgs.mkShell {
          name = "aisec-invariants-mlir";

          packages = with pkgs; [
            bazelisk    # reads .bazelversion, fetches matching bazel
            uv          # ad-hoc Python scripting
            git         # Bazel's git_override fetches HEIR
          ];

          shellHook = ''
            echo "aisec-invariants-mlir devshell"
            echo "  bazelisk: $(bazelisk version 2>/dev/null | head -1 || echo ready)"
            echo "  uv:       $(uv --version)"
            echo ""
            echo "First run:"
            echo "  bazelisk build //...   # LLVM + MLIR + HEIR + aisec-opt"
            echo "  bazelisk test  //...   # lit + filecheck"
          '';
        };
      };
    };
}
