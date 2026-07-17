# Native R Binary Dependency Evidence

RC MetaStudio installs normal R dependencies from the dated Public PPM snapshot
recorded in `RCMetaR-r-dependencies.json`. Windows x64, macOS Intel, and macOS
Apple Silicon must each produce one cold-cache and one warm-cache run before the
binary policy is accepted for release packaging.

Every run must retain the `RCMS_R_BINARY_EVIDENCE` log records emitted by the
shared installer. The policy record names R architecture, `.Platform$pkgType`,
the exact repository and resolved binary contribution URL, provider, and
snapshot. The binary-package record lists all 54 required ordinary packages as
binary, and the binary-closure record lists every additional resolved package
that must also come from the native binary index.
The sole source-exception record must name HSROC 2.1.9, the canonical CRAN
Archive URL and pinned SHA256, and `type=source`, `repos=NULL`, and
`dependencies=FALSE`.

A cold run is valid only when binary-index preflight succeeds for the complete
hard dependency closure and installation logs contain `type=binary` for normal
packages. Missing binaries, R-version drift, architecture drift, package-type
drift, repository drift, or source fallback fail the run. A warm run must reuse
the target-specific cache and still emit and validate the policy, binary
package, installed/loadable package, and HSROC source-exception summaries.
Caches must never cross `windows-x64`, `macos-x64`, or `macos-arm64`.

The dated snapshot fixes the version graph but not immutable package bytes.
Release qualification therefore promotes the already-built artifact and keeps
the final artifact digest plus the existing bundled-library load and Mach-O
relocation evidence. Local Windows verification exercises the policy and
regression seams; native macOS acceptance requires hosted cold and warm runs on
both runner architectures.
