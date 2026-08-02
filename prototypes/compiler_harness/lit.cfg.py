"""Standalone lit configuration for the compiler confidentiality harness."""

import hashlib
import json
import os
import platform
import re
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
config.test_exec_root = os.path.abspath(
    os.environ.get("LIT_BUILD_ROOT", os.path.join(_root, "build", "lit"))
)
os.makedirs(config.test_exec_root, exist_ok=True)
config.environment["LIT_BUILD_ROOT"] = config.test_exec_root

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
_llvm_objdump = _tool_in_llvm_bin("llvm-objdump")
_llvm_readobj = _tool_in_llvm_bin("llvm-readobj")
_mlir_opt = _required_tool("mlir-opt")
_mlir_translate = _tool_in_llvm_bin("mlir-translate")
_filecheck = _required_tool("FileCheck")
_make = shutil.which("make")
_host_cc = shutil.which(os.environ.get("HOST_CC", "cc"))
_host_cc_command = _quote(os.path.realpath(_host_cc)) if _host_cc else "host-cc-unavailable"
_z3 = _configured_executable("Z3", "z3")
if _z3:
    config.environment["Z3"] = _z3
    config.environment["PATH"] = (
        os.path.dirname(_z3)
        + os.pathsep
        + config.environment.get("PATH", "")
    )


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

    fixtures_root = os.path.join(_root, "fixtures")
    try:
        identities = []
        for directory, _, filenames in os.walk(fixtures_root):
            if os.path.basename(directory) == "candidate" and "artifact.json" in filenames:
                identities.append(os.path.join(directory, "artifact.json"))
        identities.sort()
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


def _probe_output(command):
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError:
        return None
    return completed.stdout if completed.returncode == 0 else None


def _probe_sps_nfv2_intrinsic():
    """Reject stock LLVM's ordinary-external-call interpretation of the name."""

    if not _llvm_as or not _llvm_dis or not _opt:
        return False
    source = """\
declare void @llvm.sps.release(...)
define void @probe(i32 %payload) {
entry:
  call void (...) @llvm.sps.release(i32 %payload)
  call void (...) @llvm.sps.release(i32 %payload)
  ret void
}
"""
    try:
        with tempfile.TemporaryDirectory(dir=config.test_exec_root) as probe_dir:
            source_path = os.path.join(probe_dir, "nfv2-probe.ll")
            bitcode_path = os.path.join(probe_dir, "nfv2-probe.bc")
            with open(source_path, "w", encoding="utf-8") as stream:
                stream.write(source)
            if _probe_output([_llvm_as, source_path, "-o", bitcode_path]) is None:
                return False
            rendered = _probe_output([_llvm_dis, bitcode_path, "-o", "-"])
            if rendered is None:
                return False
            required_attributes = ("memory(none)", "noduplicate", "nomerge")
            if any(attribute not in rendered for attribute in required_attributes):
                return False
            if "speculatable" in rendered:
                return False
            marker = re.compile(
                r"\bcall\s+void\s+\(\.\.\.\)\s+@llvm\.sps\.release\("
            )
            pipelines = (
                "default<O2>",
                "sps-final-weaken-v2,function(dce),globaldce",
            )
            for pipeline in pipelines:
                optimized = _probe_output(
                    [_opt, f"-passes={pipeline}", "-S", bitcode_path, "-o", "-"]
                )
                if optimized is None or len(marker.findall(optimized)) != 2:
                    return False
            return True
    except OSError:
        return False


