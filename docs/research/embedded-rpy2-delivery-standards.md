# Standards for shipping embedded R through rpy2

**Status:** Research recommendation, 18 July 2026  
**Scope:** RC MetaStudio, Python 3.11, PyQt6, PyInstaller, in-process rpy2, Windows x64, macOS Intel x64, and macOS Apple Silicon arm64  
**Decision constraint:** Keep rpy2 as the Python-to-R integration layer.

## Executive recommendation

Keep the in-process rpy2 architecture. Distribute it as three independently built and qualified native products, each containing:

1. the PyInstaller **onedir** application;
2. a private, immutable CRAN R runtime at a fixed bundle-relative location;
3. a private, immutable R package library assembled from locked binary archives wherever binaries exist;
4. an rpy2 CFFI **API-mode** bridge built for the exact Python ABI, R release, operating system, and CPU architecture; and
5. a machine-verifiable manifest covering provenance, hashes, native dependencies, architectures, deployment targets, licenses, and signing state.

Do not use a system R installation, Homebrew, Conda, XQuartz, Rtools, a compiler, user-installed R packages, or network package installation at application runtime. Do not put this payload in a PyInstaller onefile executable. Treat the complete R/rpy2 payload as a versioned native subsystem of the application, not as data that PyInstaller can discover automatically.

The preferred release architecture is:

```text
official CRAN runtime + locked package archives + pinned rpy2 source
                              |
                              v
             target-native R integration-kit build
       (win-x64 | macos-x64 | macos-arm64; exact hashes)
                              |
                              v
              PyInstaller onedir application assembly
                              |
                              v
             closure audit -> smoke -> sign -> notarize
                              |
                              v
                    immutable release artifact
```

This conclusion supersedes the recommendation in `embedded-r-delivery-architecture.md` to make an `Rscript` worker the end-state architecture. A Python helper process using rpy2 could remain a future responsiveness or crash-containment option, but replacing rpy2 is neither required nor recommended for the current port. The existing non-X11 macOS runtime profile remains valid and complementary.

## Why this is the best fit

### rpy2 is viable, but it is part of the native ABI

rpy2 does not turn R into an ordinary pure-Python dependency. `rpy2-rinterface` embeds R and crosses a C boundary; consequently its reliable unit of compatibility is the tuple:

```text
Python ABI + rpy2-rinterface + R + operating system + CPU architecture
```

The release process should build and qualify that tuple together. Updating only R, only rpy2, or only Python invalidates the integration-kit qualification and requires rebuilding all three target kits.

R's embedding manual imposes constraints that a desktop application must make explicit: R must be initialized only once, its home and library search paths must be established before loading the shared library, `LC_NUMERIC` must remain `C`, and embedded R has principally been designed and tested on the main thread. On Windows, the loaded `R.dll` must match the headers and import library used at build time. These are product invariants, not CI conveniences. [R extension manual: embedding R under Unix-alikes](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Embedding-R-under-Unix_002dalikes), [threading issues](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Threading-issues), [calling `R.dll` directly](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Calling-R_002edll-directly)

### Use CFFI API mode for the release bridge

rpy2 supports two CFFI approaches:

- **ABI mode** uses C declarations at runtime and dynamically opens R's shared library.
- **API mode** uses a compiled CFFI extension generated against R's headers and libraries.

