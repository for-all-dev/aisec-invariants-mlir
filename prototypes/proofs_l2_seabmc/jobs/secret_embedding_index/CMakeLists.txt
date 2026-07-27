# Address channel: Obs = the set of table slots read.
#
# Both fixtures return the SAME secret-dependent value (table[secret & 15]), so
# only the access pattern can separate them -- which is why this job needs the
# read-metadata flags and the oracle job does not.
add_l2_proof(NAME   secret_embedding_index_bad
             SOURCE unit_proof/secret_embedding_index_bad_harness.c
             EXPECT sat
             FLAGS  ${SEA_READ_CHANNEL_FLAGS})

add_l2_proof(NAME   secret_embedding_index_fixed
             SOURCE unit_proof/secret_embedding_index_fixed_harness.c
             EXPECT unsat
             FLAGS  ${SEA_READ_CHANNEL_FLAGS})
