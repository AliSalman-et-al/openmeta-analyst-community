# Simplifying target-native R/rpy2 desktop packaging

**Status:** Research recommendation, 18 July 2026  
**Scope:** RC MetaStudio, PyQt6, PyInstaller onedir, in-process rpy2, Windows
x64, macOS Intel x64, and macOS Apple Silicon arm64  
**Decision constraint:** Keep native R binaries and rpy2 CFFI API mode; do not
use a compatibility layer or require R on the user's machine.

## Executive decision

Replace the independent, immutable R integration-kit producer and offline
assembler with **one target-native package job per supported target**. Each job
should perform one linear build:

```text
authenticate official R installer/package
                |
                v
stage target-native R + locked PPM binaries + HSROC + local RCMetaR
                |
                v
build/install rpy2 in API mode against that exact staged R
                |
                v
PyInstaller onedir collection (Python + PyQt6 + Qt + rpy2 + staged R)
                |
                v
final native-closure audit + real packaged smoke + manifest + archive
                |
                v
future: sign/notarize the already-qualified target artifact, then re-smoke
```

The final packaged application is the only promoted build product. A compact
manifest records its exact inputs, downloaded archive hashes, installed R
package versions, native architecture, tool versions, and output inventory.
There is no separately uploaded/downloaded R kit, kit digest, derivation
record, offline Python cache inside a kit, or second assembly environment.

This is not a relaxation of quality. It moves authentication, provenance, ABI
qualification, native-closure inspection, and smoke testing to the artifact
that users will actually run. It removes an intermediate product whose
handoffs have no requirement in R, rpy2, PyInstaller, Apple, Microsoft, or Posit
documentation.

For this one-week prerelease application, a reusable content-addressed R kit is
premature infrastructure. It may become worthwhile only when multiple products
or many release builds consume an identical R stack often enough to amortize a
separate producer, storage, compatibility, and promotion contract.

## Why the current design is failing

Commit `cdc5b3e` added 6,098 lines across 44 files. The central integration-kit
implementation is over 1,000 lines, and the producer/profile/provenance layer is
over 2,000 lines before its contract tests. It also changed one native build
into two fresh-runner jobs joined by an artifact upload/download and by an
offline Python package cache carried inside the R artifact.

The resulting failure surface includes:

- producer-only R installation, signature, package-download, cache, and
  manifest-shape failures before PyInstaller runs;
- an archive format that must preserve framework links and Python cache state;
- producer/consumer Python, R, CPU, target, lock, and path agreement;
- a kit manifest plus a final derivation manifest plus final deployment
  evidence describing substantially the same native payload;
- relocation once for the kit and again for its final app location; and
- separate tests for kit creation, kit authentication, offline assembly, kit
  derivation, and final application qualification.

