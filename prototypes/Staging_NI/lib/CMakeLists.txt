add_mlir_library(StagingNITransforms

  VerifyStagingNonInterference.cpp

  DEPENDS
    MLIRPassIncGen

  LINK_LIBS PUBLIC
    MLIRIR
    MLIRPass
    MLIRSupport

    MLIRFuncDialect
    MLIRAffineDialect
    MLIRSCFDialect
    MLIRMemRefDialect
    MLIRControlFlowDialect
    MLIRTensorDialect
    MLIRArithDialect

    MLIRAffineAnalysis
    MLIRAnalysis
)