#include <map>
#include <cstring>
#include <iostream>
#include <fstream>
#include <iomanip>
#include <cstdlib>

static std::map<std::pair<int, int>, int> allocations;

enum alloc_type {
    EMPTY = 0, // Placeholder value for use in array
    CALLOC,
    MALLOC,
    REALLOC,
    FREE, 
};

static const char *const type_names[] = {
    [CALLOC]    = "Calloc",
    [MALLOC]    = "Malloc",
    [REALLOC]   = "Realloc",
    [FREE]      = "Free"
};

extern "C" __attribute__((nothrow))
void register_alloc(size_t size, enum alloc_type type) {
    // std::cerr << "Storing " << size << " with type " << type_names[type] << std::endl;

    allocations[std::make_pair(size, type)] += 1;
}

extern "C" __attribute__((destructor))
void write_to_file(void) {
    char *out_file = std::getenv("RESULT_OUT_FILE");

    if (out_file == NULL)
        return;

    if (allocations.size() == 0) {
        std::cerr << "No Heap Allocations to Store "  << std::endl;
        return;
    }

    std::ofstream file;
    file.open(out_file, std::ofstream::out | std::ofstream::app);

    // std::cerr << "Storing " << allocations.size() << " allocation sizes to file " << out_file << std::endl;

    for (const auto& [key, val]: allocations) {
        file << "Count:\t" << val << ", Size:\t" << key.first << ", Type:\t" << type_names[key.second] << std::endl;
    }

    file.close();

}

extern "C" {
    void *malloc(size_t size) {
        register_alloc(size, MALLOC);

        extern void *__libc_malloc(size_t);
        return __libc_malloc(size);
    }


    void *calloc(size_t nmemb, size_t size) {
        register_alloc(size * nmemb, CALLOC);

        extern void *__libc_calloc(size_t, size_t);
        return __libc_calloc(nmemb, size);
    }

    void *realloc(void *ptr, size_t size) {
        register_alloc(size, REALLOC);

        extern void *__libc_realloc(void *, size_t);
        return __libc_realloc(ptr, size);
    }

    void free(void *ptr) {
        register_alloc(0, FREE);

        extern void __libc_free(void *);
        __libc_free(ptr);
    }
}

