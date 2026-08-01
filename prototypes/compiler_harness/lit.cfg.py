"""Standalone lit configuration for the compiler confidentiality harness."""

import hashlib
import json
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
    "examples",
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


def _configured_executable(env_name, fallback=""):
    configured = os.environ.get(env_name, "")
    candidate = configured or fallback
    if not candidate:
        return None
    resolved = shutil.which(candidate) or os.path.abspath(candidate)
    if os.path.isfile(resolved) and os.access(resolved, os.X_OK):
        return os.path.realpath(resolved)
    return None


_clang = _tool_in_llvm_bin("clang")
_llc = _tool_in_llvm_bin("llc")
_opt = _tool_in_llvm_bin("opt")
_llvm_as = _tool_in_llvm_bin("llvm-as")
_llvm_dis = _tool_in_llvm_bin("llvm-dis")
_llvm_config = _tool_in_llvm_bin("llvm-config")
_mlir_opt = _required_tool("mlir-opt")
_mlir_translate = _tool_in_llvm_bin("mlir-translate")
_filecheck = _required_tool("FileCheck")
_make = shutil.which("make")
_host_cc = shutil.which(os.environ.get("HOST_CC", "cc"))
_host_cc_command = _quote(os.path.realpath(_host_cc)) if _host_cc else "host-cc-unavailable"


