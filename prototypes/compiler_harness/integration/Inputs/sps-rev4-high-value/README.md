# Rev. 4 high-value fixture inputs

These hand-authored LLVM inputs exercise the highest-value fail-closed cases
from the Rev. 4 SPS specifications.  Lit assembles every input to temporary
bitcode, verifies it, reparses it, and checks the decisive LLVM shape.

The `release-marker` family is now explicitly a retired negative corpus. Its
function-shaped emitters, outlined wrappers, and callable
markers are not SPS-LLVM-NF-v2 carriers. NFv2 accepts only
`llvm.sps.release`, with identity supplied by
`ReleaseImplementationBindingV2.emitMarkerInstructionId`; see
`integration/nfv2-release-intrinsic-contract.test` for the current structural
contract.

The companion `cases.json` is a harness matcher catalog, not a verifier report.
It separates stage acceptance, `AuditAll` raw solver results, query
dispositions, replay prerequisites, and final `ModelStatus` matchers instead of
collapsing them into one fixture verdict. Every entry is deliberately
`CandidateOnly`, `claimable: false`, and `current_status: Pending` until a
pinned LLVM 22.1.8 capture and the Rev. 4 relational verifier exist.  Passing
these tests establishes fixture integrity and compiler-boundary coverage only;
it does not establish `NFConforms` or compute `ModelStatus`.

The `retirement-coverage` family is the one family here that measures a
property rather than accepting or rejecting a shape. `retirement-coverage.ll.in`
holds two entries with one shared post-release secret-dependent difference and
two different authorized releases. `check_rev4_high_value_fixtures.py` parses
the released projection and the step indices out of that module, enumerates an
8-bit secret pair domain, and emits a per-`(entry, coalition)`
`SPS-Harness-Retirement-Statistic-v2` record: the retirement statistic that
`SPS_Lecture_Notes/part5-soundness.tex:210-219` says could ship today. The
enumeration is a harness model of how the release partitions pairs, not LLVM
semantics and not a solver result, and no `ModelStatus` is computed for either
entry. See `integration/rev4-retirement-coverage-hole.test`.

The `.ll.in` suffix is intentional.  These inputs are assembled explicitly by
their integration tests and are not mistaken for frozen canonical artifacts by
the harness-wide checked-in `.ll` inventory.
