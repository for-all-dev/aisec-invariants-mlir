/*
 * Observation projection (Obs_Theta) for the address channel.
 *
 * The attacker observes WHICH table slots a run touched, not the value it
 * returned. That distinction is the whole point of this job: the fixed variant
 * of secret_embedding_index returns the SAME value as the bad one (a masked
 * constant-time full scan), so the returned value cannot discriminate them --
 * only the access pattern can.
 *
 * Read metadata is byte-granular and sea_reset_read/sea_is_read act on a single
 * address, so the footprint is taken per element rather than over the buffer.
 *
 * sea_is_read reads metadata memory rather than table[], so measuring the
 * footprint does not itself pollute the footprint being measured.
 *
 * Requires --horn-shadow-mem-load-is-def, without which a load is a MemUse,
 * stamps nothing, and every footprint reads back as 0.
 */
#pragma once

#include "seahorn/seahorn.h"

#include <stddef.h>
#include <stdint.h>

extern void sea_tracking_on(void);
extern void sea_tracking_off(void);
extern void memhavoc(void *, size_t);
/* OpSem treats a nullary function whose name starts with "nd" as nondet. */
extern uint32_t nd_u32(void);

#define TABLE_N 16

/* Clear the read footprint of the whole table. */
static inline void clear_footprint(const uint32_t *t) {
  for (unsigned i = 0; i < TABLE_N; ++i)
    sea_reset_read((char *)&t[i]);
}

/* Obs_Theta: bit i set iff table[i] was read since the last clear_footprint. */
static inline uint32_t read_footprint(const uint32_t *t) {
  uint32_t fp = 0;
  for (unsigned i = 0; i < TABLE_N; ++i)
    fp |= ((uint32_t)sea_is_read((char *)&t[i])) << i;
  return fp;
}
