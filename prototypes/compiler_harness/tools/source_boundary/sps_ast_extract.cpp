// Extract SPS locator annotations through Clang's typed AST.
//
// This is deliberately a LibTooling consumer.  Source text, clang AST dumps,
// and LLVM annotation metadata are not authoring interfaces.

#include "clang/AST/ASTConsumer.h"
#include "clang/AST/Attr.h"
#include "clang/AST/DeclCXX.h"
#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/FrontendActions.h"
#include "clang/Index/USRGeneration.h"
#include "clang/Tooling/CommonOptionsParser.h"
#include "clang/Tooling/Tooling.h"
#include "llvm/ADT/SmallString.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/raw_ostream.h"

#include <algorithm>
#include <set>
#include <string>
#include <vector>

using namespace clang;
using namespace clang::tooling;

namespace {

llvm::cl::OptionCategory Category("SPS source annotation extractor");

std::vector<std::string> annotations(const Decl *declaration) {
  std::vector<std::string> values;
  for (const auto *attribute : declaration->specific_attrs<AnnotateAttr>())
    values.push_back(attribute->getAnnotation().str());
  std::sort(values.begin(), values.end());
  return values;
}

std::string declarationIdentity(const FunctionDecl *declaration) {
  llvm::SmallString<128> identity;
  if (index::generateUSRForDecl(declaration->getCanonicalDecl(), identity))
    return {};
  return identity.str().str();
}

llvm::json::Array strings(const std::vector<std::string> &values) {
  llvm::json::Array result;
  for (const auto &value : values)
    result.push_back(value);
  return result;
}

class CallVisitor : public RecursiveASTVisitor<CallVisitor> {
public:
  explicit CallVisitor(ASTContext &context) : context(context) {}

  bool VisitCallExpr(CallExpr *call) {
    llvm::json::Object value;
    if (const FunctionDecl *callee = call->getDirectCallee()) {
      value["direct"] = true;
      value["callee"] = callee->getNameAsString();
      value["calleeIdentity"] = declarationIdentity(callee);
    } else {
      value["direct"] = false;
    }
    const SourceManager &source_manager = context.getSourceManager();
    SourceLocation location =
        source_manager.getExpansionLoc(call->getExprLoc());
    if (location.isValid() && source_manager.isWrittenInMainFile(location))
      value["offset"] =
          static_cast<int64_t>(source_manager.getFileOffset(location));
    calls.push_back(std::move(value));
    return true;
  }

  llvm::json::Array take() { return std::move(calls); }

private:
  ASTContext &context;
  llvm::json::Array calls;
};

class FunctionVisitor : public RecursiveASTVisitor<FunctionVisitor> {
public:
  FunctionVisitor(ASTContext &context, llvm::json::Array &functions)
      : context(context), functions(functions) {}

