# Migrate PyQt Signals by Compatibility Slice

PyQt4 old-style signal and slot usage will be migrated incrementally as needed by each compatibility slice instead of rewritten globally at the start of the port. Signal behavior is tied to table updates, dirty-state tracking, analysis triggers, and GUI workflow state, so a broad rewrite could introduce silent behavior changes that are hard to attribute.

Each migrated signal path should be covered by the workflow or model behavior that required the migration.
