/* Vulnerable pre-9b8d306 poly_frommsg from pq-crystals/kyber ref (CVE-2024-37880) */
#include <stdint.h>
#define KYBER_N 256
#define KYBER_Q 3329
#define KYBER_SYMBYTES 32
#define KYBER_INDCPA_MSGBYTES KYBER_SYMBYTES
typedef struct { int16_t coeffs[KYBER_N]; } poly;

void poly_frommsg(poly *r, const uint8_t msg[KYBER_INDCPA_MSGBYTES])
{
  unsigned int i,j;
  int16_t mask;
  for(i=0;i<KYBER_N/8;i++) {
    for(j=0;j<8;j++) {
      mask = -(int16_t)((msg[i] >> j)&1);
      r->coeffs[8*i+j] = mask & ((KYBER_Q+1)/2);
    }
  }
}
