/*
 * Case: MT-CM5 unproved ABI alias separation
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-countermodel-encoding
 *
 * Relationship to upstream:
 *   Encodes countermodel MT-CM5 from the SPS Rev-4 metatheory, which refutes
 *   the invalid principle "unproved ABI alias separation may be assumed". No
 *   upstream body is copied.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   the public output target
 *
 * Expected confidentiality issue:
 *   The secret is stored through p and a value is reloaded through q, then sent
 *   to a public output. An analysis that ASSUMES p and q are disjoint leaves the
 *   abstract q object untouched and proves a constant output. In an admitted
 *   concrete call with p == q, the store updates the byte read through q, and
 *   two secret values produce two public outputs.
 *
 *   Merely naming two buffers differently establishes neither choice. This is
 *   why the alias-honesty premise is load-bearing: PublicAliasTopology is a
 *   conjunct of LowEq^0, and EntryABIConforms must include the complete alias
 *   relation.
 *
 * Why the outcome is unknown and not unsafe:
 *   With no proved Disjoint clause and no declared MayAlias realization in the
 *   product, neither safety nor a counterexample follows. The honest result is
 *   Unknown(AliasBindingMismatch) with the separation obligation named. The two
 *   sound repairs are (a) put the alias into the product's beta.alias so it can
 *   be caught, or (b) put disjointness into the ABI admission contract and open
 *   a deployment obligation.
 *
 * Deliberate trap:
 *   A first implementation will almost certainly assume two distinct pointer
 *   arguments are disjoint. Nothing in this file licenses that.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm abi_alias_unproved.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
void abi_alias_unproved(unsigned secret, unsigned *p, unsigned *q,
                        unsigned *public_output)
{
  *p = secret;
  *public_output = *q;
}
