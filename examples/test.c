#include <stdlib.h>
#include <stdio.h>

int main(int argc, char **argv) {
    void *ptr = NULL;

    ptr = malloc(2);
    free(ptr);


    ptr = malloc(2);
    free(ptr);

    ptr = malloc(4);
    free(ptr);
    
    ptr = realloc(ptr, 32);
    free(ptr);

    ptr = calloc(8, 4);
    free(ptr);

    return 0;
}
