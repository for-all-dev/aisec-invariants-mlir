cmake_minimum_required(VERSION 3.16)
project(proofs_l2_seabmc NONE)

# L2 self-composition unit proofs over the prototypes/compiler_harness fixtures,
# discharged with SeaBMC. See README.md.
#
#   cmake -S . -B build -DSEAHORN_ROOT=/path/to/seahorn/build/run
#   ctest --test-dir build --output-on-failure
#
# Nothing is compiled here: each proof is a single C file that #includes its
# fixture, and `sea` drives clang itself. So this project is NONE-language and
# only registers tests.

enable_testing()
find_package(Python3 COMPONENTS Interpreter REQUIRED)

# --- locating SeaHorn ---------------------------------------------------------
set(SEAHORN_ROOT "$ENV{SEAHORN_ROOT}" CACHE PATH
    "SeaHorn install root -- the directory containing bin/sea")

find_program(SEA_EXE sea
  HINTS "${SEAHORN_ROOT}/bin"
  PATHS ENV PATH)

if(NOT SEA_EXE)
  message(FATAL_ERROR
    "Could not find the 'sea' driver.\n"
    "Pass -DSEAHORN_ROOT=<seahorn>/build/run (the directory holding bin/sea), "
    "or put sea on PATH.")
endif()
message(STATUS "sea: ${SEA_EXE}")

# SeaHorn links z3 and yices at run time and does not always find them itself;
# a missing libz3 shows up as an unhelpful "error while loading shared
# libraries" from seapp, mid-pipeline. Try to locate them next to the install.
set(SEA_LD_LIBRARY_PATH "" CACHE STRING
    "Extra LD_LIBRARY_PATH for sea (z3 / yices); usually <seahorn>/deps/*/lib")

if(NOT SEA_LD_LIBRARY_PATH)
  get_filename_component(_sea_bin "${SEA_EXE}" DIRECTORY)
  file(GLOB _dep_libs
       "${_sea_bin}/../../../deps/z3-*/lib"
       "${_sea_bin}/../../../deps/yices-*/lib"
       "${_sea_bin}/../../deps/z3-*/lib"
       "${_sea_bin}/../../deps/yices-*/lib")
  if(_dep_libs)
    list(JOIN _dep_libs ":" SEA_LD_LIBRARY_PATH)
    message(STATUS "sea runtime libs: ${SEA_LD_LIBRARY_PATH}")
  endif()
endif()

# --- flag sets ----------------------------------------------------------------
# Bit-precise, memory-precise operational semantics. Mirrors the configuration
# verify-c-common uses (seahorn/sea_base.yaml) minus its project specifics.
set(SEA_SUBCOMMAND "bpf" CACHE STRING "sea subcommand")
set(SEA_BASE_FLAGS
    -m64
    --inline
    --horn-unify-assumes=true
    --horn-gsa
    --bmc=opsem
    --horn-vcgen-use-ite
    --horn-vcgen-only-dataflow=true
    --horn-bmc-coi=true
    --sea-opsem-allocator=static
    --horn-explicit-sp0=false
    --horn-bv2-lambdas
    --horn-bv2-simplify=true
    --horn-bv2-extra-widemem
    CACHE STRING "Common sea flags for every proof")

# Only jobs whose observation is an ADDRESS need these. --horn-shadow-mem-load-is-def
# makes a load a MemDef so the opsem can stamp read metadata at the loaded
# address; it is gated per DSA node, so a program that never calls sea_is_read
# is unaffected. Requires a SeaHorn with the read-metadata channel (see README).
set(SEA_READ_CHANNEL_FLAGS
    --horn-bv2-tracking-mem
    --horn-shadow-mem-load-is-def
    CACHE STRING "Extra flags for proofs observing a read/address channel")

string(REPLACE ";" " " SEA_BASE_FLAGS_STR "${SEA_BASE_FLAGS}")
configure_file(verify.py.in verify.py @ONLY)
set(VERIFY_PY "${CMAKE_CURRENT_BINARY_DIR}/verify.py")

# --- registering a job --------------------------------------------------------
# Internal: register one direction.
function(_add_l2_proof NAME SOURCE EXPECT FLAGS)
  set(_abs "${CMAKE_CURRENT_SOURCE_DIR}/${SOURCE}")
  if(NOT EXISTS "${_abs}")
    message(FATAL_ERROR "add_l2_job(${NAME}): no such harness: ${_abs}")
  endif()
  add_test(NAME "${NAME}_${EXPECT}_test"
           COMMAND "${Python3_EXECUTABLE}" "${VERIFY_PY}"
                   --expect=${EXPECT} "${_abs}" ${FLAGS})
  set_tests_properties("${NAME}_${EXPECT}_test" PROPERTIES TIMEOUT 1800)
endfunction()

# add_l2_job(NAME <job> BAD <harness.c> FIXED <harness.c> [FLAGS ...])
#
# Registers a job as a CALIBRATED PAIR and refuses to register half of one.
# This is enforced here rather than left to convention because an `unsat` alone
# is indistinguishable from a proof that checks nothing: a degenerate
# observation, or one aimed at the wrong thing, also yields `unsat`. Only the
# leaky fixture's `sat` establishes that the setup can detect the leak it is
# supposed to detect, which is what makes the repaired fixture's `unsat`
# informative. Both directions therefore ship together or not at all.
#
# If a counterpart genuinely does not exist -- some fixtures are `unknown` for
# want of an L0 contract rather than repaired -- pass
# UNPAIRED_JUSTIFICATION "<why>". That still configures, but prints a warning
# at configure time, so the exception is visible and deliberate.
function(add_l2_job)
  cmake_parse_arguments(J "" "NAME;BAD;FIXED;UNPAIRED_JUSTIFICATION" "FLAGS" ${ARGN})
  if(NOT J_NAME)
    message(FATAL_ERROR "add_l2_job: NAME is required")
  endif()

  if(NOT J_BAD OR NOT J_FIXED)
    if(J_UNPAIRED_JUSTIFICATION)
      message(WARNING
        "add_l2_job(${J_NAME}): registered UNPAIRED -- "
        "${J_UNPAIRED_JUSTIFICATION}")
    else()
      message(FATAL_ERROR
        "add_l2_job(${J_NAME}): both BAD and FIXED are required.\n"
        "  A lone `unsat` is also what a degenerate observation produces, so "
        "the repaired fixture's `unsat` means nothing without the leaky "
        "fixture's `sat` to show the observation can see the leak at all.\n"
        "  If a counterpart genuinely does not exist, pass "
        "UNPAIRED_JUSTIFICATION \"<why>\".")
    endif()
  endif()

  if(J_BAD)
    _add_l2_proof("${J_NAME}_bad" "${J_BAD}" sat "${J_FLAGS}")
  endif()
  if(J_FIXED)
    _add_l2_proof("${J_NAME}_fixed" "${J_FIXED}" unsat "${J_FLAGS}")
  endif()
endfunction()

add_subdirectory(jobs/secret_embedding_index)
add_subdirectory(jobs/explicit_error_oracle)
