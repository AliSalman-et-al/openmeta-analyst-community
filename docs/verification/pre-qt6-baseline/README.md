# Pre-Qt6 diagnostic baseline

This directory binds the final known-good PyQt5 state to commit
`e8a21fc3c277e8a8c144413dfa320ea9e68a20e4` and the annotated
`pre-qt6-baseline` tag. It is an immutable diagnostic oracle for the Native
Qt6 Port, not a supported runtime, release branch, package target, or forward
CI lane.

`manifest.json` records the locked runtime and packaging identities and hashes
all retained payloads. `observed-golden-baseline.zip` is the successful real
authoritative comprehensive capture from the tagged code: all eleven curated
workflows have observed numeric and/or formatted text output plus a
hash-verified plot. Every capture records `authoritative: true`, an exact
Python 3.11.9 / PyQt5 5.15.11 / Qt 5.15.2 / SIP 12.18.0 / rpy2 3.6.7
identity, R 4.6.1, and RCMetaR 0.1.2; the recorded baseline environment must
match before the bundle can be imported.
`observed-golden-summary.json` is its compact validation index.
`rendered-interface/` contains actual PNG renders of the startup and
new-dataset surfaces captured from that same code. `sample-projects/` contains
normalized, reviewable semantic snapshots for every committed `.rcms` sample.
`sample-analysis-evidence.json` binds each converted sample to its tagged Git
blob, normalized semantic hash, and successful authoritative numeric, text, and
plot evidence. The original Golden bundle covers amino, continuous, and lymph;
`sample-analysis/` retains equivalent tagged-environment captures for BCG and
meantime, which were not part of the original curated set.

`qt-port-inventory.json` classifies the Qt-bearing migration surface, including
application-owned versus allowed Designer properties, and records the initial
results of eight executable zero-legacy detectors. Run the detectors against
the current tree at any point with:

```powershell
uv run python scripts/capture_pre_qt6_baseline.py `
  --legacy-report artifacts/qt6-zero-legacy-report.json
```

Add `--require-zero` at final cutover to make any remaining occurrence fail.

Validate the evidence and tag with:

```powershell
uv run python scripts/capture_pre_qt6_baseline.py --check --require-tag
```

The comprehensive bundle was produced from a detached `pre-qt6-baseline`
worktree after `uv sync --locked --python 3.11.9`, with R 4.6.1, the tagged
RCMetaR 0.1.2 source, and a writable `r_tmp`. The capture supplied the exact
locked identities above to the tagged Golden Analysis capture API and used its
`authoritative` mode. It was then imported with:

```powershell
uv run python scripts/capture_pre_qt6_baseline.py --write `
  --observed-golden-bundle <output>/comprehensive-golden-baseline.zip
```

`--write` is a one-time PyQt5/pickle capture operation. It verifies the tracked
runtime, forms, samples, scripts, packaging, workflow, and lock inputs against
the tagged commit before importing legacy code, rejects incomplete or
wrong-commit golden bundles, rejects local-debug captures and any missing or
mismatched runtime identity, and refuses to run after any input drifts. Forward
CI uses only `--check`, which validates frozen Git blobs, ZIP members, artifact
hashes, JSON, PNGs, capture authority, and exact environment identity without
importing PyQt5 or executing pickle.
