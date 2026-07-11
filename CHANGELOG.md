# Changelog

All notable RC MetaStudio changes will be recorded in this file.

RC MetaStudio starts a fresh maintained-product changelog. Historical release history for the Original OpenMeta[Analyst] Project is not reconstructed here; see [NOTICE.md](NOTICE.md) for provenance.

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
