# RC MetaStudio Migration Plan

This plan tracks the phased migration from the OpenMeta[Analyst] Community modernization codebase to RC MetaStudio. The migration is intentionally split into reviewable phases so identity, file-format, layout, CI, packaging, and documentation changes remain diagnosable.

## Ground Rules

- Preserve Analysis Behavior unless a reviewed Statistical Modernization Drift or Compatibility Exception records the change.
- Do not preserve OpenMeta[Analyst], OpenMetaAnalyst, OpenMetaR, `openmetar.*`, `.oma`, `OMA_*`, `modern`, or generic legacy framing in active surfaces.
- Keep historical ADRs as decision history; use later ADRs as the authority when decisions conflict.
- Do not redesign deep module interfaces during the mechanical identity and layout migration.
- Do not ship `.oma` import, conversion, migration, bundled help, network callback, or automatic diagnostic-upload features.

## Active-Surface Rename Audit

Use this as an audit checklist, not a blind global replacement. Historical ADRs, `NOTICE.md` provenance, scholarly/statistical references, and original copyright notices are exceptions when the old term is historically accurate.

| Old active-surface token | Current target |
| --- | --- |
| `OpenMeta[Analyst]`, `OpenMetaAnalyst`, `Open Meta-Analyst` | `RC MetaStudio` |
| `OpenMeta[Analyst] Community` | `RC MetaStudio` |
| `OpenMetaR` | `RCMetaR` |
| `openmetar` / `openmetar.*` | `rcmetar` / `rcmetar.*` |
| `.oma` | `.rcms` |
| `OMA_*` | `RCMS_*` |
| `openmeta-analyst-community-modern` | `rc-metastudio` |
| `modern-*` lane names | evidence-based lane names such as `smoke`, `fast`, `package`, `r-stack`, `analysis-regression`, `verification` |
| Brown/Tufts/CEBM support links and callbacks | remove, or replace static project links with `https://github.com/AliSalman-et-al/` |
| generic `legacy` framing | precise terms such as Original OpenMeta[Analyst] Project, Retired Reference Implementation, Retired OMA Compatibility, or RC MetaStudio |

## Decision Index

Use these ADRs as the current authority for implementation. Older ADRs remain historical records; when they conflict with the ADRs below, the later RC MetaStudio ADR supersedes them.

Identity and provenance:

- [ADR 0082](../adr/0082-use-rcmetar-as-the-final-r-package-identity.md): Use RCMetaR as the final R package identity.
- [ADR 0083](../adr/0083-use-derived-maintained-file-copyright-notices.md): Treat rewritten original-source descendants as Derived Maintained Files.
- [ADR 0087](../adr/0087-keep-historical-adrs-and-rename-active-surfaces.md): Keep historical ADRs, rename active surfaces.
- [ADR 0088](../adr/0088-centralize-project-provenance-in-notice.md): Centralize provenance in `NOTICE.md`.
- [ADR 0089](../adr/0089-use-gplv3-license-file-and-spdx-headers.md): Use GPLv3 license file and SPDX headers.
- [ADR 0120](../adr/0120-preserve-scholarly-and-copyright-attribution-only.md): Preserve scholarly and copyright attribution only.
- [ADR 0122](../adr/0122-remove-community-fork-language.md): Remove community-fork language.
- [ADR 0163](../adr/0163-use-open-source-desktop-software-description.md): Use the canonical RC MetaStudio product description.
- [ADR 0164](../adr/0164-use-research-consultancy-as-publisher.md): Use Research Consultancy (RC) as publisher.
- [ADR 0165](../adr/0165-list-ali-salman-as-maintainer-and-author-of-modifications.md): List Ali Salman as maintainer and author of modifications.
- [ADR 0166](../adr/0166-use-gpl-3-or-later-spdx-for-maintained-files.md): Use GPL-3.0-or-later SPDX for maintained files.
- [ADR 0167](../adr/0167-inventory-third-party-assets-and-components.md) and [ADR 0168](../adr/0168-add-third-party-notices-when-bundled-components-remain.md): Inventory third-party components and add notices when needed.

