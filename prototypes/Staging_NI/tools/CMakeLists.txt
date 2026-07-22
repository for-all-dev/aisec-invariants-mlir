message(STATUS "========== ENTERING TOOLS ==========")

add_mlir_tool(staging-ni-opt
  staging-ni-opt.cpp
)

target_link_libraries(staging-ni-opt
  PRIVATE
    StagingNITransforms

    MLIRAffineDialect
    MLIRArithDialect
    MLIRTensorDialect
    MLIRSCFDialect
    MLIRFuncDialect

    MLIROptLib
)