# Third-Party Inventory Expectations

Release packaging must preserve license notices for bundled third-party components and assets separately from RC MetaStudio copyright, provenance, and affiliation language.

## Scope

Before a release package is published, inventory bundled materials that ship with the application artifact, including:

- Python runtime dependencies and vendored package metadata included in the distributable.
- R runtime components, RCMetaR dependencies, and bundled R package sources or binaries.
- Qt runtime files, plugins, translations, and platform resources included by packaging.
- UI assets, icons, images, fonts, CSS, JavaScript, HTML remnants, and generated resources.
- Packaging helper files, launcher scripts, templates, and included external tools.

Normal development-only dependencies that are not bundled into a release artifact may be documented through the lockfile and package metadata rather than copied into release notices.

## Required Output

The release inventory must record, for each bundled third-party item:

- Component or asset name.
- Upstream project or source location when known.
- Version, commit, or source date when available.
- License name and license text location.
- Why the item is bundled.
- Whether attribution or redistribution terms require release-package notices.

If bundled third-party materials remain beyond normal package metadata, create or update `THIRD_PARTY_NOTICES.md` before publishing the package. Do not create an empty placeholder; the file should contain actual bundled-component notices discovered by the inventory.

## Boundaries

`NOTICE.md` remains focused on RC MetaStudio maintainership, Original OpenMeta[Analyst] Project provenance, GPL posture, warranty terms, and affiliation disclaimers.

`THIRD_PARTY_NOTICES.md`, when required, records third-party bundled materials and their licenses so those materials are not accidentally represented as RC MetaStudio-owned work.
