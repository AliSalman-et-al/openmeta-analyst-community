# Scope First R Stack Modernization to Openmetar

The first R Stack modernization slice will target the bundled `openmetar` package, its package metadata, and the external packages its functions call directly. Transitive CRAN dependencies will be resolved by CRAN, and other bundled R packages such as `HSROC` will be handled in follow-up slices unless `openmetar` cannot build or pass compatibility checks without touching them.

This keeps the migration reviewable and lets Analysis Behavior drift be attributed to concrete direct dependency changes instead of a simultaneous full-stack rewrite.