Project files, samples, and settings:

- [ADR 0084](../adr/0084-adopt-rcms-project-files-and-retire-oma-compatibility.md): Adopt `.rcms` files and retire `.oma` compatibility.
- [ADR 0085](../adr/0085-do-not-ship-oma-migration-tooling.md): Do not ship `.oma` migration tooling.
- [ADR 0101](../adr/0101-commit-rcms-sample-projects-with-a-manifest.md): Commit `.rcms` samples with a manifest.
- [ADR 0102](../adr/0102-start-rcms-as-the-renamed-project-file-container.md): Start `.rcms` as the renamed project-file container.
- [ADR 0121](../adr/0121-keep-scientific-sample-project-names.md): Keep scientific sample names.
- [ADR 0133](../adr/0133-use-rc-metastudio-project-file-labels.md): Use `RC MetaStudio Project (*.rcms)` labels.
- [ADR 0142](../adr/0142-use-lowercase-rcms-project-extension.md): Use lowercase `.rcms`.
- [ADR 0143](../adr/0143-reset-settings-and-config-namespaces.md) and [ADR 0144](../adr/0144-do-not-ship-settings-migration.md): Reset settings/config namespaces and do not migrate old settings.
- [ADR 0147](../adr/0147-convert-sample-projects-to-new-module-paths.md): Convert sample projects to new module paths.
- [ADR 0148](../adr/0148-treat-pickle-project-storage-as-transitional.md) and [ADR 0149](../adr/0149-do-not-add-a-user-facing-pickle-warning.md): Treat pickle storage as transitional without user-facing warning.
- [ADR 0158](../adr/0158-treat-sample-projects-as-user-facing-examples.md): Treat sample projects as user-facing examples.
- [ADR 0161](../adr/0161-distinguish-project-files-from-analysis-datasets.md): Distinguish Project files from analysis datasets.

Python, R, API, and layout:

- [ADR 0086](../adr/0086-rename-the-r-facade-to-rcmetar.md): Rename the R facade to `rcmetar.*`.
- [ADR 0091](../adr/0091-rename-product-branded-internal-identifiers.md): Rename product-branded internal identifiers.
- [ADR 0092](../adr/0092-separate-identity-migration-from-codebase-reorganization.md): Separate identity migration from reorganization.
- [ADR 0093](../adr/0093-reorganize-files-before-redesigning-deep-modules.md): Reorganize files before deep-module redesign.
- [ADR 0094](../adr/0094-use-a-polyglot-rc-metastudio-repository-layout.md): Use the polyglot repository layout.
- [ADR 0098](../adr/0098-use-python-package-entry-points-for-rc-metastudio.md): Use Python package entry points.
- [ADR 0099](../adr/0099-test-rcmetar-as-an-independent-r-package.md) and [ADR 0100](../adr/0100-keep-rcmetar-private-to-rc-metastudio.md): Test RCMetaR independently while keeping it private.
- [ADR 0114](../adr/0114-use-rc-metastudio-as-the-python-package-name.md): Use `rc_metastudio` as the Python package.
- [ADR 0115](../adr/0115-use-rc-metastudio-as-the-primary-command-name.md): Use `rc-metastudio` as the primary command.
- [ADR 0118](../adr/0118-use-rc-metastudio-python-distribution-metadata.md): Use RC MetaStudio Python metadata.
- [ADR 0145](../adr/0145-rename-unclear-legacy-python-module-prefixes.md), [ADR 0155](../adr/0155-rename-product-era-python-classes.md), and [ADR 0156](../adr/0156-retire-the-oma-acronym-from-active-surfaces.md): Rename unclear/product-era Python identifiers and retire `OMA`.
- [ADR 0152](../adr/0152-commit-rcmetar-roxygen-generated-package-artifacts.md), [ADR 0153](../adr/0153-rename-rcmetar-product-branded-r-files-and-topics.md), [ADR 0154](../adr/0154-rename-private-openmetar-r-helpers.md), and [ADR 0157](../adr/0157-use-rcmetar-r-package-artifact-names.md): Rename and package RCMetaR correctly.

