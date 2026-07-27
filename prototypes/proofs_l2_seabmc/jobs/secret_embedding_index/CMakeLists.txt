# Address channel: Obs = the set of table slots read.
#
# Both fixtures return the SAME secret-dependent value (table[secret & 15]), so
# only the access pattern can separate them -- which is why this job needs the
# read-metadata flags and the oracle job does not.
add_l2_job(NAME  secret_embedding_index
           BAD   unit_proof/secret_embedding_index_bad_harness.c
           FIXED unit_proof/secret_embedding_index_fixed_harness.c
           FLAGS ${SEA_READ_CHANNEL_FLAGS})
