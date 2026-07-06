# Use RCMetaR R Package Artifact Names

RCMetaR package metadata and build scripts should produce normal R package artifacts using the maintained package identity, such as `RCMetaR_0.1.0.tar.gz` for the first rebranded development release. Scripts, tests, packaging assertions, and manifests should not expect `OpenMetaR_*` or `openmetar_*` artifact names.

This keeps R package build outputs aligned with the private bundled RCMetaR identity.

