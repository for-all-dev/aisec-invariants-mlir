# Value channel: Obs = (*public_wire_length, return value).
#
# BREACH/CRIME. The ciphertext is opaque but its length is not, and the bad
# variant makes that length depend on whether an attacker-chosen guess matched
# the secret byte -- one bit of oracle per query.
#
# No metadata flags: the leak is in a value the observer reads directly.
add_l2_job(NAME  breach_compressed_length
           BAD   unit_proof/breach_compressed_length_bad_harness.c
           FIXED unit_proof/breach_compressed_length_fixed_harness.c)
