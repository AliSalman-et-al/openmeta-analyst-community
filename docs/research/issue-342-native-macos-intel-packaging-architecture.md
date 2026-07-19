# Issue #342: durable native macOS Intel packaging architecture

**Status:** Research recommendation, 19 July 2026
**Scope:** [GitHub issue #342](https://github.com/AliSalman-et-al/rc-metastudio/issues/342)
**Target:** unsigned native Intel `x86_64` PyInstaller/PyQt6 application with a
private R 4.6.1 runtime and rpy2 API mode

## Recommendation

Keep the one-command, target-native build, but treat the CRAN R distribution as
an input to one small, explicit **embedded-R compatibility adapter**:

```text
authenticated CRAN Intel .pkg
  -> extract only the R.framework component without installing it
  -> adapt that private copy once (launchers, product profile, Mach-O closure)
  -> prove the staged R runs without /Library, /opt/R, XQuartz, or Tcl/Tk
  -> install only pinned macOS binary R packages into the private library
  -> build and prove rpy2 API mode against that exact staged R
  -> let PyInstaller collect Python and Qt, and copy the already-closed R tree
  -> inspect, sign ad hoc from the inside out, smoke, archive, and re-inspect
```

This is the simplest durable design for #342. Do **not** switch to a nightly
framework tarball, build a private R framework from source, temporarily install
R into `/Library/Frameworks`, or copy whatever `/opt/R` libraries happen to be
present on the runner.

The current strategy is directionally correct in choosing the official CRAN
framework. Its brittleness comes from mixing acquisition, layout discovery,
launcher repair, dependency relocation, package installation, PyInstaller
collection, and signing in one large mutable procedure. Those operations need
one-way phase boundaries and a few semantic invariants, not more path-specific
special cases.

## What upstream supports

### The stable CRAN installer is the right R input

CRAN publishes a signed and notarized R 4.6.1 Intel installer for macOS 11 and
later. It contains the R framework, R.app, and optional Tcl/Tk/X11 and Texinfo
components; CRAN explicitly says Tcl/Tk and X11 can be omitted and are needed
only for `tcltk`, while X11 use requires XQuartz
([R for macOS](https://mac.r-project.org/bin/macosx/)). That is a strong match
for the product decision to ship R but not Tcl/Tk, X11, or XQuartz.

Inspection of the pinned `R-4.6.1-x86_64.pkg` used by this repository confirms
that its exact framework component is identified by
`org.R-project.x86_64.R.fw.pkg`, has version `4.6.1`, installs at
`/Library/Frameworks`, and contains `Payload/R.framework`. The component
metadata also says `relocatable="false"` and `auth="root"`. Therefore:

- running the installer is the wrong local/CI seam because it mutates the host
  and requires privilege;
- extracting that authenticated component into a private build directory is a
  sound acquisition seam; and
- the extracted framework is not magically relocatable merely because it was
  copied, so a deliberate compatibility adapter is required.

Apple documents `pkgutil --expand` as the supported way to expand a flat
installer for inspection
([QA1798](https://developer.apple.com/library/archive/qa/qa1798/)). Use
`pkgutil --expand-full` on the supported hosted macOS runner, then resolve the
component from its `PackageInfo` identity, version, and install location. Do not
search recursively for the first directory named `R.framework`.

Authenticate both layers before extraction: require the pinned SHA-256 and a
successful Apple package-signature check. CRAN publishes the signature-check
command and identifies the Intel package as signed and notarized
([R for macOS](https://mac.r-project.org/bin/macosx/)).

### The framework-only tarball is not a locked release substitute

The R for macOS developer service publishes `R-4.6-branch-x86_64.tar.xz`, which
contains only `R.framework`, and offers persistent last-success locations for
CI. However, that artifact is a continually rebuilt **patched branch**, not the
immutable R 4.6.1 release input required here
([R for macOS developers](https://mac.r-project.org/)). It avoids package
component extraction but introduces source revision drift. It is useful for R
upstream CI, not for RC MetaStudio's version-locked release artifact.

### Building R from source is supported but is the wrong trade-off

R supports `--enable-R-framework=DIR` and an install-time `prefix`, including a
nonstandard framework location
([R Installation and Administration](https://mac.r-project.org/man/R-admin.html#Frameworks)).
That makes a private source build technically possible. It would also make this
project responsible for reproducing CRAN's compiler, Fortran, BLAS, external
library, package-binary, deployment-target, and licensing choices. R's manual
notes that macOS binary-package support is a property of CRAN builds and that a
source build may default to source packages
([install.packages](https://stat.ethz.ch/R-manual/R-devel/library/utils/html/install.packages.html)).
For a small desktop application build, this is slower, less compatible with
CRAN/Posit binaries, and substantially more infrastructure than adapting the
official binary framework.

### `R_HOME` alone cannot relocate CRAN R

This is the key fact behind the repeated launcher failures. R's generated Unix
launcher assigns a configure-time `R_HOME_DIR`, warns that a different
environment `R_HOME` is being ignored, then sources
`$R_HOME/etc/ldpaths`
([R launcher source](https://github.com/r-devel/r-svn/blob/main/src/scripts/R.sh.in)).
The CRAN Intel launcher instantiates that path as
`/Library/Frameworks/R.framework/Resources`. Moving the framework and exporting
`R_HOME` therefore cannot make `R CMD config` work.

Rscript has a different contract: its native front end honors `RHOME` and then
executes `$RHOME/bin/R`
([Rscript source](https://github.com/r-devel/r-svn/blob/main/src/unix/Rscript.c)).
The durable adaptation is consequently:

1. patch only the generated `bin/R` home/share/include/doc assignments so they
   derive `Resources` from the launcher's own location;
2. preserve R's remaining launcher logic and `R CMD` behavior;
3. preserve the native Rscript binary, but put a tiny wrapper in front of it
   that computes the same app-relative home, exports `RHOME`, and executes the
   renamed original; and
4. test `R RHOME`, `R CMD config --cppflags`, `R CMD config --ldflags`, and
   `Rscript -e ...` before building rpy2.

Replacing Rscript with `exec/R` is not equivalent to Rscript and should not be
used. Patching arbitrary occurrences of `/Library/Frameworks` throughout the
tree is also unnecessary. The adapter should modify only the two launcher
boundaries and native load commands that it owns.

### rpy2 API mode must be built against the adapted runtime

rpy2 documents `RPY2_CFFI_MODE=API`, notes that API builds need R development
headers and compiled libraries, and requires Xcode tools on macOS
([rpy2 installation](https://rpy2.github.io/doc/v3.6.x/html/overview.html)).
Its source resolves `R_HOME`, invokes `R CMD config --ldflags` and
`--cppflags`, and uses those results to compile the CFFI extension
([rpy2 situation source](https://github.com/rpy2/rpy2/blob/RELEASE_3_6_7/rpy2-rinterface/src/rpy2/situation/__init__.py),
[rpy2 build source](https://github.com/rpy2/rpy2/blob/RELEASE_3_6_7/rpy2-rinterface/setup.py)).

This establishes the correct ordering: make the private R executable and
native closure runnable first, then build `rpy2-rinterface` from its locked
source distribution with `R_HOME` pointing to that runtime and
`RPY2_CFFI_MODE=API`. A wheel built against a system R and repaired later is not
the same proof.

### Use macOS binary R packages and close their actual graphs

On a CRAN macOS build, `install.packages(type = "binary")` installs `.tgz`
binary packages matching the running R build
([install.packages](https://stat.ethz.ch/R-manual/R-devel/library/utils/html/install.packages.html)).
Posit states that its macOS binaries use the same toolchains and system
libraries as CRAN and are intended for CRAN's R distribution, not Homebrew R
([Posit Package Manager binary compatibility](https://packagemanager.posit.co/__docs__/admin/serving-binaries.html#r-configuration-steps-windows-and-macos)).

The official CRAN framework already carries its Fortran, BLAS, OpenMP, and
related runtime dylibs under `Resources/lib`, even though its build metadata
records `/opt/R/x86_64` toolchain paths. The distinction matters:

- a configure/build path recorded in `Makeconf` is not automatically a runtime
  dependency;
- an `otool -L` edge is a runtime dependency and must resolve inside the app or
  to an allowed macOS system path; and
- the runner's `/opt/R` must never be used as an implicit source of release
  bytes.

Force the pinned Posit snapshot to return binary archives, retain each archive
URL and SHA-256, install them into the framework's private library, then scan
the installed package Mach-O graph. Most macOS package binaries bundle their
system dependencies; Posit notes that a minority can still require explicit
runtime dependencies
([Posit package binaries](https://docs.posit.co/rspm/user/r-binary-packages.html)).
If a required package leaves an unresolved `/opt/R` edge, fail and handle that
package as a named exception. Do not make the build pass by copying a same-name
library from the host.

### PyInstaller should own Qt, not R relocation

PyInstaller builds for the active OS/architecture and supports thin `x86_64`
macOS targets
([PyInstaller macOS options](https://pyinstaller.org/en/stable/usage.html#macos-specific-options)).
It rewrites library paths for binaries it collects, and its bootloader does not
need `DYLD_LIBRARY_PATH`
([PyInstaller path handling](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application)).
It also rejects multiple Qt bindings and provides hooks for the selected Qt
binding
([PyInstaller Qt hook policy](https://pyinstaller.org/en/stable/hooks-config.html#qt)).

For this application, use PyInstaller as the **sole Qt collector**. Exclude
PyQt5, PySide, qtpy, and the rpy2 ABI bridge; assert one PyQt6/Qt6 root and the
required Cocoa, image, SVG/icon, style, and TLS plugin families. Do not run
`macdeployqt` after PyInstaller.

R is different: it is a complete framework filesystem with meaningful aliases,
shell launchers, an R package library, and native modules. Normalize and close
it before PyInstaller, add it through one explicit spec-owned tree/TOC as data,
and prevent PyInstaller's rpy2 dependency walk from adding a second `libR`.
Then assert the final app has exactly one `R.framework`, one real `libR.dylib`,
one `_rinterface_cffi_api` bridge, and no ABI bridge. This division is simpler
than asking both a custom adapter and PyInstaller's generic Mach-O collector to
rewrite the same R files.

Qt's own deployment documentation confirms that a private app bundle must carry
the plugins it uses and describes Cocoa/platform, image, SVG, icon-engine,
style, and other plugin rules
([Qt macOS deployment](https://doc.qt.io/qt-6/macos-deployment.html)). In this
project those rules are verification requirements; PyInstaller remains the
collector.

### Signing must be the last mutation

PyInstaller can ad-hoc sign or use a real identity, but the explicit R tree is
copied as data and may contain code that PyInstaller did not individually sign.
After all load-command changes, sign every nested Mach-O and bundle from the
inside out, then sign the outer app last. Apple explicitly instructs developers
to sign nested code from the deepest item outward and warns against using
`codesign --deep` for signing
([latest signature format](https://developer.apple.com/documentation/xcode/using-the-latest-code-signature-format),
[distribution signing](https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac)).

For #342, use an ad-hoc identity with hardened-runtime options and verify with
`codesign --verify --deep --strict`; `--deep` is appropriate for verification,
not signing. Later Developer ID signing can call the same ordered signer with a
real identity and secure timestamp. Apple requires Developer ID, hardened
runtime, a timestamp, and valid signatures for notarization
([notarization requirements](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)).

## Recommended phase contract

Each phase writes a small manifest and consumes the previous phase's manifest.
No phase searches the host to repair missing inputs.

### 1. Target and source preflight

- Require `Darwin`, `uname -m == x86_64`, `macos-15-intel`, Xcode command-line
  tools, locked Python 3.11.9, and a cleanly identified source commit.
- Explicitly reject `/Library/Frameworks/R.framework` and `/opt/R` as build
  inputs. Their presence or absence must not change the result.
- Use the public local command unchanged in CI:
  `bash scripts/package-macos.sh --architecture x64`.

GitHub documents `macos-15-intel` as an Intel hosted-runner label
([GitHub-hosted runners](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job)).

### 2. Acquire the official framework

- Download only into an immutable content cache.
- Verify the locked SHA-256 and package signature.
- Expand into a new temporary directory.
- Select exactly one component by identifier, version, install location, and
  `Payload/R.framework` topology.
- Copy with a symlink-preserving macOS tool into private staging.
- Record every source member's type, mode, link target, size, and hash.

### 3. Apply the embedded-R compatibility adapter

- Validate the official framework aliases without hard-coding a count of
  unrelated symlinks.
- Remove only the declared product exclusions (`R_X11` and `tcltk` payloads),
  then prove `capabilities("X11")` and `capabilities("tcltk")` are false. Keep
  Cairo/Quartz components whose actual graphs are closed and needed by plots.
- Convert an absolute symlink only when its target maps uniquely back into the
  same framework; otherwise fail. Do not assert that there must always be 17
  fontconfig links.
- Adapt `R` and wrap the original Rscript as described above.
- Inventory Mach-O files by format, not filename. Treat Java class files as
  class files rather than relying on the shared `CAFEBABE` magic alone.
- Rewrite every internal framework install ID and dependency to a unique
  app-relative `@loader_path` target. Map CRAN `/Library/Frameworks/R.framework`
  identities structurally. Map an `/opt/R` identity only to a unique byte that
  is already in the authenticated framework; never copy it from the host.
- Reject every remaining non-system absolute load command and every wrong or
  mixed architecture.
- Run R, Rscript, `R CMD config`, a minimal embedded calculation, and the
  non-X11/Tcl capability probe from the staged tree.

### 4. Install the locked private R library

- Resolve the declared runtime dependency closure against the dated Posit
  snapshot.
- Require `type = "binary"` and `.tgz` archives for every CRAN dependency.
- Cache archives only, not an installed R library.
- Hash and record all archives before installation.
- Build local RCMetaR and any explicitly documented source-only exception with
  the staged R; do not silently fall back from binary to source.
- Rescan and relocate the complete installed-library Mach-O graph, then run the
  real package-load and representative analysis probes.

### 5. Build strict rpy2 API mode

- Build the locked `rpy2-rinterface` source distribution in the locked Python
  environment with `R_HOME=<staged Resources>`, staged `bin` first in `PATH`,
  `RPY2_CFFI_MODE=API`, and the deployment target set.
- Require exactly one `_rinterface_cffi_api` extension and no ABI extension.
- Require Intel-only architecture and exactly one R edge resolving to the
  staged `libR`.
- Import the bridge and execute real R in process before invoking PyInstaller.

### 6. Build with the authoritative PyInstaller spec

- Generate Qt resources deterministically.
- Let PyInstaller collect Python, PyQt6, Qt6, SIP, and Qt plugins.
- Add the staged R framework with one explicit, symlink-preserving TOC.
- Remove/override PyInstaller's automatic R collection by exact membership in
  the staged framework, not by recognizing only `/Library` or `/opt` prefixes.
- Build `onedir` and a normal `.app`; retain the spec's bundle metadata and
  minimum supported macOS version.

### 7. Inspect, sign, smoke, and archive

- Inspect every final Mach-O, symlink, duplicate basename, install ID, and load
  edge before signing.
- Sign nested code in a deterministic inside-out order, app last; mutate
  nothing afterward.
- Launch through the normal `.app` entry point and execute every #342 workflow
  requirement with real R.
- Create the versioned ZIP with a macOS tool that preserves framework aliases,
  hash it, extract that exact ZIP to a fresh location, repeat inspection and
  normal-entry smoke, and bind all evidence to the ZIP hash.

## Non-negotiable invariants

1. The host is read-only input only for Apple system frameworks and build tools;
   system R, Homebrew, `/Library/Frameworks/R.framework`, `/opt/R`, user R
   libraries, XQuartz, and Tcl/Tk never supply release bytes.
2. The staged and final runtime each contain exactly one R framework, one
   concrete `libR`, one API bridge, and zero ABI bridges.
3. Every non-system native dependency resolves inside the staged/final product;
   every native file is thin `x86_64`.
4. R's launcher behavior is adapted once and tested before rpy2 is built.
5. CRAN dependencies are pinned macOS binary archives; source compilation is a
   named, reviewed exception.
6. PyInstaller is the only Qt collector; the embedded-R adapter is the only R
   relocator.
7. Signing is the final bundle mutation, and the exact archived artifact is the
   artifact that is re-inspected and smoked.

## Current design mistakes to remove

The branch as inspected on 19 July 2026 contains several patterns that explain
the sequence of brittle fixes:

- setting `R_HOME` before repairing the CRAN `R` launcher, even though upstream
  intentionally ignores it;
- discovering payload layout from incidental directory names instead of the
  installer's component identity and metadata;
- allowing missing `/opt/R` edges to be satisfied by copying host files, which
  makes output depend on runner state;
- exact-count assertions for incidental fontconfig links and other layout
  details that are not product invariants;
- replacing Rscript semantics rather than wrapping the original native
  Rscript;
- filtering PyInstaller's automatically discovered R binaries by a few source
  prefixes rather than by membership in the one staged framework;
- mixing pre-rpy2 and post-PyInstaller relocation logic, making it unclear
  which component owns a native load command; and
- signing the outer app with `--deep`-style assumptions instead of using one
  explicit inside-out signing inventory.

The recent move to resolve the exact `R-fw.pkg` component and to relocate the
private runtime before API compilation is the right correction. It should be
finished by consolidating those rules into the phased adapter above, not by
adding another fallback path.

## Migration plan from the current branch

1. **Stop CI amendment loops temporarily.** Keep the latest native failure as a
   regression fixture: the private `R` launcher attempted to source
   `/Library/Frameworks/R.framework/Resources/etc/ldpaths` during the rpy2
   build.
2. **Land the substrate probe first.** In one native job, stop after component
   extraction, launcher adaptation, full R relocation, and staged R/Rscript/CMD
   config probes. No packages, rpy2, Qt, or PyInstaller yet.
3. **Make the adapter data-driven.** Replace exact incidental counts and host
   copying with structural component, symlink, and Mach-O graph rules.
4. **Add the binary-package closure.** Prove every archive and installed native
   edge before adding rpy2.
5. **Add rpy2 API mode.** Make import plus an embedded R calculation the phase
   gate.
6. **Reconnect the existing PyInstaller and #342 smoke path.** Remove duplicate
   R collection, then use the final inspection and signing inventory.
7. **Only then optimize.** Cache downloads and locked tool environments; do not
   cache or promote a staged framework, installed R library, rpy2 bridge, or
   partially built app.

This sequence gives each failure one owner and one diagnostic manifest. It is
still a single local/CI command and a single native build job; the phases are
code boundaries, not new artifacts or workflows.

## Decision summary

| Option | Decision | Reason |
| --- | --- | --- |
| Extract stable CRAN `.pkg` framework component and adapt a private copy | **Use** | Authenticated, matches CRAN/Posit binary packages, no host install, bounded adaptation |
| Patched/nightly framework-only tarball | Reject | Moving branch artifact, not the locked R 4.6.1 release |
| Build a private R framework from source | Reject for #342 | Recreates CRAN toolchain/distribution work and weakens binary compatibility |
| Install CRAN R into `/Library/Frameworks` during CI | Reject | Privileged host mutation and conflicts with local/CI symmetry |
| Homebrew/Conda R | Reject | Different distribution and package-binary compatibility boundary |
| Copy unresolved `/opt/R` libraries from the runner | Reject | Non-reproducible, host-dependent release bytes |
| PyInstaller collects Qt; explicit adapter closes R | **Use** | One owner per native subsystem and no duplicate deployment tool |
