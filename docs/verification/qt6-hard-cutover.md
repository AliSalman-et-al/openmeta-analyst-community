# Qt6 Hard Cutover Verification

Issue #340 makes the native PyQt6 path the only maintained source and Fast
Verification path. `scripts/verify-qt6.ps1` now closes the cutover with these
fail-closed checks:

- `rc_metastudio.qt6_cutover` rejects active alternate bindings, pickle project
  storage, `.rcms.state`, tracked generated Qt Python, generated Python package
  inputs, and stale Qt5 packaging declarations.
- `docs/verification/qt6-legacy-test-classification.json` classifies every
  frozen PyQt5-era test surface. The two large GUI regression surfaces are
  restored and natively ported, preserving 131 behavioral tests across project
  open/save, CSV, defaults, results, plots, edit/export, settings, startup, and
  all-cell paint paths. The frozen deleted-node inventory contains only the 12
  tests whose underlying Qt5/pickle/generated-code surface was actually removed;
  every other collected node remains present in the strict 879-node taxonomy.
- `scripts/import_qt_modules.py` imports all 45 handwritten PyQt6-bearing
  modules in isolated warnings-as-errors processes after deterministic form and
  binary-resource generation. The same closed discovery output, including the
  active Qt verification scripts, is passed to pinned strict `ty`, so imports
  and type checking cannot silently diverge. The 30 necessary PyQt6 override
  ignores are individually bound to their file, qualified class/function owner,
  diagnostic rule, and full normalized function AST in a fail-closed allowlist;
  new, moved, re-owned, re-signatured, re-ruled, or edited ignores fail
  verification.
- the repository codemod runs a second time in check mode and must reproduce
  the empty committed report in `qt6-codemod-second-run.json`.
- controlled native processes retain `QT_FATAL_WARNINGS=1` for the application
  shell, calculators, analysis, Results, Network View, remaining surfaces, and
  failure teardown.

The Qt6 Integration Verification workflow runs source smoke followed by Fast
Verification on Windows x64, macOS Intel x64, and macOS ARM64. The Windows
and macOS source lanes require Default R Evidence for both smoke and Fast
Verification. The Windows
vertical slice additionally runs the complete Golden, Versioned Project Format,
sample, model/signal, locale, accessibility, adaptive-layout, real-R, and native
GUI evidence gates. Hosted results are required because local Windows evidence
cannot substitute for either native Cocoa architecture.