UI, resources, help, and callbacks:

- [ADR 0095](../adr/0095-treat-qt-ui-files-as-canonical-resources.md): Treat Qt `.ui` files as canonical resources.
- [ADR 0108](../adr/0108-remove-bundled-legacy-help.md), [ADR 0150](../adr/0150-delete-bundled-help-and-help-access-together.md): Remove bundled legacy help and Help access together.
- [ADR 0109](../adr/0109-keep-an-rc-metastudio-about-legal-dialog.md) and [ADR 0137](../adr/0137-keep-license-and-provenance-inside-about-legal.md): Keep About/Legal as the legal/provenance UI.
- [ADR 0110](../adr/0110-remove-network-callbacks-and-use-github-links.md) and [ADR 0111](../adr/0111-replace-bug-report-callbacks-with-static-github-links.md): Remove callbacks and use static GitHub links.
- [ADR 0113](../adr/0113-rename-branding-assets-before-replacing-icons.md): Rename branding assets before replacing icons.
- [ADR 0126](../adr/0126-do-not-auto-collect-diagnostics-for-issues.md): Do not auto-collect diagnostics.
- [ADR 0138](../adr/0138-remove-openmeta-branding-from-generated-results.md): Remove OpenMeta branding from generated results.
- [ADR 0146](../adr/0146-rename-identity-bearing-qt-form-names.md): Rename identity-bearing Qt form names.
- [ADR 0160](../adr/0160-keep-only-a-functional-rebranded-welcome-screen.md): Keep only a functional rebranded welcome screen.

Docs, tests, CI, packaging, and cleanup:

- [ADR 0096](../adr/0096-keep-runtime-scratch-output-out-of-source-layout.md) and [ADR 0097](../adr/0097-remove-committed-generated-and-cache-artifacts.md): Keep runtime/generated artifacts out of source.
- [ADR 0103](../adr/0103-use-rcms-environment-variable-prefixes.md): Use `RCMS_*` environment variables.
- [ADR 0104](../adr/0104-use-rc-metastudio-release-and-ci-artifact-names.md), [ADR 0105](../adr/0105-use-evidence-based-verification-lane-names.md), and [ADR 0106](../adr/0106-remove-legacy-framing-from-active-surfaces.md): Rename release/CI artifacts and remove modernization/legacy framing.
- [ADR 0107](../adr/0107-rewrite-readme-for-rc-metastudio.md): Rewrite README.
- [ADR 0112](../adr/0112-move-packaging-definitions-under-packaging.md): Move packaging definitions under `packaging/`.
- [ADR 0116](../adr/0116-restructure-active-docs-away-from-modernization.md): Restructure active docs.
- [ADR 0117](../adr/0117-organize-tests-by-runtime-and-evidence-type.md): Organize tests by runtime and evidence type.
- [ADR 0119](../adr/0119-use-rc-metastudio-names-for-product-branded-outputs.md): Use RC MetaStudio names for outputs.
- [ADR 0123](../adr/0123-do-not-open-a-public-contribution-workflow.md), [ADR 0124](../adr/0124-state-contribution-policy-in-readme.md), and [ADR 0125](../adr/0125-allow-public-issue-feedback-without-public-code-contributions.md): Document contribution and issue policies.
- [ADR 0130](../adr/0130-add-targeted-supersession-notes-to-conflicting-adrs.md): Add targeted supersession notes.
- [ADR 0131](../adr/0131-add-an-identity-migration-audit-script.md) and [ADR 0132](../adr/0132-test-high-risk-identity-boundaries-first.md): Add identity audit and high-risk tests.
- [ADR 0134](../adr/0134-reset-rc-metastudio-and-rcmetar-versioning.md), [ADR 0135](../adr/0135-lock-rcmetar-version-to-rc-metastudio.md), and [ADR 0136](../adr/0136-start-an-rc-metastudio-changelog.md): Reset versioning and start changelog.
- [ADR 0139](../adr/0139-use-a-specific-repository-url-when-available.md), [ADR 0140](../adr/0140-use-rc-metastudio-as-the-repository-name.md), and [ADR 0141](../adr/0141-review-git-attributes-during-artifact-cleanup.md): Set repository URL/name and review git attributes.
- [ADR 0151](../adr/0151-rewrite-evidence-carrying-tests-and-delete-low-value-string-locks.md): Rewrite evidence tests, delete low-value string locks.

