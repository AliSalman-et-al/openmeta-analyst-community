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


def main():
    meta_form = read_repo_file("src/meta_form.py")
    macos_build = read_repo_file("scripts/build-macos-binary.sh")

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


if __name__ == "__main__":
    main()
