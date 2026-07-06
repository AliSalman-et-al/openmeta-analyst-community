# Separate Identity Migration from Codebase Reorganization

The RC MetaStudio identity migration should be completed as a distinct workstream before broad codebase reorganization. The identity workstream renames product, package, API, file-format, documentation, tests, manifests, scripts, packaging, and user-facing surfaces to RC MetaStudio, RCMetaR, `rcmetar.*`, and `.rcms` while preserving Analysis Behavior.

After that compiles and passes the rebased verification suite, structural reorganization should proceed around deeper modules and explicit seams. Keeping these workstreams separate makes regressions diagnosable: failures during the identity migration are not mixed with behavior changes from moved modules or redesigned interfaces.

