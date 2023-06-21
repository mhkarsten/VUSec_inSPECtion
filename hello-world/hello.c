#include <stdio.h>
#include <stdlib.h>

int main() {
    int glorious_int = 5;

    char *testalloc = (char *) malloc(10);

    testalloc[0] = 'H';
    testalloc[1] = 'I';
    testalloc[2] = '\0';

    printf("Hello, World! %d, Goodbye %s\n", glorious_int, testalloc);
    free(testalloc);
    return 0;
}
