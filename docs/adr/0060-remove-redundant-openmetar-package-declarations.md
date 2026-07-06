# Remove Redundant Openmetar Package Declarations

The `openmetar` package metadata should declare only packages that `openmetar` directly needs at runtime, plus build/test/documentation dependencies where they are actually used. Historically declared packages that are not directly called by `openmetar` should be removed from `openmetar`'s `DESCRIPTION` instead of kept as defensive app-level bundle dependencies.

Broader R packages needed by the Windows distributable or future app workflows should be installed and verified through the app's R dependency installation and packaging scripts, not through inaccurate `openmetar` package metadata.
