// Function under test (pure, no globals -> no link collisions when duplicated).
int fut(int a, int b, int c) { int m = -(!!a); return (m & b) | (~m & c); }
