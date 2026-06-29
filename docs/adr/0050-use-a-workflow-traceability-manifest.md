# Use a Workflow Traceability Manifest

The Full Legacy App Port should use a committed `docs/modernization/workflow-traceability.json` file to map every Release Cutover workflow from the User-Facing Workflow Inventory to its compatibility evidence.

Each workflow entry should have a stable ID and trace to one of: a Golden Coverage Matrix row, GUI Verification Evidence entry, documented omission, Compatibility Exception, or GUI Compatibility Exception. Compatibility Exception and GUI Compatibility Exception references should point to committed exception manifests. Pending entries are allowed while the Comprehensive Golden Baseline gate is still open, but the gate is not satisfied until every Release Cutover workflow has a non-pending trace.

This keeps the "all existing features except Network Meta-Analysis" scope machine-checkable. Prose-only traceability would allow inventory items to drift away from golden coverage and GUI evidence without CI noticing.

The first CI enforcement step should validate that the manifest exists, contains every Release Cutover workflow, and has internally valid trace targets. Once the Comprehensive Golden Baseline gate is ready to close, CI should reject pending trace entries for behavior-changing full-port PRs.
