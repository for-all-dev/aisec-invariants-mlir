# Declassification: R = ckks_sanitize_model(raw, mask, cert), held equal as a
# premise; Obs = *public_release. The second release-relative job after
# explicit_error_oracle, and the first whose R is a non-trivial function rather
# than a single bit.
#
# The return value is NOT observed: both fixtures return the raw plaintext to
# the caller, so asserting on it would make the fixed direction a false alarm.
#
# No metadata flags: the leak is in a value the observer reads directly.
add_l2_job(NAME  ckks_unsafe_release
           BAD   unit_proof/ckks_unsafe_release_bad_harness.c
           FIXED unit_proof/ckks_unsafe_release_fixed_harness.c)
