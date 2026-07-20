# macOS embedded R signing root cause

**Status:** Research finding, 20 July 2026  
**Scope:** Issues [#342](https://github.com/AliSalman-et-al/rc-metastudio/issues/342), [#343](https://github.com/AliSalman-et-al/rc-metastudio/issues/343), and [#344](https://github.com/AliSalman-et-al/rc-metastudio/issues/344) at repository commit `1cfa8a4e`

## Finding

The current blocker is no longer acquisition, target architecture, rpy2 API mode, or Mach-O relocation. It is that the code repairs the R framework's executable topology **before** PyInstaller, while PyInstaller subsequently reconstructs the framework and restores the original topology.

The official CRAN installer is the correct authenticated source of the target-native R runtime. Its outer framework can remain in the application, but a framework whose `Info.plist` declares `CFBundleExecutable=R` must present that final executable as a regular file when strict signing runs. R's installed topology instead makes `Versions/<version>/R` an alias of `Resources/lib/libR.dylib`. The repository already knows how to invert those two paths, but currently does it at the wrong lifecycle point.

The minimal fix is therefore:

1. install or extract the pinned official target-native R package and retain its signature, hash, version, and architecture evidence;
2. finish the private R package library and relocate its complete Mach-O closure while staged;
3. let PyInstaller collect and reconstruct `R.framework`;
4. in the **generated app**, replace `Versions/<version>/R` with the regular `libR.dylib` and replace `Resources/lib/libR.dylib` with the relative alias `../../R`;
5. relocate final private R/rpy2 load edges, inspect the final topology, and run the existing explicit inside-out signer once, last; and
6. prove both thin architectures through the frozen runtime and packaged workflow before the three-artifact candidate gate is allowed to pass.

Embedding a framework is therefore not disproven. The failure proves that pre-collection mutation cannot establish a post-collection invariant. If final-tree canonicalization still fails strict signing, the clean fallback is to collect only `R.framework/Resources` under a neutral logical `R-runtime` directory; that avoids framework classification entirely. It is a larger change and should not precede the smaller final-tree fix.

## Evidence from the failing implementation

The failure sequence shows that adding framework metadata and rearranging the `libR` alias does not solve the structural problem:

- Earlier attempts reached PyInstaller only after fixing external `/Library/Frameworks/R.framework` and `/opt/R` load edges, normalizing private dylib identities, and relocating `_rinterface_cffi_api` to the staged runtime. Those were real defects, but they are no longer the latest failure.
- Commit `1ec68001` added framework signing metadata. Commit `1cfa8a4e` went further: it sets `CFBundleExecutable=R`, replaces `Versions/<version>/R` with the regular `libR.dylib`, and makes `Resources/lib/libR.dylib` point back to it before PyInstaller collection.
- Despite that pre-collection assertion, Intel job [88291863122](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29723676339/job/88291863122) in run [29723676339](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29723676339) still failed while signing the generated app. `codesign` reported `the main executable or Info.plist must be a regular file (no symlinks, etc.)` and identified `Contents/Frameworks/R.framework` as the subcomponent. The retained `pre-sign-native-graph` is decisive: it records Mach-O at `R.framework/Versions/4.6-x86_64/Resources/lib/libR.dylib` and none at `R.framework/Versions/4.6-x86_64/R`. PyInstaller therefore reversed the pre-build swap before the signer saw the app.

That last observation matters. The staged tree passed the repository's “regular executable” assertion, but the generated bundle failed the same invariant. PyInstaller had reconstructed a framework from the collection TOC and its framework rules, so the staging layout was not authoritative for the final app. The repair belongs after collection, beside the existing final rpy2 relocation, and before inspection/signing. The final inspector—not a staging assertion—must prove which path is the regular Mach-O and which is its relative alias.

## Why `.framework` changes the rules

Apple's code-signing rules seal substantially all bundle contents, record nested code signatures, and validate symlinks. A nested framework must have its `Info.plist` at `Versions/Current/Resources`; its top level may contain only `Versions` and symlinks into `Versions/Current`. Apple specifically directs developers who see an embedded-framework failure to check top-level content, `Info.plist`, and symlink topology. It also explains that the additional `In subcomponent:` line names the nested code responsible for an outer signing failure ([Apple TN2206](https://developer.apple.com/library/archive/technotes/tn2206/)). The latest CI error is exactly this class of failure.

PyInstaller 6 intentionally recognizes `.framework` inputs, restores `Versions/Current` and top-level framework symlinks, and places the result in `Contents/Frameworks`. For ordinary mixed trees, it instead puts data below `Contents/Resources`, native libraries below `Contents/Frameworks`, and cross-links the two trees so relative layouts continue to work ([PyInstaller 6.0 framework and BUNDLE changes](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/doc/CHANGES.rst#600-2023-09-22)). The implementation opts into the first, stricter behavior by mapping its TOC under `R.framework`. That remains viable if the generated framework is canonicalized after PyInstaller's restoration; a neutral `R-runtime` destination is the fallback that opts into the second behavior.

The R project documents the CRAN installation at `/Library/Frameworks/R.framework`, with the current R home exposed through `Resources`, and documents its native libraries under `Resources/lib`. It also tells binary-package maintainers to inspect compiled code with `otool -L` and use `install_name_tool` for machine-specific dependencies ([R Installation and Administration: Frameworks](https://cran.r-project.org/doc/manuals/r-release/R-admin.html#Frameworks), [Building binary packages](https://cran.r-project.org/doc/manuals/r-release/R-admin.html#Building-binary-packages)). These facts require preserving the R **home contents and native closure**; they do not require the frozen application to advertise that private home as an Apple framework bundle.

## PyInstaller and final signing

PyInstaller rewrites Mach-O headers, invalidating prior signatures, and therefore ad-hoc signs collected binaries during assembly. With a real signing identity it enables the hardened runtime, and its final automatic app signing uses `--deep`; a failure there is only a warning that manual signing is required ([PyInstaller macOS binary code signing](https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing)). The final product should not rely on that recursive repair pass.

Apple's prescribed production order is explicit and inside-out: sign nested code first and the outer app last. Apple discourages `--deep` for signing and recommends it for final verification ([Apple Code Signing Tasks](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html), [latest code-signature format](https://developer.apple.com/documentation/xcode/using-the-latest-code-signature-format)). The repository's `scripts/sign_macos_app.py` already models the useful part of this policy by enumerating regular Mach-O files, signing deepest-first, signing nested bundles, signing the app, and then verifying the inventory. The subsequent second `codesign --force ... "$app_bundle"` is redundant and should be removed; no bytes should change after the explicit signing pass.

For future Developer ID distribution, use the same final inventory and order with a `Developer ID Application` identity and secure timestamp. Hardened Runtime is required for notarization, every executable must be signed, and exceptions should be represented only by narrowly scoped entitlements ([Apple hardened runtime](https://developer.apple.com/documentation/xcode/configuring-the-hardened-runtime), [Apple notarization preparation](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)). Neither the corrected framework nor the neutral-runtime fallback prevents that later step.

## Minimal implementation

The next iteration should move the already-written repair to the authoritative final tree:

- Remove the pre-PyInstaller executable swap. Immediately after PyInstaller, resolve the generated `Versions/Current`, require `Versions/<version>/R` to be the expected alias of `Resources/lib/libR.dylib`, move the regular dylib to `Versions/<version>/R`, and recreate `Resources/lib/libR.dylib -> ../../R`.
- Require the generated framework `Info.plist` and main executable to be regular files and the `libR` alias to be relative, in-bundle, and resolving to that executable. Record these exact file types and paths in the pre-sign graph.
- Update relocation after collection against the final physical targets. Reject all `/Library/Frameworks/R.framework`, `/opt/R`, build-root, unresolved `@rpath`, wrong-architecture, duplicate, and ambiguous load edges.
- Retain `R_HOME=Contents/Frameworks/R.framework/Resources`, the framework-specific inspector, and the outer framework identity for this attempt.
- Remove the duplicate outer `codesign` call after `sign_macos_app.py`; that helper has already signed the app last.
- Sign every regular Mach-O and valid remaining nested bundle inside-out, sign the app once, then require `codesign --verify --strict --deep --verbose=2`.

If and only if that final-tree repair still fails, switch the TOC prefix to neutral `R-runtime`, omit the framework wrapper and metadata, and point packaged `R_HOME` at `Contents/Resources/R-runtime`. PyInstaller's documented Resources/Frameworks cross-links then preserve the mixed R home without presenting it to `codesign` as a nested framework.

The native acceptance boundary remains unchanged: Intel and ARM64 must each produce a downloadable thin-architecture ZIP, launch the normal `.app`, load the private in-process R/rpy2 API runtime, complete the representative project workflow, exit cleanly, and retain hash-bound evidence. Only those results, followed by the exact three-artifact qualification matrix, prove issues #342-#344 complete.
