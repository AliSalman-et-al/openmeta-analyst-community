# Keep Platform Scope Stable During Migration

Status: superseded by ADR-0240

RC MetaStudio should keep the current CI and release platform scope stable during the identity, `.rcms`, RCMetaR, and repository layout migration. Workflow names, artifact names, bundle identifiers, and docs should be renamed, but the set of release-gated platforms should not change as part of this migration.

Platform expansion or support-policy changes should be handled in a later release-planning workstream.
