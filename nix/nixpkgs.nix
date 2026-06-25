# Nixpkgs pin for rules_nixpkgs (phase 2 of the nixification, #22).
#
# We read the pinned rev/narHash directly out of flake.lock so the devshell
# and the Bazel-side toolchain share a single source of truth. Bumping
# nixpkgs is a `nix flake update` — rules_nixpkgs picks up the new pin
# automatically on the next build.
let
  lock = builtins.fromJSON (builtins.readFile ../flake.lock);
  node = lock.nodes.nixpkgs.locked;
  src = builtins.fetchTree {
    type = "github";
    owner = node.owner;
    repo = node.repo;
    rev = node.rev;
    narHash = node.narHash;
  };
in
# Return the function that nixpkgs's default.nix exports, NOT a
# pre-evaluated pkgs set. rules_nixpkgs's cc.nix does
# `import <nixpkgs> { config = {}; }` and needs to supply its own args.
import src
