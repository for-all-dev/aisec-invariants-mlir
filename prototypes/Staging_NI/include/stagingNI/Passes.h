#ifndef STAGINGNI_PASSES_H
#define STAGINGNI_PASSES_H

#include "mlir/Pass/Pass.h"

namespace mlir {
namespace stagingni {

std::unique_ptr<Pass> createVerifyStagingNonInterferencePass();

void registerPasses();

} // namespace stagingni
} // namespace mlir

#define GEN_PASS_DECL
//#include "stagingNI/Passes.h.inc"

#endif