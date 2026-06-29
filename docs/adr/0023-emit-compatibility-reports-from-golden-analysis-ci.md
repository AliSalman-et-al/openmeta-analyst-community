# Emit Compatibility Reports From Golden Analysis CI

Golden analysis CI should emit a compatibility report artifact in addition to pass/fail test results. The report should list the datasets, analysis methods, metrics, tolerances, and observed drift values compared against the reference implementation so reviewers can understand what was verified and future R-stack modernization can reuse the same evidence.

The initial report can be simple, such as structured JSON plus a human-readable summary, and can evolve as coverage expands.
