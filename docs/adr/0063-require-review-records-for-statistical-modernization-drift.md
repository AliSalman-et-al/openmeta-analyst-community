# Require Review Records for Statistical Modernization Drift

Accepted Statistical Modernization Drift in the `openmetar` R Stack slice must be documented with enough evidence to distinguish expected modern statistical behavior from accidental regressions. Each reviewed drift record should include the Reference Implementation output, the modern `openmetar` output, the package versions and methods involved, the likely reason for the difference, an independent validation signal, and the user-facing impact.

This allows expected output changes from current CRAN packages without reducing the migration to unreviewed golden-output replacement.
