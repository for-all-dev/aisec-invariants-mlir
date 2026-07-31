#include <stdint.h>
uint64_t opaque(uint64_t x) { return x * 0x9E3779B97F4A7C15ULL + 1; }
volatile uint64_t g_sink;
void sink(uint64_t x) { g_sink = x; }
