#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <string.h>

#define MAX_ALLOCS 10000
#define DEFAULT_OUTFILE "heap_allocations.txt"

typedef struct allocation_t allocation_t;

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

struct allocation_t {
    enum alloc_type type;
    size_t size;
    size_t count;
};

static allocation_t allocs[MAX_ALLOCS] = {0};

__attribute__((destructor))
static void write_to_file(void) {
    char *out_file = getenv("RESULT_OUT_FILE");

    if (out_file == NULL)
        return;
        //out_file = strcpy((char *) malloc(strlen(DEFAULT_OUTFILE)), DEFAULT_OUTFILE);

    fprintf(stderr, "Writing tracked heap allocations to file %s\n", out_file);
    FILE *out = fopen(out_file, "w+");

    for (int i = 0; i < MAX_ALLOCS; i++) {
        allocation_t alloc = allocs[i];
        if (alloc.type == EMPTY)
            break;

        fprintf(out, "Count:\t%ld, Size:\t%ld, Type:\t%s\n", alloc.count, alloc.size, type_names[alloc.type]);
    }

    fclose(out);

    if (strcmp(out_file, DEFAULT_OUTFILE) == 0)
        free(out_file);
}

static void register_alloc(size_t size, enum alloc_type type) {
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
