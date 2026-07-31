# Rev. 4 high-value fixture inputs

These hand-authored LLVM inputs exercise the highest-value fail-closed cases
from the Rev. 4 SPS specifications.  Lit assembles every input to temporary
bitcode, verifies it, reparses it, and checks the decisive LLVM shape.

The companion `cases.json` is an oracle catalog, not a verifier report.  Every
entry is deliberately `claimable: false` and `current_status: Pending` until a
pinned LLVM 22.1.8 capture and the Rev. 4 relational verifier exist.  Passing
these tests establishes fixture integrity and compiler-boundary coverage only;
it does not establish `NFConforms` or compute `ModelStatus`.

The `.ll.in` suffix is intentional.  These inputs are assembled explicitly by
their integration tests and are not mistaken for frozen canonical artifacts by
the harness-wide checked-in `.ll` inventory.