Runtime, feature scope, and sequencing:

- [ADR 0090](../adr/0090-preserve-analysis-behavior-through-the-rc-metastudio-rebrand.md): Preserve Analysis Behavior through the rebrand.
- [ADR 0127](../adr/0127-implement-the-rc-metastudio-migration-in-small-phases.md), [ADR 0128](../adr/0128-track-the-rc-metastudio-migration-as-a-parent-issue.md), and [ADR 0129](../adr/0129-sequence-rc-metastudio-phase-issues-with-limited-parallelism.md): Implement in phased issues with limited parallelism.
- [ADR 0159](../adr/0159-use-explicit-automation-mode-for-packaged-smoke-checks.md): Use explicit automation mode for packaged smoke checks.
- [ADR 0162](../adr/0162-do-not-require-evidence-synthesis-as-product-description.md): Do not require evidence-synthesis wording.
- [ADR 0169](../adr/0169-remove-obsolete-python2-and-pyqt4-compatibility-code.md): Remove obsolete Python 2/PyQt4 code.
- [ADR 0170](../adr/0170-stay-on-pyqt5-during-identity-and-layout-migration.md), [ADR 0171](../adr/0171-stay-on-python-3-11-during-identity-and-layout-migration.md), [ADR 0172](../adr/0172-keep-r-runtime-and-dependency-policy-stable-during-migration.md), [ADR 0173](../adr/0173-keep-platform-scope-stable-during-migration.md), and [ADR 0174](../adr/0174-keep-uv-and-dependency-tooling-stable-during-migration.md): Keep runtimes, platform scope, and tooling stable.
- [ADR 0175](../adr/0175-freeze-statistical-feature-scope-during-migration.md), [ADR 0176](../adr/0176-retain-network-meta-analysis-code-for-future-activation.md), and [ADR 0177](../adr/0177-hide-retained-future-feature-code-until-verified.md): Freeze feature scope, retain future network meta-analysis code, and hide unverified features.

## Phase 1: Legal, Provenance, and README

Acceptance criteria:

- `NOTICE.md` describes original-project provenance, RC MetaStudio maintainership, GPL-3.0-or-later distribution, no-warranty terms, and affiliation disclaimer.
- `LICENSE` contains GPLv3 text.
- `README.md` is rewritten for RC MetaStudio, links to `NOTICE.md`, documents the no-public-contribution policy, and avoids modernization-era framing.
- Source-header conventions are documented for Derived Maintained Files and New Maintained Files.

Verification:

- Search active docs for stale product/support/affiliation language.
- Confirm README uses RC MetaStudio, RCMetaR, `.rcms`, and current verification lane terminology.

## Phase 2: Product, Package, and API Identity

Acceptance criteria:

- Python distribution metadata uses `rc-metastudio`.
- Python import package is `rc_metastudio`.
- Primary command is `rc-metastudio`.
- R package identity is `RCMetaR`.
- R callable facade uses `rcmetar.*`.
- Product-scoped environment variables use `RCMS_*`.
- Product-branded internal identifiers, scripts, tests, manifests, logs, and generated outputs use RC MetaStudio naming.

Verification:

- Search active surfaces for OpenMeta[Analyst], OpenMetaAnalyst, OpenMetaR, `openmetar`, and `OMA_*`.
- Run Python and R unit-level checks relevant to renamed interfaces.

## Phase 3: Project File Identity and Samples

Acceptance criteria:

