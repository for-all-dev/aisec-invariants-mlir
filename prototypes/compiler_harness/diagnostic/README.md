# Diagnostic-only scanner checks

This suite exercises an explicitly configured unary `sps-scan` prototype and
pins its five supported candidate reason classes plus one zero-finding public
control. A finding is triage; zero findings is silence, never
`ModelStatus: Proved`. Memory, aliasing, releases, coalitions, whole-entry
products, replay, candidate/conformance identity, and P4 are outside this
scanner. Set `SPS_SCAN` explicitly; the harness never guesses a build-tree
binary or labels an arbitrary executable as a versioned verifier.