def _probe_sps_nfv2_codegen(intrinsic_available):
    if (
        not intrinsic_available
        or not _llc
        or not _llvm_as
        or not _llvm_objdump
        or not _llvm_readobj
    ):
        return False
    source = """\
declare void @llvm.sps.release(...)
define i32 @nfv2_marked(i32 %payload) {
entry:
  call void (...) @llvm.sps.release(i32 %payload)
  ret i32 %payload
}
define i32 @nfv2_control(i32 %payload) {
entry:
  ret i32 %payload
}
"""
    try:
        with tempfile.TemporaryDirectory(dir=config.test_exec_root) as probe_dir:
            source_path = os.path.join(probe_dir, "nfv2-codegen-probe.ll")
            bitcode_path = os.path.join(probe_dir, "nfv2-codegen-probe.bc")
            object_path = os.path.join(probe_dir, "nfv2-codegen-probe.o")
            with open(source_path, "w", encoding="utf-8") as stream:
                stream.write(source)
            if _probe_output([_llvm_as, source_path, "-o", bitcode_path]) is None:
                return False
            common = [_llc, "-mtriple=x86_64-unknown-linux-gnu", "-O2"]
            for boundary in ("finalize-isel", "prologepilog"):
                machine_ir = _probe_output(
                    [*common, f"-stop-after={boundary}", bitcode_path, "-o", "-"]
                )
                if machine_ir is None or machine_ir.count("SPS_RELEASE") != 1:
                    return False
            assembly = _probe_output([*common, "-filetype=asm", bitcode_path, "-o", "-"])
            if assembly is None:
                return False
            if "llvm.sps.release" in assembly or "SPS_RELEASE" in assembly:
                return False
            if _probe_output(
                [*common, "-filetype=obj", bitcode_path, "-o", object_path]
            ) is None:
                return False
            object_inventory = _probe_output(
                [_llvm_readobj, "--symbols", "--relocations", object_path]
            )
            disassembly = _probe_output([_llvm_objdump, "-d", object_path])
            if object_inventory is None or disassembly is None:
                return False
            if "llvm.sps.release" in object_inventory or "SPS_RELEASE" in object_inventory:
                return False
            return "<nfv2_marked>:" in disassembly and "<nfv2_control>:" in disassembly
    except OSError:
        return False


_has_sps_nfv2_intrinsic = _probe_sps_nfv2_intrinsic()
_has_sps_nfv2_codegen = _probe_sps_nfv2_codegen(_has_sps_nfv2_intrinsic)


def _probe_clang_tooling():
    if not _llvm_config:
        return False
    includedir = _probe_output([_llvm_config, "--includedir"])
    libdir = _probe_output([_llvm_config, "--libdir"])
    if not includedir or not libdir:
        return False
    header = os.path.join(includedir.strip(), "clang", "Tooling", "Tooling.h")
    library_root = libdir.strip()
    libraries = (
        "libclang-cpp.dylib",
        "libclang-cpp.so",
        "libclang-cpp.dll",
    )
    return os.path.isfile(header) and any(
        os.path.isfile(os.path.join(library_root, name)) for name in libraries
    )


_has_clang_tooling = _probe_clang_tooling()


_sps_scan = _configured_executable("SPS_SCAN")
_sps_verifier = _configured_executable("SPS_VERIFIER")
_sps_rev41_materialized = os.environ.get("SPS_REV41_MATERIALIZED", "")
if _sps_rev41_materialized:
    _sps_rev41_materialized = os.path.abspath(_sps_rev41_materialized)
_sps_source_annotations_root = os.environ.get("SPS_SOURCE_ANNOTATIONS_ROOT", "")
if _sps_source_annotations_root:
    _sps_source_annotations_root = os.path.abspath(_sps_source_annotations_root)
    if not os.path.isdir(_sps_source_annotations_root):
        lit_config.fatal(
            "SPS_SOURCE_ANNOTATIONS_ROOT is configured but is not a directory: "
            "{!r}".format(_sps_source_annotations_root)
        )
    config.environment["SPS_SOURCE_ANNOTATIONS_ROOT"] = (
        _sps_source_annotations_root
    )
_sps_reference_root = os.environ.get("SPS_REFERENCE_ROOT", "")
if _sps_reference_root:
    _sps_reference_root = os.path.abspath(_sps_reference_root)
    if not os.path.isdir(_sps_reference_root):
        lit_config.fatal(
            "SPS_REFERENCE_ROOT is configured but is not a directory: {!r}".format(
                _sps_reference_root
            )
        )
    config.environment["SPS_REFERENCE_ROOT"] = _sps_reference_root


