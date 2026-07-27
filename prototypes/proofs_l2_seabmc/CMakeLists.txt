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

# --- registering a proof ------------------------------------------------------
# add_l2_proof(NAME <test> SOURCE <harness.c> EXPECT sat|unsat [FLAGS ...])
#
# EXPECT is part of the specification, not a convenience: a job is only
# meaningful as a CALIBRATED PAIR -- the leaky fixture must yield sat and the
# repaired one unsat. A single verdict proves nothing, because a degenerate
# observation also produces unsat.
function(add_l2_proof)
  cmake_parse_arguments(P "" "NAME;SOURCE;EXPECT" "FLAGS" ${ARGN})
  if(NOT P_NAME OR NOT P_SOURCE OR NOT P_EXPECT)
    message(FATAL_ERROR "add_l2_proof: NAME, SOURCE and EXPECT are required")
  endif()
  add_test(NAME "${P_NAME}_${P_EXPECT}_test"
           COMMAND "${Python3_EXECUTABLE}" "${VERIFY_PY}"
                   --expect=${P_EXPECT}
                   "${CMAKE_CURRENT_SOURCE_DIR}/${P_SOURCE}"
                   ${P_FLAGS})
  set_tests_properties("${P_NAME}_${P_EXPECT}_test" PROPERTIES TIMEOUT 1800)
endfunction()

add_subdirectory(jobs/secret_embedding_index)
add_subdirectory(jobs/explicit_error_oracle)
