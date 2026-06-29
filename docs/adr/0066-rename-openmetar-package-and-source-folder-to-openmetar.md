# Rename Openmetar Package and Source Folder to OpenMetaR

After the `openmetar` R Stack modernization work is stable, the bundled R package should be renamed to `OpenMetaR` as its actual R package identity, not only as display text. The rename includes the `DESCRIPTION` `Package:` field, source folder name, install/build artifacts, package load calls, dynamic `package:` discovery strings, Python R loader naming, packaging assertions, tests, docs, and manifests.

The rename is deliberately a final slice after package modernization because R package names are case-sensitive in practical use: `library(OpenMetaR)`, installed library paths, and package discovery strings must all agree on the new spelling.
