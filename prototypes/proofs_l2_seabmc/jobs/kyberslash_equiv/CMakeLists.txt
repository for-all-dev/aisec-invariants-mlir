# Functional equivalence of the KyberSlash constant-time rewrites.
#
# These are NOT non-interference jobs, which is why they use add_equiv_job
# rather than add_l2_job. KyberSlash's channel is the latency of a variable-time
# `udiv` on a secret operand -- SeaBMC models values and memory, not latency, so
# the leak itself is out of reach here (README: "Why there is no KyberSlash L2
# job"). What is in reach, and was never discharged anywhere, is that the
# rewrites preserve the function.
#
# No metadata flags: no addresses are observed, so SEA_READ_CHANNEL_FLAGS is
# deliberately absent.
#
# The three claims are read together. kyberslash2's `sat` calibrates the two
# `unsat`s -- same harness shape, same flags -- and the full/domain pair locates
# the c < q boundary exactly.

# Equivalent over the entire uint16 domain, no precondition needed.
add_equiv_job(NAME    kyberslash1_equiv
              HARNESS unit_proof/kyberslash1_equiv.c
              EXPECT  unsat)

# NOT equivalent over uint16: 49 counterexamples, first at c = 13212, from
# uint32 wraparound in `t *= 80635u`. equivalence_driver.c never saw these
# because it enumerates only c in [0, 3329).
add_equiv_job(NAME    kyberslash2_equiv_full
              HARNESS unit_proof/kyberslash2_equiv_full.c
              EXPECT  sat)

# Equivalent once the precondition every real caller satisfies is stated.
add_equiv_job(NAME    kyberslash2_equiv_domain
              HARNESS unit_proof/kyberslash2_equiv_domain.c
              EXPECT  unsat)
