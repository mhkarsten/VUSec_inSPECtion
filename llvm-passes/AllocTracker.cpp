#include <map>
#include <vector>
#include <sstream>
#include <optional>
#include <iostream>
#include <fstream>
#include <cstdlib>
#include <llvm/Pass.h>
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include <llvm/IR/Constant.h>
#include <llvm/IR/Constants.h>
#include <llvm/IR/Module.h>
#include <llvm/IR/Function.h>
#include <llvm/IR/Instruction.h>
#include <llvm/IR/Instructions.h>
#include "llvm/IR/IRBuilder.h"
#include <llvm/ADT/SmallVector.h>
#include <llvm/ADT/Twine.h>
#include "llvm/Support/raw_ostream.h"
#include <llvm/Support/Debug.h> 

#define NOINSTRUMENT_PREFIX "__noinstrument_"
#define DEBUG_TYPE "stacktrack"

using namespace llvm;

namespace {

    struct AllocTracker : PassInfoMixin<AllocTracker> {
        public:
            PreservedAnalyses run(Module &M, ModuleAnalysisManager &);
        private:
            Function *AllocRegisterFn;
    };

    PreservedAnalyses AllocTracker::run(Module &M, ModuleAnalysisManager &) {
        errs() << "IF I CAN GET THIS TO WORK I WILL BE SO HAPPY\n";
        if (!(AllocRegisterFn = M.getFunction(NOINSTRUMENT_PREFIX "register_alloc"))) {
                Type *VoidTy = Type::getVoidTy(M.getContext());
                Type *IntTy = Type::Type::getInt32Ty(M.getContext());
                FunctionType *FnTy = FunctionType::get(VoidTy, {IntTy}, false);
                AllocTracker::AllocRegisterFn = Function::Create(FnTy, GlobalValue::ExternalLinkage,
                                                NOINSTRUMENT_PREFIX "register_alloc", &M);
            }

            const auto name = Twine(NOINSTRUMENT_PREFIX "register_alloc");
            for (Function &F : M) {
                for (BasicBlock &BB : F) {
                    for (Instruction &I : BB) {
                        if (isa<AllocaInst>(I)) {
                            std::optional<TypeSize> allocSize = cast<AllocaInst>(I).getAllocationSize(M.getDataLayout());;

                            if (allocSize.has_value()) {
                                auto FnCallee = M.getOrInsertFunction(NOINSTRUMENT_PREFIX "register_alloc",
                                                Type::getVoidTy(M.getContext()), Type::getInt32Ty(M.getContext()));
                                errs() << "FOUND AN ALLOCA\n";
                                IRBuilder<> B(&I.getFunction()->getEntryBlock());
                                B.SetInsertPoint(&I);
                                B.CreateCall(AllocTracker::AllocRegisterFn->getFunctionType(), FnCallee.getCallee(), ArrayRef<Value*>(cast<Value>(ConstantInt::get(Type::getInt32Ty(M.getContext()), allocSize.value().getFixedValue()))), name);
                            }
                        }
                    }
                }
            }

        return PreservedAnalyses::none();
    }
}

/* New PM Registration */
llvm::PassPluginLibraryInfo getAllocTrackerPluginInfo() {
    return {LLVM_PLUGIN_API_VERSION, "AllocTracker", LLVM_VERSION_STRING,
            [](PassBuilder &PB) {
            PB.registerOptimizerLastEPCallback (
                [](llvm::ModulePassManager &PM, OptimizationLevel Level) {
                    PM.addPass(AllocTracker());
                });
            }};
}

#ifndef LLVM_ALLOCTRACKER_LINK_INTO_TOOLS
extern "C" LLVM_ATTRIBUTE_WEAK ::llvm::PassPluginLibraryInfo
llvmGetPassPluginInfo() {
    return getAllocTrackerPluginInfo();
}
#endif