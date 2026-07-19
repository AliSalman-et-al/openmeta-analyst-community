# Durable local and CI packaging for PyQt6, embedded R, and rpy2 API mode

**Status:** Research recommendation, 18 July 2026
**Scope:** RC MetaStudio issues [#341](https://github.com/AliSalman-et-al/rc-metastudio/issues/341),
[#342](https://github.com/AliSalman-et-al/rc-metastudio/issues/342),
[#343](https://github.com/AliSalman-et-al/rc-metastudio/issues/343), and
[#344](https://github.com/AliSalman-et-al/rc-metastudio/issues/344)
**Locked stack considered:** Python 3.11.9, PyQt6 6.11.0, Qt 6.11.1,
PyInstaller 6.21.0, R 4.6.1, and rpy2 3.6.7

## Recommendation

Use one target-native, end-to-end package command for each release target:

```text
checkout exact source
  -> authenticate and stage official target-native R
  -> install the locked private R package library
  -> build rpy2 API mode against that exact R
  -> sync the locked Python/PyQt6/PyInstaller environment
  -> generate Qt resources
  -> build one PyInstaller onedir application
  -> inspect the complete native closure
  -> smoke the user-facing frozen executable with real R
  -> archive, hash, and retain evidence
```

Run that same command from a collaborator's native machine and from a thin
GitHub Actions job. Do not split ordinary package construction into an R-kit
producer, artifact promotion, offline consumer, and final assembler. That
extra product boundary does not remove any native build: PyInstaller is not a
cross-compiler, and its output is specific to the active OS, Python, and word
size ([PyInstaller manual](https://pyinstaller.org/en/stable/),
[operating mode](https://pyinstaller.org/en/stable/operating-mode.html)). It
instead creates another cache/provenance/relocation protocol that every local
developer and CI retry must satisfy.

The durable design is three thin platform entry points sharing policy, not one
cross-platform super-script:

| Target | Native host | Public command | Product |
| --- | --- | --- | --- |
| Windows x64 | Windows x64 | `scripts/package-windows.ps1` | `RCMetaStudio-{version}-windows-x64.zip` |
| macOS Intel | Intel macOS | `scripts/package-macos.sh --architecture x64` | `RCMetaStudio-macos-x64.zip` |
| macOS Apple Silicon | arm64 macOS | `scripts/package-macos.sh --architecture arm64` | `RCMetaStudio-macos-arm64.zip` |

Windows can be developed and diagnosed locally now. The two macOS commands are
the documented collaborator interface, even though the project currently
executes them only on GitHub-hosted Macs. GitHub documents `macos-15-intel` as
Intel and `macos-15` as arm64, so those are appropriate native lanes
([GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)).
Use the explicit versioned labels rather than `macos-latest`, and record the
actual runner image version because GitHub updates GA images weekly
([runner-images](https://github.com/actions/runner-images)).

## What should be shared

Share declarative inputs and checks, not OS path/process syntax:

- one checked version policy for Python, PyQt6, Qt, SIP, PyInstaller, R, rpy2,
  R package versions, official download URLs and hashes;
- one R dependency lock/policy and one application workflow-smoke contract;
- common Python modules for manifests, archive inventory, hashes, forbidden
  dependencies, and evidence schemas;
- one Windows PyInstaller spec and one macOS spec, with the target architecture
  passed into the macOS spec;
- thin PowerShell and Bash adapters for native installation, process control,
  PE/Mach-O inspection, app launching, and archiving; and
- one reusable Actions workflow parameterized by target and runner, whose build
  step invokes the public local command.

The shell wrapper should own orchestration; the `.spec` should own PyInstaller
collection. PyInstaller spec files are executable build descriptions that can
declare binaries, data, hidden imports, macOS bundle metadata, and shared spec
configuration ([PyInstaller spec files](https://pyinstaller.org/en/stable/spec-files.html)).
Avoid duplicating the same file-placement policy in a spec, a post-copy overlay,
an assembler, and a deployment script.

## Qt and PyInstaller boundary

Retain PyInstaller 6.21 as the sole Qt collector. PyInstaller has first-party
knowledge of Qt packages, while dynamic imports and application-specific data
belong in the spec or a small project hook
([PyInstaller operating mode](https://pyinstaller.org/en/stable/operating-mode.html),
[hooks](https://pyinstaller.org/en/stable/hooks.html)). Do not add
`windeployqt`, `macdeployqt`, or a second copied Qt tree. PyInstaller 6.5 and
newer explicitly rejects multiple Qt bindings in one frozen application, and
its hook guidance recommends excluding extraneous bindings when conditional
imports could select them
([hook configuration](https://pyinstaller.org/en/stable/hooks-config.html)).

Keep explicit assertions for the plugin families RC MetaStudio actually uses:
platform/Cocoa, image formats, SVG/icon engine, style, and TLS. The authoritative
test is the frozen runtime probe plus deployment inventory, not merely the
presence of filenames in the build environment. Continue onedir packaging:
R and its native package closure are already a directory tree, failures are
diagnosable, and later signing needs access to each nested binary.

For macOS, build each thin architecture on its matching runner. Although
PyInstaller supports `x86_64`, `arm64`, and `universal2`, it requires every
collected binary to contain the requested slice and aborts on an incompatible
binary ([PyInstaller macOS multi-arch notes](https://pyinstaller.org/en/stable/feature-notes.html#macos-multi-arch-support)).
Native Intel and arm64 jobs are simpler and directly satisfy the issues; do not
use Rosetta or assemble universal2.

## Embedded R and rpy2 API-mode contract

### Stage a private, target-native R

Use the exact authenticated official R distribution for the target, install or
extract it into build-local staging, and populate a private library under that
runtime. Do not depend on an end user's R, registry, `/Library/Frameworks`,
Homebrew, Conda, or user package library.

On Windows, R Core documents unattended `/VERYSILENT`, `/DIR`, and
`/COMPONENTS` installer flags and confirms that a basic R installation is
relocatable as long as writable home and temporary directories are available
([R for Windows FAQ](https://cran.r-project.org/bin/windows/base/rw-FAQ.html#Can-I-customize-the-installation_003f),
[portable installation](https://cran.r-project.org/bin/windows/base/rw-FAQ.html#Can-I-run-R-from-a-CD-or-USB-drive_003f)).
This supports an application-relative `R/` directory beside the PyInstaller
onedir executable.

On macOS, CRAN publishes separate signed/notarized Intel and arm64 packages,
each containing an R framework and architecture-specific toolchain assumptions
([R for macOS](https://cran.r-project.org/bin/macosx/)). Preserve a canonical
`R.framework` under `RCMetaStudio.app/Contents/Frameworks`; apply only the
project's explicit non-X11/non-Tcl product profile. CRAN identifies Tcl/Tk and
X11 as optional and notes that X11 requires XQuartz. Feed the profiled framework
into PyInstaller's binary analysis so Mach-O dependencies and install names are
handled at collection time, then fail closed on any external `/Library`,
`/opt/R`, Homebrew, build-workspace, XQuartz, or wrong-architecture dependency.

### Build API mode against the staged runtime

Before installing `rpy2-rinterface`, set:

```text
R_HOME=<staged private R home>
RPY2_CFFI_MODE=API
```

rpy2 documents that it can build in CFFI `ABI`, `API`, or `BOTH` mode, that
building requires R/Python compiled libraries and development headers, and that
API-mode macOS builds require Xcode tools
([rpy2 installation](https://rpy2.github.io/doc/v3.6.x/html/overview.html)).
The build must therefore occur natively for each Python/R/CPU tuple, in the
same job that stages R. A prebuilt API bridge may be a download cache, but it
must not become a separately promoted release input unless multiple products
actually need that infrastructure.

Fail before PyInstaller unless all of these hold:

1. `_rinterface_cffi_api` imports and identifies the target CPU;
2. `_rinterface_cffi_abi` is absent from the environment and final app;
3. `rpy2.rinterface.R_BUILD_VERSION` is compatible with the staged runtime;
4. a minimal embedded-R calculation succeeds with the private library; and
5. the final frozen runtime probe reports the same R, rpy2, Python, and CPU.

Set application-relative `R_HOME`, `R_LIBS`, and loader paths before the first
rpy2 import. rpy2 explicitly directs callers to define `R_HOME` when R is not
discoverable and to investigate build/runtime R mismatches
([rpy2 low-level interface](https://rpy2.github.io/doc/v3.6.x/html/rinterface.html#initialization)).
Keep one initialization, do not attempt to restart embedded R after `endr()`,
and serialize complete R calls; rpy2 warns that R's C API is unsafe under
uncontrolled multithreading and exposes an R lock
([initialization and threading](https://rpy2.github.io/doc/v3.6.x/html/rinterface.html#multithreading)).

## Local and CI command symmetry

A collaborator's command should perform the full default build without first
downloading a CI-produced integration kit. Optional flags may skip expensive
smoke or reuse download caches for diagnosis, but the release/CI invocation
must use the strict defaults. Suggested shape:

```powershell
# Native Windows x64
.\scripts\package-windows.ps1
```

```bash
# Native macOS host matching the requested architecture
bash scripts/package-macos.sh --architecture x64
bash scripts/package-macos.sh --architecture arm64
```

The Actions workflow should do only checkout, tool bootstrap, cache restore,
the command above, and artifact/evidence upload. Cache immutable downloads
(uv wheels, official R installer/package, R package archives, Qt resource
compiler) with keys containing target, lock/policy hashes, and tool versions.
Do not cache an installed R tree, compiled bridge, PyInstaller work tree, final
app, or qualification result. A cache miss should change elapsed time, never
the selected inputs or result.

Pin third-party Actions by commit as the repository already does. Keep package
jobs manually dispatchable and required for candidate/release qualification;
run them automatically on packaging-sensitive pull requests or a scheduled
cadence rather than on every documentation-only change. This preserves fast
feedback without weakening #344.

## Artifact and evidence boundary

There are two useful gates, and they must not be conflated:

1. **Build-job qualification:** inspect and smoke the final onedir/app tree,
   then archive it and emit its SHA-256. This catches packaging failures with
   the best diagnostics.
2. **Exact-candidate qualification:** a separate #344 matrix downloads the
   three archives, verifies expected hashes, extracts those exact bytes, reruns
   deployment inspection and the complete user-facing smoke, and records the
   results by target.

Only the second gate proves the downloadable candidates. Do not rebuild between
qualification and publication. Retain one concise manifest per target with:

- source SHA and clean/dirty state;
- runner image, OS version/floor, and CPU;
- Python, PyQt6, compiled/runtime Qt, SIP, PyInstaller, R, rpy2, and RCMetaR
  identities;
- official R URL/hash/signature result and R package archive/version/hash list;
- complete final file and PE/Mach-O dependency inventory;
- required Qt plugin families, API bridge, R shared library, and architecture
  checks;
- packaged workflow results and failure diagnostics; and
- archive name, size, and SHA-256.

Evidence may reference detailed logs uploaded beside the product. It does not
need an R-kit manifest, kit derivation, consumer authentication report, and
final deployment manifest that repeat the same identities.

## Unsigned now, signable later

"Unsigned macOS" should mean **no Developer ID distribution identity**.
PyInstaller or the build may still apply a replaceable ad-hoc signature so the
assembled Mach-O bundle can execute and be checked. Keep all code in standard
bundle locations, use a stable bundle identifier, preserve the canonical
framework topology, and prove the app with hardened-runtime-compatible ad-hoc
signing. Do not add `disable-library-validation` or other security-weakening
entitlements.

Apple requires nested code to be signed before the outer bundle, places dylibs
and frameworks under `Contents/Frameworks`, and treats signed bundles as
read-only ([Apple TN2206](https://developer.apple.com/library/archive/technotes/tn2206/_index.html#//apple_ref/doc/uid/DTS40007919-CH1-TNTAG13)).
The later protected signing stage should:

1. expand the already qualified archive;
2. replace ad-hoc signatures inside-out with one Developer ID Application
   identity and hardened runtime;
3. sign the outer `.app`, verify strictly, notarize, staple, and archive;
4. compute a new hash because signing changes bytes; and
5. rerun exact signed-artifact inspection and smoke before promotion.

PyInstaller already exposes `codesign_identity` and entitlements in the macOS
bundle build surface and re-signs modified collected binaries
([PyInstaller macOS signing](https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing)).
Keep credentials and notarization out of the ordinary local/package workflow;
the unsigned build must remain completely useful without them.

## Existing pieces to retain

The current branch already has the important product-facing seams:

- authoritative Windows and macOS PyInstaller specs;
- thin public package wrappers and a reusable target workflow;
- architecture/dependency deployment inspectors;
- real packaged runtime and workflow probes;
- target-specific GitHub runner selection;
- binary-only R dependency policy plus explicit HSROC/local RCMetaR source
  exceptions;
- API-bridge/ABI-fallback assertions; and
- archive hashes, runner identity, smoke evidence, and failure diagnostics.

Retain those and simplify ownership. The recent direct-R macOS spike is the
right feasibility seam: finish proving that PyInstaller can collect the
profiled staged framework, then make the direct target-native path ordinary.

## Complexity to remove or avoid

- A separately uploaded R integration kit containing an offline Python cache,
  followed by a second clean runner that authenticates and assembles it.
- Kit manifest, derivation, producer/consumer agreement, relocation, and
  signing records that duplicate final-artifact evidence.
- Host-global R or a requirement that collaborators first obtain a privately
  published intermediate artifact.
- A second Qt collector or post-PyInstaller Qt overlay.
- Rosetta builds, universal2 assembly, cross-compiling native dependencies, or
  trying to make one macOS package serve both CPUs.
- Source builds for ordinary R dependencies when target-native binaries are
  part of the locked policy; keep only named, hash-pinned exceptions.
- Relying on mutable software preinstalled on a GitHub runner image.
- Treating pre-archive smoke as proof of the downloaded archive.
- Adding signing credentials to normal CI or weakening hardened-runtime/library
  validation to make an unsigned build launch.
- Introducing Conda, Homebrew, `renv`, `pak`, containers, or a general plugin
  framework when the current uv plus explicit R policy already owns resolution.

## Implications for #341-#344

### #341: Windows x64

Make `package-windows.ps1` self-contained: authenticate and stage official x64
R, install the private locked R library, build the API bridge, invoke the
existing PyInstaller spec, inspect, smoke, archive, and hash. Prove the same
command locally and on a fixed x64 Actions runner. The existing packaged user
workflow, scaling, resource, plugin, architecture, and diagnostic evidence is
valuable and should remain. Remove the requirement for a promoted R kit from
the collaborator entry point.

### #342: macOS Intel

Run the same linear build on `macos-15-intel`, using the official x86_64 R
package and Intel Python/Qt/rpy2 inputs. Complete the direct staged
`R.framework` PyInstaller path, reject every missing Intel slice and external
native dependency, apply ad-hoc hardened-runtime-compatible signing, and launch
through the `.app` entry point. GitHub Actions is the authoritative execution
environment until an Intel collaborator runs the documented local command.

### #343: macOS Apple Silicon

Reuse #342's policy and command on `macos-15` with arm64 official R and arm64
Python/Qt/rpy2 inputs. Differences should be data (target, URL/hash, deployment
floor, runner, archive name), not another packaging architecture. Reject Rosetta
and Intel-only dependencies in both the archive inspector and frozen runtime
probe.

### #344: three-artifact cutover

Do not rebuild. Consume the exact three archives from #341-#343, verify their
recorded hashes, extract them on matching native runners, and run the complete
cross-target qualification contract. Cut over only when all source gates and
all three exact-artifact lanes are green. Signing remains a later transformation
with its own new hashes and requalification.

## Bottom line

The best-practice solution is not a new packaging platform. It is a disciplined
native build with one public command per OS family, one locked input policy,
PyInstaller as the sole Qt/frozen-app collector, an API bridge compiled against
the exact private R it will load, strict final-tree inspection, and exact-archive
qualification. That is durable because every native assumption is explicit;
extendable because targets are data behind shared contracts; reliable because
the user-facing bytes are tested; and efficient because it eliminates an
intermediate release product rather than weakening evidence.
