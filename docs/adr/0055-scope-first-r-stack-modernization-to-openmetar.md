# Scope First R Stack Modernization to Openmetar

Supersession note: ADR 0082 supersedes this package identity for active development. The maintained private R package is `RCMetaR`, exposed through the `RCMetaR` package and `rcmetar.*` API surface.

The first R Stack modernization slice will target the bundled `openmetar` package, its package metadata, and the external packages its functions call directly. Transitive CRAN dependencies will be resolved by CRAN, and other bundled R packages such as `HSROC` will be handled in follow-up slices unless `openmetar` cannot build or pass compatibility checks without touching them.

This keeps the migration reviewable and lets Analysis Behavior drift be attributed to concrete direct dependency changes instead of a simultaneous full-stack rewrite.
