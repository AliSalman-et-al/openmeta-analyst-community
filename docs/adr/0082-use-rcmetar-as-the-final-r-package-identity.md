# Use RCMetaR as the Final R Package Identity

The final maintained R package identity for RC MetaStudio will be `RCMetaR`, superseding earlier ADRs that targeted `OpenMetaR` as the post-modernization package name. Legacy `OpenMetaR` and `openmetar` references should remain only where they describe historical provenance, compatibility fixtures, migration evidence, or legacy API behavior; current package identity, source folders, package load calls, generated artifacts, tests, docs, manifests, and packaging assertions should move to `RCMetaR`.

