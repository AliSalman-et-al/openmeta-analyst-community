# Embedded R delivery architecture for RC MetaStudio

**Research date:** 2026-07-18  
**Scope:** PyQt6/PyInstaller desktop application, RCMetaR and its R package
closure, Windows x64, macOS Intel x64, macOS Apple Silicon, and a future Linux
target.

## Recommendation

Do not try to put R *inside* the PyInstaller executable or ask PyInstaller to
discover R. Treat the released product as two independently assembled,
hash-addressed layers:

1. a PyInstaller **onedir** desktop layer that owns Python, PyQt6, Qt and the
   application; and
2. an app-owned, architecture-specific **R runtime layer** that is assembled
   before the desktop build from an official R distribution, the exact R
   package lock, licences, provenance and a complete native dependency
   manifest.

On macOS, place the R layer as a canonical nested
`Contents/Frameworks/R.framework`, keep scripts and non-code resources in their
standard framework resource locations, and sign the completed native inventory
inside-out before signing the outer app. Build and release separate Intel and
Apple Silicon artifacts. Do not create a universal2 R layer.

The strategic execution model should be a **short-lived R worker process per
analysis**, launched from the bundled R runtime with a versioned, framed
stdin/stdout protocol. The Qt process should not load `libR` and should
eventually stop shipping `rpy2`. This isolates R crashes, signals, native
libraries and cancellation from Cocoa/Qt, removes the rpy2/libR ABI from the
PyInstaller process, and makes the same backend boundary work on Windows,
macOS and Linux.

For the release currently gated by issues #342-#344, do **not** replace the
working analysis boundary at the last moment. Finish the current official-CRAN
framework product profile and qualification. Immediately after that release,
extract R assembly into a dedicated runtime-artifact workflow; then migrate
the analysis calls behind the process boundary. The current product profile is
a defensible release fix. The fragile part is rebuilding and modifying it as a
late side effect of every PyInstaller job, not the choice of official CRAN R.

## Why this is the right boundary

### PyInstaller owns Python and Qt, not R

