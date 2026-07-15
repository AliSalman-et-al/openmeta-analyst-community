# Native PyQt6 Port Research Brief

## Purpose and conclusion

RC MetaStudio can move directly from PyQt5 to PyQt6 without a runtime compatibility layer, but the safe interpretation of “complete rewrite” is a **complete native Qt-facing port**, not a simultaneous redesign of the product, statistical workflows, and GUI architecture. The maintained source should end with only PyQt6 imports and Qt6 APIs; it should not introduce `qtpy`, a local PyQt5/PyQt6 facade, Qt5Compat, or dual-binding conditionals. Analysis Behavior, `.rcms` behavior, canonical Designer forms, and established layout contracts should remain the migration oracle unless a separate decision explicitly changes them.

As of 15 July 2026, PyPI’s current PyQt6 release is 6.11.0 and requires Python 3.10 or newer. Qt’s current public documentation is 6.11.1. The repository’s Python 3.11 constraint is therefore viable. Production should pin and lock a tested PyQt6/Qt wheel set rather than express “latest” as an unbounded dependency; Riverbank’s binary wheels install the corresponding Qt libraries. [PyQt6 on PyPI](https://pypi.org/project/PyQt6/), [Riverbank PyQt overview](https://www.riverbankcomputing.com/software/pyqt)

## Repository-specific migration surface

A static audit of the current branch found:

- 98 files containing PyQt5 references: 36 handwritten source files, 29 generated UI modules, one generated Python resource module, and 27 tests (with the remainder in scripts or other support files).
- 29 canonical `.ui` files and 29 corresponding PyQt5-generated Python modules.
- One canonical `src/rc_metastudio/images/icons.qrc`; its generated `icons_rc.py` is roughly 40,000 lines.
- At least 241 short/unscoped Qt enum references. The largest families are orientation, item-data roles, alignment, scrollbar policy, window state, focus policy, keys, mouse buttons, and keyboard modifiers.
- Twenty custom `pyqtSignal` declarations across seven handwritten source files. There are no legacy string-based `SIGNAL()`/`SLOT()` calls and no handwritten `@pyqtSlot` decorators.
- Concrete displaced or removed APIs already present: `QRegExp`, `QAction` imported from `QtWidgets`, `QGraphicsSvgItem` imported from `QtSvg`, and a large model/view surface that returns or compares Qt enum values.
- Event and coordinate-sensitive code in custom keyboard, mouse, drag/drop, screen, window-placement, graphics-view, and high-DPI paths.

This is large enough to justify codemods and machine-enforced inventories, but small enough that every mechanical rewrite must be reviewed and behavior-tested.

## Binding and API changes that matter here

### Enums, flags, and integer assumptions

PyQt6 implements named enums as Python `Enum` subclasses and removes PyQt5’s short enum aliases. Code must use scoped names such as `Qt.Orientation.Horizontal`, `Qt.ItemDataRole.DisplayRole`, `Qt.AlignmentFlag.AlignCenter`, `Qt.KeyboardModifier.ControlModifier`, and `Qt.Key.Key_Return`. PyQt6 also changes enum behavior relative to PyQt5; integer conversion, equality, truthiness, bitwise combinations, and values returned from model APIs must be reviewed rather than blindly rewritten. [Riverbank: Differences Between PyQt6 and PyQt5](https://www.riverbankcomputing.com/static/Docs/PyQt6/pyqt5_differences.html)

The current table-model tests explicitly coerce alignment flags with `int(...)`; those seams need contract tests under PyQt6 because flags and plain enum values do not all behave as interchangeable integers. Keyboard shortcut combinations should use Qt6’s type-safe key/modifier APIs rather than arithmetic on unrelated enums. [Qt 6 GUI changes: QKeyCombination](https://doc.qt.io/qt-6/gui-changes-qt6.html)

### Removed, replaced, and displaced classes

- Replace `QRegExp` with `QRegularExpression` or, where no Qt regex object is required, Python’s `re`. Qt states that `QRegExp` was retired from Qt Core to Qt5Compat and warns that pattern semantics can change silently during conversion. This repository’s newline splitter should first be tested as behavior, then implemented with the smallest native API. Qt5Compat is excluded by the no-compatibility-layer constraint. [Qt 6 Core changes: regular expressions](https://doc.qt.io/qt-6/qtcore-changes-qt6.html)
- Import `QAction` from `PyQt6.QtGui`, not `QtWidgets`.
- Keep `QSvgRenderer` in `PyQt6.QtSvg`, but import `QGraphicsSvgItem` from `PyQt6.QtSvgWidgets`; Qt6 split widget/graphics SVG classes into the SVG Widgets component. [Qt SVG Widgets](https://doc.qt.io/qt-6/qtsvgwidgets-module.html)
- Audit methods removed because they were already deprecated in Qt 5. PyQt6 intentionally does not expose deprecated Qt5 APIs that remain present in Qt6 C++. [Riverbank: Differences Between PyQt6 and PyQt5](https://www.riverbankcomputing.com/static/Docs/PyQt6/pyqt5_differences.html)
- Review `QVariant` assumptions in model, settings, and persistence boundaries. Qt6 changed nullness, equality, floating-point comparison, ordering, and meta-type behavior. [Qt 6 Core changes: QVariant and QMetaType](https://doc.qt.io/qt-6/qtcore-changes-qt6.html)

### Coordinates, events, and strict typing

Qt6’s pointer-event model exposes floating-point positions (`QPointF`) through APIs such as `position()` and `globalPosition()`. Code must choose an explicit conversion boundary when an integer `QPoint` is required; truncation or rounding must not occur accidentally. This is particularly important in the graphics view, window-frame capture, drag/drop, hit testing, popup placement, and high-DPI evidence code. [QEventPoint](https://doc.qt.io/qt-6/qeventpoint.html), [QGraphicsView](https://doc.qt.io/qt-6/qgraphicsview.html)

Constructor overloads are also stricter. A codemod can rename members, but it cannot decide whether a coordinate is logical, device, scene, viewport, window, or global space. Each custom event handler should therefore receive a focused behavioral test that asserts both the type and the coordinate space at the conversion boundary.

### Signals, slots, and meta-object behavior

The repository already uses bound signal objects and `.connect()`, so it avoids the largest legacy signal syntax break. The remaining risks are:

- changed default overloads or missing overloads on built-in signals;
- stricter compatibility between declared `pyqtSignal` types and emitted values;
- connections that relied on PyQt dropping extra arguments;
- lifetime/disconnection behavior during window destruction;
- generated `connectSlotsByName()` behavior after forms and object names are regenerated.

PyQt6 documents explicit overload selection with subscription syntax when a non-default overload is needed. Every overloaded built-in signal should be connected explicitly where ambiguity affects behavior. [Riverbank: Signals and Slots](https://www.riverbankcomputing.com/static/Docs/PyQt6/signals_slots.html)

Pure Python PyQt code is not processed by C++ `moc`. The relevant Python meta-object surface is `pyqtSignal`, `pyqtSlot`, `pyqtProperty`, generated `connectSlotsByName()`, and any explicit type registration—not a wholesale C++ meta-object rewrite. Qt6’s C++ `Q_PROPERTY` complete-type rules matter only if the project later introduces compiled Qt extensions. [Qt 6 Core changes: type registration](https://doc.qt.io/qt-6/qtcore-changes-qt6.html)

## Forms and assets

ADR 0095 already makes `.ui` files canonical and treats generated Python UI modules as transitional. The native port should preserve that decision and regenerate all forms with the target PyQt6 toolchain in one controlled step. Generated output must never be mechanically hand-edited. A deterministic verification command should regenerate into a temporary directory and fail on drift.

`pyqt6-tools` should not be a production dependency: its latest PyPI release is 6.4.2.3.3 from March 2023, it is marked beta, and it is tied to an old PyQt6 line. It may be evaluated as a developer convenience for Designer only, isolated from the locked build. [pyqt6-tools on PyPI](https://pypi.org/project/pyqt6-tools/)

`pyqt6rc` is also a third-party workaround, not the preferred application asset architecture. Its own description discusses rewriting generated paths and using `pyside6-rcc`, which would mix binding toolchains. [pyqt6rc on PyPI](https://pypi.org/project/pyqt6rc/)

The clean native option is:

1. Keep the project-owned `.qrc` and SVG/bitmap files canonical.
2. Compile the `.qrc` with Qt6 `rcc` into a binary `.rcc` artifact during build.
3. Package that artifact and register it once at startup with `QResource.registerResource()`.
4. Fail startup/packaged smoke if registration or a sentinel `:/...` resource lookup fails.

Qt documents binary `.rcc` generation and runtime registration as first-party resource mechanisms. This avoids a generated Python byte-array module and does not require a PyQt compatibility package. [Qt binary resources](https://doc.qt.io/qt-6/qt-add-binary-resources.html), [QResource.registerResource](https://doc.qt.io/qt-6/qresource.html)

## Automation and strict gates

A specialized codemod is justified, but no general package should be allowed to define correctness. Prefer a repository-owned, idempotent LibCST or AST transformation with an explicit mapping manifest for imports, enum families, and unambiguous method renames. It should refuse unknown patterns and produce a report. Regex-only replacement is unsafe because identical member names occur under different enum scopes and generated files must be regenerated, not transformed.

Required post-conversion gates should include:

- zero `PyQt5`, `qtpy`, binding-switch, `Qt5Compat`, short-enum, `exec_`, and generated-PyQt5 markers outside historical documentation;
- regenerated `.ui` and `.rcc` drift checks;
- import/collection of every Qt-bearing module under PyQt6;
- warnings-as-errors for Python warnings in focused tests, plus targeted Qt logging/fatal-warning runs where stable;
- focused model-role sweeps, because paint roles can otherwise raise from C++ virtual callbacks and terminate the process;
- focused event/coordinate tests and signal emission/connection tests;
- offscreen GUI workflow tests, then real native paint evidence;
- packaged smoke from the actual distributable, including R loading, resources, Qt plugins, SVG rendering, platform style, and high-DPI capture;
- exact dependency lock and software-bill/inventory updates.

Qt’s C++ deprecation macros (`QT_DISABLE_DEPRECATED_UP_TO`) are useful when compiling C++ Qt code, but they do not make Python bindings strict. The Python port needs its own source audit plus runtime and packaged evidence. [Qt deprecation markers](https://doc.qt.io/qt-6/qtdeprecationmarkers.html)

## High-DPI and platform behavior

Qt6 enables high-DPI scaling on all platforms and changes the default scale-factor rounding policy from `Round` to `PassThrough`. Fractional Windows scales can therefore expose geometry and rendering differences even where Qt5 tests passed. The existing 100%/150% native evidence should be retained and expanded to a non-integer scale such as 125% or 175% before deciding whether to accept `PassThrough` or explicitly select another policy. [Qt 6 porting guide: High DPI](https://doc.qt.io/qt-6/portingguide.html)

Qt 6.11 supports Windows 10 1809+ and Windows 11 x64, and macOS 13+ on x86_64 and arm64. PyQt6 publishes Windows x64/ARM64 and macOS universal2 wheels. This removes the current PyQt5-Qt5 macOS Intel-wheel constraint, but expanding RC MetaStudio’s promised platform matrix is a separate product decision; the port should first preserve the existing release-gated platforms. [Qt 6.11 supported platforms](https://doc.qt.io/qt-6/supported-platforms.html), [PyQt6 wheels](https://pypi.org/project/PyQt6/)

## Packaging and deployment

The PyInstaller pipeline must be treated as a fresh Qt6 deployment qualification, not a dependency substitution. PyInstaller supports PyQt6, but the specification, collected modules, hidden imports, plugin families, resource artifact, signing inputs, and smoke probes all need re-audit. The result must prove the actual build-once candidate and immutable promotion path already adopted by the repository.

At minimum, inspect and test collection of the platform plugin (`qwindows` or `qcocoa`), image/SVG plugins and modules, styles, TLS dependencies if used, accessibility, and any print support. Qt’s platform deployment guides emphasize that plugin placement is part of the runtime contract. [Qt for Windows deployment](https://doc.qt.io/qt-6/windows-deployment.html), [Qt for macOS deployment](https://doc.qt.io/qt-6/macos-deployment.html), [PyInstaller manual](https://pyinstaller.org/en/stable/)

Do not combine the binding port with a switch away from PyInstaller unless a focused feasibility spike proves PyInstaller unsuitable. That would create a second independent migration axis.

## Recommended delivery sequence

1. **Decide scope and target contract.** Define “native port,” the exact locked Qt/PyQt line, platform matrix, compatibility oracle, and cutover rule. Explicitly supersede temporary ADR 0170.
2. **Create the inventory and zero-Qt5 audit.** Record every Qt import, generated artifact, enum family, moved class, event override, signal, Qt plugin/module, and package probe.
3. **Land Qt5-safe semantic preparations.** Replace `QRegExp`, clarify coordinate spaces, remove deprecated aliases, and strengthen behavior tests where the same native API exists in Qt5. These changes reduce the cutover diff without adding dual-binding code.
4. **Build deterministic Qt6 generation.** Regenerate all `.ui` outputs and replace generated Python resources with the decided native asset pipeline.
5. **Perform the binding cutover on the migration branch.** Change locked dependencies and imports, apply the reviewed codemod, then resolve strict enum, overload, model-role, event, SVG, and ownership failures.
6. **Restore vertical workflows.** Bring up launcher/main window, project open/save, dataset editing, each analysis family, results/plots, and failure paths with focused evidence.
7. **Qualify each native platform package.** Rebuild PyInstaller specifications and CI, run packaged R/resource/paint/high-DPI smoke, sign the build-once candidate, and verify exact-byte promotion.
8. **Enforce completion.** No PyQt5/Qt5Compat/compatibility facade remains; all canonical forms/assets regenerate; the full verification matrix and native package evidence pass; docs and dependency inventories describe only the Qt6 path.

This can be delivered in small reviewable commits and workflow slices while still having a single public runtime cutover. “No compatibility layer” does not require a single unreviewable commit.

## Decisions the grilling session must resolve

1. Does “complete rewrite” mean a complete native Qt-facing port with preserved product behavior, or a simultaneous clean-sheet GUI architecture/product redesign?
2. Is the target a fixed PyQt6 6.11 / Qt 6.11 locked line for this release, or a moving-latest policy?
3. Does main remain releasable on PyQt5 until one Qt6 cutover, while the feature branch is Qt6-only?
4. Are canonical `.ui` files retained, and are generated Python UI modules build outputs or checked-in artifacts?
5. Will resources use a Qt6 binary `.rcc` registered at startup, or another explicitly justified first-party path?
6. Which current platform/architecture matrix is release-gated, and does any expansion wait until after the port?
7. Is Qt6 `PassThrough` fractional scaling accepted, or must RC MetaStudio choose and document a different rounding policy?
8. Which compatibility outcomes are inviolable, and what evidence authorizes an exception?
9. What is the exact cutover gate and rollback policy for the last PyQt5 release?