def _xcrun_tool(name):
    xcrun = shutil.which("xcrun")
    if not xcrun:
        return None
    try:
        path = subprocess.run(
            [xcrun, "--find", name],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if path and os.path.isfile(path) and os.access(path, os.X_OK):
        return os.path.realpath(path)
    return None


def _coverage_probe(compiler, llvm_cov, llvm_profdata):
    if not compiler or not llvm_cov or not llvm_profdata:
        return False
    if any(
        not os.path.isfile(path) or not os.access(path, os.X_OK)
        for path in (compiler, llvm_cov, llvm_profdata)
    ):
        return False
    try:
        with tempfile.TemporaryDirectory(dir=config.test_exec_root) as probe_dir:
            executable = os.path.join(probe_dir, "coverage-probe")
            raw_profile = os.path.join(probe_dir, "coverage.profraw")
            indexed_profile = os.path.join(probe_dir, "coverage.profdata")
            compiled = subprocess.run(
                [
                    compiler,
                    "-x",
                    "c",
                    "-",
                    "-fprofile-instr-generate",
                    "-fcoverage-mapping",
                    "-o",
                    executable,
                ],
                input="int main(void) { return 0; }\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if compiled.returncode != 0:
                return False
            environment = dict(config.environment)
            environment["LLVM_PROFILE_FILE"] = raw_profile
            if subprocess.run(
                [executable],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode != 0:
                return False
            if subprocess.run(
                [
                    llvm_profdata,
                    "merge",
                    "-sparse",
                    raw_profile,
                    "-o",
                    indexed_profile,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode != 0:
                return False
            return (
                subprocess.run(
                    [
                        llvm_cov,
                        "report",
                        executable,
                        "-instr-profile={}".format(indexed_profile),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ).returncode
                == 0
            )
    except OSError:
        return False


def _select_coverage_triplet():
    configured_compiler = _configured_executable("HOST_COVERAGE_CC")
    compilers = [configured_compiler] if configured_compiler else [_host_cc, _clang]
    configured_cov = _configured_executable("HOST_LLVM_COV")
    configured_profdata = _configured_executable("HOST_LLVM_PROFDATA")

    seen = set()
    for compiler in compilers:
        if not compiler:
            continue
        compiler = os.path.realpath(compiler)
        adjacent = os.path.dirname(compiler)
        tool_pairs = (
            (
                os.path.join(adjacent, "llvm-cov"),
                os.path.join(adjacent, "llvm-profdata"),
            ),
            (_xcrun_tool("llvm-cov"), _xcrun_tool("llvm-profdata")),
            (_tool_in_llvm_bin("llvm-cov"), _tool_in_llvm_bin("llvm-profdata")),
            (shutil.which("llvm-cov"), shutil.which("llvm-profdata")),
        )
        for llvm_cov, llvm_profdata in tool_pairs:
            llvm_cov = configured_cov or llvm_cov
            llvm_profdata = configured_profdata or llvm_profdata
            if not llvm_cov or not llvm_profdata:
                continue
            triplet = (
                compiler,
                os.path.realpath(llvm_cov),
                os.path.realpath(llvm_profdata),
            )
            if triplet in seen:
                continue
            seen.add(triplet)
            if _coverage_probe(*triplet):
                return triplet
    return (None, None, None)


_coverage_cc, _host_llvm_cov, _host_llvm_profdata = _select_coverage_triplet()


def _file_sha256(path):
    value = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _matches_candidate_producer_toolchain():
    tools = {
        "mlir-translate": _mlir_translate,
        "llvm-as": _llvm_as,
        "llvm-dis": _llvm_dis,
        "llvm-config": _llvm_config,
    }
    if any(path is None for path in tools.values()):
        return False

    artifacts_root = os.path.join(_root, "artifacts")
    try:
        identities = sorted(
            os.path.join(artifacts_root, name, "artifact.json")
            for name in os.listdir(artifacts_root)
            if os.path.isfile(os.path.join(artifacts_root, name, "artifact.json"))
        )
        if not identities:
            return False
        expected = None
        for identity_path in identities:
            with open(identity_path, encoding="utf-8") as stream:
                identity = json.load(stream)
            hashes = identity.get("producer", {}).get("tool_sha256")
            if not isinstance(hashes, dict) or set(hashes) != set(tools):
                return False
            if expected is None:
                expected = hashes
            elif hashes != expected:
                return False
        return all(_file_sha256(path) == expected[name] for name, path in tools.items())
    except (OSError, ValueError, TypeError):
        return False


_sps_scan = _configured_executable("SPS_SCAN")
_sps_verifier = _configured_executable("SPS_VERIFIER")
_sps_teaching_materialized = os.environ.get("SPS_TEACHING_MATERIALIZED", "")
if _sps_teaching_materialized:
    _sps_teaching_materialized = os.path.abspath(_sps_teaching_materialized)
_sps_error_materialized = os.environ.get("SPS_ERROR_MATERIALIZED", "")
if _sps_error_materialized:
    _sps_error_materialized = os.path.abspath(_sps_error_materialized)


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
        ("%opt", _optional_command(_opt, "opt-unavailable")),
        ("%llvm-as", _optional_command(_llvm_as, "llvm-as-unavailable")),
        ("%llvm-dis", _optional_command(_llvm_dis, "llvm-dis-unavailable")),
        ("%sps-scan", _optional_command(_sps_scan, "sps-scan-unavailable")),
        (
            "%sps-verifier",
            _optional_command(_sps_verifier, "sps-verifier-unavailable"),
        ),
        (
            "%sps-teaching-materialized",
            _quote(_sps_teaching_materialized)
            if _sps_teaching_materialized
            else "sps-teaching-materialized-unavailable",
        ),
        (
            "%sps-error-materialized",
            _quote(_sps_error_materialized)
            if _sps_error_materialized
            else "sps-error-materialized-unavailable",
        ),
        ("%python", _quote(sys.executable)),
        ("%make", _optional_command(_make, "make-unavailable")),
        ("%host-cc", _host_cc_command),
        (
            "%host-coverage-cc",
            _optional_command(_coverage_cc, "host-coverage-cc-unavailable"),
        ),
        (
            "%host-llvm-cov",
            _optional_command(_host_llvm_cov, "host-llvm-cov-unavailable"),
        ),
        (
            "%host-llvm-profdata",
            _optional_command(_host_llvm_profdata, "host-llvm-profdata-unavailable"),
        ),
        ("%llvm_bin", _quote(_llvm_bin)),
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
if _opt:
    config.available_features.add("opt")
if _llvm_as:
    config.available_features.add("llvm-as")
if _llvm_dis:
    config.available_features.add("llvm-dis")
if _llvm_config:
    config.available_features.add("llvm-config")
if _mlir_translate:
    config.available_features.add("mlir-translate")
if _make:
    config.available_features.add("make")
if _matches_candidate_producer_toolchain():
    config.available_features.add("candidate-producer-toolchain")
if _sps_scan:
    config.available_features.add("sps-scan-unary")
if _sps_verifier:
    config.available_features.add("sps-verifier")
if _sps_teaching_materialized and os.path.isdir(_sps_teaching_materialized):
    config.available_features.add("sps-teaching-materialized")
if _sps_error_materialized and os.path.isdir(_sps_error_materialized):
    config.available_features.add("sps-error-materialized")

if _llvm_config:
    try:
        _version = subprocess.run(
            [_llvm_config, "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ).stdout.strip()
        if _version:
            config.available_features.add("llvm-{}".format(_version))
    except (OSError, subprocess.CalledProcessError) as error:
        lit_config.warning("could not query LLVM version: {}".format(error))
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


if _coverage_cc and _host_llvm_cov and _host_llvm_profdata:
    config.available_features.add("host-coverage")

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
