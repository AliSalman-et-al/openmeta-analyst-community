# Robust macOS packaging fix: isolate PyInstaller from embedded R

Date: 2026-07-21

Scope: persistent native `x86_64` and `arm64` failures while packaging a PyInstaller/PyQt6 application with an embedded CRAN `R.framework`, including GitHub Actions run [29776710891](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29776710891). This report intentionally treats the repository's current build steps as hypotheses, not requirements.

## Conclusion

The smallest robust architecture is to stop asking PyInstaller to ingest, transform, classify, relocate, and sign `R.framework`.

Build the ordinary Python/Qt `.app` with PyInstaller, explicitly exclude every R-derived binary discovered during Analysis, then inject one already-normalized and already-relocated R runtime into the completed app. After injection, make no content or Mach-O changes. One repository-owned finalizer should inventory nested code, sign inside-out, sign the outer app last, and run Apple's strict recursive verification. Before the full app build, the normalized R framework should have to pass a tiny fixture-app embedding/signing test.

This is materially smaller than the current responsibility overlap:

1. the CRAN installer supplies an installed framework;
2. repository scripts mutate its topology and Mach-O graph;
3. PyInstaller analyzes R-linked binaries, relocates the supplied explicit TOC, applies its own macOS framework rules, and signs the bundle;
4. repository scripts mutate collected code again;
5. a second signer replaces every signature and seals the app again.

The current design has too many independent authorities over the same filesystem and signature graph. Passing more path shapes through that design will not make it stable.

## Directly observed facts

### Current failing run

In the arm64 job of run [29776710891](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29776710891), the following happened in order:

- a fresh native `rpy2-rinterface` was built;
- the staged R framework was canonicalized and relocated;
- PyInstaller warned that R's `libgfortran.5.dylib`, `libquadmath.0.dylib`, and `libgcc_s.1.1.dylib` had invalid SDK version `0.0.0`, had been collected under flat destinations, and would likely cause code-signing and hardened-runtime problems;
- PyInstaller's BUNDLE signing completed;
- the repository then changed `_rinterface_cffi_api.abi3.so`, invalidating its prior signature;
- the repository signer individually signed and verified the enumerated Mach-O files and nested bundles;
- final `codesign --verify --deep --strict` failed on the outer app with `No such file or directory`.

These statements come from the first-party job log, not an interpretation of a cached artifact. They prove that the failing path reaches final recursive validation. They do **not** prove which nested path caused `codesign` to return that diagnostic, because verbosity level 2 did not emit an `In subcomponent:` line.

The current spec supplies an explicit R TOC to PyInstaller, filters Analysis binaries, then extends `a.datas` with the framework TOC ([spec](../../packaging/pyinstaller/rc-metastudio-macos.spec)). The build canonicalizes R both before and after BUNDLE creation and relocates the rpy2 bridge after PyInstaller signs ([build script](../../scripts/build-macos-package.sh)). The repository signer then signs every Mach-O, nested bundle, and outer app ([signer](../../scripts/sign_macos_app.py)). Those are repository facts; none is an Apple or PyInstaller requirement.

### Platform rules that constrain a correct solution

Apple requires nested code to be signed from the deepest component outward, with the top-level app last. It also says signing is the final build step and any later modification invalidates the signature. The outer seal records nested signatures and non-code resources in `Contents/_CodeSignature/CodeResources`. [Apple, *Code Signing Tasks*, lines 150–159 and 213–216](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html)

Apple recognizes `Contents/Frameworks` as a code-only location for frameworks and dylibs. Code outside standard code locations is treated as a resource as well as code; custom subdirectories inside code locations are unsupported and can break signing. Apple further warns that a framework can sign successfully by itself yet fail when nested in an app, and requires a framework `Info.plist` under `Versions/Current/Resources`. [Apple, *Code Signing Tasks*, lines 218–281](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html)

