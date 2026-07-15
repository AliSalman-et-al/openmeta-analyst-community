# Treat Pickle Project Storage as Transitional

Status: superseded by ADR-0252

The initial `.rcms` migration may preserve the current pickle-based serialized project content shape so the identity and layout migration stays mechanical. Pickle should not be treated as the long-term RC MetaStudio project-file format because it is fragile across module renames and unsafe for untrusted files.

A later project-file workstream should design a versioned structured format before RC MetaStudio makes strong long-term file-format stability claims.
