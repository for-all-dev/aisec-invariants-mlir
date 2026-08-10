# Post-MVP integrity and robust-declassification examples

These examples use an `authorizers`/`authorized_by` relation that is deliberately
outside the SPS Rev4 confidentiality claim. They remain parseable design inputs,
but they have no Rev4 `ModelStatus` oracle and are not discovered by the default
lit suite.

A future integrity or robust-declassification extension may adopt them only after
it gives authorization influence its own normative semantics and result domain.
Rev4 release audience and release-table conformance must not be conflated with
that extension.
