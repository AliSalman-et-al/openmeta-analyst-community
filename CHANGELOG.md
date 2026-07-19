# Changelog

All notable RC MetaStudio changes will be recorded in this file.

RC MetaStudio starts a fresh maintained-product changelog. Historical release history for the Original OpenMeta[Analyst] Project is not reconstructed here; see [NOTICE.md](NOTICE.md) for provenance.

## 0.2.0 - 2026-07-19

### Added

- Added the first native Qt 6 / PyQt6 release of RC MetaStudio for Windows x64.
- Added a self-contained Windows package with Python 3.11, Qt 6.11, R 4.6.1, RCMetaR 0.2.0, and an API-mode rpy2 bridge.
- Added the versioned ZIP-and-JSON `.rcms` project format with schema validation, atomic saves, and converted sample projects.

### Changed

- Replaced the Qt 5 and PyQt5 application runtime with the locked native Qt 6 stack.
- Updated generated forms, resources, layouts, accessibility behavior, and packaged automation for Qt 6.
- Made the Windows x64 package the sole 0.2.0 downloadable artifact; native Intel and Apple Silicon macOS packages are deferred to 0.2.1.

### Removed

- Removed the PyQt5 compatibility surface and legacy pickle-based project loading from the maintained application.

### Fixed

- Fixed Windows packaging so R is staged without elevation and the complete Qt/R application is built and qualified through one local-and-CI command.
- Fixed dark-mode contrast for highlighted effect-size cells and Results-window plot previews.
- Fixed Results-window SVG and raster plots inheriting the dark themed scene background instead of painting an opaque white canvas.
- Fixed dataset-type wizard icons so they follow the active light or dark palette, and made the Diagnostic choice match the other button geometry.
- Fixed standard meta-analysis Method and Parameters dialogs incorrectly using diagnostic likelihood-ratio wording.

## 0.1.2 - 2026-07-15 (Prerelease)

### Added

- Added adaptive, screen-bounded layouts across the main workspace, Results window, dataset editor, setup wizard, analysis configuration, data-entry, and supporting dialogs.
- Added packaged native-layout evidence for Windows x64 and macOS Intel x64, including high-DPI and constrained-screen scenarios.
- Added a self-contained semantic SVG icon system for application actions and statistical concepts.

### Changed

- Improved window placement, size persistence, splitter behavior, overflow handling, and high-DPI scaling across the application.
- Improved keyboard access, focus handling, text visibility, and control sizing in data-entry and analysis workflows.
- Improved Results-window plot fitting and made SVG plots render reliably in Qt across supported platforms.
- Refined functional icon artwork and sizing while preserving existing app and splash branding.

### Fixed

- Fixed layout clipping, overlap, unreachable controls, and unstable resizing on smaller screens and enlarged display scales.
- Fixed table copy and paste when no cells are selected.
- Fixed empty-dataset handling in the dataset editor.
- Fixed first-show sizing in the Method and Parameters dialog.

## 0.1.1 - 2026-07-11 (Prerelease)

### Added

- Added publication-style Default, RevMan, and BMJ forest plots across supported analysis families.
- Added publication-style bubble plots for meta-regression results.
- Added editable plot controls for supported forest and bubble plots.
- Added Windows x64 and macOS Intel x64 prerelease packages.

### Changed

- Improved plot sizing and live reflow in the Results window.
- Improved plot layout, labels, spacing, scaling, and display precision across supported styles.
- Improved PDF, PNG, SVG, and TIFF export behavior and removed unwanted intermediate files.
- Split diagnostic forest results into separate editable plots for each metric.
- Simplified diagnostic and meta-regression setup so method, parameter, covariate, and plot choices use consistent screens.
- Simplified the README around downloading and using RC MetaStudio; moved maintenance commands into a separate maintainer guide.

### Fixed

- Fixed plot edits that did not apply, did not close as expected, or failed for cumulative, leave-one-out, subgroup, and diagnostic forest plots.
- Fixed missing plot-editing and export actions for supported result types.
- Fixed regenerated plots overlapping later Results-window content.
- Fixed plots rendering too small on first display or failing to follow window resizing.

## 0.1.0 - 2026-07-06

### Added

- Established RC MetaStudio as the maintained product identity for open-source desktop software for advanced meta-analysis by Research Consultancy (RC).
- Added centralized provenance, license posture, no-warranty, and affiliation-disclaimer documentation in `NOTICE.md`.
- Added the maintainer policy that unsolicited public code contributions are not currently accepted while public issue feedback may be accepted.
- Documented release-packaging expectations for third-party component and asset inventory.

### Changed

- Started the maintained RC MetaStudio release history instead of extending the Original OpenMeta[Analyst] Project release history.
- Adopted GPL-3.0-or-later as the maintained distribution posture where permitted by the original GPL-2.0-or-later grant.
- Defined `.rcms` as the maintained RC MetaStudio project-file identity and RCMetaR as the private bundled R package identity for the rebrand.

### Removed

- Removed README language that presented the maintained product as RC MetaStudio Community or as a community fork.
- Recorded the breaking identity direction away from retired project-file, R-package, and abandoned support-channel names for future phase issues.
