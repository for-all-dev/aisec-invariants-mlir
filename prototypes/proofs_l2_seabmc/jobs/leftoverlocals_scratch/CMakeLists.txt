# Value channel: Obs = (*shared_scratch, *next_tenant_output, return value).
#
# Residue in uncleared GPU local memory. The scratch buffer is in the
# observation, not just the handed-over output -- the next tenant can read it
# either way, and that is the actual vulnerability.
#
# No metadata flags: the leak is in a value the observer reads directly.
add_l2_job(NAME  leftoverlocals_scratch
           BAD   unit_proof/leftoverlocals_scratch_bad_harness.c
           FIXED unit_proof/leftoverlocals_scratch_fixed_harness.c)
