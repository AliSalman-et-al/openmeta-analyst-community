# RC MetaStudio

RC MetaStudio is open-source desktop software for advanced meta-analysis, developed and maintained by Research Consultancy (RC).

RC MetaStudio is derived from the Original OpenMeta[Analyst] Project and is independently maintained by Ali Salman and RC MetaStudio contributors. See [NOTICE.md](NOTICE.md) for original-project provenance, current maintainership, license posture, warranty terms, and the affiliation disclaimer.

## What It Provides

- A graphical desktop workflow for study data entry, meta-analysis setup, and result review.
- Python 3.11 and PyQt5 application code for the maintained desktop path.
- The bundled private RCMetaR R package interface for R-backed analysis behavior.
- `.rcms` project files as the maintained RC MetaStudio project-file identity.

Analysis behavior is preserved unless a reviewed compatibility exception or statistical modernization drift record says otherwise.

## Running From Source

Use the locked uv environment from the repository root:

```powershell
uv sync --locked
uv run rc-metastudio
```

Developer source runs need an R installation with the packages used by the analysis backend. Normal desktop users should not need to install R packages manually when using a packaged release.

Install the required R packages into a local R library:

```r
Sys.setenv(R_LIBS_USER = "path/to/local/r-library")
source("scripts/install-r-deps.R")
```

The bundled R package is rcmetar. Prefer the product names and policy in this README, [NOTICE.md](NOTICE.md), and [CHANGELOG.md](CHANGELOG.md) when documentation conflicts with older historical records.

## Verification

Run the smoke verification lane for the fastest local check:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-smoke.ps1
```

Run the fast verification lane for routine local evidence:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-fast.ps1
```

Run area-specific checks when changing GUI, R Stack, golden analysis, or packaging behavior:

```powershell
uv run pytest tests -m gui
uv run pytest tests -m r_stack
uv run pytest tests -m golden
uv run pytest tests -m packaging_contract
```

## Packaging Scope

Windows is the active packaged release target. macOS package jobs are available for release-candidate validation but remain opt-in.

To bump the aligned RC MetaStudio and bundled RCMetaR version surfaces, run:

```powershell
uv run python scripts\bump_version.py 0.1.2 --date 2026-08-09
```

The script updates `pyproject.toml`, `uv.lock`, application version constants, `r/RCMetaR/DESCRIPTION`, and creates a changelog section when one does not already exist. Edit `CHANGELOG.md` afterward so the release notes describe user-visible changes rather than commit logs.

Before release packaging, bundled third-party components and assets must be inventoried and their license notices preserved separately from RC MetaStudio copyright and provenance. See [docs/release/third-party-inventory.md](docs/release/third-party-inventory.md).

## Feedback And Contributions

Public [GitHub Issues](https://github.com/AliSalman-et-al/rc-metastudio/issues) may be used for bug reports and feedback. Issue reports should not include private project data unless the reporter deliberately chooses to share it.

RC MetaStudio does not automatically collect, upload, or attach diagnostics for issue reports. Any future diagnostic export must be explicit, local, user-controlled, and clear about its contents.

Unsolicited public code contributions are not currently accepted. See [CONTRIBUTING.md](CONTRIBUTING.md) for the maintainer policy.

## License

RC MetaStudio is distributed under the GNU General Public License, version 3 or later, where permitted by the original GPL-2.0-or-later grant covering derived OpenMeta[Analyst] portions. See [LICENSE](LICENSE), [NOTICE.md](NOTICE.md), and [docs/legal/source-headers.md](docs/legal/source-headers.md).
