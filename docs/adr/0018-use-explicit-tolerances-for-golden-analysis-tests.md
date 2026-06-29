# Use Explicit Tolerances for Golden Analysis Tests

Golden analysis tests will compare parsed numerical outputs against the reference implementation using tight, explicit tolerances rather than exact string equality. Core estimates, confidence intervals, p-values, heterogeneity values, and weights should be compared as numbers; result text may be normalized for whitespace and formatting; generated plots should initially be checked for existence and associated analysis parameters, with deeper content checks added where practical.

This preserves the statistical compatibility target without making the first migration milestone fail on incidental formatting or rendering differences.
