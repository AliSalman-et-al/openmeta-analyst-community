# Changelog

All notable RC MetaStudio changes will be recorded in this file.

RC MetaStudio starts a fresh maintained-product changelog. Historical release history for the Original OpenMeta[Analyst] Project is not reconstructed here; see [NOTICE.md](NOTICE.md) for provenance.

## 0.1.1 - Unreleased

### Added

- Added metafor-backed forest plot rendering for default, RevMan, and BMJ styles, including entered-effect and one-arm analysis families.
- Added journal-ready SVG-first plot export devices with PNG, PDF, and TIFF conversion support.
- Added side-by-side diagnostic forest plot composition and visual QA contact-sheet tooling.
- Added metafor-backed bubble plot rendering for meta-regression outputs.
- Added focused R renderer tests and visual QA coverage for forest and bubble plot behavior.

### Changed

- Replaced the legacy custom forest plot renderer with the metafor-backed renderer.
- Replaced the legacy bubble plot renderer with the metafor-backed renderer.
- Improved forest plot layout preflight, spacing, axis labels, headers, gutters, text scaling, and raw-column visibility across supported styles.
- Renamed RCMetaR R source files to canonical `.R` casing and refreshed generated package documentation.

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
