// Harness for binsec -checkct. Secrets/publics are GLOBALS so the SSE script
// can mark them (see checkct.cfg). Pick the function under test at compile time:
//   gcc -DFUNC=select_leaky ...   or   -DFUNC=select_ct ...
#include <stdlib.h>

extern int FUNC(int secret, int a, int b);

int secret;      // marked `secret global` in checkct.cfg
int a, b;        // marked `public global`

int main(void) {
    int r = FUNC(secret, a, b);
    exit(r & 1);
}
