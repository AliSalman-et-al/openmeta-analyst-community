# Native macOS R package binaries for CI and packaging

## Decision summary

For R 4.6.1 on both supported macOS architectures, RC MetaStudio should install
every normal CRAN dependency with `install.packages(..., type = "binary")` and
must fail when the current architecture's binary repository cannot satisfy the
request. The preferred normal-package repository is a tested, dated snapshot
from **Posit Public Package Manager (Public PPM)**. It currently serves native
R 4.6 binaries for every one of the 54 packages in RC MetaStudio's explicit
normal CRAN set on both Intel and Apple Silicon, and Posit's snapshot pipeline
publishes a snapshot only after its binaries are ready.

`HSROC 2.1.9` remains the sole source-build exception. Public PPM mirrors its
source but does not currently expose an R 4.6 macOS binary for either
architecture. Prefer the canonical CRAN Archive tarball and its pinned digest;
using Public PPM for that same source offers no compilation-time benefit and
serves a repacked archive with different bytes.

This recommendation does not require `pak`, `setup-r-dependencies`, or a
self-hosted Posit Package Manager server. The existing
`r-lib/actions/setup-r` step installs the official architecture-specific CRAN
build of R 4.6.1; that runtime selects the matching binary repository through
`.Platform$pkgType`.

## Primary-source findings

### R 4.6.1 has separate native package repositories

CRAN publishes distinct R 4.6.1 installers and package-binary trees for the two
architectures:

| Runner target | Official R build | `.Platform$pkgType` | CRAN binary path |
| --- | --- | --- | --- |
| `macos-15-intel` / x86_64 | Big Sur x86_64 | `mac.binary.big-sur-x86_64` | `bin/macosx/big-sur-x86_64/contrib/4.6` |
| `macos-15` / arm64 | Sonoma arm64 | `mac.binary.sonoma-arm64` | `bin/macosx/sonoma-arm64/contrib/4.6` |