  bool VisitFunctionDecl(FunctionDecl *function_decl) {
    SourceManager &source_manager = context.getSourceManager();
    if (!source_manager.isWrittenInMainFile(function_decl->getLocation()))
      return true;

    const FunctionDecl *canonical = function_decl->getCanonicalDecl();
    if (!seen.insert(canonical).second)
      return true;

    std::vector<const FunctionDecl *> declarations;
    bool has_sps_annotation = false;
    for (const FunctionDecl *redecl : function_decl->redecls()) {
      if (!source_manager.isWrittenInMainFile(redecl->getLocation()))
        continue;
      declarations.push_back(redecl);
      for (const auto &value : annotations(redecl))
        has_sps_annotation |= value.rfind("sps.", 0) == 0;
      for (const ParmVarDecl *parameter : redecl->parameters())
        for (const auto &value : annotations(parameter))
          has_sps_annotation |= value.rfind("sps.", 0) == 0;
    }
    if (!has_sps_annotation)
      return true;

    const FunctionDecl *definition = function_decl->getDefinition();
    const FunctionDecl *shape = definition ? definition : function_decl;
    QualType return_type = shape->getReturnType().getCanonicalType();

    std::set<const FunctionDecl *> same_name;
    for (const NamedDecl *named :
         shape->getDeclContext()->lookup(shape->getDeclName()))
      if (const auto *candidate = dyn_cast<FunctionDecl>(named))
        same_name.insert(candidate->getCanonicalDecl());

    llvm::json::Object function;
    function["symbol"] = shape->getNameAsString();
    function["identity"] = declarationIdentity(shape);
    function["isDefinition"] = definition != nullptr;
    function["isExternC"] = shape->isExternC();
    function["isMethod"] = isa<CXXMethodDecl>(shape);
    function["isOverloaded"] = same_name.size() > 1;
    function["isTemplate"] =
        shape->getTemplatedKind() != FunctionDecl::TK_NonTemplate;
    function["isVariadic"] = shape->isVariadic();
    const auto *function_type = shape->getType()->getAs<FunctionType>();
    function["usesDefaultCallingConvention"] =
        function_type && function_type->getCallConv() == CC_C;
    function["returnType"] = return_type.getAsString();
    function["returnIsVoid"] = return_type->isVoidType();
    function["returnIsInteger"] = return_type->isIntegerType();
    function["returnIsFloating"] = return_type->isFloatingType();
    function["returnBitWidth"] =
        return_type->isVoidType()
            ? 0
            : static_cast<int64_t>(context.getTypeSize(return_type));

    llvm::json::Array declaration_values;
    for (const FunctionDecl *redecl : declarations) {
      llvm::json::Object declaration;
      declaration["annotations"] = strings(annotations(redecl));
      llvm::json::Array parameter_annotations;
      for (const ParmVarDecl *parameter : redecl->parameters())
        parameter_annotations.push_back(strings(annotations(parameter)));
      declaration["parameterAnnotations"] = std::move(parameter_annotations);
      declaration_values.push_back(std::move(declaration));
    }
    function["declarations"] = std::move(declaration_values);

    llvm::json::Array parameters;
    for (unsigned index = 0; index < shape->getNumParams(); ++index) {
      const ParmVarDecl *parameter_decl = shape->getParamDecl(index);
      QualType type = parameter_decl->getType().getCanonicalType();
      llvm::json::Object parameter;
      parameter["index"] = static_cast<int64_t>(index);
      parameter["name"] = parameter_decl->getNameAsString();
      parameter["type"] = type.getAsString();
      parameter["isPointer"] = type->isPointerType();
      parameter["isFunctionPointer"] =
          type->isPointerType() && type->getPointeeType()->isFunctionType();
      parameter["usesDefaultAddressSpace"] =
          !type->isPointerType() ||
          (type.getAddressSpace() == LangAS::Default &&
           type->getPointeeType().getAddressSpace() == LangAS::Default);
      parameter["isInteger"] = type->isIntegerType();
      parameter["isFloating"] = type->isFloatingType();
      parameter["bitWidth"] =
          type->isPointerType()
              ? 0
              : static_cast<int64_t>(context.getTypeSize(type));
      parameters.push_back(std::move(parameter));
    }
    function["parameters"] = std::move(parameters);

    llvm::json::Array calls;
    if (definition && definition->getBody()) {
      CallVisitor call_visitor(context);
      call_visitor.TraverseStmt(definition->getBody());
      calls = call_visitor.take();
    }
    function["calls"] = std::move(calls);
    functions.push_back(std::move(function));
    return true;
  }

private:
  ASTContext &context;
  llvm::json::Array &functions;
  std::set<const FunctionDecl *> seen;
};

class Consumer : public ASTConsumer {
public:
  explicit Consumer(ASTContext &context) : visitor(context, functions) {}

  void HandleTranslationUnit(ASTContext &context) override {
    visitor.TraverseDecl(context.getTranslationUnitDecl());
    llvm::json::Object root;
    root["cplusplus"] = static_cast<bool>(context.getLangOpts().CPlusPlus);
    root["functions"] = std::move(functions);
    llvm::outs() << llvm::formatv("{0:2}\n",
                                  llvm::json::Value(std::move(root)));
  }

private:
  llvm::json::Array functions;
  FunctionVisitor visitor;
};

class Action : public ASTFrontendAction {
public:
  std::unique_ptr<ASTConsumer> CreateASTConsumer(CompilerInstance &compiler,
                                                 StringRef) override {
    return std::make_unique<Consumer>(compiler.getASTContext());
  }
};

} // namespace

int main(int argc, const char **argv) {
  auto parser = CommonOptionsParser::create(argc, argv, Category);
  if (!parser) {
    llvm::errs() << llvm::toString(parser.takeError()) << '\n';
    return 2;
  }
  ClangTool tool(parser->getCompilations(), parser->getSourcePathList());
  return tool.run(newFrontendActionFactory<Action>().get());
}
