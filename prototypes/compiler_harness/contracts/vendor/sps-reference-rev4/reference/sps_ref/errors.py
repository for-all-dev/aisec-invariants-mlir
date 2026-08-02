"""Stable fail-closed errors for the executable reference slice."""


class ReferenceError(Exception):
    """Base class for a reference construction or validation failure."""

    reason = "ReferenceToolInconsistency"


class SchemaError(ReferenceError):
    reason = "ReferenceSchemaMismatch"


class UnsupportedError(ReferenceError):
    reason = "ReferenceProfileUnsupported"


class UninitializedOutputError(ReferenceError):
    reason = "UninitializedOutputByte"


class SolverUnavailableError(ReferenceError):
    reason = "ReferenceSolverUnavailable"


class ReplayError(ReferenceError):
    reason = "ReferenceReplayRejected"
