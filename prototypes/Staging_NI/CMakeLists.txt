cmake_minimum_required(VERSION 3.20)
project(StagingNI)

find_package(MLIR REQUIRED CONFIG)
find_package(LLVM REQUIRED CONFIG)

list(APPEND CMAKE_MODULE_PATH
    ${MLIR_CMAKE_DIR}
    ${LLVM_CMAKE_DIR}
)

include(TableGen)
include(AddLLVM)
include(AddMLIR)

include_directories(
  include
  ${MLIR_INCLUDE_DIRS}
  ${LLVM_INCLUDE_DIRS}
  ${LLVM_MAIN_SRC_DIR}/../mlir/include
)

include_directories(include)

# -------------------------------------------------------
# TableGen
# -------------------------------------------------------

set(LLVM_TARGET_DEFINITIONS include/stagingNI/Passes.td)

set(LLVM_TARGET_DEFINITIONS include/stagingNI/Passes.td)

mlir_tablegen(Passes.h.inc -gen-pass-decls)
add_public_tablegen_target(MLIRPassIncGen)

# -------------------------------------------------------

add_subdirectory(lib)
add_subdirectory(tools)