CRAN's macOS page identifies the R 4.6.1 arm64 installer as requiring macOS 14+
and the Intel installer as requiring macOS 11+, and links separate Sonoma-arm64
and Big-Sur-x86_64 package directories. The R for macOS maintainer documents
`mac.binary.sonoma-arm64` for R 4.6 arm64 and states that the Intel build keeps
the `mac.binary.big-sur-x86_64` setup. [CRAN R for macOS](https://cran.r-project.org/bin/macosx/),
[R for macOS build configurations](https://mac.r-project.org/)

R's administration manual says that `type = "binary"` is supported by the
official CRAN macOS build, that macOS binary archives use `.tgz`, and that
`.Platform$pkgType` supplies the platform/build-specific repository selector.
Binary repositories are laid out under `bin/macosx/<build>/contrib/<R major.minor>`.
Consequently the installer should use `type = "binary"`, not hard-code a
directory: the installed R runtime owns the architecture mapping.
[R Installation and Administration: macOS binary packages](https://cran.r-project.org/doc/manuals/r-release/R-admin.html#macOS-packages),
[R `install.packages` documentation](https://stat.ethz.ch/R-manual/R-devel/library/utils/help/install.packages.html)

GitHub's runner-image inventory confirms that `macos-15-intel` is x64 while
`macos-15` is arm64. These fixed labels are preferable to `macos-latest` for
this release contract. [GitHub Actions runner images](https://github.com/actions/runner-images#available-images)

On 2026-07-17, the official CRAN `PACKAGES.gz` indexes for both R 4.6 binary
trees contained all 54 non-base/non-recommended package names explicitly listed
by `scripts/install-r-deps.R`. Availability is time-sensitive, so CI must still
perform the preflight on every cold cache rather than encode this observation
as a permanent assumption:

- [R 4.6 Sonoma arm64 binary index](https://cran.r-project.org/bin/macosx/sonoma-arm64/contrib/4.6/PACKAGES.gz)
- [R 4.6 Big Sur x86_64 binary index](https://cran.r-project.org/bin/macosx/big-sur-x86_64/contrib/4.6/PACKAGES.gz)

### Public PPM is viable for all normal dependencies

The [Posit Package Manager binary-serving documentation](https://docs.posit.co/rspm/admin/serving-binaries.html)
describes the commercial/self-hosted product, not only the free hosted service.
It says Package Manager builds CRAN binaries during its daily snapshot process,
rebuilds `LinkingTo` dependents together, and publishes a snapshot only after
the binaries are available. For macOS it uses the same toolchains and system
libraries as CRAN, supports both x86_64 and ARM64, and supports the current R
minor series plus four previous series. Its R 4.6 binaries are built against
the oldest compatible R 4.6 patch and are intended to work with R 4.6.0 through
R 4.6.X, including this repository's R 4.6.1.

Public PPM is a free hosted instance of that product. Posit explicitly states
that it does not provide professional support for the public instance; a
self-hosted customer controls synchronization, curation, storage, availability,
and local/Git sources, while Public PPM users do not have those administrative
controls. [Posit Package Manager introduction](https://docs.posit.co/rspm/admin/),
[Posit Service Terms](https://posit.co/about/posit-service-terms-of-use)

Public PPM's live status API reported Package Manager 2026.06.0, binary support
enabled, macOS architectures `x86_64` and `arm64`, and supported R binary
series including 4.6. [Public PPM status API](https://packagemanager.posit.co/__api__/status)
For macOS, Posit says to use the same base repository URL as for sources;
standard R repository resolution and `.Platform$pkgType` select the native
binary subtree. [Posit: using Windows and macOS binary packages](https://docs.posit.co/rspm/admin/serving-binaries.html#using-windows-and-macos-binary-packages)

Exact base URLs are:

- moving repository: `https://packagemanager.posit.co/cran/latest`;
- dated repository: `https://packagemanager.posit.co/cran/<YYYY-MM-DD>`;
- evaluated snapshot: `https://packagemanager.posit.co/cran/2026-07-16`.

With `type = "binary"`, R 4.6.1 resolves those bases to:

- arm64: `<base>/bin/macosx/sonoma-arm64/contrib/4.6`;
- Intel: `<base>/bin/macosx/big-sur-x86_64/contrib/4.6`.

Live checks on 2026-07-17 found all 54 explicitly listed normal packages in
both Public PPM `latest` binary indexes and in both indexes for the dated
2026-07-16 snapshot:

- [Public PPM R 4.6 Sonoma arm64 binaries](https://packagemanager.posit.co/cran/2026-07-16/bin/macosx/sonoma-arm64/contrib/4.6/PACKAGES.gz)
- [Public PPM R 4.6 Big Sur x86_64 binaries](https://packagemanager.posit.co/cran/2026-07-16/bin/macosx/big-sur-x86_64/contrib/4.6/PACKAGES.gz)

The live Public PPM and CRAN binary versions matched for 53 of the 54 packages.
The exception was `lme4`: Public PPM served `2.0-1` while CRAN served `2.0-6`
on both architectures. That is not a missing binary, and `2.0-1` is already the
version recorded by this repository's dependency manifest. It demonstrates
that Public PPM is a coherent package snapshot, not a byte-for-byte alias for
the current CRAN binary tree.

### Snapshots improve version reproducibility, not immutable bytes

Posit provides snapshots of public repositories every business day, excluding
weekends and holidays. A dated repository URL selects packages available at
that snapshot; if a requested date is not itself a snapshot, Package Manager
may resolve it to the nearest matching snapshot. The implementation should
therefore choose a date shown as available, record the resolved snapshot, and
not generate a URL mechanically from the build date.
[Posit: frozen repository URLs](https://docs.posit.co/rspm/user/get-repo-url.html#getting-frozen-urls-for-improving-reproducibility)

A dated snapshot fixes the package-version graph, but it is not an immutable
binary-content guarantee. Posit documents that it rebuilds packages, including
packages in historical snapshots, when critical security patches affect their
bundled libraries. macOS packages commonly bundle those libraries, so users
must reinstall to receive the rebuilt secure package. RC MetaStudio must retain
its build-once/promote-exact-bytes release model and record installed versions,
downloaded package hashes where available, and the final application artifact
digest. [Posit binary security](https://docs.posit.co/rspm/admin/serving-binaries.html#cran-binary-security)

### Public PPM cannot eliminate the HSROC source build

The Public PPM source mirror serves HSROC at
`https://packagemanager.posit.co/cran/latest/src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz`,
and its public package API records HSROC 2.1.9 as archived, compiled code, and
dependent on `lattice`, `coda`, `MASS`, and `MCMCpack`.
[Public PPM HSROC metadata](https://packagemanager.posit.co/__api__/repos/cran/packages/HSROC)

However, on 2026-07-17:

- HSROC was absent from both Public PPM R 4.6 macOS binary indexes, including
  the 2019-09-21 snapshot where Public PPM's history says 2.1.9 became current;
- the Public PPM binary API returned no binary record for R 4.6 on either
  x86_64 or arm64;
- direct candidate archived-binary URLs returned 404.

This is consistent with Posit's stated **best-effort** policy for archived
package binaries and its coverage of up to four years of historical releases.
HSROC 2.1.9 is now older than that historical window. The supported outcome is
still one source compilation.

Public PPM's served source archive is not byte-identical to CRAN's archive.
On 2026-07-17 it had SHA-256
`98bb0a2b2f49973240e008996f5381e0dac37e46bb08f037895719453dbe91f6`
and size 2,033,525 bytes, while the canonical CRAN archive had SHA-256
`5476fa76d7723717e203925a1da442813e3645790ef9b633a145cbc04a08b874`
and size 2,023,525 bytes. Both contained the same 89 paths and reported HSROC
2.1.9, but the different archive bytes mean the sources are not interchangeable
under a content-pin policy. Public PPM's metadata reports the upstream CRAN
checksum, not the SHA-256 of the repacked bytes served by its archive URL.
Keeping the canonical CRAN tarball is therefore the clearer provenance choice.

### Self-hosted Package Manager would be a separate infrastructure decision

A self-hosted Posit Package Manager instance could cache package files,
control synchronization, curate CRAN, run air-gapped, and supplement local or
Git sources with organization-built macOS binaries. It cannot add custom
binaries to its CRAN source, so making HSROC a maintained local source/binary
would require a separate local-source policy rather than transparently filling
the CRAN archive. [Posit: local and Git binaries](https://docs.posit.co/rspm/admin/serving-binaries.html#local-and-git-binaries)

That operational and licensing expansion is unnecessary for the immediate CI
problem. Public PPM plus the existing GitHub Actions library cache obtains the
normal-package speed benefit without deploying package infrastructure. Revisit
self-hosting only if the project later requires controlled uptime, internal
packages, organization-managed binary provenance, or air-gapped builds.

### Provider comparison

| Concern | Official CRAN macOS binaries | Public PPM macOS binaries | Self-hosted Package Manager |
| --- | --- | --- | --- |
| Cold-build speed | Removes normal-package compilation; network time remains | Same fundamental binary speedup; no evidence justifies claiming downloads are always faster than CRAN | Same binary speedup; local/network placement can be optimized by the operator |
| Current RC MetaStudio coverage | All 54 normal packages on both architectures on 2026-07-17 | All 54 normal packages on both architectures in `latest` and the 2026-07-16 snapshot | Depends on the instance's sync/configuration; can consume the same Posit-built CRAN binaries |
| Cross-package consistency | CRAN publishes architecture repositories, but a source release may lead its binary | Daily snapshot waits for the snapshot's binaries and rebuilds `LinkingTo` dependents together | Same Posit snapshot capability, under administrator-controlled synchronization |
| Version reproducibility | Requires an external snapshot/pinning mechanism | Business-day dated snapshots pin the version graph, but security rebuilds can change bytes | Curated/frozen repositories and retained content are administrator-controlled, subject to the chosen retention policy |
| Provenance | Direct CRAN-distributed binaries | Posit-built from CRAN sources with CRAN-compatible macOS toolchains; adds Posit as build/distribution authority | Adds the organization's server/configuration plus Posit's package-service/build provenance |
| Availability/support | CRAN mirror ecosystem; no project-specific support | Free hosted service; Posit states no professional support | Licensed/operated service with deployable HA, support, storage, and air-gap options |
| HSROC 2.1.9 | Canonical source archive available; no current binary | Repacked source available; no R 4.6 macOS binary found | Could model HSROC as a separate local source and upload organization-built binaries, but cannot add them to the CRAN source |

Both CRAN and Public PPM eliminate the dominant compilation cost. Public PPM's
material advantage for this repository is coherent, date-addressable binary
sets; it is not a proven per-download bandwidth advantage. The recommended
balance is Public PPM for all normal binaries, canonical CRAN for the one
pinned archive source, and the existing architecture-specific cache for warm
runs.

### `type = "both"` is not strict enough

The default on a CRAN macOS R build is `type = "both"`. R first considers a
binary but can install source when no binary exists or when the source is newer.
That is precisely the fallback that causes the current long builds. Explicit
`type = "binary"` restricts the operation to binaries matching the current R
build. `options(install.packages.check.source = "no")` suppresses comparisons
against a newer source release; `options(install.packages.compile.from.source =
"never")` is useful defense-in-depth but governs `type = "both"` and is not a
substitute for passing `type = "binary"`.
[R `install.packages`: binary packages](https://stat.ethz.ch/R-manual/R-devel/library/utils/help/install.packages.html),
[R options used by package installation](https://stat.ethz.ch/R-manual/R-devel/library/base/help/options.html)

`install.packages()` can report unavailable packages by warning rather than by
throwing a reliable error for every shape of request. A strict CI installer
should therefore preflight against `available.packages(type = "binary")` and
stop with the package names and `contrib.url(..., type = "binary")` before
calling the installer. It should also assert that every requested package is in
the target library afterward.

### HSROC remains the single source exception

CRAN's archive lists `HSROC_2.1.9.tar.gz` as the newest HSROC release. The
tarball's `DESCRIPTION` declares `NeedsCompilation: yes` and dependencies on R,
`lattice`, `coda`, `MASS`, and `MCMCpack`. The four package dependencies must
therefore be present before the archive install; `lattice` and `MASS` come with
the recommended R library, while `coda` and `MCMCpack` are in RC MetaStudio's
normal CRAN binary set. [CRAN HSROC archive](https://cran.r-project.org/src/contrib/Archive/HSROC/)

Install the archive only after the binary phase:

```r
utils::install.packages(
  "https://cran.r-project.org/src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz",
  lib = lib,
  repos = NULL,
  type = "source",
  dependencies = FALSE
)
```

The source tarball downloaded on 2026-07-17 had SHA-256
`5476fa76d7723717e203925a1da442813e3645790ef9b633a145cbc04a08b874`.
The implementation should record and verify that digest before installation so
the exception is content-pinned, not merely URL- and version-pinned. It should
continue to verify the installed version is exactly `2.1.9`.

## Repository diagnosis

There are two different causes in the current branch:

1. `scripts/verify_rcmetar_r_default.py:336` explicitly chooses `"source"`
   for every non-Windows host. The macOS source compilation is intentional in
   the generated R snippet, not a CRAN mirror or runner defect.
2. `scripts/install-r-deps.R:45-52` chooses `c("binary", "source")` whenever
   `.Platform$pkgType` is not `"source"`, and lines 60-88 retry unresolved
   packages using the next type. On macOS this silently converts any missing
   normal binary into a source build.

The package installer already separates HSROC at
`scripts/install-r-deps.R:105-125`, and the default-evidence verifier separately
models its CRAN dependencies and archive install at
`scripts/verify_rcmetar_r_default.py:293-356`. The change should preserve these
seams and make the normal-package phase strict rather than introduce a new
dependency manager.

The workflows already isolate caches by architecture and R version:

- `.github/workflows/fast-verification.yml:161-165` keys default-evidence
  libraries by matrix target, R 4.6.1, and dependency-policy hashes.
- `.github/workflows/package-target.yml:52-56` keys bundled libraries by archive
  platform, resolved R version, repository key, and policy hashes.
- `scripts/build-macos-package.sh:443-450` adds an inner cache key derived from
  R version, the installer, dependency manifest, package DESCRIPTION, and CRAN
  repository.

Changing `scripts/install-r-deps.R` already invalidates these caches through
the file hash. Nevertheless, bumping the human-readable cache generations
(`r-default-evidence-v1` and `bundled-r-library-v3`) makes the policy transition
obvious and prevents restore-key changes elsewhere from reviving a library
populated under the source-fallback policy.

The manifest is stale in one relevant respect:
`docs/verification/RCMetaR-r-dependencies.json:4-8` still names R 4.6.0 while
the workflows install R 4.6.1. Its current `latest-compatible` CRAN policy also
does not distinguish latest compatible *binary* on macOS from latest source.

## Recommended implementation contract

Use one shared R policy in both `scripts/install-r-deps.R` and the R snippet
generated by `scripts/verify_rcmetar_r_default.py`. On macOS, `repo` should be
the selected, tested Public PPM snapshot base (for example the evaluated
`https://packagemanager.posit.co/cran/2026-07-16`), while HSROC retains its
separate canonical CRAN Archive URL:

```r
expected_macos_pkg_type <- switch(
  R.version$arch,
  x86_64 = "mac.binary.big-sur-x86_64",
  aarch64 = "mac.binary.sonoma-arm64",
  stop("Unsupported macOS R architecture: ", R.version$arch)
)

if (identical(Sys.info()[["sysname"]], "Darwin")) {
  if (getRversion() != "4.6.1") {
    stop("macOS binary policy requires R 4.6.1, found ", getRversion())
  }
  if (!identical(.Platform$pkgType, expected_macos_pkg_type)) {
    stop("Unexpected macOS R binary type: ", .Platform$pkgType)
  }
}

options(
  repos = c(CRAN = repo),
  timeout = 600,
  install.packages.check.source = "no",
  install.packages.compile.from.source = "never"
)

missing <- required[!vapply(required, installed_in_target_or_runtime, logical(1))]
binary_db <- utils::available.packages(repos = repo, type = "binary")
unavailable <- setdiff(missing, rownames(binary_db))
if (length(unavailable)) {
  stop(
    "Required CRAN binaries unavailable from ",
    utils::contrib.url(repo, type = "binary"),
    ": ", paste(unavailable, collapse = ", ")
  )
}

if (length(missing)) {
  utils::install.packages(
    missing,
    lib = lib,
    dependencies = NA,
    type = "binary"
  )
}
```

The production version should compute and validate the full hard-dependency
closure from the binary database (or let the binary install resolve it and
fail, followed by a complete installed-package assertion), not only preflight
the top-level vector. Base and recommended packages already supplied by the R
runtime should be accepted only after `requireNamespace()`/version checks.

Then:

1. Verify `lattice`, `coda`, `MASS`, and `MCMCpack` load from the combined
   target/runtime library paths.
2. Download HSROC to a file, verify its SHA-256, and install that local file
   with `repos = NULL, type = "source", dependencies = FALSE`.
3. Assert HSROC version `2.1.9`, all required namespaces, and the expected
   machine architecture.
4. Emit `.Platform$pkgType`, `R.version$arch`, the binary `contrib.url`, and a
   clear `binary`/`source-exception` package summary into CI logs/evidence.

### Manifest changes

Update `docs/verification/RCMetaR-r-dependencies.json` to:

- set the target R runtime to `4.6.1`;
- define the macOS policy as Public PPM's native CRAN-package binaries only for
  normal packages;
- record Public PPM as the normal-package provider and the exact tested
  snapshot URL/date rather than the moving `latest` alias;
- record both expected macOS package types/repository layouts;
- mark HSROC as the sole `source_exception` with URL, version, SHA-256, and
  declared dependency names;
- distinguish an expected package version from an observed version. CRAN may
  publish a newer source before its macOS binary; the accepted macOS version is
  the newest compatible binary in the architecture-specific index.

The verifier should read this policy rather than duplicate the HSROC URL,
version, dependencies, and new digest in Python literals.

### Workflow and cache changes

- Keep `r-lib/actions/setup-r@v2` pinned as it is. Its documentation states
  that it downloads/caches the selected R version and sets an isolated
  `R_LIBS_USER`; it does not install application dependencies. Set
  `use-public-rspm: true` on the macOS jobs so the action's R profile and
  `RSPM`/`RENV_CONFIG_REPOS_OVERRIDE` environment agree with the chosen
  provider. The option defaults to false on macOS and true on x86_64 Windows
  and Linux.
  [setup-r documentation](https://github.com/r-lib/actions/tree/v2/setup-r)
- Do not rely on that action input alone. `scripts/install-r-deps.R` currently
  replaces the global repository option with `RCMS_CRAN_REPO`, and
  `verify_rcmetar_r_default.py` passes its own repository argument. Set those
  explicitly to the chosen Public PPM snapshot, or refactor them to consume one
  manifest-owned repository policy. The setup action's source sets Public PPM
  to `https://packagemanager.posit.co/cran/latest`; a dated project policy must
  override that moving alias.
  [setup-r implementation](https://github.com/r-lib/actions/blob/v2/setup-r/dist/index.js)
- Keep the existing application-controlled library caches and architecture
  separation. Do not share an Intel library with arm64 or a Sonoma-arm64
  library with Big-Sur-arm64.
- Bump the cache generation once when the policy lands. Continue hashing the
  installer, manifest, DESCRIPTION, R version, repository identity, and target
  architecture. Change `RCMS_CRAN_REPO_KEY` from `cloud-r-project-org` to a
  value that includes Public PPM and the snapshot identifier.
- The `setup-r-dependencies` action is not needed here. It uses static `pak`
  builds and provides its own dependency cache for both x86_64 and arm64 macOS,
  but adopting it would duplicate the custom bundle cache and require encoding
  the archived HSROC exception in a second package-resolution system.
  [setup-r-dependencies documentation](https://github.com/r-lib/actions/tree/v2/setup-r-dependencies)

## Risks and required evidence

- **Binary publication lag:** Public PPM's coherent snapshots reduce the normal
  source-before-binary race, but Posit still documents cases where a package
  has no supported binary. The job should fail with the missing binary name
  instead of compiling; keep using the last accepted dated snapshot until a
  replacement snapshot satisfies both architectures.
- **Hosted-service dependency:** Public PPM is free and professionally
  unsupported. Preserve architecture-specific GitHub caches, make repository
  failures explicit, and keep a reviewed fallback procedure to the equivalent
  official CRAN binary snapshot/index rather than silently switching origins
  during a release build.
- **Snapshot mutability:** a dated Public PPM URL pins versions but Posit may
  rebuild binary bytes for security fixes. Record the snapshot, package
  versions, and final artifact digest; promote the already-built artifact
  rather than rebuilding a release from the same URL later.
- **Architecture/OS drift:** R 4.6 arm64 uses Sonoma binaries, while Intel uses
  Big Sur binaries. Assert the package type in the job so Rosetta or a wrong R
  installer cannot silently produce a mixed bundle.
- **Relocation:** CRAN macOS binaries can contain native libraries built against
  the official architecture-specific toolchain and `/opt/R/<arch>` ecosystem.
  The existing Mach-O relocation and packaged-library checks must still inspect
  every bundled R package, reject unresolved build-host paths, and run from the
  extracted distributable. The R for macOS maintainer explicitly separates
  `/opt/R/arm64` and `/opt/R/x86_64`. [R for macOS build configurations](https://mac.r-project.org/)
- **HSROC still compiles:** a C compiler remains required for the one exception.
  Remove the current Homebrew/`Makevars` provisioning only after a cold build
  proves HSROC compiles and all binary packages load without it; binary
  installation alone does not prove packaged dynamic-library closure.
- **Cache provenance:** a cache hit hides install logs. Record policy version,
  R version, package type, architecture, repository, and installed package
  versions in evidence, and validate a scheduled or manually triggered cold
  cache on both architectures.

Acceptance evidence should include one cold and one warm run for Intel and
arm64. Cold logs must show binary installs for every normal CRAN package and one
source install for HSROC only; warm runs must prove the architecture-scoped
cache is reused. The evidence must also name the Public PPM snapshot and prove
the binary preflight found all 54 normal packages on both architectures. Both
extracted macOS artifacts must pass the existing R namespace/load probes and
Mach-O relocation checks.
