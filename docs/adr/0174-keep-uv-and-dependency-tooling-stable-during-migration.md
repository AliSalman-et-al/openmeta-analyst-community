# Keep uv and Dependency Tooling Stable During Migration

RC MetaStudio should keep `uv` and the current dependency tooling during the identity, `.rcms`, RCMetaR, and repository layout migration. Project metadata and package settings should be updated for the new package layout, but package-manager or test-runner changes should be deferred unless required for the migration to work.

This keeps tooling risk separate from the rename and layout work.

