# Native macOS Qt6 packaging solution

**Status:** Solution architecture and CI learning record, 20 July 2026  
**Scope:** Issues [#342](https://github.com/AliSalman-et-al/rc-metastudio/issues/342), [#343](https://github.com/AliSalman-et-al/rc-metastudio/issues/343), and [#344](https://github.com/AliSalman-et-al/rc-metastudio/issues/344)  
**Companion diagnosis:** [macos-r-runtime-signing-root-cause.md](macos-r-runtime-signing-root-cause.md)

## Decision

Build two independent, thin macOS applications on native GitHub-hosted runners: Intel x64 on `macos-15-intel` and Apple Silicon ARM64 on `macos-15`. For each target, acquire architecture-locked Qt, Python, and official CRAN R inputs; let PyInstaller be the sole Qt collector; embed one private R/rpy2 API runtime; canonicalize and relocate the **generated** application; sign that final tree once, inside-out; then qualify the downloadable ZIP through the ordinary `.app` entry point. A release candidate is acceptable only when those two artifacts and the Windows x64 artifact are built from the same protected source SHA and independently pass the same hash-bound product workflow.

This is deliberately not a universal2 design. The issue contracts require two native artifacts, and native runners expose architecture mistakes directly instead of allowing Rosetta or a second slice to mask them ([#342](https://github.com/AliSalman-et-al/rc-metastudio/issues/342), [#343](https://github.com/AliSalman-et-al/rc-metastudio/issues/343)).

## Why this architecture works

### 1. Make the target contract explicit before collecting anything

One checked-in target manifest should own the runner architecture, R installer URL and digest, R framework version, expected Mach-O machine, Python version, Qt version, artifact name, and evidence target. The build must reject disagreement between the runner, manifest, downloaded payload, and final binaries.

Qt documents that a deployed GUI application is a bundle containing its runtime resources and that dynamic deployments must include the QPA platform plugin (`libqcocoa.dylib`) plus the used plugin families. It recommends controlling plugin search paths with `qt.conf` or application library paths and checking linked libraries with `otool -L` ([Qt for macOS deployment](https://doc.qt.io/qt-6/macos-deployment.html)). R likewise documents the CRAN framework layout and the libraries under `Resources/lib`, and directs binary maintainers to inspect and rewrite machine-specific dependencies with `otool` and `install_name_tool` ([R Installation and Administration: Frameworks](https://cran.r-project.org/doc/manuals/r-release/R-admin.html#Frameworks), [building binary packages](https://cran.r-project.org/doc/manuals/r-release/R-admin.html#Building-binary-packages)). These are build inputs and invariants, not properties to infer after packaging.

### 2. Use one collector and one private runtime closure

PyInstaller remains the sole Qt dependency collector. The build supplies it an explicit, already-profiled R framework TOC and the rpy2 CFFI API bridge; it rejects the ABI bridge, system R paths, `/opt/R`, `/opt/X11`, unresolved `@rpath` edges, wrong architecture, duplicate install identities, and ambiguous dependency targets.

This boundary matters because PyInstaller 6 has macOS-specific handling for frameworks, places native libraries in `Contents/Frameworks`, and modifies Mach-O headers while collecting them. Those modifications invalidate prior signatures, so collection is necessarily followed by final relocation and signing ([PyInstaller macOS notes](https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing), [PyInstaller 6 bundle changes](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/doc/CHANGES.rst#600-2023-09-22)). The source or staging tree is therefore not authoritative; the generated `.app` is.

### 3. Canonicalize embedded R after PyInstaller

The decisive repair is post-collection canonicalization of `Contents/Frameworks/R.framework`:

1. retain only the canonical framework root members `R`, `Resources`, and `Versions`;
2. make `Versions/<version>/R` the regular Mach-O named by `CFBundleExecutable`;
3. make `Versions/<version>/Resources/lib/libR.dylib` the relative alias `../../R`;
4. rebase the moved executable's local dependencies from `@loader_path/<library>` to `@loader_path/Resources/lib/<library>`;
5. relocate the final collected rpy2 API bridge against that physical `libR`; and
6. inspect every final Mach-O and framework link before signing.

Apple's framework validation treats symlink topology, `Info.plist`, nested code, and the regular main executable as signing structure. It also explains that an `In subcomponent:` diagnostic identifies the nested bundle responsible for an outer failure ([Apple TN2206](https://developer.apple.com/library/archive/technotes/tn2206/)). The earlier CI sequence demonstrated the lifecycle error: a valid staging mutation was reconstructed by PyInstaller, whereas moving the same invariant to the final tree allowed strict signing to pass ([failing pre-fix run](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29723676339), [post-collection canonicalization commit](https://github.com/AliSalman-et-al/rc-metastudio/commit/e7bd732), [dependency-rebase commit](https://github.com/AliSalman-et-al/rc-metastudio/commit/9f9227f), [minimal framework-root commit](https://github.com/AliSalman-et-al/rc-metastudio/commit/b03eb8b)).

The neutral `R-runtime` layout remains a fallback, not the primary design. Once strict signing succeeded against the corrected framework, replacing the framework wrapper would add churn without solving the subsequent runtime or evidence-contract failures.

### 4. Sign the final immutable tree inside-out

No payload bytes may change after signing. Enumerate regular Mach-O files, sign deepest nested code first, sign nested bundles, sign the outer app last, then run strict deep verification and separately record the post-sign inventory. For current community artifacts the identity is ad-hoc (`-`); the same signing plan accepts a Developer ID identity later.

Apple prescribes signing nested code before its containing bundle and discourages `--deep` as a signing mechanism; `--deep` remains useful for verification ([Apple Code Signing Guide](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html)). Hardened Runtime is a signing capability required on the future notarized path, and exceptions should be represented by narrowly scoped entitlements rather than changes to bundle layout ([Apple hardened runtime](https://developer.apple.com/documentation/xcode/configuring-the-hardened-runtime), [Apple notarization preparation](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)). Thus the unsigned-community workflow is future-signing-friendly without retaining a dormant signing workflow: identity, timestamp, runtime options, entitlements, notarization, and stapling can be added as a final promotion policy around the same already-qualified app structure.

### 5. Qualify product behavior, not merely assembly

For each native target, the build has three increasingly strong gates:

- a frozen-runtime probe that proves the packaged Python, Qt/Cocoa, and in-process rpy2/R substrate can initialize;
- packaged automation that opens a real converted project, edits data, performs an R-backed analysis, validates result text and SVG, saves, reopens, exercises dialogs, clipboard, keyboard/accessibility, locale and fractional scaling, and exits cleanly; and
- archive reinspection after extracting the exact ZIP, proving its SHA-256, target architecture, framework links, deployment manifest, logs, and embedded qualification evidence.

GitHub Actions artifacts are designed to persist build outputs and share exact files between jobs, and GitHub documents validating downloaded artifacts before using them ([GitHub Actions artifact documentation](https://docs.github.com/en/actions/tutorials/store-and-share-data)). The candidate workflow therefore initializes one release identity from version, protected-master SHA, targets, and trust profile; builds three immutable target artifacts; inventories and hashes each; and blocks the candidate gate unless all matrix jobs succeed. This implements the “same bytes” boundary required by [#344](https://github.com/AliSalman-et-al/rc-metastudio/issues/344); source smoke or a manually inspected local app is supporting evidence, not a substitute.

## What the CI iterations taught us

1. **Order is a correctness property.** R acquisition, profiling, native-closure relocation, PyInstaller collection, final-tree canonicalization, final relocation, graph inspection, signing, runtime probing, product smoke, archiving, and archive reinspection must occur in that order.
2. **Final-tree evidence outranks staging assertions.** PyInstaller can reconstruct framework topology and rewrite Mach-O headers. Assertions made before it runs cannot prove the shipped tree.
3. **Signing success is only a structural milestone.** The first strict-signing success exposed the next independent frozen-runtime failure. Each gate should retain distinct stdout, stderr, JSON, and inventory files so a later failure does not erase the earlier proof.
4. **Symlinks require semantic validation.** ZIP mode bits are not a portable contract for symlinks. Validate the archived entry type and relative target, resolve it inside the extracted bundle, and compare it with the manifest's expected framework version.
5. **Version labels are not interchangeable.** The product R version, package URL, framework directory (which may include an architecture suffix), PPM platform path, and R package compatibility label are separate manifest fields. Deriving one from another caused avoidable CI-only failures.
6. **Provenance must survive the archive boundary.** Direct-build inputs, source signatures and hashes, target contract, PPM archives, runtime logs, signing inventories, deployment graph, and smoke evidence must be copied into the qualification directory before ZIP creation, and archive inspection must validate the archived copy.
7. **Keep workflows thin.** Reusable platform packaging workflows should call the public packaging commands and upload outputs; the scripts own packaging invariants. Candidate orchestration should only bind exact inputs, fan out the three native builds, and join their results.

## Closure standard

The implementation is the right solution architecture, but the note does not itself prove the issues closed. Closure requires a current-head green Intel package run for #342, a current-head green ARM64 package run for #343, and a protected-master candidate run in which Windows x64, macOS x64, and macOS ARM64 consume one release identity, verify exact artifact hashes, pass their native product qualification, and join at a green release gate for #344. The issue and PR links should point to those retained runs and artifact evidence before closure.
