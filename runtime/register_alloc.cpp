#include <map>
#include <cstring>
#include <iostream>
#include <iomanip>

#define NOINSTRUMENT(name) __noinstrument_##name
#define NOINSTRUMENT_PREFIX "__noinstrument_"

using namespace std;

namespace {
    static map<unsigned, unsigned> counters;

    extern "C" __attribute__((nothrow))
    void NOINSTRUMENT(register_alloc)(int allocSize) {
        counters[allocSize]++;
        cerr << "Alloc of size " << allocSize << endl;
    }

    __attribute__((destructor))
    static void NOINSTRUMENT(store_alloca)() {
        
        cerr << "Should be storing to file here" << endl;

    }
}