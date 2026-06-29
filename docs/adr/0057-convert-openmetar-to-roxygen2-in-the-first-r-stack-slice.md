# Convert Openmetar to Roxygen2 in the First R Stack Slice

The first `openmetar` R Stack modernization slice will modernize `DESCRIPTION`, replace `exportPattern()` with explicit exports and imports, get `R CMD build` and `R CMD check` passing under the latest CRAN dependency set, and convert the package to roxygen2-generated documentation and NAMESPACE.

This accepts a larger package-surface change in the same slice so the package follows current R package conventions end to end, rather than preserving a temporary hand-maintained namespace style that would immediately need another migration.
