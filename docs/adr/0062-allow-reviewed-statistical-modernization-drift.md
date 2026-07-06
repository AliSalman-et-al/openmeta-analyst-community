# Allow Reviewed Statistical Modernization Drift

The `openmetar` R Stack modernization slice may accept statistically different outputs from the Reference Implementation when the differences are caused by moving from decade-old R package behavior to current CRAN package behavior and the modern outputs are judged correct. Such differences are expected in this slice, but they must be documented as reviewed Statistical Modernization Drift instead of silently replacing the compatibility oracle.

This narrows the older default that Analysis Behavior drift blocks modernization by default: for this R Stack slice, numerical equivalence remains useful for triage, but correctness under current statistical packages is the acceptance target.
