#include <stdlib.h>
int f0(int, int, int);
int f2(int, int, int);
int gx, gy, gz;
void DIFF(void) { volatile int hit = 1; (void)hit; }   // reach target
int main(void) {
    int r0 = f0(gx, gy, gz);
    int r2 = f2(gx, gy, gz);
    if (r0 != r2) DIFF();
    exit(0);
}
