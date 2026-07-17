// Harness for binsec -checkct (layer B). `secret` is the confidential index;
// a,b public. Pick the kernel with -DFUNC=<name>.
#include <stdlib.h>
extern int FUNC(int secret, int a, int b);
int secret;   // `secret global` in b.cfg
int a, b;     // `public global`
int main(void) { int r = FUNC(secret, a, b); exit(r & 1); }
