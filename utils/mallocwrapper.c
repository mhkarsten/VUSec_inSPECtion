#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <stdbool.h>

#define MAX_ALLOCS 1000
#define OUT_NAME "heap_allocations.out"

static bool exit_registered = false;

typedef struct allocation_t allocation_t;

enum alloc_type {
    EMPTY = 0, // Placeholder value for use in array
    CALLOC,
    MALLOC,
    REALLOC,
    FREE, 
};

const char *const type_names[] = {
    [CALLOC]    = "Calloc",
    [MALLOC]    = "Malloc",
    [REALLOC]   = "Realloc",
    [FREE]      = "Free"
};

struct allocation_t {
    enum alloc_type type;
    size_t size;
    size_t count;
};

static allocation_t allocs[MAX_ALLOCS] = {0};

void write_to_file(void) {
    FILE *out = fopen(OUT_NAME, "w+");

    for (int i = 0; i < MAX_ALLOCS; i++) {
        allocation_t alloc = allocs[i];
        if (alloc.type == EMPTY)
            break;

        fprintf(out, "Count:\t%ld, Size:\t%ld, Type:\t%s\n", alloc.count, alloc.size, type_names[alloc.type]);
    }

    fclose(out);
}

void register_exit() {
    if (!exit_registered) {
        atexit(write_to_file);
        exit_registered = true;
    }
}

void register_alloc(size_t size, enum alloc_type type) {
    int i = 0;

    while(  allocs[i].type != EMPTY &&
            (allocs[i].type != type || 
            allocs[i].size != size))
        i += 1;

    if (allocs[i].type == EMPTY) {
        allocs[i].type = type;
        allocs[i].size = size;
        allocs[i].count = 1;
    } else {
        allocs[i].count += 1;
    }
}

void *malloc(size_t size) {
    register_exit();

    register_alloc(size, MALLOC);

    extern void *__libc_malloc(size_t);
    return __libc_malloc(size);
}


void *calloc(size_t nmemb, size_t size) {
    register_exit();

    register_alloc(size * nmemb, CALLOC);

    extern void *__libc_calloc(size_t, size_t);
    return __libc_calloc(nmemb, size);
}

void *realloc(void *ptr, size_t size) {
    register_exit();

    register_alloc(size, REALLOC);

    extern void *__libc_realloc(void *, size_t);
    return __libc_realloc(ptr, size);
}

void free(void *ptr) {
    register_exit();

    register_alloc(0, FREE);

    extern void __libc_free(void *);
    __libc_free(ptr);
}
