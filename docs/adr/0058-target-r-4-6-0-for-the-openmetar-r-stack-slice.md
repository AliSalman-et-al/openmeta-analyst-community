# Target R 4.6.0 for the Openmetar R Stack Slice

The first `openmetar` R Stack modernization slice will target the documented modern artifact runtime: R 4.6.0 with rpy2 3.6.7. External CRAN packages should be updated to the latest versions installable under that runtime, but the R runtime itself should not change in this slice unless dependency resolution proves R 4.6.0 is not viable.

This keeps the R package migration aligned with the existing in-process backend evidence from ADR 0052 while still allowing direct `openmetar` dependencies to move to current CRAN releases.
