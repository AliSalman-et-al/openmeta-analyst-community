# Split Modern CI verification from packaging

Supersession note: Issue #244 supersedes the active workflow, script, cache, artifact, and local command names in this ADR. Current maintained names use evidence-lane language such as smoke, fast, package, r-stack, analysis-regression, and verification instead of `modern-*` labels.

The Modern CI Path will separate the Fast Verification Lane used on pull requests and pushes from the Packaging Lane that produces full PyInstaller distributables. This keeps ordinary development feedback focused on deterministic source verification while reserving the slower R runtime bundling, packaged smoke checks, ZIP creation, and artifact upload work for manual, release, or packaging-relevant runs.

The local Smoke Verification command provides an optional quick preflight. The Fast Verification Lane proves source correctness through locked Python dependency sync, strict collection, manifest validation, fast and Golden pytest coverage, and Default R Evidence. It does not run PyInstaller, assemble a bundled R runtime, install bundled R libraries into an artifact tree, run packaged smoke checks, create distributable ZIPs, or upload distributable artifacts except when a packaging-relevant change explicitly opts into the Packaging Lane.

Local development should also default to the Fast Verification Lane. Full packaging remains available through an explicit opt-in command or flag so developers do not pay PyInstaller, R runtime assembly, packaged smoke, ZIP creation, and artifact-upload-equivalent costs during normal source verification.

The Fast Verification Lane has a Fast Feedback Budget of under ten minutes on GitHub and under two minutes locally after dependencies are warm. Checks that cannot meet this budget should move out of the default lane unless they are required release evidence. This target follows current fast-feedback testing guidance such as DORA's test-automation capability, while the lane's locked inputs, cache keys, and pinned workflow actions follow modern reproducibility and supply-chain guidance from uv, GitHub Actions, SLSA, OpenSSF Scorecard, and Reproducible Builds practices.

R Stack verification is split into Default R Evidence and Full R Stack Evidence. Default R Evidence belongs in the Fast Verification Lane. Full R Stack Evidence retains broad R dependency installation, `R CMD build`, `R CMD check`, analysis smoke coverage, installed-version validation, and real rpy2 bridge tests in one required, serialized Windows job so source changes cannot merge without deep statistical evidence.

The Packaging Lane should run on explicit manual requests, release/tag events, and path-aware packaging triggers. Packaging-relevant paths include PyInstaller scripts, local workflow scripts, R dependency installation and verification scripts, Python lock/configuration files, GitHub workflow packaging logic, `src/R/**`, packaging entry points such as `src/launch.py`, bundled sample data, and bundled documentation.

GitHub exposes source verification, Full R Stack Evidence, and path-gated package qualification as explicit jobs in the integration workflow. The final gate checks every classified job result, including classifier failure, so skipped work cannot produce a false green. Release artifact publication remains in separate workflows.

Local verification uses the single `scripts/verify.py` entry point (`smoke`,
`fast`, and `r-stack`) alongside the package commands. Platform-specific
wrapper scripts are retired rather than preserved as compatibility wrappers.

The first packaging reproducibility target is deterministic process and artifact layout rather than byte-for-byte identical distributables. Packaging should use the same locked inputs, package policy, artifact contents, stable metadata where practical, and explicit documentation of known non-determinism; byte-identical ZIPs are not important for the next milestone and can be reconsidered only after timestamp, ZIP ordering, PyInstaller, R package, and provenance controls are designed.

The Fast Verification Lane uses locked Python inputs and a pinned CRAN-compatible repository for Default R cache misses. Broad R dependency installation belongs in Full R Stack Evidence or the Packaging Lane, where cache misses and repository behavior are explicit.

Packaging should cache dependency inputs rather than assembled outputs. Good caches include uv packages keyed by `uv.lock`, R package libraries keyed by R version and R dependency policy hash, and PyInstaller cache only where invalidation is explicit; assembled app directories, dist/work trees as trusted outputs, and final ZIP files should be rebuilt cleanly.

R package acquisition should use an explicit CRAN Repository Policy rather than a hard-coded default mirror. R Dependency Cache keys should include the R runtime version, R dependency policy, package metadata, and repository policy so faster mirrors or package-manager-backed repositories can be used deliberately without stale cache reuse.

Package-relevant changes run Windows package qualification plus focused native macOS packaging contracts. Full native macOS Intel and Apple Silicon package workflows remain architecture-specific and retain their own evidence.

macOS packaging produces architecture-specific artifacts with clean layout assertions and smoke checks. Trusted release workflows own Developer ID signing, hardened runtime entitlements, notarization through Apple's `notarytool`, stapling, and protected secret handling.

Developer documentation uses a lane command matrix. Daily work points to `scripts/verify.py fast`; R Stack changes also run `scripts/verify.py r-stack`; packaging and release changes use the package commands; macOS package commands remain explicit architecture-specific invocations.
