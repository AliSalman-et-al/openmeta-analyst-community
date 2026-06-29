# Rename Openmetar After the Modern Behavior Baseline

The package rename from `openmetar` to `OpenMetaR` should happen after the current R Stack modernization is stable, the Modern Behavior Baseline exists, and the Reference Implementation has been retired as the active oracle. The rename should then update the package identity, source folder, package load calls, dynamic discovery strings, tests, packaging assertions, docs, and manifests, followed by re-verifying or re-capturing the Modern Behavior Baseline under the new name.

Doing the rename after the baseline transition avoids juggling three package identities at once: Reference Implementation `openmetar`, modernized lowercase `openmetar`, and final `OpenMetaR`.
