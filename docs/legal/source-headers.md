# Source Header Policy

RC MetaStudio uses compact SPDX headers in maintained source files. Full project provenance and affiliation language belongs in top-level `NOTICE.md`, not repeated in every module.

## New Maintained Files

Use this header for files created independently for RC MetaStudio:

```text
SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
SPDX-License-Identifier: GPL-3.0-or-later
```

## Derived Maintained Files

Files derived from the Original OpenMeta[Analyst] Project should use the RC MetaStudio SPDX header and preserve applicable original copyright or provenance lines where they remain accurate.

Do not replace original authorship with RC MetaStudio authorship. The maintained header identifies current modifications and distribution posture; original-project attribution remains preserved through accurate file-level notices where needed and the centralized provenance in `NOTICE.md`.

## Third-Party Materials

Do not relabel bundled third-party components, generated assets, copied resources, or external package materials as RC MetaStudio-owned source. Release packaging inventory and notices are handled through [docs/release/third-party-inventory.md](../release/third-party-inventory.md).
