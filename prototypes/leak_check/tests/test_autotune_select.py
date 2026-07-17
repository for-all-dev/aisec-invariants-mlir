"""Calibration of the autotune-selection DETECTOR (PRINCIPLES 5: a tool must be
trusted only after its own logic is checked). `probe_autotune_select.py` needs a
torch build and minutes of compilation; this pins its two parsers against
recorded log fragments so the regressions that produced one INCONCLUSIVE run
cannot come back silently.

    uv run pytest tests/test_autotune_select.py -q

The two bugs guarded here (see leak_check.autotune-select.agents.md 5):
  * the decision parser exiting the AUTOTUNE block at the strides:/dtypes: lines
    that sit before the candidates -> every winner read as None, making
    "decisions identical" vacuously true;
  * the codegen channel keeping select_algorithm noise / bare object addresses,
    so the same-class control spuriously "differs".
"""

import probe_autotune_select as P

# A real AUTOTUNE block: header, then strides:/dtypes: lines BEFORE the
# candidates (the shape that broke the first parser), then the winner stat.
AUTOTUNE_BLOCK = """\
AUTOTUNE packed_linear(512x512, 1459233x1, 512x512)
strides: [512, 1], [1, 0], [1, 512]
dtypes: torch.float32, torch.float32, torch.float32
  cpp_CppMicroGemmFP32Vec_0 2.2311 ms 100.0%
  _mkl_linear 2.8246 ms 79.0%
SingleProcess AUTOTUNE benchmarking takes 0.35 seconds and 1.87 seconds precompiling for 2 choices
{"num_choices": 2, "num_triton_choices": 0, "best_kernel": "cpp_CppMicroGemmFP32Vec_0", "best_time": 2.23}
"""


def test_parser_reads_winner_past_strides_dtypes():
    winner, cands = P.parse_decision(AUTOTUNE_BLOCK)
    # The regression read winner=None, candidates=[] here.
    assert winner == "cpp_CppMicroGemmFP32Vec"
    assert [f for f, _ in cands] == ["cpp_CppMicroGemmFP32Vec", "_mkl_linear"]


def test_parser_none_when_no_autotune():
    winner, cands = P.parse_decision(
        "some unrelated log line\nMax autotune selects from 1 choices."
    )
    assert winner is None and cands == []


def _output_code_line(body):
    # Mimic a TORCH_LOGS output_code line: the [__output_code] tag is what the
    # codegen channel keys on to exclude select_algorithm noise.
    return f"V0717 11:00:00.000000 123 torch/_inductor/x.py:1] [0/0] [__output_code] {body}"


def test_codegen_ignores_object_addresses_and_autotune_noise():
    # Two "dumps" identical except for a bare id() pointer (no 0x prefix) and the
    # interleaved autotune benchmark noise -- the same-class control must see them
    # as equal.
    common = [
        _output_code_line("def call(args):"),
        _output_code_line("buf0 = empty_strided_cpu((512, 512), (512, 1))"),
    ]
    dump_a = "\n".join(
        [_output_code_line("_frozen_param1 = None  # torch.float32 (512, 512) 7f0cbbfc96d0")]
        + common
        + ["  cpp_CppMicroGemmFP32Vec_0 2.2311 ms 100.0% "]
    )
    dump_b = "\n".join(
        [_output_code_line("_frozen_param1 = None  # torch.float32 (512, 512) 7f7ea9576750")]
        + common
        + ["  cpp_CppMicroGemmFP32Vec_0 2.0007 ms 100.0% "]
    )
    assert P.normalize_codegen(dump_a) == P.normalize_codegen(dump_b)


def test_codegen_still_distinguishes_real_difference():
    # A genuine codegen difference (different kernel body) must NOT be normalized away.
    a = _output_code_line("buf0 = extern_kernels.mm(arg0, arg1, out=buf0)")
    b = _output_code_line("buf0 = cpp_micro_gemm(arg0, arg1, out=buf0)")
    assert P.normalize_codegen(a) != P.normalize_codegen(b)


def test_fingerprint_excludes_noisy_timings():
    # Same winner + candidate set but different (jittering) percentages must share
    # a fingerprint -- the decision is the channel, the timing is not.
    r1 = {"winner": "cpp", "candidates": [("cpp", 100.0), ("mkl", 71.9)]}
    r2 = {"winner": "cpp", "candidates": [("cpp", 100.0), ("mkl", 92.1)]}
    assert P.fingerprint(r1) == P.fingerprint(r2)
