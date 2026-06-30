# Modern Test Taxonomy Audit

Initial audit for ADR 0079. This file records the starting classification used to split CI lanes; runtime classes are initial estimates until replaced by measured `pytest --durations` data.

## Summary

- Collected pytest nodes: 133
- Lanes: fast=26, golden=17, gui=65, packaging_contract=16, r_stack=9
- Sizes: large=59, medium=32, small=42
- Decisions: keep=133

## Cleanup Themes

- The GUI and real R Stack tests are large integration evidence and should not define the default fast feedback loop.
- Packaging contract tests currently use source-text assertions; keep only explicit release-contract guards and rewrite the rest toward structured parsing or executable behavior.
- Tests with opportunistic R skips should move behind Default R Evidence or Full R Stack Evidence instead of being treated as ordinary fast tests.
- Parallelism is deferred until fast tests are isolated from shared cwd, environment, QApplication, QSettings, and R temporary state.

## Next Audit Work

- Replace estimated runtime classes with measured durations.
- Identify duplicate GUI coverage after tests move into lane directories.
- Mark text assertion tests for rewrite or removal during packaging contract cleanup.