rpy2 3.6.6 changed Windows selection to prefer API mode and fall back to ABI mode, aligning Windows with other platforms. Its own source selects `_rinterface_cffi_api` for API mode and `_rinterface_cffi_abi` for ABI mode. [rpy2 change log](https://rpy2.github.io/doc/latest/html/changes.html), [rpy2 `openrlib.py`](https://github.com/rpy2/rpy2/blob/master/rpy2-rinterface/src/rpy2/rinterface_lib/openrlib.py)

For distributable, signed applications, API mode is the stronger standard:

- it moves header/API compatibility to a controlled target-native build step;
- it permits a bridge artifact to be qualified against the exact staged R runtime;
- it fails during build or load rather than silently accepting a broadly compatible declaration set; and
- on macOS it uses CFFI's `extern "Python"` callback mechanism rather than old-style runtime-generated callback trampolines.

The final point matters to hardened runtime. rpy2's callback source uses CFFI `def_extern()` in API mode and runtime `ffi.callback()` wrappers in ABI mode. CFFI documents that those old-style ABI callbacks on macOS can require the `com.apple.security.cs.allow-unsigned-executable-memory` entitlement, and recommends API-mode `extern "Python"` callbacks instead. Apple treats such entitlements as hardened-runtime exceptions. Therefore an API-only bridge offers the better path to a normally hardened, notarized application without weakening code-signing policy. [rpy2 callback implementation](https://github.com/rpy2/rpy2/blob/master/rpy2-rinterface/src/rpy2/rinterface_lib/callbacks.py), [CFFI callback documentation](https://cffi.readthedocs.io/en/release-1.15/using.html#callbacks-old-style), [Apple hardened-runtime exception guidance](https://developer.apple.com/documentation/security/resolving-common-notarization-issues)

This is a forward-looking change to RC MetaStudio's current contract. The repository presently sets `RPY2_CFFI_MODE=ABI`, excludes `_rinterface_cffi_api` from the macOS PyInstaller build, and makes the macOS inspector reject the API extension. Those controls should not simply be removed. Replace them together with an API-only build, dependency-relocation rules, fail-closed inspection, and packaged hardened-runtime tests.

The qualified wheel should be built from the pinned `rpy2-rinterface` source distribution on each target, with the staged release R selected during compilation. The released application should include `_rinterface_cffi_api` and reject `_rinterface_cffi_abi`; otherwise rpy2's fallback can conceal a broken API build. Record the bridge's build inputs and native imports in the integration-kit manifest.

API mode does not eliminate dynamic linking. On macOS, rewrite the API extension's `libR` dependency to the canonical app-relative `R.framework` location and audit it with `otool`. On Windows, register the private R DLL directories before importing rpy2 and audit the extension's PE imports. The bridge and the runtime remain one qualified unit.

If release timing forces temporary ABI-mode use, qualify it as an explicit exception. Test the actually signed application under hardened runtime on clean Intel and Apple Silicon machines, inspect its entitlements, and do not claim normal hardened-runtime compatibility merely because an unsigned CI build launches. ABI mode should not remain the long-term packaging standard.

## Build and artifact architecture

### Build a reusable R integration kit per target

Create one content-addressed integration-kit artifact for each target:

```text
r-integration-kit/
  runtime/                 # R or R.framework payload
  library/                 # locked, read-only R package library
  wheels/                  # exact rpy2 bridge wheel(s)
  manifest.json            # versions, sources, hashes, ABI and policy
  native-dependencies.json # complete PE or Mach-O closure
  licenses/                # R, rpy2, packages, native dependencies
  sources.json             # corresponding-source and build provenance
```

Its cache/promote key should include at least:

- exact R version and official installer SHA-256;
- exact Python implementation and ABI;
- exact `rpy2`, `rpy2-rinterface`, and `rpy2-robjects` versions;
- operating system, architecture, and deployment target;
- R-package lock digest and exact package-archive hashes;
- R runtime-profile version, including the non-X11 macOS policy;
- integration-kit builder revision; and
- toolchain identity for packages or bridges compiled from source.

Build the kit once, test it directly, and promote it by digest. Ordinary PyInstaller builds should download that exact artifact rather than reinstalling R packages. This makes R acquisition and package compilation independent of application assembly, shortens release feedback loops, and prevents a package repository from changing the output beneath the same nominal dependency list.

### Clear ownership boundaries

Use these ownership rules:

| Concern | Owner |
|---|---|
| Obtain and verify official R | Integration-kit builder |
| Resolve/install locked R packages | Integration-kit builder |
| Compile HSROC, RCMetaR, or another source-only package | Integration-kit builder on the native target |
| Build API-mode rpy2 bridge | Integration-kit builder on the native target |
| Collect Python, PyQt6, Qt, and rpy2 Python modules | PyInstaller |
| Insert the qualified R runtime/library/bridge | Final app assembler |
| Rewrite and validate native dependencies | Final app assembler |
| Sign nested code, sign app, notarize/staple | Final app assembler, after every mutation |

PyInstaller's contributed rpy2 hook declares hidden Python imports; it does not make the external R installation a portable, policy-qualified runtime. Explicit integration-kit ownership is still required. [PyInstaller rpy2 hook](https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/master/_pyinstaller_hooks_contrib/stdhooks/hook-rpy2.py)

### Use onedir, never onefile for this product

PyInstaller onefile applications extract bundled support files to a temporary directory on every launch. PyInstaller also discourages combining onefile and a macOS `.app` bundle, and current macOS bundles rely on symlinks in their onedir layout. Embedded R needs stable relative paths, preserved framework links, inspectable native code, predictable signing, and a writable area separate from the runtime. Onedir is therefore the appropriate product format. [PyInstaller operating mode](https://pyinstaller.org/en/stable/operating-mode.html), [macOS app bundle guidance](https://pyinstaller.org/en/stable/usage.html#building-mac-os-x-app-bundles), [spec-file documentation](https://pyinstaller.org/en/latest/spec-files.html)

## Runtime acquisition and package installation

### Start from official CRAN distributions

Prefer official CRAN binaries over a custom R build:

- **macOS:** acquire the architecture-specific signed/notarized CRAN installer, verify its hash and signing identity, and extract the `R-fw.pkg` payload into staging. Do not copy a mutable `/Library/Frameworks/R.framework` from a build machine.
- **Windows:** acquire and hash the official x64 installer, then perform an unattended install into a disposable staging directory using the installer's documented `/VERYSILENT`, `/DIR`, and `/COMPONENTS` switches. A basic R for Windows installation is relocatable.

This retains the CRAN build configuration and toolchain that Posit package binaries target. Homebrew or Conda R would add a different prefix, toolchain, and dependency model; Posit explicitly cautions that its macOS and Windows binaries are intended for CRAN R and might not work with alternative R distributions. [CRAN R for macOS](https://cran.r-project.org/bin/macosx/), [R for Windows FAQ](https://cran.r-project.org/bin/windows/base/rw-FAQ.html#Installation-and-Usage), [Posit binary-serving documentation](https://docs.posit.co/rspm/admin/serving-binaries.html)

A custom R build is justified only if a required OS deployment floor cannot be met by CRAN's distribution and the project accepts permanent ownership of the compiler, SDK, Fortran runtime, configuration flags, reproducibility, security updates, and corresponding-source obligations.

### Use Posit Public Package Manager binaries, with immutable promotion

For CRAN packages, use an explicit dated Posit Public Package Manager snapshot and the correct target binary repository. Posit builds Windows and macOS packages using the same toolchains and system libraries as CRAN and supports Windows x86_64 plus macOS x86_64 and arm64. Require the expected binary package type and fail if the resolver selects source, except for an explicit, reviewed exception such as HSROC or the local RCMetaR package. [Posit binary-serving documentation](https://docs.posit.co/rspm/admin/serving-binaries.html)

A dated snapshot URL is a resolution input, not sufficient artifact identity. Posit may rebuild binaries for security reasons. Download each archive once, record its repository URL and package metadata, calculate its SHA-256, and promote the exact bytes into the integration kit or a controlled artifact store. The final manifest—not a future repository response—is the release source of truth.

Build source-only exceptions once per target inside the integration-kit workflow. Record the source archive hash, compiler and SDK, configure arguments, build log, produced file hashes, and complete native closure. Do not build them during each PyInstaller job.

### Make the embedded library hermetic

At application launch:

- set `R_HOME` to the canonical private runtime before any rpy2 import;
- set `.libPaths()`/`R_LIBS` to the private, read-only library only;
- suppress site and user profiles and user environment files as product policy;
- reject or ignore ambient `R_HOME`, `R_LIBS`, `R_LIBS_USER`, and user package trees in a frozen build;
- retain `RCMS_R_HOME`/`RCMS_R_LIBS` overrides only for explicit development and test modes;
- provide writable `HOME`, temp, cache, and application-data locations outside the installed bundle; and
- initialize with quiet/no-save/no-restore/no-startup options before importing `rpy2.robjects`.

The runtime must never install, update, or load arbitrary R packages during normal use. Updates replace the whole signed application atomically.

## In-process lifecycle and Qt integration

### Initialization contract

Create one bootstrap seam that runs before any direct or transitive rpy2 import. It should:

1. identify the frozen app root without consulting system R;
2. validate the integration-kit manifest, architecture, and required files;
3. set R home, library, locale, startup, temp, and DLL-search policy;
4. register Windows DLL directories or establish macOS app-relative native resolution;
5. set and verify API-only CFFI mode;
6. import and initialize rpy2 exactly once on the Qt GUI/main thread; and
7. expose an immutable runtime identity for probes and diagnostics.

Fail with a user-actionable product error if any invariant is violated. Never fall back to a system R, a different bridge mode, or a user library.

RC MetaStudio already configures bundle-relative R paths before importing `rpy2.robjects`, which is the correct ordering. The hardened version should stop using ambient paths as frozen-runtime candidates, stop defaulting to ABI mode, set startup isolation explicitly, and verify the loaded R and bridge identities rather than only the configured strings.

### Main-thread and serialization contract

R's main-thread limitation and rpy2's lock solve different problems. rpy2's `rlock` and RC MetaStudio's `threading.RLock` prevent overlapping entry; neither makes it supported to call R from arbitrary `QThread` workers. [rpy2 low-level interface](https://rpy2.github.io/doc/latest/html/rinterface.html), [R threading issues](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Threading-issues)

For the current in-process design:

- initialize and call R only on the Qt GUI/main thread;
- serialize the **entire logical analysis operation**, including callbacks, conversions, graphics-device use, and cleanup—not just individual `ro.r(...)` calls;
- add a fail-closed thread-identity assertion at the common R gateway;
- prohibit nested Qt event loops or background callbacks that can re-enter R; and
- document that long analyses block the GUI until a separately designed execution architecture is adopted.

If responsiveness later becomes unacceptable, a helper **Python process that still uses rpy2** is a valid evolution. It would require a typed request/result protocol and intentional plot/file transfer. That is a product design change, not a packaging prerequisite and not a reason to replace rpy2 now.

### Events and shutdown

R and GUI event loops are difficult to mesh; do not allow embedded R to install or control a separate GUI event loop. Remove the Tcl/Tk and X11 surfaces on macOS and use the application's Qt UI plus non-interactive R graphics output. The R embedding manual discusses platform-specific event processing and warns that embedded front-ends own this integration. [R extension manual](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Embedding-R-under-Unix_002dalikes)

Use one explicit shutdown policy. rpy2 warns that ending embedded R is irreversible; R cannot subsequently be initialized successfully in the same process. Prevent `q()`/`quit()` from analysis code, stop accepting R work during application shutdown, close graphics devices and temporary resources on the main thread, then either call rpy2's `endr()` exactly once from controlled application teardown or deliberately rely on process exit if qualification proves that safer. Do not rely on arbitrary Python finalizer order. Repeated launch/analyze/exit stress tests should decide between those two policies. [rpy2 embedded-R lifecycle](https://rpy2.github.io/doc/latest/html/rinterface.html)

## Platform-specific standards

### macOS Intel and Apple Silicon

Ship separate thin artifacts. Do not create a universal2 application by merging independently built R, Python, Qt, and package binaries. Build and test x86_64 on a native Intel runner and arm64 on a native Apple Silicon runner. GitHub currently offers `macos-15-intel` and arm64 `macos-15` hosted labels. [GitHub Actions runner images](https://github.com/actions/runner-images#available-images), [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)

Use this canonical placement and preserve the framework's versioned symlink topology:

```text
RC MetaStudio.app/
  Contents/
    MacOS/RC MetaStudio
    Frameworks/R.framework/
      Versions/<major.minor>/Resources/
      Resources -> Versions/Current/Resources
      R -> Versions/Current/R
```

Profile out only product-prohibited optional surfaces, then compute native closure again. RC MetaStudio's researched non-X11 profile removes:

1. `Resources/library/tcltk/`
2. `Resources/modules/R_X11.so`
3. `Resources/modules/R_de.so`
4. `Resources/library/grDevices/libs/cairo.so`

Do not bundle XQuartz. Do not treat a path discovered in an optional module that the product has excluded as a required runtime dependency.

Recursively inspect every Mach-O file in the application, including Qt plugins, Python extensions, rpy2, `R.framework`, and R-package shared objects. For each file, verify:

- the one expected architecture only;
- deployment target no newer than the product floor;
- a canonical install ID where applicable;
- all non-system imports resolve inside the application;
- no `/opt/R`, `/opt/X11`, Homebrew, Conda, build-workspace, or `/Library/Frameworks/R.framework` path remains; and
- exactly one canonical `libR.dylib` payload exists.

Rewrite allowed internal dependencies with `@rpath`/`@loader_path` references before signing. Distinguish scripts and symlinks from Mach-O files before invoking `lipo`, `otool`, or `install_name_tool`.

After all mutation, sign nested code from the inside out with the same Developer ID team identity, then sign the outer app with hardened runtime and a secure timestamp. Apple library validation permits Apple-signed code or code signed by the same Team ID; re-signing the complete private Python/Qt/R/rpy2/package closure makes `com.apple.security.cs.disable-library-validation` unnecessary. Do not use `codesign --deep` as the signing algorithm; use strict deep verification after correct inside-out signing. Submit the final artifact for notarization and staple the ticket. [Apple bundle placement](https://developer.apple.com/documentation/bundleresources/placing-content-in-a-bundle), [embedding nonstandard code](https://developer.apple.com/documentation/xcode/embedding-nonstandard-code-structures-in-a-bundle), [code-signing in depth](https://developer.apple.com/library/archive/technotes/tn2206/), [notarizing macOS software](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution), [library-validation entitlement](https://developer.apple.com/documentation/BundleResources/Entitlements/com.apple.security.cs.disable-library-validation)

#### Deployment-floor conflict requiring a product decision

As of this research date, CRAN R 4.6.1 for Apple Silicon requires macOS 14 or later, while its Intel build requires macOS 11 or later. Issue #343's macOS 13+ Apple Silicon claim is therefore incompatible with using the official R 4.6.1 arm64 runtime. The preferred honest choice is to raise the arm64 artifact's minimum to macOS 14. Alternatives are to pin an older CRAN R or own a custom R build; either changes the qualified runtime and must be evaluated against RCMetaR and package requirements. [CRAN R for macOS](https://cran.r-project.org/bin/macosx/)

PyInstaller recommends building on the oldest macOS version that must be supported because its bootloader and collected binaries inherit compatibility constraints. Independently validate each release artifact on the oldest claimed OS, not only on the current hosted runner. [PyInstaller macOS notes](https://pyinstaller.org/en/stable/usage.html#making-macos-apps-forward-compatible)

### Windows x64

Place the relocatable private runtime at a fixed path next to the onedir application payload, for example `RC MetaStudio/R`. Never query the Registry or accept a system `R_HOME` in a frozen release.

Before importing the API bridge, use Windows' secure DLL-search facilities. Call `SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_DEFAULT_DIRS)` where compatible and retain handles returned by Python's `os.add_dll_directory()` for the minimum required private directories, including R's x64 binary directory and any explicitly bundled package/vendor DLL directory. Prefer this over broad `PATH` mutation, and never depend on the current working directory. Microsoft recommends `SetDefaultDllDirectories` plus `AddDllDirectory` to reduce DLL preloading risk. [Microsoft DLL security](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-security), [DLL search order](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order), [`SetDefaultDllDirectories`](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-setdefaultdlldirectories)

Recursively inspect every PE file for x64 architecture and a closed import graph. Reject Rtools/MSYS2/build paths, unexpected DLLs, duplicate `R.dll`, and dependencies that resolve only on the CI runner. Allow only documented Windows system DLLs outside the application. Test on a clean Windows host without R, Rtools, Git/MSYS2, or compilers installed.

Official R 4.6 uses the Universal C Runtime; supported Windows 10/11 hosts provide it. The R embedding manual also calls out stack-size requirements and recommends an active-code-page UTF-8 manifest for modern Windows front-ends. Preserve the application's UTF-8 manifest and include deep/recursive R calls in packaged stress tests. [R for Windows FAQ](https://cran.r-project.org/bin/windows/base/rw-FAQ.html#Installation-and-Usage), [calling `R.dll` directly](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Calling-R_002edll-directly)

Windows signing can remain deferred under the current product decision, but the artifact and manifest format should reserve signing identity/timestamp fields and the pipeline should support Authenticode signing without changing package contents afterward. Microsoft's SignTool supports signing, timestamping, and verification. [SignTool documentation](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)

## Native dependency closure

Package metadata alone cannot prove closure because an R package or extension may load a library lazily. Use all three layers:

1. **Declared package closure:** recursively resolve R `Depends`, `Imports`, and `LinkingTo` from the lock.
2. **Static native closure:** recursively inspect every Mach-O load command or PE import until only application-owned files and a small OS-system allowlist remain.
3. **Dynamic feature probes:** on clean hosts, execute every native-heavy product surface, especially graphics, network meta-analysis, HSROC, serialization, and packages known to use optional or delayed loading.

The closure report should record each native object's relative path, owner, SHA-256, architecture, deployment target, install ID, direct imports, resolved destination, and signing identity. Fail on unresolved or ambiguous dependencies. Do not copy every library from a build host as a substitute for dependency analysis.

## Required qualification matrix

Every target must pass the following against the final assembled artifact, not merely against source or the integration kit:

### Provenance and identity

- official installer signature/hash and exact source URL recorded;
- exact R and R-package archive hashes recorded;
- exact Python, PyQt6, Qt, rpy2 component, R, and package versions observed at runtime;
- integration-kit digest embedded in the application evidence;
- loaded `R_HOME`, `libR`/`R.dll`, bridge mode, and library paths resolve inside the application;
- API extension present, ABI extension absent, and no fallback accepted.

### Hermetic launch

- clean host with no R, package library, compiler, XQuartz, or Rtools;
- poisoned environment containing fake system/user R paths and profiles;
- offline launch and representative analysis;
- install path with spaces and non-ASCII characters;
- read-only installed application with writable user temp/data directories.

### In-process behavior

- initialization occurs exactly once on the main thread;
- common gateway rejects a worker-thread call;
- concurrent UI actions cannot overlap R operations;
- callbacks, conversion, errors, interrupts, plotting, and cleanup stay serialized;
- representative binary, continuous, diagnostic, meta-regression, network, and HSROC analyses match golden outputs;
- project save/reopen and `.rcms` samples preserve results;
- locale tests retain `LC_NUMERIC=C` and Unicode paths/data;
- repeated launch, analyze, close, and relaunch tests expose teardown/finalizer defects.

### Native and platform policy

- recursive native closure and one-architecture policy pass;
- no external build/install prefixes and one canonical R shared library;
- oldest claimed OS passes the complete smoke suite;
- macOS non-X11/Quartz graphics policy passes without XQuartz;
- macOS `codesign --verify --deep --strict`, Gatekeeper assessment, hardened-runtime launch, and—once credentials exist—notarization/stapling pass;
- signed macOS artifacts contain no `allow-unsigned-executable-memory`, `disable-library-validation`, or other unexplained exception entitlement.

## Security, updating, and licensing

Treat the private R runtime and package library as executable code:

- install them read-only and sign/hash them;
- never execute code from user libraries or write into the bundled library;
- do not download or install packages at runtime;
- update R, rpy2, and R packages only through a rebuilt, fully requalified, atomically replaced application;
- retain an SBOM and source/build provenance for incident response; and
- rebuild all three targets when a native dependency receives a security update.

R is distributed under GPL-2 or GPL-3, and current rpy2 metadata declares GPL-2.0-or-later; RC MetaStudio's GPL-3.0-or-later license is compatible at that level. Each release should include R and rpy2 license texts, third-party notices, each R package's `DESCRIPTION` license information and license file, and an inventory of bundled native libraries. Preserve or offer the corresponding source and the scripts/patches needed to reproduce modified GPL-covered binaries. Review every R package and native dependency for additional license conditions; obtain legal review for any restrictive or unclear package. [R licensing](https://www.r-project.org/Licenses/), [R `license()` documentation](https://search.r-project.org/R/refmans/base/html/license.html), [rpy2 package metadata](https://pypi.org/project/rpy2/)

## Recommended migration sequence for RC MetaStudio

### Stage 0: finish the current unsigned qualification honestly

- Keep the current in-process rpy2 behavior and non-X11 runtime profile while the existing macOS x64/arm64 packaging issues are stabilized.
- Fix closure tooling by classifying files before native inspection and by calculating closure only after optional surfaces have been removed.
- Treat ABI mode as a temporary release exception, not the final hardened-runtime standard.
- Resolve the Apple Silicon OS-floor conflict explicitly before advertising support.

### Stage 1: extract integration-kit production

- Move official R acquisition, Posit binary resolution, source-only package builds, runtime profiling, and native-closure generation into one target-native workflow.
- Promote immutable, hash-addressed kits for Windows x64, macOS x64, and macOS arm64.
- Make PyInstaller assembly consume only promoted kit digests.

### Stage 2: migrate the bridge contract to API-only

- Build pinned `rpy2-rinterface` API-only wheels against each exact staged R.
- Update bootstrap to require API mode before any rpy2 import.
- Update PyInstaller collection and deployment inspectors to require `_rinterface_cffi_api` and reject ABI fallback.
- Relocate and audit the API extension's R dependency.
- Add main-thread assertions, whole-operation serialization, startup isolation, and loaded-runtime identity probes.

### Stage 3: release hardening

- Validate the exact final artifacts on the oldest supported OS and clean machines.
- Sign the complete macOS native closure inside-out with one Team ID, then notarize and staple.
- Add Windows Authenticode signing later without changing the artifact architecture.
- Promote a release only when all target-specific evidence refers to the same source revision, lock digest, and product-version manifest.

## Decision summary

| Decision | Standard |
|---|---|
| Python/R integration | Keep in-process rpy2 |
| PyInstaller format | Onedir |
| R source | Official architecture-specific CRAN distribution |
| R package source | PPM binary snapshot, exact archives promoted by hash |
| Source-only exceptions | Build once per target in integration-kit workflow |
| rpy2 CFFI mode | Target-native API-only release bridge |
| Runtime discovery | Fixed app-relative path; no system fallback |
| R calls | Initialize once and execute on Qt main thread; serialize whole operations |
| macOS deliverables | Separate thin x64 and arm64 apps; preserve `R.framework` |
| Apple Silicon floor with R 4.6.1 | macOS 14+, unless R choice/build strategy changes |
| Optional macOS GUI dependencies | Exclude Tcl/Tk, X11, and XQuartz surfaces per product profile |
| Windows DLL loading | Restricted `AddDllDirectory` search; no current-directory/system-R reliance |
| Signing | Mutate first, sign nested code inside-out, outer app last, then notarize |
| Updates | Whole-app immutable rebuild and replacement |

The essential standard is not merely “bundle R.” It is to ship a closed, platform-native, cryptographically identified R/rpy2 subsystem whose build inputs and runtime behavior are inseparable from the application release.
