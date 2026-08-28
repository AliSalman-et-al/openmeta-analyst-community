# RC MetaStudio project format

RC MetaStudio saves projects as `.rcms` files. The current format is version 1.

## Archive contents

An `.rcms` file is a ZIP archive with exactly three UTF-8 JSON members:

- `manifest.json` identifies the format and records hashes for the data members.
- `project.json` stores the analysis dataset and project content.
- `state.json` stores portable application state needed to reopen the project.

The schemas are packaged under `src/rc_metastudio/project_schemas/v1`. They are the authoritative field-level contract.

## Compatibility

The reader accepts released structured versions for which schemas and migrations exist. It rejects unknown versions before decoding project data. Historical pickle projects are not supported.

The writer always emits the current version. Saving a loaded older structured version therefore upgrades it to the current format.

## Safety and durability

The reader validates member names, sizes, compression ratios, hashes, JSON structure, schemas, and project semantics. It rejects duplicate properties, non-finite numbers, path traversal, links, extra archive members, and resource use above the configured limits.

Saving is atomic. RC MetaStudio writes and synchronizes a temporary file in the destination directory, replaces the destination, then synchronizes the directory where the platform supports it. A failed save does not intentionally replace the previous project.

The writer produces deterministic JSON and ZIP metadata for the same project content. This makes project differences reviewable and keeps fixtures stable.

## What belongs in a project

Project files contain portable analysis data and state. Machine-specific settings, temporary output, caches, and window placement do not belong in an `.rcms` file.