def _probe_sps_rev41_verifier(path):
    """Enable V2 tests only for a verifier that advertises the exact contract."""

    if not path:
        return False
    output = _probe_output([path, "capabilities", "--format=json"])
    if output is None:
        return False
    try:
        value = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return False
    required_features = {
        "accepted-bad-replay-v2",
        "complete-observation-latency-schedule-v2",
        "diagnostic-health-v2",
        "module-requiredness-v2",
        "sps-run-report-v2",
    }
    return (
        isinstance(value, dict)
        and value.get("formatId") == "SPS-Exact-Verifier-Capabilities-v2"
        and value.get("specRevision") == "4.1"
        and value.get("profileId") == "SPS-LLVM-NF-v2"
        and isinstance(value.get("features"), list)
        and required_features <= set(value["features"])
    )


_has_sps_rev41_verifier = _probe_sps_rev41_verifier(_sps_verifier)


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
        (
            "%llvm-objdump",
            _optional_command(_llvm_objdump, "llvm-objdump-unavailable"),
        ),
        (
            "%llvm-readobj",
            _optional_command(_llvm_readobj, "llvm-readobj-unavailable"),
        ),
        ("%sps-scan", _optional_command(_sps_scan, "sps-scan-unavailable")),
        (
            "%sps-verifier",
            _optional_command(_sps_verifier, "sps-verifier-unavailable"),
        ),
        (
            "%sps-rev41-materialized",
            _quote(_sps_rev41_materialized)
            if _sps_rev41_materialized
            else "sps-rev41-materialized-unavailable",
        ),
        (
            "%sps-source-annotations-root",
            _quote(_sps_source_annotations_root)
            if _sps_source_annotations_root
            else "sps-source-annotations-root-unavailable",
        ),
        (
            "%sps-reference-root",
            _quote(_sps_reference_root)
            if _sps_reference_root
            else "sps-reference-root-unavailable",
        ),
        ("%z3", _optional_command(_z3, "z3-unavailable")),
        # -B is load-bearing, not hygiene. Several suites execute the vendored
        # SPS reference closure in place, and sync_sps_reference.py refuses any
        # __pycache__ inside that closure. Without -B the first in-place run
        # writes caches that make every later --check fail, and __pycache__/ is
        # gitignored so the poisoned tree still looks clean. Do not remove.
        ("%python", _quote(sys.executable) + " -B"),
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
        ("%fixtures", _quote(os.path.join(_root, "fixtures"))),
        ("%harness", _quote(_root)),
        (
            "%checkpoint-runner",
            "{} {}".format(
                _quote(sys.executable),
                _quote(os.path.join(_root, "tools", "checkpoint_runner.py")),
            ),
        ),
        (
            "%sps-boundary",
            "{} {} --clang {} --llvm-config {}".format(
                _quote(sys.executable),
                _quote(os.path.join(_root, "tools", "sps_boundary.py")),
                _optional_command(_clang, "clang-unavailable"),
                _optional_command(_llvm_config, "llvm-config-unavailable"),
            ),
        ),
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
if _has_clang_tooling:
    config.available_features.add("clang-tooling")
if _llvm_objdump:
    config.available_features.add("llvm-objdump")
if _llvm_readobj:
    config.available_features.add("llvm-readobj")
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
if _has_sps_rev41_verifier:
    config.available_features.add("sps-rev4.1-verifier")
if _sps_rev41_materialized and os.path.isdir(_sps_rev41_materialized):
    config.available_features.add("sps-rev4.1-materialized")
if _sps_source_annotations_root and os.path.isdir(_sps_source_annotations_root):
    config.available_features.add("sps-source-annotations-upstream")
if _sps_reference_root:
    config.available_features.add("sps-reference-upstream")
if _z3:
    config.available_features.add("z3")
if _has_sps_nfv2_intrinsic:
    config.available_features.add("sps-nfv2-intrinsic")
if _has_sps_nfv2_codegen:
    config.available_features.add("sps-nfv2-codegen")

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
