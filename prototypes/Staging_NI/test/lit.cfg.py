"""Lit configuration for the Staging_NI test suite.

Run with:
    uvx lit test/ -v
(or any `lit` on PATH) from the Staging_NI project root, after building
`staging-ni-opt` (`cmake -B build && ninja -C build staging-ni-opt`).
"""

import os
import shutil

import lit.formats

config.name = "Staging_NI"
config.test_format = lit.formats.ShTest(execute_external=False)
config.suffixes = [".mlir"]
config.test_source_root = os.path.dirname(__file__)

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_staging_ni_opt_dir = os.path.join(_project_root, "build", "tools")

# FileCheck ships as FileCheck-<ver> on Debian/Ubuntu (llvm-18-tools); fall
# back to a bare "FileCheck" for other layouts.
_filecheck = shutil.which("FileCheck-18") or shutil.which("FileCheck")
_filecheck_dir = os.path.dirname(_filecheck) if _filecheck else None

path_dirs = [d for d in (_staging_ni_opt_dir, _filecheck_dir) if d and os.path.isdir(d)]
config.environment["PATH"] = os.pathsep.join([*path_dirs, config.environment.get("PATH", "")])

config.substitutions.append(("%staging-ni-opt", "staging-ni-opt"))
config.substitutions.append(("%FileCheck", os.path.basename(_filecheck) if _filecheck else "FileCheck"))
