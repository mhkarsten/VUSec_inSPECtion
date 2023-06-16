#include <map>
#include <vector>
#include <sstream>
#include <optional>
#include <iostream>
#include <llvm/Pass.h>
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
    class AllocTracker : public ModulePass {
        public:
            static char ID;
            virtual bool runOnModule(Module &M) override;
        private:
            Function *AllocRegisterFn;
    };
}

[[maybe_unused]] bool AllocTracker::runOnModule(Module &M) {
    bool Changed = false;
    
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
                        errs() << "FOUND AN ALLOCA";
                        IRBuilder<> B(&I.getFunction()->getEntryBlock());
                        B.SetInsertPoint(&I);
                        B.CreateCall(AllocTracker::AllocRegisterFn->getFunctionType(), FnCallee.getCallee(), ArrayRef<Value*>(cast<Value>(ConstantInt::get(Type::getInt32Ty(M.getContext()), allocSize.value().getFixedValue()))), name);
                        Changed = true;
                    }
                }
            }
        }
    }


    LLVM_DEBUG(dbgs() << "This is a message for mypass\n"); 
    errs() << "AT LEAST SOME EVIDENCE OF EXECUTION HELLOOOOO";
    return Changed;
}

char AllocTracker::ID = 0;
static RegisterPass<AllocTracker> X("allocs-instrument",
        "Instrument all stack allocations (alloca) with a call to "
        "a function that tracks stack usage at runtime",
        false, false);