Apple's canonical framework anatomy has a real versioned executable and top-level executable/Resources symlinks through `Versions/Current`. Strict validation also checks symlinks; dangling links and links escaping an app can cause Gatekeeper rejection. [Apple, *Bundle Structures — Framework Bundles*](https://developer.apple.com/library/archive/documentation/CoreFoundation/Conceptual/CFBundles/BundleTypes/BundleTypes.html#//apple_ref/doc/uid/10000123i-CH101-SW4) and [Apple Technical Note TN2206](https://developer.apple.com/library/archive/technotes/tn2206/)

R's official macOS distribution is an installer containing `R.framework`; its documented `R.home()` is the root `Resources` symlink through `Versions/Current`, and its installed package library lives inside that framework. That establishes the **installer** layout, but it does not establish that an arbitrarily transformed copy nested in a third-party app is valid. [R for macOS FAQ, sections 1.3, 3.4, and 10.10](https://mac.r-project.org/man/RMacOSX-FAQ.html)

R's installed framework is deliberately unusual: its official internals documentation says the root `R` link ultimately targets `Versions/Current/Resources/lib/libR.dylib`, while the framework `Resources` link and BLAS-selection symlinks have R runtime meaning. Therefore rewriting it into a generic Apple executable layout is **not proved semantics-preserving by structural validation alone**. [R Internals, *The macOS R Framework*](https://mac.r-project.org/man/R-ints.html#The-macOS-R-Framework) and [R for macOS FAQ, BLAS and `R.home()` sections](https://mac.r-project.org/man/RMacOSX-FAQ.html)

