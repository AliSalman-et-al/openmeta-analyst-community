# ADR 0280: Use Lane Directories Instead of a Per-Node Test Taxonomy

## Status

Accepted — August 2026

## Context

ADR 0079 introduced a permanent JSON manifest that classified every collected
pytest node, injected markers from that manifest, and enforced that the ledger
and collection stayed identical. The completed suite audit showed that this
ledger duplicated information already present in the test ownership
directories and made ordinary test changes require unrelated metadata edits.
The per-node records did not add a stronger behavioral guarantee.

## Decision

The active verification suite is organized by authoritative lane directories:
`tests/python/fast`, `tests/python/gui`, `tests/r_stack`,
`tests/analysis_regression/golden`, and `tests/packaging/contract`. Pytest
markers are registered and derived from those directories for selection. Tests
that share process state declare that requirement explicitly; for example,
QSettings tests use the `qsettings` marker and GUI selections receive an
offscreen QApplication with isolated settings.

The historical Qt6 cutover classification remains because it records the
legacy surface and its disposition. Its replacement evidence is validated at
stable file paths, not against a live collected-node database. No replacement
taxonomy or metadata manifest is introduced.

## Consequences

Adding or moving a test changes its owning directory and, when needed, its
explicit module marker. There is no active per-node ledger to regenerate or
keep synchronized. ADR 0079 remains the historical record of the earlier
manifest decision and is superseded for the maintained suite by this ADR.
