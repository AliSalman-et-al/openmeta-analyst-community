# Track Openmetar R Stack Dependencies and Drift as Manifests

The `openmetar` R Stack modernization slice should produce machine-readable manifests for direct package dependencies and reviewed Statistical Modernization Drift. The dependency manifest should record each direct runtime, build, test, or documentation package, why it is needed, whether it is CRAN or bundled local code, and the installed version used for verification. The drift manifest should key reviewed output differences by workflow or result family and include the evidence required by ADR 0063.

These manifests give CI and future migration work a stable contract for package-version verification and prevent accepted statistical changes from becoming stale prose.
