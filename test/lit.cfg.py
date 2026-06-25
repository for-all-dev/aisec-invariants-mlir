"""Lit configuration for the aisec-invariants-mlir test suite.

Run with:
    bazelisk test //test/...
"""

import os
import lit.formats

config.name = "aisec-invariants-mlir"
config.test_format = lit.formats.ShTest(execute_external=False)
config.suffixes = [".mlir"]
config.test_source_root = os.path.dirname(__file__)

# Locate the aisec-opt binary in Bazel runfiles. The llvm:lit_test rule puts
# the test source at <runfiles>/_main/test/..., and //tools/aisec-opt:aisec-opt
# at <runfiles>/_main/tools/aisec-opt/aisec-opt. Walking up from this file
# gets us the workspace root inside runfiles.
_workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_aisec_opt = os.path.join(_workspace_root, "tools", "aisec-opt", "aisec-opt")
if os.path.exists(_aisec_opt):
    config.environment["PATH"] = (
        os.path.dirname(_aisec_opt)
        + os.pathsep
        + config.environment.get("PATH", "")
    )

# FileCheck comes from the llvm-project runfiles alongside our tests.
_filecheck = os.path.join(
    _workspace_root, "..", "+_repo_rules+llvm-project", "llvm", "FileCheck"
)
if os.path.exists(_filecheck):
    config.environment["PATH"] = (
        os.path.dirname(_filecheck)
        + os.pathsep
        + config.environment["PATH"]
    )

config.substitutions.append(("%aisec-opt", "aisec-opt"))
