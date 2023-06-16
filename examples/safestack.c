#include <stdio.h>
int main() {
	long int x = 10;
	long int arr[100] = {0};
	
	x = 123;
	arr[93] = 12345;

	printf("arr[93]: (%p, 0x%lx), x: (%p, 0x%lx)\n", arr+93, arr[93], &x, x);

	return 0;
}