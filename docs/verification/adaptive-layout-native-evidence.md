# Controlled Adaptive-Layout Native Evidence

Native screenshots are controlled release-qualification evidence, not a
GitHub-hosted build gate. GitHub-hosted runners do not contract display
geometry, DPI, scaling, fonts, or window-manager state, so package construction
must never fail because an exact viewport does not fit their transient desktop.

Deterministic layout policy, reflow, reachability, restoration, clamping,
splitter, paint-role, and validator tests remain required in CI. Hosted Windows
and macOS packages also run a narrow native smoke that proves the expected Qt
plugin loaded, the main window became Qt-visible, the bundled sample/R stack
initialized, and the process exited cleanly. That smoke makes no exact geometry
or screenshot claim.

## Controlled capture

Run against the final package ZIP on a preflighted interactive machine:

```powershell
.\scripts\capture-adaptive-layout-evidence-windows.ps1 `
  -Package .\artifacts\RCMetaStudio-windows-x64.zip
```

```bash
bash scripts/capture-adaptive-layout-evidence-macos.sh \
  artifacts/RCMetaStudio-macos-x64.zip
```

The commands first run the native smoke, then capture exact 800 by 600 and 1024
by 640 scenarios at scale factors 1.0 and 1.5, validate the manifests and PNGs,
and write `PACKAGE_SHA256`. Evidence qualifies only that digest.

Before capture, record OS build, architecture, unlocked interactive session,
screen count, available geometry, native scale, logical DPI/DPR, and expected
fonts. Do not use offscreen/minimal plugins. If the controlled display cannot
fit a required scenario, the qualification is incomplete; `capability-
unavailable` is diagnostic, not a pass.

## Human review

Complete each generated `HUMAN_REVIEW.md`. Check reflow, spacing, required
content, reachable actions, undistorted plots/icons, native fonts/chrome, and
cross-platform consistency. Do not add pixel-diff baselines.

For layout-system, Qt, supported-OS, font, or icon changes, attach controlled
Windows and Intel Mac evidence to the release qualification record when those
hosts are available. Otherwise record `not-run: controlled display unavailable`
in release notes. Deterministic CI and native hosted smoke still must pass.
