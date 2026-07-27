# Declassification: the API deliberately releases one bit (padding validity),
# so that release is a PREMISE the two runs are constrained to agree on, and
# only surplus distinguishability is a violation.
#
# Needs no metadata flags at all -- the leak is in a value the observer reads
# directly, so plain output equality suffices.
add_l2_proof(NAME   explicit_error_oracle_bad
             SOURCE unit_proof/explicit_error_oracle_bad_harness.c
             EXPECT sat)

add_l2_proof(NAME   explicit_error_oracle_fixed
             SOURCE unit_proof/explicit_error_oracle_fixed_harness.c
             EXPECT unsat)
