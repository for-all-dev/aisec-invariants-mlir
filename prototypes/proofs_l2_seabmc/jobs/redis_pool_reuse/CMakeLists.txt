# Value channel: Obs = return value, as seen by actor B.
#
# Connection-pool cross-tenant leak: a cancelled request leaves A's response on
# the pooled connection and the bad variant hands it to the next borrower.
#
# No metadata flags: the leak is in a value the observer reads directly.
add_l2_job(NAME  redis_pool_reuse
           BAD   unit_proof/redis_pool_reuse_bad_harness.c
           FIXED unit_proof/redis_pool_reuse_fixed_harness.c)