These are consequences of the chosen intermediate artifact, not intrinsic
requirements of embedded R. PyInstaller itself is native-target only—it is not
a cross-compiler—so all three release products already require target-native
jobs ([PyInstaller manual](https://pyinstaller.org/en/stable/)). An additional
native producer does not eliminate those jobs.

## Requirements that are genuinely irreducible

The following controls must remain even in the simpler design.

### Three native release builds

Build Windows x64 on Windows, macOS x64 on Intel macOS, and macOS arm64 on Apple
Silicon. PyInstaller explicitly requires building on the target OS, and the
official CRAN macOS release itself has separate arm64 and x86_64 packages with
different minimum macOS versions and toolchains
([PyInstaller manual](https://pyinstaller.org/en/stable/),
[CRAN R for macOS](https://cran.r-project.org/bin/macosx/)). Do not merge them
into a universal binary.

### A private, fixed R runtime and library

The app must set bundle-relative `R_HOME` and its private R library before the
first rpy2 import. rpy2 says `R_HOME` must be discoverable and warns that a
build-time/runtime R mismatch must be investigated
([rpy2 low-level interface](https://rpy2.github.io/doc/latest/html/rinterface.html)).
Windows R makes this straightforward: R Core documents that a basic
installation is relocatable, provided R has writable home and temporary
locations
([R for Windows FAQ](https://cran.r-project.org/bin/windows/base/rw-FAQ.html#Can-I-run-R-from-a-CD-or-USB-drive_003f)).

### API-mode rpy2 built on each target

rpy2's API mode is a compiled extension and requires the R development headers
and libraries; rpy2 documents `RPY2_CFFI_MODE=API` and notes that API-mode macOS
builds require Xcode tools
([rpy2 overview](https://rpy2.github.io/doc/latest/html/overview.html)). Build it
in the same target job against the exact staged R. The final frozen application
must contain `_rinterface_cffi_api` and reject ABI fallback.

This build step does **not** require publishing a wheel or a kit. The extension
only needs to exist in the package job's locked Python environment when
PyInstaller analyzes it.

### Embedded-R lifecycle rules

R Core says embedded R is designed and tested on the main thread
([R threading issues](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Threading-issues)).
rpy2 says initialization should occur only once, ending R is effectively
irreversible, and its lock can serialize R API interactions
([rpy2 low-level interface](https://rpy2.github.io/doc/latest/html/rinterface.html)).
Keep the existing single bootstrap, main-thread assertion, whole-analysis lock,
startup isolation, and explicit shutdown policy. These are runtime correctness
controls, independent of how the files reach the app bundle.

### Binary-only normal R dependencies

Use the dated Public PPM repository already recorded by the project, require
native binary package type, and fail rather than silently compile normal
dependencies from source. Posit states that its Windows and macOS packages use
the same toolchains and system libraries as CRAN, are compatible with CRAN R,
and cover Windows x86_64 plus macOS x86_64 and arm64
([Posit binary documentation](https://docs.posit.co/rspm/admin/serving-binaries.html)).

Keep HSROC as the single externally downloaded source exception and local
RCMetaR as the project-owned source build. Their archive/source hashes,
compiler identity, and installed versions must be recorded.

### Final-artifact native closure and packaged smoke

The application must still prove that every non-system PE/Mach-O dependency
resolves inside the product, that all native files match the expected CPU, that
the loaded R/rpy2/package identities are correct, and that representative
analyses and clean exit work from the packaged application. These checks should
run once against the final tree, not once against an intermediate kit and again
against a derived tree.

On Windows, preserve explicit private DLL directories before importing rpy2.
Microsoft recommends fully qualified DLL paths or a restricted loader search
using `SetDefaultDllDirectories`/`AddDllDirectory` to prevent DLL preloading
([Microsoft DLL security](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-security),
[SetDefaultDllDirectories](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-setdefaultdlldirectories)).
Python's `os.add_dll_directory()` is the direct supported API for extension
module and `ctypes` dependency resolution
([Python 3.11 `os.add_dll_directory`](https://docs.python.org/3.11/library/os.html#os.add_dll_directory)).

## What should be deleted

After the replacement pipeline is green on all three targets, delete:

- the reusable `r-integration-kit-producer.yml` workflow and its producer job;
- integration-kit upload/download, digest outputs, and `needs` edge;
- the kit-contained uv cache and offline environment reconstruction;
- `r_integration_kit.py`, kit producer wrappers, kit provenance, kit
  derivation, and kit-only bridge relocation;
- the embedded `r-integration-kit/manifest.json` and `derivation.json` product
  directories;
- kit authentication, cache-shape, offline-assembly, producer/consumer, and
  derivation tests; and
- duplicated kit-specific qualification fields from deployment inspectors,
  signing scripts, and release-candidate workflow.

Retain and simplify:

- the existing R binary policy and exact dependency closure;
- the explicit non-X11 product profile;
- the native API-bridge assertion;
- one final deployment inspector per OS;
- runtime bootstrap and R-call serialization;
- real packaged smoke tests; and
- one final build manifest and archive inventory per target.

The likely net result is deletion of several thousand lines and one full job
per target, with no loss of a user-facing guarantee.

## Recommended target job

### 1. Establish the locked build environment

Check out the exact source SHA and install the pinned Python patch release and
uv bootstrap. Stage R first, then run `uv sync --locked` with that `R_HOME` and
`RPY2_CFFI_MODE=API`, because the locked environment includes rpy2's compiled
interface. Pin PyInstaller and all GitHub Actions. Cache only download caches
keyed by `uv.lock`, the R dependency-policy digest, R version, target, and PPM
snapshot. A cache miss must affect speed only, never correctness.

Do not cache or promote an installed R tree, compiled API bridge, PyInstaller
work directory, or assembled app during this migration.

### 2. Authenticate and stage official R

Use the official CRAN distribution for the exact target:

- **Windows:** download the versioned x64 installer, require its checked-in
  SHA-256 and a valid Authenticode chain, record its actual signer and timestamp,
  then install `main,x64` silently into a build-local staging directory. R Core
  documents `/VERYSILENT`, `/DIR`, `/COMPONENTS`, and successful exit status
  ([R for Windows FAQ](https://cran.r-project.org/bin/windows/base/rw-FAQ.html#Can-I-customize-the-installation_003f)).
- **macOS:** download the versioned architecture-specific `.pkg`, require its
  checked-in SHA-256, require `pkgutil --check-signature` to identify the
  expected R Project Team ID, and install it on the clean ephemeral native
  runner. CRAN itself instructs users to verify the package signature and says
  the packages are signed and notarized
  ([CRAN R for macOS](https://cran.r-project.org/bin/macosx/)).

Do not hard-code a Windows signer's human name as the root of trust. Individual
R Core signers and certificates can change. The exact installer SHA-256 is the
immutable input pin; valid platform signature verification is the independent
publisher/chain check. Any version or hash update remains a reviewed repository
change.

### 3. Apply one small macOS product profile

Before dependency collection, remove the product-prohibited optional surfaces
already identified by the repository:

```text
Resources/library/tcltk/
Resources/modules/R_X11.so
Resources/modules/R_de.so
Resources/library/grDevices/libs/cairo.so
```

This is a small, explicit profile—not a general runtime pruner or dependency
profiler. CRAN describes Tcl/Tk and X11 as optional and says X11 requires
separately installed XQuartz
([CRAN R for macOS](https://cran.r-project.org/bin/macosx/)). RC MetaStudio uses
Qt and noninteractive graphics, so these modules should not enter dependency
analysis at all.

Do not patch every launcher, configuration string, or optional reference in R.
The frozen app embeds through libR, sets its private `R_HOME`, and does not ship
the R GUI. Qualification should judge actual native imports and the observed
runtime, not harmless textual build-prefix strings in unused files.

### 4. Install the R package closure directly into staged R

Run the existing binary-policy installer once with:

- the exact dated Public PPM URL;
- `type="binary"` and source compilation disabled for normal packages;
- a private target library under the staged runtime;
- retained archive URL, version, and SHA-256 evidence;
- the pinned HSROC source archive; and
- `R CMD INSTALL` for the current local RCMetaR source.

Then load every required namespace from the isolated private library and run
the installed RCMetaR check/smoke seam. There is no need to introduce `renv`,
`pak`, Conda, Homebrew, `rig`, or another package manager: the repository's
small explicit policy already does the required binary-only resolution, and a
second resolver would add rather than remove ownership.

Public PPM may rebuild binaries to deliver security fixes, even in historical
package streams. Posit documents this explicitly
([Posit CRAN binary security](https://docs.posit.co/rspm/admin/serving-binaries.html#cran-binary-security)).
Therefore a dated snapshot pins package versions, while the final build manifest
pins the exact bytes observed for a particular release candidate. Promote that
release candidate without rebuilding it.

### 5. Build rpy2 API mode in the same environment

With staged `R_HOME` selected and `RPY2_CFFI_MODE=API`, install the locked rpy2
components into the same uv environment used by PyInstaller. Assert before
freezing that:

- `_rinterface_cffi_api` imports;
- `_rinterface_cffi_abi` is absent;
- rpy2's build R identity matches staged R; and
- a minimal in-process R calculation succeeds.

This gives exactly the native tuple that matters—Python ABI, rpy2, R, OS, and
CPU—without serializing it into a second product.

### 6. Let PyInstaller own final collection

Extend each authoritative `.spec` so `Analysis` receives the staged R directory
tree in addition to the current Python, PyQt6, Qt, and rpy2 inputs. Add the tree
once at its intended `R`/`R.framework` destination and let current PyInstaller's
automatic binary-versus-data reclassification send Mach-O/PE files through
native dependency analysis while retaining non-code files at matching relative
paths. The macOS R framework must remain a framework under
`Contents/Frameworks`; do not implement a second handwritten tree classifier or
post-build recursive copier.

PyInstaller's official hook/spec documentation says `binaries` undergo
recursive dynamic-library dependency analysis
([PyInstaller hooks](https://pyinstaller.org/en/stable/hooks.html),
[PyInstaller spec files](https://pyinstaller.org/en/stable/spec-files.html#adding-binary-files)).
Current PyInstaller also automatically reclassifies binary versus data inputs,
preserves framework/symlink topology, places code under `Contents/Frameworks`
and data under `Contents/Resources`, cross-links mixed trees, rewrites macOS
library paths, and re-signs changed Mach-O files
([PyInstaller macOS bundle notes](https://pyinstaller.org/en/stable/usage.html#building-macos-app-bundles),
[PyInstaller change log](https://github.com/pyinstaller/pyinstaller/blob/develop/doc/CHANGES.rst)).

That is the same generic recursive collector/relocator already trusted for
Python, Qt, rpy2, and R-package native extensions. Maintaining a second generic
Mach-O/PE closure engine for R duplicates PyInstaller's responsibility and has
been a major source of failures.

#### Required feasibility gate

Before deleting the old path, run one focused macOS x64 spike that feeds the
profiled staged `R.framework` and private package library through PyInstaller
6.21.0. The spike passes only if the resulting app:

1. has canonical `R.framework` links and locations;
2. contains one `libR` identity;
3. contains no XQuartz, Homebrew, Conda, `/opt/R`, build-workspace, or system R
   dependency in any final Mach-O import;
4. imports the API bridge under ad-hoc hardened-runtime-compatible signing; and
5. completes the real packaged analysis and exit smoke.

If PyInstaller exposes a narrow, reproducible limitation, add one narrow custom
hook or post-`COLLECT`, pre-`BUNDLE` adjustment for that limitation. Do **not**
restore a general R kit, recursive relocator, or second assembler. PyInstaller
explicitly supports project-local hooks for package-specific collection needs
([PyInstaller hooks](https://pyinstaller.org/en/stable/hooks.html)).

### 7. Inspect, smoke, manifest, and archive once

Run the final platform inspector against the finished onedir tree/app bundle.
It should fail closed on architecture mismatch, unresolved non-system imports,
forbidden external roots, ABI fallback, missing package/license files, or a
runtime identity mismatch. Then run representative `.rcms` analyses, rendering,
export, and clean shutdown from the frozen executable.

Generate one concise `build-manifest.json` after these checks containing:

- source SHA and dirty-state assertion;
- target, OS image, architecture, and deployment floor;
- Python, PyInstaller, PyQt6, Qt, rpy2, and R versions;
- official R URL, SHA-256, signature status, signer, and timestamp;
- PPM snapshot plus every downloaded R archive URL/version/SHA-256;
- HSROC and local RCMetaR source identities;
- installed R package inventory and license metadata;
- final native dependency inventory and forbidden-root result;
- packaged-smoke result; and
- archive path, size, and SHA-256.

This manifest replaces the kit manifest, kit derivation, and duplicated final
qualification manifest. Detailed logs remain CI artifacts; they do not need to
be embedded in the application.

## macOS signing and bundle rules

The R framework belongs in `Contents/Frameworks`. Apple says frameworks and
dynamic libraries belong there, resources belong in `Contents/Resources`, and
wrong placement can cause latent signing/notarization failures
([Apple bundle placement](https://developer.apple.com/documentation/bundleresources/placing-content-in-a-bundle)).
Apple specifically documents embedding an open-source language runtime as a
nonstandard-code case and requires the signed app bundle to remain read-only
([Apple nonstandard code structures](https://developer.apple.com/documentation/xcode/embedding-nonstandard-code-structures-in-a-bundle)).

PyInstaller should perform its collection and path rewriting before release
signing. When the Developer ID certificate becomes available, sign all nested
Mach-O code inside-out with the same Team ID, sign the outer app last with
hardened runtime and a secure timestamp, notarize with `notarytool`, staple, and
repeat the packaged smoke. Apple records nested signatures recursively and
explicitly recommends inside-out signing instead of `codesign --deep` signing
([Apple code signing in depth](https://developer.apple.com/library/archive/technotes/tn2206/)).
Notarization requires hardened runtime and produces a ticket that can be stapled
([Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution),
[Apple notarization issue guidance](https://developer.apple.com/documentation/security/resolving-common-notarization-issues)).

Signing is a protected follow-on job because credentials are intentionally not
available to ordinary pull-request builds. That separation is irreducible, but
it should consume the exact unsigned target artifact—not rebuild R, rpy2, Qt,
or the application. Because signing changes bytes, create a signed manifest
that references the unsigned input digest and final signed digest, rather than
reintroducing a general derivation framework.

Windows signing can remain deferred. When adopted, sign the final EXE/DLL/PYD
set and verify it with SignTool's default authentication policy and RFC 3161
timestamp support
([Microsoft SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)).

## CI topology

Use four ordinary workflow units:

```text
source-verification
       |
       +--> package-windows-x64  --------> unsigned artifact + manifest
       +--> package-macos-x64    --------> unsigned artifact + manifest
       +--> package-macos-arm64  --------> unsigned artifact + manifest
                                              |
                                              v (protected, when available)
                                      sign/notarize target artifact
                                              |
                                              v
                                      re-inspect + re-smoke + publish
```

Each package job is self-contained and has no producer job dependency. The
three jobs share one target-native build command and vary only in a small target
adapter for official R acquisition, platform paths, and final native inspection.
Keep source/static tests out of the expensive matrix except for a small native
contract subset needed to protect package assembly.

For pull requests, run source verification and one explicitly selected native
package lane when packaging inputs change. Run all three package lanes on the
protected branch and release candidates. Scheduled jobs may warm download
caches and report PPM availability, but must not create release inputs.

The job should upload diagnostics with `if: failure()` and the finished artifact
plus manifest on success. Avoid artifact upload/download inside the build lane.
This removes a full runner startup, a large archive transfer, and redundant uv/R
environment setup from every target build.

## Reproducibility and security without the kit

The simpler pipeline retains strong, proportionate controls:

| Concern | Control |
|---|---|
| Official R identity | Versioned official URL, checked-in SHA-256, platform signature verification, recorded signer |
| Python identity | Checked-in `uv.lock`, pinned Python patch, `uv sync --locked` |
| R package resolution | Dated PPM snapshot, binary-only fail-closed policy, exact downloaded archive hashes |
| Source exceptions | Checked-in URL/version/SHA-256; target-native build log and installed package hash |
| rpy2 ABI | API-only build in the target job against staged R; frozen import/runtime assertion |
| Native closure | PyInstaller dependency collection plus independent final PE/Mach-O inspector |
| Runtime isolation | Bundle-relative R home/library, startup isolation, safe Windows DLL directories, no system fallback |
| Release identity | One final build manifest and archive SHA-256 tied to source SHA |
| Promotion | Promote the exact qualified archive; never rebuild a release candidate |
| Supply chain | Full-SHA action pins, least-privilege workflow permissions, no secrets in unsigned builders |
| Licensing | Installed-package/license inventory plus retained corresponding-source URLs/hashes |

Byte-for-byte repeatability across separate signed builds is not necessary for
the prerelease. The meaningful contract is reproducible, reviewed inputs; a
fully inventoried final tree; and promotion of the exact artifact that passed
qualification. If future compliance requires offline reconstruction, retain
the verified download archives in a content-addressed release store. That store
still need not become an independently executable R integration product.

## Alternatives rejected

### Keep and repair the independent integration kit

This offers reuse only when a kit is consumed many times without changing
Python, rpy2, R packages, application packaging policy, or target image. The
current kit also carries Python cache state, so its reuse boundary is much wider
than R. For three release targets and an unreleased application, the producer,
consumer, authentication, derivation, storage, and compatibility contracts cost
more than the saved work. Reject now; reconsider only with measured repeated
consumption.

### Install R on the user's machine

This is operationally simpler for the builder but transfers ABI, package,
security, and support failures to users. It violates the self-contained desktop
product requirement and makes the loaded R unqualified. Reject.

### PyInstaller onefile

Onefile extracts dependencies for every launch and PyInstaller discourages its
use for macOS app bundles. It is a poor fit for a large framework, stable
bundle-relative paths, inspection, signing, and notarization
([PyInstaller operating modes](https://pyinstaller.org/en/stable/operating-mode.html),
[PyInstaller macOS app bundles](https://pyinstaller.org/en/stable/usage.html#building-macos-app-bundles)).
Reject; keep onedir.

### Custom R, Homebrew, Conda, or another R distribution

These can remove optional CRAN components but add a compiler/toolchain and
binary-compatibility policy. Posit explicitly targets CRAN R on Windows and
macOS and cautions that its binaries may not work with other distributions
([Posit binary documentation](https://docs.posit.co/rspm/admin/serving-binaries.html#r-configuration-steps-windows-and-macos)).
Reject for the prerelease.

### Copy R after PyInstaller and relocate it ourselves

This keeps a second generic native dependency collector and mutates the app
after PyInstaller has structured/signed it. It is safer only if a focused spike
proves PyInstaller cannot collect the staged framework correctly. Prefer a
narrow hook first; keep a thin post-assembly adapter only as a documented last
resort, always before final signing.

### `renv`, `pak`, `rig`, or a second package manager

These are useful general tools, but the repository already has a small explicit
binary closure, one source exception, and local RCMetaR. Adding another resolver
does not remove official-R staging, API bridge compilation, PyInstaller
collection, native inspection, or signing. Reject until the dependency policy
itself becomes difficult to maintain.

## Staged migration

### Stage 0: stop extending the kit

Freeze new integration-kit features and fixes except changes needed to keep the
branch recoverable. Treat the current path as a temporary fallback during the
spike.

### Stage 1: one-day macOS x64 PyInstaller collection spike

Use the existing official-R acquisition, non-X11 profile, package policy, and
API bridge build, but feed the staged runtime directly to the macOS spec. Run
the five feasibility gates listed above. This answers the only material unknown:
whether PyInstaller 6.21 can preserve and relocate this exact R framework.

### Stage 2: one linear target package command

Create one command with named phases—`stage-r`, `install-r-packages`,
`prepare-rpy2`, `freeze`, `inspect`, `smoke`, `manifest`, `archive`—and three
small target adapters. A phase should emit a concise marker and fail directly;
it should not create another cross-job protocol.

### Stage 3: replace the workflow topology

Make `package-target.yml` contain a single job. Remove the reusable producer,
artifact handoff, offline cache reconstruction, and kit inputs. Run Windows x64,
macOS x64, and macOS arm64 on the exact same source SHA.

### Stage 4: qualify before deleting

Require two consecutive green builds for each target, including real packaged
analysis and exit smoke. Compare manifests to confirm only expected target
differences. Then remove the kit implementation, contracts, and duplicated
inspector/signing fields in one focused deletion change.

### Stage 5: add protected signing later

When the Apple certificate is issued, add a protected sign/notarize/re-smoke job
that consumes the exact macOS artifact. Keep Windows signing deferred as already
decided. Neither signing path should rebuild the application.

## Acceptance criteria

The migration is complete when:

1. each target is produced by one native package job with no kit job or
   intermediate artifact transfer;
2. the exact official R input passes hash and platform-signature verification;
3. all normal R dependencies come from the selected PPM binary snapshot, with
   only HSROC and local RCMetaR built from source;
4. rpy2 API mode is built against staged R and ABI fallback is absent;
5. PyInstaller owns the final Python/Qt/rpy2/R collection and native dependency
   rewriting, with at most one documented narrow target hook;
6. the final artifact has no unresolved non-system dependency or forbidden
   external R/XQuartz/Homebrew/Conda/build path;
7. the frozen executable reports the expected R, rpy2, RCMetaR, and dependency
   identities from its private library;
8. representative `.rcms` analyses, rendering/export, and clean shutdown pass
   from the final archive on all three targets;
9. one manifest binds all inputs, installed packages, native inventory, tests,
   and the final archive digest to the source SHA;
10. release promotion reuses the exact qualified archive without rebuilding;
    and
11. the integration-kit workflow, implementation, metadata, and kit-only tests
    are deleted.

## Bottom line

The product needs a private native R subsystem, not a separately productized R
integration kit. Build that subsystem in the same native job and environment as
the application that consumes it. Let the pinned PyInstaller spec perform the
generic collection and relocation it already performs for every other native
dependency, then independently inspect and exercise the final artifact. This is
the smallest architecture that preserves the important standards while sharply
reducing runtime, code volume, handoffs, and failure modes.
