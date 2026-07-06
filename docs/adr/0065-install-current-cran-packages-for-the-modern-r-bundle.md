# Install Current CRAN Packages for the Modern R Bundle

The modern R dependency installer should stop installing archived CRAN package versions for the `openmetar` R Stack modernization slice. It should install the latest CRAN package versions compatible with the target R 4.6.0 runtime, while handling bundled local packages such as `HSROC` separately.

Archive pins such as `metafor 1.9-9`, `igraph 1.0.1`, and `lme4 1.1-12` were useful for preserving Reference Implementation behavior, but they directly conflict with the modernization goal of validating `openmetar` against current CRAN package behavior.
