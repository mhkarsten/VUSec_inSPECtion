#include <map>
#include <cstring>
#include <iostream>
#include <fstream>
#include <iomanip>
#include <cstdlib>
#include <llvm/IR/Type.h>

#define NOINSTRUMENT(name) __noinstrument_##name
#define NOINSTRUMENT_PREFIX "__noinstrument_"
#define DEFAULT_OUTFILE "stacktrack.txt"

using namespace std;

namespace {
    // Maps type ID and size to their count
    static map<pair<int, int>, int> allocations;
    
    const char *const type_names[] = {
        [llvm::Type::TypeID::HalfTyID]      = "16-bit floating point",
        [llvm::Type::TypeID::BFloatTyID]    = "16-bit floating point (7-bit significand)",
        [llvm::Type::TypeID::FloatTyID]     = "32-bit floating point",
        [llvm::Type::TypeID::DoubleTyID]    = "64-bit floating point",
        [llvm::Type::TypeID::X86_FP80TyID]  = "80-bit floating point (X87)",
        [llvm::Type::TypeID::FP128TyID]     = "128-bit floating point (112-bit significand) ",
        [llvm::Type::TypeID::PPC_FP128TyID] = "128-bit floating point (two 64-bits, PowerPC) ",
        [llvm::Type::TypeID::VoidTyID]      = "void",
        [llvm::Type::TypeID::LabelTyID]     = "label",
        [llvm::Type::TypeID::MetadataTyID]  = "metadata",
        [llvm::Type::TypeID::X86_MMXTyID]   = "MMX vectors (64 bits, X86 specific)",
        [llvm::Type::TypeID::X86_AMXTyID]   = "AMX vectors (8192 bits, X86 specific)",
        [llvm::Type::TypeID::TokenTyID ]    = "token",
        [llvm::Type::TypeID::IntegerTyID]   = "integer",
        [llvm::Type::TypeID::FunctionTyID]  = "function",
        [llvm::Type::TypeID::PointerTyID]   = "pointer",
        [llvm::Type::TypeID::StructTyID]    = "struct",
        [llvm::Type::TypeID::ArrayTyID]     = "array",
        [llvm::Type::TypeID::FixedVectorTyID]       = "Fixed width SIMD vector",
        [llvm::Type::TypeID::ScalableVectorTyID]    = "Scalable SIMD vector"
        // [llvm::Type::TypeID::TypedPointerTyID]      = "Typed pointer used by some GPU targets",
        // [llvm::Type::TypeID::TargetExtTyID]         = "Target extension"
    };

    
    extern "C" __attribute__((nothrow)) __attribute__((no_sanitize("memory")))
    void NOINSTRUMENT(register_alloc)(int alloc_size, int typeID) {
        allocations[make_pair(alloc_size, typeID)] += 1;
        // cerr << "Alloc of size " << alloc_size << " and type " << type_names[typeID] <<  " with count " << allocations[make_pair(alloc_size, typeID)] << endl;
    }

    
    extern "C" __attribute__((destructor)) __attribute__((no_sanitize("memory")))
    static void NOINSTRUMENT(save_allocs)() {
        char *out_file = getenv("RESULT_OUT_FILE");

        if (out_file == NULL)
            return;
            //out_file = strcpy((char *) malloc(strlen(DEFAULT_OUTFILE)), DEFAULT_OUTFILE);

        if (allocations.size() == 0) {
            cerr << "No Allocations to store "  << endl;
            return;
        }

        ofstream file;
        file.open(out_file);

        cerr << "Storing " << allocations.size() << " allocation sizes to file " << out_file << endl;

        for (const auto& [key, val]: allocations) {
            file << val << " allocations size: " << key.first << ", type: " << type_names[key.second] << endl;
        }

        file.close();
        
        // if (strcmp(out_file, DEFAULT_OUTFILE) == 0)
        //     free(out_file);
    }
}