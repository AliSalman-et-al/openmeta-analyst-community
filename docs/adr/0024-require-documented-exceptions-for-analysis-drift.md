# Require Documented Exceptions for Analysis Drift

Real statistical drift discovered during the Python 3 and Qt 5 port blocks the milestone by default. Any intentional difference from the reference implementation must be documented as a compatibility exception with the affected dataset, analysis method, metric, old output, new output, reason, and user impact.

This keeps the preservation goal enforceable while still allowing rare, deliberate exceptions when the team chooses them explicitly.