- `.rcms` is the only supported project-file extension.
- Developer documentation makes clear that the initial `.rcms` container preserves the current pickle-based content shape and is transitional pending a later structured format.
- `.oma` support is removed from active app behavior, tests, docs, file dialogs, packaging, and workflow manifests.
- Existing repository sample projects are converted or renamed to `.rcms`.
- `sample_projects` contains committed `.rcms` fixtures and a manifest describing provenance, analysis family, workflow coverage, and test usage.

Verification:

- App and tests open `.rcms` sample projects.
- Search active surfaces for `.oma` except historical/provenance records.

## Phase 4: Repository Layout

Target layout:

```text
/
├── src/rc_metastudio/
│   ├── __init__.py
│   ├── __main__.py
│   ├── app/
│   ├── analysis/
│   ├── data/
│   ├── gui/
│   ├── persistence/
│   └── resources/
│       ├── qt/
│       └── images/
├── r/RCMetaR/
├── tests/
│   ├── python/
│   ├── r/
│   ├── integration/
│   └── packaging/
├── sample_projects/
├── packaging/
├── scripts/
└── docs/
```

Acceptance criteria:

- Loose Python modules move under `src/rc_metastudio`.
- `src/R/OpenMetaR` moves to `r/RCMetaR`.
- Qt `.ui` files and images move under packaged resources.
- Generated UI Python is treated as transitional or build output.
- Import paths, resource paths, and test discovery are updated mechanically.

Verification:

- Run smoke and relevant fast verification lanes.
- Confirm imports resolve through the installed package, not loose source files.

## Phase 5: Verification and CI Lane Renames

Acceptance criteria:

- Active workflow, script, test, and docs labels use evidence-based names such as `smoke`, `fast`, `package`, `r-stack`, `analysis-baseline`, `analysis-regression`, and `verification`.
- `modern` and generic `legacy` framing are removed from active surfaces.
- Tests are organized by runtime and evidence type rather than `tests/modern`.

Verification:

- CI/workflow dry runs or local script runs use new lane names.
- Search active surfaces for `modern` and generic `legacy` outside historical ADRs.

## Phase 6: Packaging and Release Identity

Acceptance criteria:

- Packaging definitions live under `packaging/`.
- PyInstaller builds use the package entry point.
- Windows executable is `RCMetaStudio.exe`.
- macOS bundle is `RCMetaStudio.app`.
- Release archives use RC MetaStudio names.
- Bundle identifiers use RC MetaStudio ownership naming.

Verification:

- Build packaging contracts or packaged smoke checks for changed platform paths.
- Confirm generated artifacts contain no OpenMeta[Analyst], OMA, OpenMetaR, or `modern` names.

## Phase 7: Remove Bundled Help and Callbacks

Acceptance criteria:

- Bundled legacy HTML help is removed.
- In-app Help access to legacy docs is removed.
- About/Legal dialog is rewritten for RC MetaStudio.
- Brown/CEBM/Tufts callbacks, support links, update checks, and bug-report submission callbacks are removed.
- Static project/issue links point to `https://github.com/AliSalman-et-al/` where needed.

Verification:

- Search app UI strings and Qt resources for obsolete help/support URLs.
- Manual or automated GUI check confirms no broken Help action remains.

## Phase 8: Generated and Runtime Artifact Cleanup

Acceptance criteria:

- Committed `.pyc`, `__pycache__`, cache directories, stale build outputs, and runtime scratch outputs are removed.
- Runtime analysis artifacts go to app-managed cache/temp locations or explicit test temp directories.
- `.gitignore` prevents generated/cache artifacts from returning.

Verification:

- Repository status after tests does not show generated noise.
- Tests that need outputs assert against temporary directories.

## Deferred Work

- Deep-module redesign and interface reshaping.
- Public RCMetaR package support.
- `.rcms` structured file-format redesign.
- New RC MetaStudio user documentation.
- Replacement branding/icons.
- Diagnostic bundle export.
- Public contribution workflow.
