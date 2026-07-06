# Treat Sample Projects as User-Facing Examples

Committed `.rcms` files under `sample_projects` should be treated as user-facing examples first and shared test inputs second. They should have readable scientific names, clear manifest entries, and representative workflow coverage.

Test-only edge cases or artificial corrupted files should live under `tests/fixtures` rather than cluttering the user-facing sample project set.

