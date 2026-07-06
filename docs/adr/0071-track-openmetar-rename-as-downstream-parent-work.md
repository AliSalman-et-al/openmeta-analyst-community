# Track Openmetar Rename as Downstream Parent Work

Retiring the Reference Implementation as the active oracle, rebasing analysis regression on a Modern Behavior Baseline, and renaming the package identity from `openmetar` to `OpenMetaR` should be tracked as a separate downstream parent issue rather than added to the current `openmetar` CRAN modernization parent.

The current parent focuses on modernizing the existing lowercase package against current CRAN dependencies. The rename and baseline authority shift depend on that work being stable, but they affect broader documentation, tests, packaging, CI authority, and runtime identity.
