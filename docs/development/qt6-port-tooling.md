# Qt6 port tooling

Issue #331 owns the mechanical boundary for the Native Qt6 Port. The mapping
manifest at `config/qt6-codemod-mappings.json` is authoritative for binding
imports, moved classes, scoped enums, and deliberately manual sites discovered
by the immutable port inventory. Update the manifest and its fixture coverage
before accepting a new mechanical pattern.

Run a dry migration and retain its JSON report:

```powershell
uv run python scripts/qt6_port.py codemod --report build/qt6-codemod-report.json <paths>
```

Add `--write` only after reviewing the report. The command plans every
input before writing any file; one refusal prevents all writes and identifies
the exact file, line, column, symbol, and required action. Generated form and
resource Python is always refused because canonical `.ui` and `.qrc` inputs
must be regenerated. `--check` fails when an unambiguous rewrite remains and is
the idempotence gate used after the repository-wide application.

`--write` rejects symbolic-link targets and stages encoded bytes in same-folder
temporary files. It rechecks source bytes and filesystem identity before every
replacement, preserves source encoding, newline convention, and mode, and
rolls back prior replacements if a later atomic replacement fails.
Input aliases (including detectable hard links) and any report/input overlap
are rejected before writing. JSON reports themselves use a same-folder atomic
replacement and cannot be symbolic links. Strict reports, expected snapshots,
and written snapshots are pairwise preflighted by normalized path and file
identity. A failed post-replace directory durability check restores the prior
report or removes a newly created one; a restoration failure retains the
primary error and states that the destination may have changed.
If restoration itself fails, the sole fsynced recovery backup is retained and
its exact path is included in the error for deliberate recovery.

The independent strict scanner rejects active legacy or compatibility inputs:

```powershell
uv run python -W error scripts/qt6_port.py strict --root . <paths>
```

It parses Python rather than matching comments or strings, except for genuine
generator provenance markers. It rejects PyQt5 imports and requirements,
binding facades, short enums, displaced or removed APIs, runtime form loading,
stale generated modules, generated Python resource payloads, and constant or
ambiguous `importlib.import_module`/`__import__` binding loads, including
`builtins.__import__` and its imported aliases. Qualified Qt 5
compatibility modules are rejected even when reached through the PyQt6 root.
Relative `importlib.import_module` calls are resolved only from constant name
and package arguments; missing, nonconstant, expanded, unknown, or duplicate
argument forms fail closed rather than guessing Python import semantics.
During the
dependency-ordered cutover, `verify-qt6.ps1` scans dependency files with zero
allowances and every authoritative source module against the exact
cryptographic backlog in `config/qt6-strict-source-backlog.json`. That temporary
backlog permits no drift and is replaced by Issue #332's mechanical report;
Issue #340 makes the final repository-wide zero-finding scan mandatory.

Regenerate that snapshot only as a reviewed migration-backlog change, using the
same authoritative input root as verification:

```powershell
uv run python -W error scripts/qt6_port.py strict --root . --write-snapshot config/qt6-strict-source-backlog.json src/rc_metastudio
```

The compact snapshot hashes the complete sorted finding records and records
their total and per-rule counts; it is not a count-only allowance.

`verify-qt6.ps1` runs `ty` with all configured rules at error severity and runs
the maintained pytest lane with Python warnings as errors.
`QT_FATAL_WARNINGS=1` is scoped to its standalone
native GUI smoke process and restored afterwards, keeping unrelated platform
plugin noise out of the broad test process.
