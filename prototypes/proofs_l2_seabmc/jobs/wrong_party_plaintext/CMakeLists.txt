# Value channel: Obs = *unauthorized_mailbox ONLY.
#
# The observation scope carries this job. Both fixtures write the plaintext to
# *authorized_mailbox -- correctly, since that party is entitled to it. Widening
# Obs to include it would make the fixed direction report a leak that is not
# there.
#
# No metadata flags: the leak is in a value the observer reads directly.
add_l2_job(NAME  wrong_party_plaintext
           BAD   unit_proof/wrong_party_plaintext_bad_harness.c
           FIXED unit_proof/wrong_party_plaintext_fixed_harness.c)
