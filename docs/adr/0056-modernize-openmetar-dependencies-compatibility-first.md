# Modernize Openmetar Dependencies Compatibility First

The `openmetar` package will move direct runtime packages from `Depends` to `Imports`, keeping only the R runtime in `Depends`, while using explicit NAMESPACE imports as an intermediate compatibility step. Calls will be rewritten to `pkg::function()` only where files are already being touched for CRAN-latest API compatibility.

Current R package guidance prefers `Imports` for required dependencies and explicit namespacing in package code, but applying that style mechanically across the full legacy analysis surface at the same time as statistical-package upgrades would make Analysis Behavior regressions harder to attribute.
