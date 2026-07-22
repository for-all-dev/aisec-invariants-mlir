"""Standalone lit configuration for the compiler confidentiality harness."""

import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile

import lit.formats


config.name = "compiler-ct-harness"
config.test_format = lit.formats.ShTest(execute_external=True)
config.suffixes = [".mlir", ".test"]
config.excludes = [
    ".git",
    ".venv",
    "build",
    "README.md",
    "requirements-test.txt",
]

_root = os.path.dirname(os.path.abspath(__file__))
config.test_source_root = _root
config.test_exec_root = os.environ.get(
    "LIT_BUILD_ROOT", os.path.join(_root, "build", "lit")
)
os.makedirs(config.test_exec_root, exist_ok=True)

_llvm_bin = os.path.abspath(
    os.environ.get("LLVM_BIN", "/opt/homebrew/opt/llvm/bin")
)
config.environment["PATH"] = _llvm_bin + os.pathsep + config.environment.get("PATH", "")


def _tool_in_llvm_bin(name):
    path = os.path.join(_llvm_bin, name)
    if os.path.isfile(path) and os.access(path, os.X_OK):
        return os.path.realpath(path)
    return None


def _required_tool(name):
    path = _tool_in_llvm_bin(name)
    if not path:
        lit_config.fatal(
            "required tool '{}' was not found in LLVM_BIN={!r}".format(name, _llvm_bin)
        )
    return path


def _quote(path):
    return shlex.quote(path)


_clang = _tool_in_llvm_bin("clang")
_llc = _tool_in_llvm_bin("llc")
_mlir_opt = _required_tool("mlir-opt")
_mlir_translate = _tool_in_llvm_bin("mlir-translate")
_filecheck = _required_tool("FileCheck")
_make = shutil.which("make")
_host_cc = shutil.which(os.environ.get("HOST_CC", "cc"))
_host_cc_command = _quote(os.path.realpath(_host_cc)) if _host_cc else "host-cc-unavailable"


def _optional_command(path, unavailable):
    return _quote(path) if path else unavailable


config.substitutions.extend(
    [
        ("%mlir-opt", _quote(_mlir_opt)),
        (
            "%mlir-translate",
            _optional_command(_mlir_translate, "mlir-translate-unavailable"),
        ),
        ("%FileCheck", _quote(_filecheck)),
        ("%clang", _optional_command(_clang, "clang-unavailable")),
        ("%llc", _optional_command(_llc, "llc-unavailable")),
        ("%python", _quote(sys.executable)),
        ("%make", _optional_command(_make, "make-unavailable")),
        ("%host-cc", _host_cc_command),
        ("%harness", _quote(_root)),
    ]
)


def _clang_targets():
    if not _clang:
        return set()
    try:
        completed = subprocess.run(
            [_clang, "--print-targets"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        lit_config.warning("could not query Clang targets: {}".format(error))
        return set()

    targets = set()
    for line in completed.stdout.splitlines():
        if " - " in line:
            targets.add(line.split(" - ", 1)[0].strip())
    return targets


_targets = _clang_targets()
if _clang:
    config.available_features.add("clang")
if _llc:
    config.available_features.add("llc")
if _mlir_translate:
    config.available_features.add("mlir-translate")
if _make:
    config.available_features.add("make")
if {"x86", "x86-64"} & _targets:
    config.available_features.add("x86-target")
if {"aarch64", "arm64"} & _targets:
    config.available_features.add("aarch64-target")
if "riscv32" in _targets:
    config.available_features.add("riscv32-target")


def _can_execute_host_program():
    if not _host_cc or platform.system() not in {"Darwin", "Linux"}:
        return False
    try:
        with tempfile.TemporaryDirectory(dir=config.test_exec_root) as probe_dir:
            executable = os.path.join(probe_dir, "host-probe")
            compiled = subprocess.run(
                [_host_cc, "-x", "c", "-", "-o", executable],
                input="int main(void) { return 0; }\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if compiled.returncode != 0:
                return False
            return subprocess.run(
                [executable], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            ).returncode == 0
    except OSError:
        return False


if _can_execute_host_program():
    config.available_features.add("host-execution")

_riscv_gcc = os.environ.get("RISCV_GCC", "")
if _riscv_gcc:
    _riscv_gcc = shutil.which(_riscv_gcc) or _riscv_gcc
else:
    for candidate in (
        "riscv32-unknown-elf-gcc",
        "riscv32-elf-gcc",
        "riscv32-gcc",
    ):
        _riscv_gcc = shutil.which(candidate)
        if _riscv_gcc:
            break

if _riscv_gcc and os.path.isfile(_riscv_gcc) and os.access(_riscv_gcc, os.X_OK):
    config.available_features.add("riscv32-gcc")
    _riscv_gcc_command = _quote(os.path.realpath(_riscv_gcc))
else:
    _riscv_gcc_command = "riscv32-gcc-unavailable"

config.substitutions.append(("%riscv32-gcc", _riscv_gcc_command))