PyInstaller 6 deliberately relocates binaries/frameworks into `Contents/Frameworks`, data into `Contents/Resources`, and cross-links the two trees. It also attempts to repair collected framework structures for signing. [PyInstaller 6.0 changelog](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/doc/CHANGES.rst#600-2023-09-22) This means an explicit mixed-content R tree passed through PyInstaller is not a byte-preserving copy operation.

PyInstaller's own changelog says a missing framework `Info.plist` can make `codesign` reject the final app and says invalid/too-old Mach-O SDK versions are likely to cause signing and hardened-runtime trouble. [PyInstaller 6.2 changelog](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/doc/CHANGES.rst#620-2023-11-11) A PyInstaller maintainer also records an unresolved architectural limitation: framework contents are processed/signed as collected binaries rather than cached and signed as one framework entity. [PyInstaller issue #8160](https://github.com/pyinstaller/pyinstaller/issues/8160#issuecomment-1868151560) This is maintainer evidence about PyInstaller's implementation, not an Apple guarantee.

GitHub says hosted runner images are updated weekly and recommends explicit OS labels to avoid `-latest` migrations. The repository already uses explicit macOS 15 architecture labels, which controls the OS family but not the exact weekly image. [GitHub Actions runner-images README](https://github.com/actions/runner-images#available-images)

## What is proved, inferred, and still unknown

| Statement | Status | Basis |
|---|---|---|
| The final arm64 app seal is invalid in run 29776710891. | Fact | Strict deep verification returned non-zero. |
| The app path itself was absent. | Disproved as a useful reading | The signer had just traversed and signed that directory; `codesign`'s terse diagnostic is not a filesystem proof. |
| The explicit R TOC still results in R libraries entering PyInstaller's binary analysis. | Fact | PyInstaller named staged R sources and flat collection destinations in its warning. |
| The flat duplicate R libraries caused the outer-seal failure. | Plausible inference, unproved | PyInstaller warns they threaten signing, but the log lacks a failing subcomponent. |
| R.framework topology caused the outer-seal failure. | Plausible inference, unproved | Apple warns a standalone-valid framework may fail when nested; current diagnostic is insufficient. |
| A dangling or escaping symlink caused `No such file or directory`. | Strong first diagnostic hypothesis, unproved | Apple says strict validation checks symlinks; the current pipeline does not retain the complete post-PyInstaller `lstat/readlink` graph in the failure log. |
| Signing every Mach-O individually proves the app is valid. | False | Apple separately validates nested bundle structure and the outer resource envelope. |
| A green cached build proves a clean build is reproducible. | False | Run 71 reused an rpy2 artifact while later clean runs compiled it and exposed different load commands; see [the run-71 investigation](manual-package-qualification-71-cache-dependent-green.md). |
| Ad-hoc hardened-runtime signing proves future Developer ID/notarization. | Partial only | It exercises structural signing, not certificate trust, trusted timestamp, Gatekeeper assessment, notarization, or stapling. |
| The current R canonicalization is correct. | Unproved | It is repository-defined and has not yet passed an isolated nested-framework fixture plus the final app check on both architectures. |
| A GitHub runner limitation explains the failure. | Unsupported | The same runner image family reaches deterministic code-signing failures; image drift is a reproducibility risk, not current root-cause evidence. |

## Recommended architecture

### 1. Give each tool one ownership boundary

- **PyInstaller owns:** Python, PyQt6, the bootloader, its ordinary dependency graph, and initial `.app` layout.
- **The R adapter owns:** acquisition verification, runtime pruning, R package installation, symlink normalization, and Mach-O relocation in a staging directory.
- **The injector owns:** a byte/topology-preserving copy of the finalized R framework into `Contents/Frameworks/R.framework` after PyInstaller is completely finished.
- **The final signer owns:** all final signatures and verification. Nothing writes into the app after it begins.

Do not pass R through `a.datas` or PyInstaller's framework relocation. PyInstaller may import/analyze rpy2 against staged R, but the spec must fail closed if any source inside staged R remains in `a.binaries` after filtering. The build should additionally fail if an R-derived basename appears at a destination outside the injected framework.

Why this is the smallest robust change: the application can keep the official R framework form and existing R_HOME contract; only the unsafe ownership overlap is removed. It does not require replacing PyInstaller, rewriting the app, or building a novel R distribution.

### 2. Prove R independently before paying for a full build

Create a minimal native fixture app with a conventional `Contents` layout. Inject the exact staged `R.framework`, sign all nested Mach-O/framework code inside-out, sign the fixture app, and require:

- `codesign --verify --strict --verbose=4 R.framework`;
- `codesign --verify --deep --strict --verbose=4 Fixture.app`;
- a symlink manifest with every target resolving inside the framework;
- `Info.plist`/`CFBundleExecutable` consistency;
- one architecture per native file and no forbidden host paths in load commands;
- execution of `Rscript` and an rpy2 API calculation against that same tree.
- preservation of R-specific semantics: root `Resources`, root `R`, `R.home()`, launcher behavior, `libR.dylib`, active BLAS selection, package discovery/loading, and Quartz capability.

This fixture distinguishes “our R payload cannot be nested according to Apple's rules” from “PyInstaller's app is wrong.” If it fails, stop changing the production app and fix the adapter. If it passes but the production app fails, diff the two sealed layouts and signing inventories.

### 3. Normalize and relocate exactly once

All `install_name_tool`, file promotion, symlink creation, package installation, and pruning must finish in staging. Generate a content/topology manifest afterward. Injection must preserve that manifest, and the app copy must match before signing.

Remove post-BUNDLE canonicalization and bridge relocation. Instead, relocate the rpy2 bridge while it is still a collected build input, before PyInstaller's final assembly, or patch the completed bridge **before** R injection and before the sole final signing phase. There must be one explicit “app frozen” boundary after which only signature files may change.

### 4. Diagnose failures as artifacts, not console anecdotes

On every failure at the final boundary, upload a compressed unsigned/failing app (or at minimum its complete filesystem/symlink manifest, Info.plists, Mach-O inventory, load commands, `_CodeSignature` trees, and PyInstaller TOCs). Run and retain separate results for:

1. shallow outer verification;
2. strict verification of each nested bundle;
3. deep strict outer verification at verbosity 4;
4. `codesign -d --verbose=4` for the app and reported subcomponent.

Do not “fix” this by removing deep verification. Apple's own guidance says nested validation matters and provides `In subcomponent:` specifically to locate failures.

### 5. Separate clean reproducibility from accelerated CI

Keep caches for speed, but qualification must include an explicitly cache-cold lane or cache key that includes architecture, Python ABI, R version/package lock, rpy2 version, compiler/Xcode identity, and adapter revision. Record whether each native artifact was built or restored. Pin explicit runner OS labels and record the exact runner image/Xcode version in evidence; do not assume the label freezes the image.

### 6. Define two signing gates

The ordinary PR gate can use ad-hoc signing to prove structure and executable behavior. The release gate must use Developer ID with hardened runtime and timestamp, then exercise Apple's distribution checks (including notarization/stapling when credentials exist). The finalizer should accept an identity without changing bundle construction, which keeps today's workflow future-signing friendly.

## Ranked alternatives

### A — Post-PyInstaller injection with one final signer (recommended)

Risk: medium. Change size: moderate. Confidence: highest available without changing the application architecture.

It preserves PyInstaller for what it officially handles well and prevents it from transforming the unusual R payload. Its failure modes become separable and observable.

### B — Build an application-specific R runtime from source

Risk: medium-high initially, lower steady-state. Change size: large. Confidence: potentially highest long-term.

If the official installer framework cannot pass the isolated fixture after minimal normalization, build R from locked source/toolchains into a layout designed for embedding, with explicit deployment targets and SDK metadata. This can eliminate the CRAN framework's installer-specific assumptions and the `0.0.0` SDK-warning binaries, but it creates compiler, Fortran, BLAS, Quartz, and package-build ownership. Do this only after the fixture proves the installer-derived approach structurally impossible or release signing rejects its SDK metadata.

### C — Prebuild and pin an architecture-specific qualified R+rpy2 kit

Risk: medium. Change size: moderate. Confidence: good as an acceleration layer, poor as the root fix alone.

A content-addressed kit can remove cache accidents and repeated package compilation, but it must be produced by the same isolated qualification and injection design. Pinning the artifact that made run 71 green would preserve an unexplained success, not establish correctness.

### D — Continue expanding the explicit TOC/canonicalization/signing exceptions

Risk: high. Change size: deceptively small per iteration, unbounded cumulatively. Confidence: low.

This retains multiple owners of the same framework and has already produced serial path-shape failures. More pattern matching cannot prove PyInstaller's relocation and Apple's framework validation agree.

### E — Require users to install R, or ship it beside the app

Risk: high product risk. Change size: small technically. Confidence: low for the stated product.

It abandons self-containment and introduces host-version drift. A sidecar runtime also conflicts with Gatekeeper path randomization expectations when an app is moved independently; Apple explicitly warns against loading unprotected code outside the app bundle. [Apple, *Signing Disk Images*, lines 299–319](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html)

## Implementation order and stopping rules

1. Add failure-forensics at verbosity 4 and preserve the current failing bundle evidence. Do not alter signing semantics yet.
2. Add the isolated R fixture-app gate. If it fails, fix only the R adapter until it passes on clean arm64 and x86_64 runners.
3. Remove R TOC injection from the production PyInstaller spec; fail if Analysis retains any staged-R member.
4. Inject the fixture-qualified R tree after PyInstaller and verify byte/topology identity.
5. Move every mutation before a single final signing boundary. Sign and verify once.
6. Run focused cold builds for each architecture. Only after both pass, run runtime/UI smokes and archive roundtrip.
7. Run a second clean build on each architecture. One green run is evidence of a specimen; two clean independent runs are the minimum evidence against accidental cache dependence.
8. Preserve the exact artifacts and manifests used for issue acceptance.

Stop and redesign rather than adding another path exception if either condition occurs:

- the same staged framework passes standalone verification but fails the minimal nested fixture; or
- PyInstaller still discovers or emits any R-derived binary outside the injected framework after the spec's exclusion gate.

## Acceptance evidence

A durable fix is established only when all of the following are tied to the same commit:

- cache-cold arm64 and x86_64 builds succeed twice independently;
- the isolated framework fixture passes on both architectures;
- PyInstaller TOCs contain no R payload and the final app contains no flattened R duplicates;
- final shallow and deep strict code-sign verification pass, with complete inventories retained;
- frozen rpy2 API calculation, Rscript probe, Qt/Cocoa UI smoke, all required golden/sample projects, and archive extract-and-rerun pass;
- protected-branch builds reproduce the results;
- the release-signing path uses the same unsigned bundle construction and differs only in identity/timestamp/notarization steps.

Until those conditions hold, a successful cached workflow or an individually valid set of Mach-O files is not evidence that the macOS product is fixed.
