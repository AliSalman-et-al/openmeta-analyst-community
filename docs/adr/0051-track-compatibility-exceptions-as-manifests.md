# Track Compatibility Exceptions as Manifests

Compatibility Exceptions and GUI Compatibility Exceptions should be tracked in committed machine-readable manifests as well as any human-readable summary.

The manifests should provide stable exception IDs, affected workflows, affected evidence or golden rows, reason, reviewer or approval reference, decision date, before and after behavior, and any expiry or follow-up. This lets CI validate Workflow Traceability Manifest references and prevents accepted differences from becoming informal notes.

Empty manifests are useful before exceptions exist because they establish the validation target. Adding an exception should be an explicit reviewed change, not an incidental test update.

Only accepted exceptions should satisfy workflow traceability or golden comparison gates. Each accepted exception must include `id`, `status`, `affected_workflows`, `reason`, `approved_by`, `approved_at`, `before_behavior`, `after_behavior`, and either `follow_up` or `expires_at`. Proposed or pending exceptions may be recorded, but they must not close compatibility gates.
