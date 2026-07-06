# Keep R Runtime and Dependency Policy Stable During Migration

RC MetaStudio should keep the current R runtime and dependency policy stable during the identity, `.rcms`, RCMetaR, and repository layout migration. Updating R versions, CRAN dependency policy, or statistical package versions should be handled in a later R Stack workstream.

This preserves Analysis Behavior while the package and API identity changes from OpenMetaR/`openmetar.*` to RCMetaR/`rcmetar.*`.

