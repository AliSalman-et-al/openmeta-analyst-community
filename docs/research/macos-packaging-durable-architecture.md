# Durable macOS packaging architecture

**Status:** Research recommendation, 20 July 2026  
**Scope:** Durable resolution of [#342](https://github.com/AliSalman-et-al/rc-metastudio/issues/342), [#343](https://github.com/AliSalman-et-al/rc-metastudio/issues/343), and [#344](https://github.com/AliSalman-et-al/rc-metastudio/issues/344)

## Decision

Keep two independent, thin macOS products: `macos-x64` built and exercised on GitHub's native Intel runner, and `macos-arm64` built and exercised on a native Apple Silicon runner. Both builds consume one versioned target manifest and the same packaging command, but never share compiled Python, Qt, R, or R-package payloads. Join them with Windows only after each exact archive has passed native qualification.

Treat the generated `.app` as the first authoritative deployment tree. PyInstaller is the sole Qt collector; the packaging code then canonicalizes the collected `R.framework`, relocates all final Mach-O edges, validates the complete graph, signs the immutable tree inside-out, runs the product workflow, archives it, and repeats structural validation against the extracted ZIP. No payload mutation is permitted after signing or archive hashing.

This is preferable to a universal application today. PyInstaller supports `x86_64`, `arm64`, and `universal2`, but explicitly requires compatible input binaries for the selected target. Qt also permits universal builds, yet the embedded stack includes Python extensions, rpy2, CRAN R frameworks, and compiled R packages whose slices and deployment floors must all agree. Two native products make that agreement observable and independently recoverable; a universal bundle would add a merge operation without reducing the required native tests ([PyInstaller macOS options](https://pyinstaller.org/en/stable/man/pyinstaller.html#macos-specific-options), [Qt macOS architectures](https://doc.qt.io/qt-6/macos.html#architectures)).

## The durable build contract

The repository should have one declarative target registry containing, for each target:

- runner label, host machine architecture, delivery target, artifact name, and minimum macOS version;
- exact Python, PyInstaller, PyQt/Qt, R installer, CRAN snapshot, and R package inputs;
- source URLs, SHA-256 values, official-package signature expectations, and architecture expectations; and
- expected framework version directory, executable topology, required Qt plugins, and allowed system-library roots.

All scripts and workflows should resolve this registry rather than derive one version label from another. R's product version, CRAN installer filename, framework directory, package repository platform, and package-compatibility label are different facts. Pinning and validating each one eliminates a major class of CI-only drift. R documents both its macOS framework installation and the need for binary maintainers to inspect and rewrite machine-specific dependencies using `otool` and `install_name_tool` ([R Installation and Administration: Frameworks](https://cran.r-project.org/doc/manuals/r-release/R-admin.html#Frameworks), [R Installation and Administration: binary packages](https://cran.r-project.org/doc/manuals/r-release/R-admin.html#Building-binary-packages)).

The effective deployment target must also be fixed before any native compilation. Qt warns against lowering its supported target and states that a binary will not run below its deployment target. The build should therefore export the repository's supported floor before building Python extensions or R packages, and inspect `LC_BUILD_VERSION` in every final Mach-O rather than trusting an environment variable after the fact ([Qt platform and deployment-target guidance](https://doc.qt.io/qt-6/macos.html#supported-versions)).

## Final-tree ownership

PyInstaller should remain the only Qt dependency collector. Qt requires the Cocoa QPA plugin (`libqcocoa.dylib`), the used plugin families, private Qt frameworks, and controlled plugin search paths; it recommends `qt.conf` and `otool` inspection for a self-contained deployment ([Qt for macOS deployment](https://doc.qt.io/qt-6/macos-deployment.html), [Qt plugin deployment](https://doc.qt.io/qt-6/deployment-plugins.html)). Adding a second collector such as `macdeployqt` after PyInstaller would create two components that can copy, rewrite, and sign the same graph.

The lifecycle is therefore fixed:

1. acquire and authenticate target-native inputs;
2. build the private R package library under the final deployment floor;
3. profile the complete R framework/native closure and give PyInstaller an explicit TOC;
4. let PyInstaller assemble the `.app`;
5. canonicalize `Contents/Frameworks/R.framework` in the generated app;
6. relocate the final rpy2 bridge and every private Mach-O edge;
7. reject wrong-architecture slices, unresolved `@rpath`, external R/X11/build paths, duplicate install identities, and ambiguous resolutions;
8. sign once, inside-out;
9. run frozen-runtime and representative product qualification;
10. create the ZIP, extract it with symlink-preserving tooling, and repeat validation against those exact bytes.

This ordering is not incidental. PyInstaller preserves macOS frameworks and adjusts Mach-O headers while collecting them; those transformations make pre-collection topology and signatures non-authoritative ([PyInstaller macOS code-signing notes](https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing), [PyInstaller 6 bundle changes](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/doc/CHANGES.rst#600-2023-09-22)). The durable invariant is consequently expressed and tested on the final app and again on the extracted archive.

For embedded R, keep the canonical framework representation now proven by the implementation: `Versions/<version>/R` is the regular Mach-O declared by `CFBundleExecutable`, while `Versions/<version>/Resources/lib/libR.dylib` is a relative in-framework alias to it. Only `R`, `Resources`, and `Versions` belong at the framework root. Validate the symlink type, relative target, resolved in-bundle destination, plist placement, and executable type—not ZIP mode bits alone. Apple's framework-signing guidance specifically calls out framework structure, `Info.plist`, symlinks, and nested subcomponents as signature-validation concerns ([Apple TN2206](https://developer.apple.com/library/archive/technotes/tn2206/)).

## Signing and notarization without a dormant workflow

The unsigned-community pipeline should exercise the real signing plan with ad-hoc identity `-`. The plan enumerates regular Mach-O files and valid nested code bundles, signs deepest code first and the outer app last, then verifies every item and performs strict deep verification. Apple prescribes inside-out signing and discourages `--deep` as a signing mechanism; deep verification remains appropriate ([Apple Code Signing Guide: signing code](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html)).

Production signing should be a policy/profile change around the same immutable app structure, not a parallel packaging implementation. A future trusted profile supplies:

- a `Developer ID Application` identity from an environment-protected secret;
- secure timestamps and Hardened Runtime;
- a reviewed, minimal entitlement file where runtime behavior genuinely requires exceptions;
- notarization of the already-qualified deliverable, followed by stapling; and
- post-staple validation and a new hash-bound stage record.

Apple requires Hardened Runtime for notarized software and recommends narrowly scoped capabilities and entitlements ([Apple hardened runtime](https://developer.apple.com/documentation/xcode/configuring-the-hardened-runtime), [Apple notarization workflow](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)). Keeping identity, timestamp, entitlements, notarization credentials, and stapling as inputs to one signer avoids a dormant workflow drifting away from the package it will eventually sign.

A signed artifact cannot be byte-identical to its unsigned input. The durable handoff is therefore a state transition that records the unsigned artifact hash as input and the signed/notarized artifact hash as output. It must never rebuild application payloads. This preserves traceability while acknowledging the intentional signature and ticket mutations.

## Evidence and supply-chain model

One release-set manifest should bind the product version, full protected-branch commit SHA, trust profile, target list, and hashes of every policy-defining input. Each target advances through ordered, hash-chained stages such as `assembled`, `unsigned-qualified`, `verified`, `attested`, and later `signed`/`notarized`. A join gate rejects missing targets, foreign commits, skipped stages, changed archive hashes, or policy-input drift.

For every target, retain separately:

- downloaded-input provenance and official signature evidence;
- direct-build input manifest and hashes;
- pre-sign and post-sign native graphs and signing inventories;
- frozen-runtime stdout/stderr;
- representative analysis, save/reopen, launch, locale, accessibility, clipboard, and fractional-scale evidence;
- archive hash and extracted-tree inspection; and
- a CycloneDX SBOM generated from the final extracted inventory.

GitHub's artifact attestations cryptographically bind released artifacts to repository, workflow, commit, and triggering event, and can separately bind an SBOM. GitHub also stresses that attestations must be verified and are provenance—not a claim that software is safe ([GitHub artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations), [GitHub provenance and SBOM attestation procedure](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)). Therefore attest the ZIP that users download and its final SBOM only after native qualification, and verify those attestations during promotion. Do not attest routine intermediate test artifacts.

The current file-level CycloneDX inventory is useful for byte accountability but is not yet a dependency-grade SBOM. Long term, enrich it with package identity and relationships from locked Python distributions, Qt modules/plugins, R itself, and installed R packages while retaining file hashes. This can be introduced as a schema evolution without weakening today's inventory gate.

## CI simplification

Keep only four workflow roles:

1. fast source verification;
2. reusable native package builders, one Windows workflow and one two-target macOS matrix;
3. candidate orchestration that initializes one release identity, invokes builders, and joins exact outputs; and
4. qualification/promotion that downloads, verifies, attests, and publishes without rebuilding.

Workflows should select runners, configure least-privilege permissions, invoke public scripts, upload exact outputs, and join results. Packaging order, validation rules, manifest schemas, and signing inventory belong in versioned scripts with contract tests. Pin third-party Actions by commit, keep caches performance-only, and authenticate/hash every restored external input before it affects a release. GitHub recommends least-privilege `GITHUB_TOKEN` permissions and pinning actions to full commit SHAs as the immutable form of action selection ([GitHub secure use of reference workflows](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions#using-third-party-actions), [GitHub workflow permissions](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions#permissions)).

The macOS matrix may remain `max-parallel: 1` while Intel capacity is scarce, but target independence must not depend on serialization. Fail-fast should stay disabled so a failure on one architecture does not erase evidence from the other. Concurrency cancellation is appropriate for manual qualification of superseded commits, not for an immutable release candidate already selected for publication.

## Maintenance rules

- Update pinned Python, Qt, R, PyInstaller, or runner images one dimension at a time and require both native package lanes before merging.
- Keep a retained known-good candidate as the comparison point for graph, inventory, archive size, startup, and representative-analysis changes.
- Make parsers tolerant of harmless presentation differences in first-party tool output, but keep validators strict about semantic evidence. Store raw stdout/stderr beside parsed JSON so parser defects are diagnosable.
- Test manifest schemas, archive symlink semantics, signature-output parsing, graph rejection rules, and delivery-state transitions on Windows/Linux; reserve macOS CI for real Mach-O, codesign, LaunchServices, Cocoa, and R-runtime behavior.
- Never infer success from assembly alone. A green macOS deliverable means the exact extracted archive starts normally on its native architecture and completes the representative in-process R workflow.

## Closure and ongoing health

Issues #342 and #343 are durably resolved only when current protected-branch runs produce downloadable native Intel and ARM64 archives whose exact extracted bytes pass structural, signature, runtime, and representative product qualification. Issue #344 additionally requires the Windows, Intel, and ARM64 results to share one release identity and pass the hash-bound join gate.

After closure, make that candidate gate required for release publication rather than for every source-only pull request. Track median build time, cache hit rate, archive size, native-file count, package count, and time-to-first-product-smoke as trend data; alert on unexpected deltas, but keep correctness gates based on explicit contracts. This architecture then remains understandable: build natively, own the final tree, mutate once, sign once, test the shipped bytes, and promote only by verified hashes.
