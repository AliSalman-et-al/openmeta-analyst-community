# Maintaining RC MetaStudio

Use this guide to set up, change, and verify the application. Keep temporary plans, investigation notes, and work status in GitHub Issues.

## Set up the repository

RC MetaStudio uses Python 3.11 and [uv](https://docs.astral.sh/uv/). From the repository root:

```powershell
uv sync --locked
```

The lockfile is authoritative. Change dependencies in `pyproject.toml`, update `uv.lock`, and commit both files together.

## Run verification

Use the unified runner for normal source work:

```powershell
# Representative Python, project-format, and Qt resource checks
uv run python scripts/verify.py smoke

# Fast Python tests, golden analysis tests, and default R evidence
uv run python scripts/verify.py fast

# Full RCMetaR and R integration evidence
uv run python scripts/verify.py r-stack
```

For deterministic complexity, dependency, churn, and hotspot evidence, run the
locked code-health command against a comparison commit. Both snapshots are
measured from their named revisions: history is bounded at the measured head,
and Radon, Complexipy, and Grimp analyze that revision's source. The command
writes machine-readable JSON and a short text report; the exit status enforces
only new cycles, forbidden boundary imports, and changed-function thresholds.

```powershell
uv run python scripts/code_health.py --base 8b7796b --head HEAD `
  --baseline artifacts/code-health/baseline.json `
  --output artifacts/code-health/final.json `
  --report artifacts/code-health/final.txt
```

Use the stable rewrite baseline `8b7796b` for trend snapshots (as the CI
workflow does) and use the PR or push base separately for changed-code gates.
CI passes the recorded baseline artifact with `--baseline`; this makes the
final report compare directly with the evidence that was emitted for that
baseline, rather than relying on a branch name or an implicit merge base.
Use the same commit for `--base` and `--head` to capture a baseline snapshot.
The report records rename-aware 30-, 90-, and 180-day line churn. Hotspots are
ranked as normalized 180-day churn multiplied by cyclomatic complexity density;
coupling, cycles, cognitive complexity, maintainability, defect history, and
revision-bound typing indicators are reported independently. The typing
indicators report annotated-parameter and annotated-return coverage plus
`Any` annotations, `type: ignore` directives, and casts to `Any`; repository-wide strict `ty`
verification remains part of the Qt6 verification lane.

Add `--sync` when the environment may be stale. Add `--require-r-evidence` when R is required, or `--skip-r-evidence` when a separate full R run owns that evidence.

During development, run the narrowest relevant test file first. The maintained suites are grouped by execution needs:

- `tests/python/fast`: quick Python behavior and contract tests
- `tests/python/gui`: PyQt6 interaction and layout tests
- `tests/analysis_regression/golden`: statistical regression tests
- `tests/r_stack`: Python-to-R integration tests
- `tests/packaging/contract`: package and workflow contracts

Run strict collection after changing test configuration or suite structure:

```powershell
uv run pytest --strict-markers tests --collect-only -q
```

For Qt source or GUI changes, generate the forms and run the relevant native lane:

```powershell
.\scripts\verify-qt6.ps1
```

This command generates Qt6 modules, runs Ty, and then runs the GUI and native smoke stages. CI can select one lane:

```powershell
.\scripts\verify-qt6.ps1 -Section Core
.\scripts\verify-qt6.ps1 -Section RemainingSurfaces
```

Ty checks `src/rc_metastudio`, `scripts`, `tests`, and `r/RCMetaR/inst/qa`. Generated Qt modules take precedence over the editable `.ui` sources during the check.

## Work with generated Qt code

Files under `src/rc_metastudio/forms/*.ui` are the editable form sources. Generated Python modules belong under the selected build directory and must not be committed. `scripts/build_qt6.py generate` compiles forms and resources before tests, typing, or packaging.

## Repository layout

- `src/rc_metastudio`: application code and packaged resources
- `r/RCMetaR`: bundled statistical package
- `sample_projects`: user-facing example projects
- `scripts`: build, verification, and release commands
- `packaging`: PyInstaller and platform packaging definitions
- `config`: machine-readable policy used by builds and tests
- `tests`: executable behavior and distribution contracts

Keep machine-readable contracts beside their consumer. Keep frozen test data under `tests`, not under `docs`.

## Change versions

Use the version command so Python, RCMetaR, the lockfile, and changelog stay aligned:

```powershell
uv run python scripts/bump_version.py 0.2.4
```

Review the generated changelog heading and complete its release notes before publishing. See [Releasing RC MetaStudio](release.md) for the hosted build and promotion steps.

## License notices

New maintained source files use:

```text
SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
SPDX-License-Identifier: GPL-3.0-or-later
```

Preserve accurate original authorship in derived files. Do not label third-party code or assets as RC MetaStudio-owned. Before a release, review the components actually bundled into each artifact and add `THIRD_PARTY_NOTICES.md` if their licenses require notices beyond the included package metadata. Do not add an empty placeholder.