PyInstaller freezes a Python interpreter and imported Python/native modules.
It is not a cross-compiler, and each platform must be built natively. Its
one-file mode extracts support files into a temporary directory at every run;
one-file macOS app bundles are explicitly discouraged, and current POSIX
bundles rely heavily on preserved symbolic links. An R installation is a
large, internally structured runtime with scripts, package metadata, shared
libraries, loadable modules and symlinks, so it is a poor one-file payload.
[PyInstaller operating modes](https://pyinstaller.org/en/stable/operating-mode.html),
[PyInstaller macOS and one-file guidance](https://pyinstaller.org/en/stable/usage.html#building-mac-os-x-app-bundles),
[PyInstaller symlink requirements](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#requirements-imposed-by-symbolic-links-in-frozen-application)

The repository's macOS spec already follows the correct collection boundary:
PyInstaller collects PyQt6/Qt and rpy2, while `scripts/build-macos-package.sh`
adds R later. The architectural improvement is to replace the mutable source
installation and late closure traversal with a previously qualified runtime
artifact. PyInstaller should consume only a runtime manifest and destination;
it should never resolve, install, prune or relocate R.

### An R worker is safer than in-process embedding

R documents embedding as an alternative-front-end API. On Unix-like systems
it requires a shared R build and careful `R_HOME` and library-path setup. R
also says embedded R is designed and tested in the main thread, and calls event
loop integration one of the hardest front-end problems. On Windows, direct
embedding must coordinate R's event processing with the GUI, use a sufficiently
large stack, match R.dll, and use UCRT/UTF-8 correctly.
[R Extensions: alternative front ends and Unix embedding](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Embedding-R-under-Unix_002dalikes),
[R Extensions: event-loop and threading constraints](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Threading-issues),
[R Extensions: Windows embedding](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Calling-R_002edll-directly)

rpy2 is specifically an interface to R embedded in the Python process. Its
ABI/API modes still require the compiled R and Python runtimes and place R's
lifecycle in the Qt process. The repository currently has extensive
R-object-to-Python conversion code and uses rpy2 ABI mode, so changing this is
a migration rather than a packaging flag.
[rpy2 overview and build modes](https://rpy2.github.io/doc/latest/html/overview.html),
[rpy2 project description](https://rpy2.github.io/)

A worker process uses R's supported `Rscript` front end instead. The operating
system becomes the isolation boundary:

- an R abort or native package crash cannot corrupt the Qt process;
- a hung analysis can be terminated as a process tree after a bounded grace
  period;
- R signals, stacks and event loops no longer contend with Cocoa/Qt;
- no `libR` or rpy2 native extension is loaded by the signed GUI executable;
- one request can be made reproducible with a clean process, `--vanilla`, a
  fixed package library and a private working directory; and
- the protocol can be tested against an unfrozen Python client, a frozen app,
  and the standalone R worker with identical fixtures.

The default should be one worker per analysis, not a persistent R server. The
few hundred milliseconds of startup are small relative to a statistical
analysis, while per-job isolation makes state leakage, cancellation and crash
recovery much simpler. A persistent worker can be added later only if measured
startup cost warrants it.

## The runtime artifact

Build one immutable artifact for each tuple:

`(R version, target OS, target architecture, OS floor/distribution,
R-package lock digest, runtime-policy version)`.

The artifact is an input to application assembly, not a cache that may be
silently refreshed. It should contain:

- the selected official R runtime payload;
- a single read-only application R library containing RCMetaR and the exact
  hard dependency closure;
- no compilers, headers used only for package compilation, package caches,
  user library, R.app/RGui, manuals or optional UI/device surfaces that the
  product does not expose;
- runtime launchers and a worker entry script;
- all license texts and generated third-party notices;
- source URLs and hashes sufficient to satisfy redistribution obligations;
- an SBOM-like file inventory with SHA-256, file kind, architecture, load
  commands/imports, install identity and owning component; and
- a signed provenance statement binding R, repository snapshot, package
  versions, source/binary classification, toolchain/runner and policy version.

The application assembly job must verify the artifact digest, re-run the
native dependency and architecture inspector, place it in the final product,
and sign it. It must not install packages or discover new native dependencies.

### macOS source and layout

Use the official architecture-specific CRAN installer as the upstream runtime
source and extract the `R-fw.pkg` payload into staging instead of installing R
globally and copying `/Library/Frameworks/R.framework`. CRAN publishes distinct
R 4.6.1 Intel and Apple Silicon packages. Tcl/Tk and Texinfo are optional
installer components, and X11/Tcl/Tk requires separately installed XQuartz.
[CRAN R for macOS](https://cran.r-project.org/bin/macosx/)

The official framework still contains dynamically loadable X11/Tcl/Tk
surfaces. RC MetaStudio's existing, researched product profile removes the
four unused surfaces and fails closed on upstream layout drift; retain that
policy in the runtime builder. Do not install or traverse XQuartz. See
`docs/research/macos-embedded-r-x11-runtime-policy.md` for the exact exclusion
and verification contract.

An app-owned framework is an upstream-supported build shape. R's build manual
says `--enable-R-framework` implies a shared R library, allows a non-default
framework prefix at configure or install time, and documents the CRAN
framework build. That does not make every third-party package automatically
relocatable; the runtime builder must still inspect all Mach-O files.
[R Administration: macOS frameworks](https://cran.r-project.org/doc/manuals/r-release/R-admin.html#Frameworks),
[R Administration: CRAN macOS build configuration](https://cran.r-project.org/doc/manuals/r-release/R-admin.html#Other-libraries)

Apple requires executable content to be placed in standard code locations:
frameworks and dynamic libraries under `Contents/Frameworks`, helper tools
under `Contents/MacOS` or `Contents/Helpers`, and scripts/data under
`Contents/Resources`. Incorrect placement can pass local development yet fail
distribution. Apple also recommends signing nested code inside-out and using
`--deep` for verification rather than discovery/signing.
[Apple: placing content in a bundle](https://developer.apple.com/documentation/bundleresources/placing-content-in-a-bundle),
[Apple TN2206: nested code and inside-out signing](https://developer.apple.com/library/archive/technotes/tn2206/)

Therefore the final macOS shape should be:

```text
RCMetaStudio.app/
  Contents/
    MacOS/RCMetaStudio                 # PyInstaller GUI executable
    Frameworks/
      ... PyQt6/Qt/Python code ...
      R.framework/                     # canonical, product-profiled framework
    Resources/
      rcms-r-worker.R                  # signed as a resource, not Mach-O code
      r-runtime-manifest.json
      third-party-notices/
```

The R worker executable may be the framework's normal `Rscript` launcher. The
GUI locates it by bundle-relative path, never `PATH`, the registry or a global
framework.

All Mach-O files and nested code should be signed with the application's
Developer ID identity and hardened runtime before the outer app is sealed.
Hardened-runtime library validation permits Apple libraries and libraries
signed with the same Team ID. Re-signing the final, relocated R/Qt/Python
inventory with the app's identity avoids the broad
`disable-library-validation` entitlement. Notarization requires Developer ID,
hardened runtime, secure timestamps and valid signatures for all executables.
[Apple library validation entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.disable-library-validation),
[Apple notarization requirements](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)

Continue separate Intel and arm64 artifacts. GitHub's fixed labels identify
`macos-15-intel` as x64 and `macos-15` as arm64; runner images change weekly,
so retain the exact image version in provenance.
[GitHub runner image architectures and cadence](https://github.com/actions/runner-images#available-images)

### Windows source and layout

Use the official CRAN Windows installer, install/extract it into a staging
directory with only the required component, add the locked application
library, then archive the resulting `R/` runtime layer. R's Windows FAQ says a
basic installation is relocatable and documents unattended `/DIR` and
`/COMPONENTS` installer options. The shipped GUI must use the app-relative
`R/bin/Rscript.exe`, not registry discovery.
[R for Windows FAQ: customization and portable use](https://cran.r-project.org/bin/windows/base/rw-FAQ.html#Installation-and-Usage)

The existing `R/` beside the PyInstaller onedir application is therefore the
right product layout. Move its creation and package installation out of
`build-windows-package.ps1` into the same immutable runtime-layer pipeline used
on macOS. Keep PE import closure and x64 checks. The worker process eliminates
the need for the PyInstaller executable to load R.dll or ship rpy2, but the R
worker and package DLLs still require deployment inspection.

### Linux target

Linux should not be described as one universal binary target. Choose and state
a glibc baseline/distribution, build natively for each architecture, and test
on the oldest supported image. PyInstaller intentionally does not bundle core
system libraries such as libc. Posit Package Manager's Linux binaries are
distribution-specific, and Posit recommends matching Posit R binaries for
best compatibility.
[PyInstaller operating modes and system libraries](https://pyinstaller.org/en/stable/operating-mode.html),
[Posit Package Manager binary distributions](https://docs.posit.co/rspm/admin/serving-binaries.html)

For a future Linux release, use a distribution-specific app image/container
format around the same two layers. Do not use a Linux R layer produced on one
distribution on another merely because both report x86_64. Keep Linux outside
the current three-artifact release gate, as issue #344 already specifies.

## Package acquisition and reproducibility

Keep the dated Posit Public Package Manager policy for normal packages. Posit
builds CRAN binaries as part of a snapshot, rebuilds `LinkingTo` dependents,
and publishes the snapshot only after binaries are ready. On macOS and Windows
it uses CRAN's toolchains and explicitly says those binaries are intended for
CRAN R, not alternative R distributions. PPM recommends a repository URL
frozen to a date for reproducibility.
[Posit: serving binaries](https://docs.posit.co/rspm/admin/serving-binaries.html),
[Posit: repository versioning](https://docs.posit.co/rspm/admin/repositories/)

Continue to fail rather than compile when a normal Windows/macOS binary is
missing. Keep HSROC as the named, hash-pinned source exception. Record package
archive hashes after download because a repository date pins the package view,
not necessarily every future byte served for a rebuilt security binary. Build
and promote the immutable runtime artifact once; do not reconstruct release
artifacts from a dated URL later.

For each R package, retain:

- name, version, source repository/snapshot and archive SHA-256;
- binary platform tag or named source exception;
- DESCRIPTION license expression and bundled license files;
- hard dependency edges (`Depends`, `Imports`, `LinkingTo`);
- native binary inventory and external runtime dependencies; and
- the source archive or durable equivalent download location.

## Worker protocol contract

Use a small, versioned protocol rather than exposing arbitrary R evaluation.
One practical contract is length-prefixed UTF-8 JSON control messages plus
files for tables, SVG/PDF and large results:

```json
{
  "protocol": 1,
  "request_id": "uuid",
  "operation": "binary_meta_analysis",
  "project_schema": 1,
  "input_path": "job/input.json",
  "output_dir": "job/output"
}
```

The worker returns structured progress and exactly one terminal result with
domain error codes, output paths, sizes and hashes. Requirements:

- launch a fixed app-relative Rscript with `--vanilla` and a fixed worker
  script; never invoke a shell;
- set `R_HOME`, `R_LIBS`, `R_LIBS_USER`, locale, timezone and a private writable
  temp/home directory explicitly;
- clear user startup files, inherited R package paths and package-manager
  environment variables;
- allow only named operations and schema-validated data; do not accept source
  strings to evaluate;
- use an application-owned job directory with atomic result publication;
- stream bounded progress/log records and cap individual message sizes;
- on cancellation, request cooperative shutdown, then terminate/kill the whole
  worker tree after fixed deadlines;
- delete abandoned scratch directories on next launch; and
- never update the embedded runtime or install packages on an end-user machine.

The Qt side can own this through `QProcess` without blocking the event loop.
RCMetaR should own the R operation implementations; the worker should be a thin
request dispatcher and serializer.

## Options considered

| Option | Strengths | Material problems | Decision |
| --- | --- | --- | --- |
| Copy the installed R framework during each app build, then discover/prune/relocate | Smallest immediate change; official CRAN/PPM compatibility | Host installation is mutable; late discovery repeatedly exposes optional components; app build mixes acquisition, package resolution, relocation and signing | Keep only to finish #342; replace with a pre-qualified runtime input |
| App-owned official `R.framework` runtime artifact | CRAN/PPM binary compatibility; canonical Apple code bundle; smallest toolchain ownership | Still needs a versioned product profile, Mach-O closure, re-signing and provenance | **Preferred runtime for macOS** |
| Extract official installer payload rather than install/copy | Deterministic component selection; no dependence on `/Library/Frameworks`; hashable upstream input | Installer layout can change and must fail closed | **Preferred acquisition method** |
| Build purpose-specific R from source | Can configure `--without-x`, omit R.app/Tcl/Tk and own the deployment prefix | Own compiler/SDK/Fortran/BLAS/security update chain; PPM says macOS binaries target CRAN R; likely forces a project binary repository or large source builds | Future option only if runtime minimization justifies permanent toolchain ownership |
| Conda/micromamba environment | Cross-platform solver, native dependency closure, explicit specs with checksums; conda-forge's macOS R recipe uses `--without-x` and no framework | Alternative R distribution is not PPM/CRAN-binary compatible; prefix relocation remains; nonstandard macOS code layout increases signing/notarization work; adds a second Python/Qt solver unless kept R-only | Do not adopt for the release product |
| `conda-pack` runtime | Replays conda relocation and can pre-rewrite a destination prefix | Build OS must match target, unpacked environments are not relocatable again, package cache is required, and signing still remains product-owned | Not superior to official R runtime artifacts here |
| `rig` | Excellent CI/developer installer for official R versions and both Mac architectures | Manages system installations, permissions, links, registry and user libraries; it does not create a redistributable app runtime | Use only as optional CI setup, not as payload builder |
| R-universe | Provides Windows/macOS binaries and useful independent package builds | Package repository, not an R runtime; adds another binary provenance and snapshot policy without solving signing/layout | Keep as fallback research source, not normal release origin |
| In-process rpy2 | Rich object conversion; existing implementation and tests | R lifetime/signals/event loop and libR ABI live in Qt process; crashes/hangs contaminate GUI; rpy2 native collection/signing is another coupled stack | Transitional only |
| Short-lived app-owned R worker | Crash/cancellation isolation; no libR/rpy2 in GUI; same boundary on every OS; clean per-job state | Requires a typed serialization boundary and migration of current rpy2 conversions | **Preferred strategic execution model** |
| Rserve/network service | Established out-of-process model | Larger protocol/auth/network surface than a local desktop worker; persistent state and lifecycle; unnecessary listening socket | Do not use; use private stdio IPC |
| universal2 macOS artifact | One download | Every Python, Qt, R and package native component must contain compatible dual slices; CRAN publishes separate R/package trees; doubles signing/inspection complexity | Continue separate x64 and arm64 artifacts |
| External user-installed R | Small artifact and no redistribution work | Version/architecture/package drift, poor first-run experience, global mutation, cannot meet #342-#344 complete-stack evidence | Control only; reject for release |

Conda's relocation is real but not magic: its own documentation says moving an
environment can break it, while `conda-pack` rebuilds relocation from cached
package sources and imposes same-OS and one-time-relocation constraints.
[conda-pack overview and caveats](https://conda.github.io/conda-pack/),
[micromamba explicit specifications](https://mamba.readthedocs.io/en/stable/user_guide/micromamba.html),
[conda-forge R build recipe](https://github.com/conda-forge/r-base-feedstock/blob/main/recipe/build-r-base.sh)

`rig` describes itself as an R installation manager and performs system/user
configuration. R-universe describes a package-binary service. Neither supplies
the app-owned, signed runtime boundary needed here.
[rig README](https://github.com/r-lib/rig),
[R-universe binary documentation](https://docs.r-universe.dev/install/binaries.html)

## Security, licensing and updates

R is distributed under GPL-2 or GPL-3, and rpy2 uses the same GPL-2-or-later
license. RC MetaStudio is already GPL-3 and RCMetaR declares GPL (>= 2), so the
recommended process boundary is motivated by reliability, not an attempt to
avoid the project's existing license. Binary distribution still needs a
complete, auditable license/source process for R, every R package and bundled
native library.
[R license terms](https://www.r-project.org/Licenses/),
[rpy2 license](https://rpy2.github.io/)

Publish beside every release:

- the app artifact and SHA-256;
- the exact runtime-layer manifest and digest;
- third-party notices and license texts inside the app and release assets;
- corresponding source archives, or equivalent durable access with clear
  directions, for GPL-covered binaries and modifications;
- the packaging/relocation/profile scripts used to produce the runtime; and
- a vulnerability/update inventory that maps every native file to its owning
  R package or upstream component.

Do not self-update the signed R layer in place. Updates should produce a new
runtime artifact, a newly assembled/signed/notarized app and a full
qualification result. On macOS no packaged byte may change after the inner-to-
outer signing pass.

## Verification and retained evidence

### Runtime-layer qualification

Run before PyInstaller application assembly:

1. Verify every upstream archive hash and the PPM snapshot/package lock.
2. Verify R version, architecture, OS floor and runtime-policy version.
3. Validate the complete hard dependency closure and source-exception allowlist.
4. Load every required namespace in a clean `Rscript --vanilla` process.
5. Run RCMetaR's package-native tests and representative analysis/artifact
   probes.
6. Inspect every PE/Mach-O/ELF file, its architecture, imports/load commands,
   install identity, unresolved paths and owning component.
7. Reject build-host paths, missing libraries, wrong architecture, duplicate
   identities and unexpected native files.
8. Emit the content manifest, license inventory, source map and runtime digest.

### Final application qualification

After combining the frozen desktop layer and runtime layer:

- verify both input digests and prove no undeclared file was added;
- repeat native architecture/dependency inspection from the extracted
  distributable;
- on macOS sign every nested Mach-O/bundle with the same identity, then the
  outer app; run `codesign --verify --deep --strict`, Gatekeeper assessment,
  notarization and stapling when credentials are available;
- launch only the user-facing executable, then have it launch the worker by its
  bundle-relative path;
- run the exact golden open/edit/analyse/result/SVG/save/reopen workflows;
- exercise worker cancellation, invalid requests, R errors, hard timeout,
  forced worker crash and app exit while analysis is running;
- prove the GUI stays responsive and can start a subsequent clean job after
  each failure mode; and
- retain runner/image identity, artifact hashes, manifests, logs and failure
  diagnostics.

### Update and reproducibility qualification

- one cold and one warm runtime build per architecture;
- byte/hash comparison where inputs and toolchain image are identical;
- rebuild-from-source drill for every GPL component;
- scheduled PPM binary-availability and security-refresh audit without changing
  the accepted release artifact; and
- periodic clean-machine launch with no global R, XQuartz, Homebrew, conda,
  registry entry or user R library.

## Migration plan

### Phase 0: complete the current release gate

1. Fix the current product-profile implementation defect and complete #342.
   Hosted run 29635438001 reached the explicit product-profile phase and failed
   because its evidence probe passed the framework's `Resources/R` shell
   launcher to `lipo`; this is a file-classification bug, not evidence that the
   official framework approach is untenable.
2. Qualify the same policy on arm64 for #343 and the three exact artifacts for
   #344.
3. Do not introduce conda, a custom R compiler, a worker protocol or a new
   packaging engine into this one-week release gate.

### Phase 1: make R a first-class build artifact

1. Create a dedicated `build-r-runtime` pipeline for Windows x64, macOS x64 and
   macOS arm64.
2. Download and hash the official R installers; extract to staging without
   mutating the runner's system R.
3. Install the locked PPM binaries and HSROC exception, apply the macOS product
   profile, relocate and inspect.
4. Emit immutable runtime archives, manifests, licences and provenance.
5. Change both package scripts to require an exact runtime artifact/digest and
   remove all package installation from the app build.

This immediately makes retries faster and turns optional upstream components
or package-native dependency drift into a runtime-builder failure rather than
an opaque late PyInstaller failure.

### Phase 2: introduce the backend protocol behind the existing interface

1. Define operation/result schemas from the calls currently exposed through
   `meta_py_r_backend.py`; use golden fixtures to lock semantics.
2. Add an R worker dispatcher that calls RCMetaR and serializes typed results.
3. Add a Python client implementing the existing backend interface via
   `QProcess`/stdio.
4. Run in-process rpy2 and worker backends against the same golden contract in
   CI until they are equivalent.
5. Switch packaged builds to the worker backend while retaining source tests
   for the old backend during one migration window.

### Phase 3: remove rpy2 from the release product

1. Remove rpy2 and its metadata/native extensions from PyInstaller specs and
   deployment manifests.
2. Remove the packaged R environment manipulation that exists only for
   in-process loading.
3. Add crash, cancellation and recovery evidence to all native package lanes.
4. Delete the old in-process backend only after all golden and packaged gates
   are green.

### Phase 4: Linux and future maintenance

1. Select the first supported Linux distribution/glibc floor and architecture.
2. Build a distribution-specific R layer from official/Posit R plus PPM
   binaries and qualify it with the same worker protocol.
3. Re-evaluate a project-built minimal R only if measured artifact size,
   security surface or unsupported upstream components justify owning the
   compiler and package-binary supply chain permanently.

## Decision checkpoints

Adopt the runtime-layer architecture now if all of these stay true:

- normal R packages remain available as CRAN-compatible PPM binaries;
- the product does not need Tcl/Tk/X11;
- separate native macOS downloads remain acceptable; and
- the official R framework can be relocated and signed without weakening
  library validation.

Escalate to a custom R build only if the official framework repeatedly exposes
required, unshippable dependencies after the optional product profile is
applied, or if a formal minimal-runtime/security requirement outweighs the
toolchain cost. Escalate to conda only if the product intentionally standardizes
its entire Python, R and native dependency supply chain on conda-forge; using
conda only to avoid understanding R.framework would replace one mixed supply
chain with two.

