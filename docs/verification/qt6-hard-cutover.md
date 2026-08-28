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
  every other collected node from the frozen 879-node historical baseline
  remains represented. The classification is historical evidence only; its
  replacement references are checked at stable file paths rather than against
  a live pytest node ledger.
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

## Issue #340 hosted acceptance record

The hard cutover passed at
[commit `87e364211889ae0c2455d3fa3494603ed739836c`](https://github.com/AliSalman-et-al/rc-metastudio/commit/87e364211889ae0c2455d3fa3494603ed739836c)
in [GitHub Actions run `29570846208`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29570846208).
All required jobs and the integration gate succeeded:

| Required target | Job | Elapsed result |
| --- | --- | --- |
| Qt6 verification change classifier | [`87853992919`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29570846208/job/87853992919) | Passed |
| Windows native Qt6 vertical slice | [`87854012519`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29570846208/job/87854012519) | Passed in 15m12s |
| Windows x64 source smoke and Fast Verification | [`87854012512`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29570846208/job/87854012512) | Passed in 4m55s |
| macOS Intel x64 source smoke and Fast Verification | [`87854012503`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29570846208/job/87854012503) | Passed in 5m01s |
| macOS Apple Silicon ARM64 source smoke and Fast Verification | [`87854012485`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29570846208/job/87854012485) | Passed in 2m26s |
| Required-lane integration gate | [`87856892344`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29570846208/job/87856892344) | Passed |

The Windows raw log records `Imported 45 handwritten Qt modules with warnings
fatal.` at 09:42:28, proving the isolated warnings-as-errors execution audit
covered the complete strict Qt-bearing inventory. It records calculator
`main-return` followed by `verified-hard-exit` at 09:55:47, with no fatal Python
or access-violation diagnostic. At 09:56:12 the same job reported `validated 15
remaining native Qt6 surfaces at 1.0, 1.25, 1.5, 1.75`, proving that the
terminal calculator boundary did not skip the downstream remaining-surface
gate.

### Retained native evidence

| Artifact | Hosted identity and archive integrity | Independent content validation |
| --- | --- | --- |
| `native-calculator-evidence` | [ID `8403347571`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29570846208/artifacts/8403347571); 36,855 bytes; `sha256:b13dd3a71a3d1d30ab17c877da010a5d66630443556f8beb6085d4899a6033e2` | Extracted bundle contains three PNGs plus `evidence.json`; `validate_evidence_bundle` accepted exactly three calculator records. |
| `native-remaining-surface-evidence` | [ID `8403348289`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29570846208/artifacts/8403348289); 778,474 bytes; `sha256:0126a75fe29d183504b8d27216c73cdf3e1dbe72535fa7f097595f6d21b3f4df` | Extracted bundle contains 64 files; the validator accepted all four scale manifests and all 15 surfaces. |

The SHA256 values are the uploaded ZIP digests reported by GitHub Actions;
content validation was performed after extraction and is a separate check. The
two extracted bundles contain 68 files in total: four calculator files and 64
remaining-surface files.

### Cold installation proof versus warm acceptance

[Run `29562674627`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29562674627)
at commit
[`c685fe8b1c65d9070e426af8570ce71a2ad2a4e7`](https://github.com/AliSalman-et-al/rc-metastudio/commit/c685fe8b1c65d9070e426af8570ce71a2ad2a4e7)
was the cold Default R Evidence proof. Its target-specific Default R cache keys
were absent, and all three source lanes installed and validated the dependency
closure successfully:

| Cold target | Successful source job | Required package type |
| --- | --- | --- |
| Windows x64 | [`87828352663`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29562674627/job/87828352663) | `win.binary` |
| macOS Intel x64 | [`87828352662`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29562674627/job/87828352662) | `mac.binary.big-sur-x86_64` |
| macOS Apple Silicon ARM64 | [`87828352673`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29562674627/job/87828352673) | `mac.binary.sonoma-arm64` |

That earlier run is not the cutover acceptance run: its pre-fix Windows native
job failed during calculator process exit, so its integration gate also failed.
It is retained only as proof of cold installation and cache population.

The successful final run `29570846208` is the distinct warm-cache proof. All
three source lanes restored their target-specific Default R caches and still
revalidated the dated Public PPM snapshot `2026-07-16`, the 139-package binary
closure, their platform-specific package type above, and the sole permitted
source exception: HSROC 2.1.9 with
`sha256:5476fa76d7723717e203925a1da442813e3645790ef9b633a145cbc04a08b874`.
The warm run, native artifacts, and green integration gate together constitute
the Issue #340 acceptance evidence.
