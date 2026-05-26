#!/usr/bin/env python3
"""Source-level checks for macOS startup regressions.

The application itself is a Python 2/PyQt4 desktop app, so these checks avoid
importing GUI modules and instead verify the startup contracts that protect the
macOS .app launch path.
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_repo_file(relative_path):
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def assert_contains(text, needle, description):
    if needle not in text:
        raise AssertionError(description)


def assert_not_contains(text, needle, description):
    if needle in text:
        raise AssertionError(description)


def assert_before(text, first, second, description):
    first_index = text.find(first)
    second_index = text.find(second)
    if first_index == -1 or second_index == -1 or first_index >= second_index:
        raise AssertionError(description)


def main():
    launch = read_repo_file("src/launch.py")
    meta_form = read_repo_file("src/meta_form.py")
    ma_data_table_view = read_repo_file("src/ma_data_table_view.py")
    main_wizard = read_repo_file("src/main_wizard.py")
    results_window = read_repo_file("src/results_window.py")
    ui_meta = read_repo_file("src/ui_meta.py")
    ui_results_window = read_repo_file("src/ui_results_window.py")
    macos_build = read_repo_file("scripts/build-macos-binary.sh")

    assert_contains(
        launch,
        "AA_DontUseNativeMenuBar",
        "macOS startup must disable Qt's native menu bar before QApplication is created.",
    )
    assert_contains(
        launch,
        "configure_macos_qt()",
        "macOS Qt compatibility settings must run before QApplication construction.",
    )
    assert_before(
        launch,
        "    configure_macos_qt()",
        "app = QtGui.QApplication(sys.argv)",
        "macOS Qt compatibility settings must run before QApplication construction.",
    )
    assert_contains(
        launch,
        "log_macos_runtime()",
        "macOS startup must log whether the GUI binary is running under Rosetta.",
    )
    assert_contains(
        ui_meta,
        "self.menu_bar.setNativeMenuBar(False)",
        "The main menu bar must not use Qt 4's native macOS menu bridge.",
    )
    assert_contains(
        ui_results_window,
        "self.menubar.setNativeMenuBar(False)",
        "Secondary menu bars must not use Qt 4's native macOS menu bridge.",
    )
    assert_contains(
        main_wizard,
        "qm = QMenu(self)",
        "Wizard recent-file menus must be parented to the page that owns them.",
    )
    assert_not_contains(
        ma_data_table_view,
        ".popup(",
        "Table context menus must use synchronous exec_() instead of async popup().",
    )
    assert_not_contains(
        results_window,
        ".popup(",
        "Results context menus must use synchronous exec_() instead of async popup().",
    )
    assert_contains(
        meta_form,
        "mark_dirty=True",
        "MetaForm.set_model must let callers suppress dirty-state changes.",
    )
    assert_contains(
        meta_form,
        "mark_dirty=False",
        "Opening an existing dataset must not leave the document marked dirty.",
    )
    assert_contains(
        meta_form,
        "recalculate_outcomes=False",
        "Opening a dataset must suppress eager outcome recalculation during startup.",
    )
    assert_contains(
        macos_build,
        "launcher started",
        "The macOS launcher must log startup context before running the GUI binary.",
    )
    assert_contains(
        macos_build,
        "launcher exiting with status",
        "The macOS launcher must log the GUI process exit status.",
    )
    assert_contains(
        macos_build,
        "validate_macho_x86_64",
        "The macOS build must validate native bundle files for Rosetta-loadable x86_64 slices.",
    )
    assert_contains(
        macos_build,
        "lipo -archs",
        "The macOS build and launcher logs must report Mach-O architecture slices.",
    )
    assert_contains(
        macos_build,
        "sysctl.proc_translated",
        "The macOS launcher must log Rosetta translation state when available.",
    )


if __name__ == "__main__":
    main()
