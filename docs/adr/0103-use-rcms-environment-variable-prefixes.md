# Use RCMS Environment Variable Prefixes

RC MetaStudio should rename product-scoped environment variables from `OMA_*` to `RCMS_*` during the identity migration. Scripts, tests, CI workflows, packaging, documentation, and runtime configuration should use the new prefix without preserving supported fallback reads from the old OpenMeta[Analyst] namespace.

Temporary unshipped migration tooling may read legacy names only when needed to convert repository-owned fixtures, but maintained runtime and developer workflows should expose RC MetaStudio configuration through `RCMS_*`.

