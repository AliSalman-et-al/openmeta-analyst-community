# Split Modern CI verification from packaging

Supersession note: Issue #244 supersedes the active workflow, script, cache, artifact, and local command names in this ADR. Current maintained names use evidence-lane language such as smoke, fast, package, r-stack, analysis-regression, and verification instead of `modern-*` labels.

The Modern CI Path will separate the Fast Verification Lane used on pull requests and pushes from the Packaging Lane that produces full PyInstaller distributables. This keeps ordinary development feedback focused on deterministic source verification while reserving the slower R runtime bundling, packaged smoke checks, ZIP creation, and artifact upload work for manual, release, or packaging-relevant runs.

The Smoke Verification Lane should run before the broader Fast Verification Lane and fail quickly on broken collection, manifest sanity, representative compatibility parsing, project-load compatibility, and Default R Evidence prerequisites. The Fast Verification Lane then proves source correctness through locked Python dependency sync, manifest validation, modern pytest coverage, and OpenMetaR R Stack verification. It does not run PyInstaller, assemble a bundled R runtime, install bundled R libraries into an artifact tree, run packaged smoke checks, create distributable ZIPs, or upload distributable artifacts except when a packaging-relevant change explicitly opts into the Packaging Lane.

Local development should also default to the Fast Verification Lane. Full packaging remains available through an explicit opt-in command or flag so developers do not pay PyInstaller, R runtime assembly, packaged smoke, ZIP creation, and artifact-upload-equivalent costs during normal source verification.

The Fast Verification Lane has a Fast Feedback Budget of under ten minutes on GitHub and under two minutes locally after dependencies are warm. Checks that cannot meet this budget should move out of the default lane unless they are required release evidence. This target follows current fast-feedback testing guidance such as DORA's test-automation capability, while the lane's locked inputs, cache keys, and pinned workflow actions follow modern reproducibility and supply-chain guidance from uv, GitHub Actions, SLSA, OpenSSF Scorecard, and Reproducible Builds practices.

R Stack verification should split into Default R Evidence and Full R Stack Evidence. Default R Evidence belongs in the Fast Verification Lane; the existing full verifier behavior, including broad R dependency installation, `R CMD build`, `R CMD check`, analysis smoke coverage, installed-version validation, and real rpy2 bridge tests, belongs in an opt-in, scheduled, release, or packaging-gated lane.

The Packaging Lane should run on explicit manual requests, release/tag events, and path-aware packaging triggers. Packaging-relevant paths include PyInstaller scripts, local workflow scripts, R dependency installation and verification scripts, Python lock/configuration files, GitHub workflow packaging logic, `src/R/**`, packaging entry points such as `src/launch.py`, bundled sample data, and bundled documentation.

GitHub should expose the split as separate workflows rather than one large workflow with many gated jobs: a default `modern-fast` workflow for the Fast Verification Lane and a `modern-package` workflow for Packaging Lane and Full R Stack Evidence. This keeps required checks and workflow intent visible in the GitHub UI.

Local scripts should use lane-named entry points such as `verify-modern-smoke`, `verify-modern-fast`, `verify-modern-r-stack-full`, and `package-modern-*`. The old `run-modern-workflow-local.*` wrapper-style entry points should be retired rather than preserved as compatibility wrappers.

The first packaging reproducibility target is deterministic process and artifact layout rather than byte-for-byte identical distributables. Packaging should use the same locked inputs, package policy, artifact contents, stable metadata where practical, and explicit documentation of known non-determinism; byte-identical ZIPs are not important for the next milestone and can be reconsidered only after timestamp, ZIP ordering, PyInstaller, R package, and provenance controls are designed.

The Fast Verification Lane should be no-network by default except for trusted CI setup and cache restoration. Broad external dependency downloads, especially CRAN/R package installation, belong in Full R Stack Evidence or Packaging Lane where cache misses and registry behavior are visible instead of hidden inside ordinary pull-request feedback.

Packaging should cache dependency inputs rather than assembled outputs. Good caches include uv packages keyed by `uv.lock`, R package libraries keyed by R version and R dependency policy hash, and PyInstaller cache only where invalidation is explicit; assembled app directories, dist/work trees as trusted outputs, and final ZIP files should be rebuilt cleanly.

R package acquisition should use an explicit CRAN Repository Policy rather than a hard-coded default mirror. R Dependency Cache keys should include the R runtime version, R dependency policy, package metadata, and repository policy so faster mirrors or package-manager-backed repositories can be used deliberately without stale cache reuse.

Windows remains the only default Packaging Lane target for now. macOS Intel packaging stays manual opt-in, and macOS arm64 remains experimental/manual until Windows packaging is fast, clean, deterministic, and the modern test taxonomy is under control; macOS scripts should still be improved through a researched, platform-specific cleanup path.

macOS packaging should first produce explicit unsigned/ad-hoc architecture-specific `.app` ZIP artifacts with clean layout assertions and smoke checks. Developer ID signing, hardened runtime entitlements, notarization through Apple's `notarytool`, stapling, and secret handling belong to a separate future release stage rather than the current CI packaging cleanup.

Developer documentation should replace the old single local workflow with a lane command matrix. Daily work should point to `verify-modern-fast`; R Stack changes should point to full R Stack verification; packaging/release changes should point to package scripts; macOS package commands should remain explicit manual architecture-specific invocations.
