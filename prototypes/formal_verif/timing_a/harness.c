// Harness for binsec -checkct (layer A). Secrets/publics are GLOBALS so the SSE
// script (a.cfg) can mark them. Pick the function under test at compile time:
//   gcc -DFUNC=a_div_divisor ...
#include <stdlib.h>

extern int FUNC(int secret, int a, int b);

int secret;   // marked `secret global` in a.cfg
int a, b;     // marked `public global`

int main(void) {
    int r = FUNC(secret, a, b);
    exit(r & 1);
}
