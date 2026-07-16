import importlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import rc_metastudio.qt6_port_tools as port_tools
from rc_metastudio.qt6_port_tools import (
    MigrationRefused,
    MigrationTransactionError,
    apply_migration_transaction,
    load_mapping_manifest,
    migrate_source,
    prepare_file_migration,
    scan_paths,
    write_atomic_text,
)


ROOT = Path(__file__).resolve().parents[3]
PORT_SCRIPT = ROOT / "scripts/qt6_port.py"


def test_codemod_rewrites_imports_moved_classes_and_scoped_enums_with_comments():
    source = '''# module comment
from PyQt5 import QtCore  # binding comment
from PyQt5.QtWidgets import QAction, QUndoCommand, QUndoStack, QWidget

alignment = QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter  # enum comment
action = QAction("Run")
'''

    result = migrate_source(source, filename="example.py")

    assert result.code == '''# module comment
from PyQt6 import QtCore  # binding comment
from PyQt6.QtGui import QAction, QUndoCommand, QUndoStack
from PyQt6.QtWidgets import QWidget

alignment = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter  # enum comment
action = QAction("Run")
'''
    assert [change.kind for change in result.transformations] == [
        "binding-import",
        "moved-class-import",
        "moved-class-import",
        "moved-class-import",
        "binding-import",
        "scoped-enum",
        "scoped-enum",
    ]
    assert result.refusals == ()


def test_codemod_preserves_explicit_overload_and_ignores_unbound_lookalikes():
    source = '''from PyQt5.QtCore import Qt, pyqtSignal

class Local:
    AlignLeft = 1

signal = pyqtSignal([int], [str])
signal[int].connect(print)
local = Local.AlignLeft
value = "Qt.AlignLeft and PyQt5 stay text"
qt_value = Qt.AlignLeft
'''

    result = migrate_source(source, filename="overloads.py")

    assert "signal[int].connect(print)" in result.code
    assert "Local.AlignLeft" in result.code
    assert '"Qt.AlignLeft and PyQt5 stay text"' in result.code
    assert "Qt.AlignmentFlag.AlignLeft" in result.code


def test_codemod_and_strict_scan_cover_class_scoped_qt6_enums(tmp_path):
    source = """from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QSizePolicy

events = (QEvent.Show, QtCore.QEvent.Resize)
policy = QSizePolicy.Expanding
metric = QtWidgets.QStyle.PM_DefaultFrameWidth
"""

    migrated = migrate_source(source, filename="class-enums.py")

    assert "QEvent.Type.Show" in migrated.code
    assert "QtCore.QEvent.Type.Resize" in migrated.code
    assert "QSizePolicy.Policy.Expanding" in migrated.code
    assert "QtWidgets.QStyle.PixelMetric.PM_DefaultFrameWidth" in migrated.code
    assert migrated.refusals == ()

    candidate = tmp_path / "class-enums.py"
    candidate.write_text(source.replace("PyQt5", "PyQt6"), encoding="utf-8")
    findings = scan_paths([candidate], root=tmp_path)
    assert {item.rule for item in findings} == {"short-class-enum"}


def test_codemod_refuses_ambiguous_enum_and_removed_class_with_locations():
    source = '''from PyQt5.QtCore import Qt, QRegExp
mode = Qt.AA_EnableHighDpiScaling
pattern = QRegExp("x")
'''

    with pytest.raises(MigrationRefused) as caught:
        migrate_source(source, filename="ambiguous.py")

    report = caught.value.result
    assert [(item.line, item.symbol) for item in report.refusals] == [
        (1, "PyQt5.QtCore.QRegExp"),
        (2, "Qt.AA_EnableHighDpiScaling"),
    ]
    assert all(item.action for item in report.refusals)
    assert report.code == source


def test_codemod_is_idempotent_and_report_is_json_serializable():
    first = migrate_source(
        "from PyQt5.QtCore import Qt\nvalue = Qt.Checked\n",
        filename="idempotent.py",
    )
    second = migrate_source(first.code, filename="idempotent.py")

    assert second.code == first.code
    assert second.transformations == ()
    assert second.refusals == ()
    assert json.loads(first.to_json())["transformations"][0]["file"] == "idempotent.py"


def test_mapping_manifest_covers_every_discovered_enum_and_displaced_class():
    manifest = load_mapping_manifest()
    inventory = json.loads(
        (ROOT / "docs/verification/pre-qt6-baseline/qt-port-inventory.json").read_text(
            encoding="utf-8"
        )
    )
    enum_names = {item["symbol"].rsplit(".", 1)[-1] for item in inventory["short_enums"]}
    covered_enums = set(manifest.scoped_enums) | set(manifest.ambiguous_enums)
    displaced = {item["symbol"] for item in inventory["removed_or_displaced_apis"]}

    assert enum_names <= covered_enums
    assert {"QAction", "QGraphicsSvgItem", "QRegExp"} <= displaced
    assert {path.rsplit(".", 1)[-1] for path in manifest.moved_classes} == {
        "QAction",
        "QGraphicsSvgItem",
        "QUndoCommand",
        "QUndoStack",
    }
    assert any(path.endswith(".QRegExp") for path in manifest.removed_apis)


def test_class_scoped_enum_manifest_targets_exist_in_locked_pyqt6():
    manifest = load_mapping_manifest()
    assert len(manifest.class_scoped_enums) == 59
    for qt5_symbol, replacement in manifest.class_scoped_enums.items():
        parts = qt5_symbol.replace("PyQt5", "PyQt6", 1).split(".")
        owner = importlib.import_module(".".join(parts[:2]))
        for part in parts[2:-1]:
            owner = getattr(owner, part)
        assert not hasattr(owner, parts[-1])
        target = owner
        for part in replacement.split("."):
            target = getattr(target, part)
        assert target is not None


@pytest.mark.parametrize(
    ("name", "source", "rule"),
    [
        ("binding.py", "from PyQt5 import QtCore\n", "pyqt5-import"),
        ("compat.py", "import qtpy\n", "binding-facade"),
        ("enum.py", "from PyQt6.QtCore import Qt\nx = Qt.AlignLeft\n", "short-enum"),
        ("removed.py", "from PyQt6.QtCore import QRegExp\n", "removed-api"),
        ("generated.py", "# Form implementation generated from reading ui file\n", "stale-generator"),
        ("runtime.py", "from PyQt6.uic import loadUi\n", "runtime-form-loading"),
        ("resource.py", "qt_resource_data = b'bytes'\n", "generated-python-resource"),
        ("requirement.txt", "PyQt5==5.15.11\n", "pyqt5-requirement"),
    ],
)
def test_strict_scan_rejects_forbidden_migration_patterns(tmp_path, name, source, rule):
    candidate = tmp_path / name
    candidate.write_text(source, encoding="utf-8")

    findings = scan_paths([candidate], root=tmp_path)

    assert [finding.rule for finding in findings] == [rule]
    assert findings[0].line == (2 if name == "enum.py" else 1)


def test_strict_scan_has_no_false_positive_for_comments_strings_or_native_scopes(tmp_path):
    candidate = tmp_path / "native.py"
    candidate.write_text(
        '''from PyQt6.QtCore import Qt
# PyQt5, loadUi, Qt.AlignLeft, and qt_resource_data are migration prose.
message = "Qt5Compat and QRegExp are not active code"
alignment = Qt.AlignmentFlag.AlignLeft
''',
        encoding="utf-8",
    )

    assert scan_paths([candidate], root=tmp_path) == ()


def test_codemod_cli_writes_a_complete_report_and_second_check_is_empty(tmp_path):
    candidate = tmp_path / "candidate.py"
    report_path = tmp_path / "report.json"
    candidate.write_bytes(b"from PyQt5.QtCore import Qt\r\nvalue = Qt.Checked\r\n")
    original_mode = stat.S_IMODE(candidate.stat().st_mode)

    first = subprocess.run(
        [
            sys.executable,
            str(PORT_SCRIPT),
            "codemod",
            "--write",
            "--report",
            str(report_path),
            str(candidate),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    second = subprocess.run(
        [sys.executable, str(PORT_SCRIPT), "codemod", "--check", str(candidate)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["changed_files"] == [candidate.resolve().as_posix()]
    assert [item["kind"] for item in report["transformations"]] == [
        "binding-import",
        "scoped-enum",
    ]
    assert report["refusals"] == []
    assert json.loads(second.stdout)["changed_files"] == []
    assert first.stderr == second.stderr == ""
    assert candidate.read_bytes().endswith(b"Qt.CheckState.Checked\r\n")
    assert stat.S_IMODE(candidate.stat().st_mode) == original_mode


def test_dotted_import_without_alias_is_losslessly_refused():
    source = "import PyQt5.QtWidgets\nwidget = PyQt5.QtWidgets.QWidget()\n"

    with pytest.raises(MigrationRefused) as caught:
        migrate_source(source, filename="dotted.py")

    assert caught.value.result.code == source
    assert caught.value.result.refusals[0].line == 1
    assert "alias" in caught.value.result.refusals[0].action


def test_manifest_drives_moved_and_removed_module_attribute_diagnostics(tmp_path):
    moved = "from PyQt6 import QtWidgets\naction = QtWidgets.QAction()\n"
    removed = "from PyQt5 import QtCore\npattern = QtCore.QRegExp('x')\n"

    with pytest.raises(MigrationRefused) as moved_error:
        migrate_source(moved, filename="moved.py")
    with pytest.raises(MigrationRefused) as removed_error:
        migrate_source(removed, filename="removed.py")

    assert moved_error.value.result.refusals[0].symbol == "PyQt6.QtWidgets.QAction"
    assert removed_error.value.result.refusals[0].symbol == "PyQt5.QtCore.QRegExp"
    candidate = tmp_path / "moved.py"
    candidate.write_text(moved, encoding="utf-8")
    assert [item.rule for item in scan_paths([candidate], root=tmp_path)] == [
        "removed-api"
    ]


def test_parenthesized_per_alias_comments_are_refused_without_trivia_loss():
    source = '''from PyQt5.QtWidgets import (
    QAction,  # moved action
    QWidget,  # retained widget
)
'''

    with pytest.raises(MigrationRefused) as caught:
        migrate_source(source, filename="comments.py")

    assert caught.value.result.code == source
    assert "comment" in caught.value.result.refusals[0].action


def test_qt_bound_method_rewrite_is_safe_and_unrelated_lookalike_is_ignored(tmp_path):
    source = '''from PyQt5.QtWidgets import QApplication
app = QApplication([])
exit_code = app.exec_()
worker = Worker()
other = worker.exec_()
'''

    result = migrate_source(source, filename="methods.py")

    assert "exit_code = app.exec()" in result.code
    assert "worker.exec_()" in result.code
    candidate = tmp_path / "native.py"
    candidate.write_text(result.code, encoding="utf-8")
    assert scan_paths([candidate], root=tmp_path) == ()


def test_shadowed_qt_alias_refuses_every_rewrite_and_leaves_source_unchanged():
    source = '''from PyQt5.QtCore import Qt
before = Qt.AlignLeft
def render(Qt):
    return Qt.AlignRight
'''

    with pytest.raises(MigrationRefused) as caught:
        migrate_source(source, filename="shadowed.py")

    assert caught.value.result.code == source
    assert any(item.symbol == "Qt" and item.line == 3 for item in caught.value.result.refusals)


def test_file_transaction_rejects_concurrent_edit_and_cleans_temps(tmp_path):
    candidate = tmp_path / "candidate.py"
    candidate.write_bytes(b"from PyQt5.QtCore import Qt\r\nvalue = Qt.Checked\r\n")
    plan = prepare_file_migration(candidate)
    candidate.write_bytes(b"# concurrent edit\r\n")

    with pytest.raises(MigrationTransactionError, match="changed after planning"):
        apply_migration_transaction([plan])

    assert candidate.read_bytes() == b"# concurrent edit\r\n"
    assert not list(tmp_path.glob(".rcms-qt6-*"))


def test_file_transaction_rolls_back_prior_replace_and_cleans_temps(tmp_path, monkeypatch):
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    original = b"from PyQt5.QtCore import Qt\nvalue = Qt.Checked\n"
    first.write_bytes(original)
    second.write_bytes(original)
    plans = [prepare_file_migration(first), prepare_file_migration(second)]
    real_replace = os.replace
    target_replaces = 0

    def fail_second_target(source, destination):
        nonlocal target_replaces
        if Path(destination) in {first, second} and ".backup-" not in Path(source).name:
            target_replaces += 1
            if target_replaces == 2:
                raise OSError("injected replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_second_target)
    with pytest.raises(MigrationTransactionError, match="injected replace failure"):
        apply_migration_transaction(plans)

    assert first.read_bytes() == second.read_bytes() == original
    assert not list(tmp_path.glob(".rcms-qt6-*"))


def test_file_transaction_rejects_symlink(tmp_path):
    target = tmp_path / "target.py"
    link = tmp_path / "link.py"
    target.write_text("from PyQt5 import QtCore\n", encoding="utf-8")
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(MigrationTransactionError, match="symbolic link"):
        prepare_file_migration(link)
    completed = subprocess.run(
        [sys.executable, str(PORT_SCRIPT), "codemod", "--write", str(link)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "symbolic link" in completed.stderr
    assert target.read_text(encoding="utf-8") == "from PyQt5 import QtCore\n"


def test_dependency_policy_rejects_alternate_bindings_from_requirement_inputs(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("PySide6==6.11.0\n", encoding="utf-8")

    findings = scan_paths([requirements], root=tmp_path)

    assert [item.rule for item in findings] == ["alternate-binding-requirement"]


def test_maintained_lane_scans_authoritative_inputs_and_treats_warnings_as_errors():
    workflow = (ROOT / "scripts/verify-qt6.ps1").read_text(encoding="utf-8")

    assert "pyproject.toml" in workflow
    assert "uv.lock" in workflow
    assert "requirements*.txt" in workflow
    assert "constraints*.txt" in workflow
    assert "src/rc_metastudio" in workflow
    assert "qt6-strict-source-backlog.json" in workflow
    assert "uv run pytest -W error" in workflow


def test_report_path_cannot_alias_any_input_and_report_replace_is_atomic(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate.py"
    source = b"from PyQt5 import QtCore\n"
    candidate.write_bytes(source)
    aliases = [candidate, tmp_path / "." / "candidate.py"]
    hardlink = tmp_path / "hardlink.py"
    has_hardlink = False
    try:
        os.link(candidate, hardlink)
        aliases.append(hardlink)
        has_hardlink = True
    except OSError:
        pass
    symlink = tmp_path / "symlink.py"
    try:
        symlink.symlink_to(candidate)
        aliases.append(symlink)
    except OSError:
        pass
    for report in aliases:
        completed = subprocess.run(
            [
                sys.executable,
                str(PORT_SCRIPT),
                "codemod",
                "--write",
                "--report",
                str(report),
                str(candidate),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert candidate.read_bytes() == source
    if has_hardlink:
        completed = subprocess.run(
            [
                sys.executable,
                str(PORT_SCRIPT),
                "codemod",
                "--report",
                str(tmp_path / "separate-report.json"),
                str(candidate),
                str(hardlink),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert candidate.read_bytes() == source
    completed = subprocess.run(
        [
            sys.executable,
            str(PORT_SCRIPT),
            "codemod",
            str(candidate),
            str(candidate),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "alias the same file" in completed.stderr

    report = tmp_path / "report.json"
    report.write_text("old report\n", encoding="utf-8")
    real_replace = os.replace

    def fail_report_replace(source_path, destination):
        if Path(destination) == report:
            raise OSError("report replace failure")
        return real_replace(source_path, destination)

    monkeypatch.setattr(os, "replace", fail_report_replace)
    with pytest.raises(MigrationTransactionError, match="report replace failure"):
        write_atomic_text(report, "new report\n")
    assert report.read_text(encoding="utf-8") == "old report\n"
    assert not list(tmp_path.glob(".rcms-qt6-report-*"))


def test_qualified_qt5_compatibility_modules_are_rejected(tmp_path):
    source = "from PyQt6.QtCore5Compat import QTextCodec\n"
    with pytest.raises(MigrationRefused, match="compatibility"):
        migrate_source(source, filename="compat.py")
    candidate = tmp_path / "compat.py"
    candidate.write_text(source, encoding="utf-8")
    assert [item.rule for item in scan_paths([candidate], root=tmp_path)] == [
        "binding-facade"
    ]


def test_unresolved_or_reassigned_exec_is_refused_but_non_qt_instance_is_not():
    unresolved = "result = app.exec_()\n"
    reassigned = '''from PyQt5.QtWidgets import QApplication
app = QApplication([])
app = replacement
result = app.exec_()
'''
    for source in (unresolved, reassigned):
        with pytest.raises(MigrationRefused, match="exec_"):
            migrate_source(source, filename="exec.py")


def test_same_destination_import_rewrite_preserves_every_byte_except_binding_token():
    source = '''# before
from PyQt5.QtCore import (  # opening
    Qt,  # enum namespace
    pyqtSignal,  # signal
)
# after
'''
    result = migrate_source(source, filename="formatting.py")
    assert result.code == source.replace("PyQt5", "PyQt6", 1)


def test_dynamic_binding_imports_are_rejected_without_unrelated_false_positives(tmp_path):
    source = '''import builtins as builtin_api
import importlib
from builtins import __import__ as builtin_import
legacy = importlib.import_module("PyQt5.QtCore")
hidden = importlib.import_module(binding_name)
compat = __import__("PyQt6.QtCore5Compat")
aliased = builtin_import("PyQt5.QtGui")
qualified = builtin_api.__import__("PyQt6.QtCore5Compat")
main = __import__("__main__")
plugin = plugin_loader.load(plugin_name)
'''
    with pytest.raises(MigrationRefused) as caught:
        migrate_source(source, filename="dynamic.py")
    assert {item.symbol for item in caught.value.result.refusals} == {
        'importlib.import_module("PyQt5.QtCore")',
        "importlib.import_module(<dynamic>)",
        '__import__("PyQt6.QtCore5Compat")',
        'builtins.__import__("PyQt5.QtGui")',
        'builtins.__import__("PyQt6.QtCore5Compat")',
    }
    candidate = tmp_path / "dynamic.py"
    candidate.write_text(source, encoding="utf-8")
    rules = [item.rule for item in scan_paths([candidate], root=tmp_path)]
    assert rules == [
        "pyqt5-import",
        "dynamic-binding-import",
        "binding-facade",
        "pyqt5-import",
        "binding-facade",
    ]
    shadowed = '''from builtins import __import__ as dynamic_import
dynamic_import = replacement
module = dynamic_import("PyQt5.QtCore")
'''
    with pytest.raises(MigrationRefused) as shadowed_error:
        migrate_source(shadowed, filename="shadowed-import.py")
    assert shadowed_error.value.result.refusals[0].symbol == (
        "builtins.__import__(<shadowed>)"
    )


def test_strict_output_paths_cannot_alias_expected_snapshot(tmp_path):
    source = tmp_path / "native.py"
    source.write_text("value = 1\n", encoding="utf-8")
    expected = tmp_path / "expected.json"
    expected.write_text(
        json.dumps(port_tools.findings_snapshot(()), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    aliases = [expected]
    hardlink = tmp_path / "expected-hardlink.json"
    try:
        os.link(expected, hardlink)
        aliases.append(hardlink)
    except OSError:
        pass
    symlink = tmp_path / "expected-symlink.json"
    try:
        symlink.symlink_to(expected)
        aliases.append(symlink)
    except OSError:
        pass
    original = expected.read_bytes()
    for report in aliases:
        completed = subprocess.run(
            [
                sys.executable,
                str(PORT_SCRIPT),
                "strict",
                "--root",
                str(tmp_path),
                "--expected-snapshot",
                str(expected),
                "--report",
                str(report),
                str(source),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert expected.read_bytes() == original


def test_staged_mode_is_applied_before_final_payload_fsync(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate.py"
    candidate.write_text("from PyQt5 import QtCore\n", encoding="utf-8")
    plan = prepare_file_migration(candidate)
    events = []
    real_chmod = os.chmod
    real_fsync = os.fsync

    def observed_chmod(path, mode):
        events.append(("chmod", Path(path)))
        return real_chmod(path, mode)

    def observed_fsync(descriptor):
        events.append(("fsync", descriptor))
        return real_fsync(descriptor)

    monkeypatch.setattr(os, "chmod", observed_chmod)
    monkeypatch.setattr(os, "fsync", observed_fsync)
    apply_migration_transaction([plan])

    assert events[0][0] == "chmod"
    assert events[1][0] == "fsync"

    second = tmp_path / "second.py"
    second.write_text("from PyQt5 import QtCore\n", encoding="utf-8")
    second_plan = prepare_file_migration(second)

    def fail_chmod(_path, _mode):
        raise OSError("mode apply failure")

    monkeypatch.setattr(os, "chmod", fail_chmod)
    with pytest.raises(MigrationTransactionError, match="mode apply failure"):
        apply_migration_transaction([second_plan])
    assert second.read_text(encoding="utf-8") == "from PyQt5 import QtCore\n"
    assert not list(tmp_path.glob(".rcms-qt6-*"))


@pytest.mark.parametrize("existing", [False, True])
def test_atomic_report_restores_destination_when_directory_fsync_fails(
    tmp_path, monkeypatch, existing
):
    report = tmp_path / "report.json"
    if existing:
        report.write_text("old report\n", encoding="utf-8")
    calls = 0

    def fail_first_sync(_path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("directory fsync failure")

    monkeypatch.setattr(port_tools, "_sync_directory", fail_first_sync)
    with pytest.raises(MigrationTransactionError, match="directory fsync failure"):
        write_atomic_text(report, "new report\n")

    assert report.exists() is existing
    if existing:
        assert report.read_text(encoding="utf-8") == "old report\n"
    assert not list(tmp_path.glob(".rcms-qt6-*"))


def test_atomic_report_preserves_primary_error_when_restoration_fails(
    tmp_path, monkeypatch
):
    report = tmp_path / "report.json"
    report.write_text("old report\n", encoding="utf-8")
    real_replace = os.replace

    def fail_directory_sync(_path):
        raise OSError("primary directory fsync failure")

    def fail_backup_restore(source, destination):
        if "backup-" in Path(source).name and Path(destination) == report:
            raise OSError("backup restore failure")
        return real_replace(source, destination)

    monkeypatch.setattr(port_tools, "_sync_directory", fail_directory_sync)
    monkeypatch.setattr(os, "replace", fail_backup_restore)
    with pytest.raises(MigrationTransactionError) as caught:
        write_atomic_text(report, "new report\n")

    message = str(caught.value)
    assert "primary directory fsync failure" in message
    assert "backup restore failure" in message
    assert "may be mutated" in message
    recovery = list(tmp_path.glob(".rcms-qt6-backup-*"))
    assert len(recovery) == 1
    assert str(recovery[0]) in message
    assert recovery[0].read_text(encoding="utf-8") == "old report\n"
    recovery[0].unlink()
    assert not list(tmp_path.glob(".rcms-qt6-*"))


@pytest.mark.parametrize(
    ("call", "rule"),
    [
        ('importlib.import_module(".QtCore", "PyQt5")', "pyqt5-import"),
        ('importlib.import_module(package="PyQt6", name=".QtCore5Compat")', "binding-facade"),
        ('importlib.import_module(".QtCore")', "dynamic-binding-import"),
        ('importlib.import_module(".QtCore", package_name)', "dynamic-binding-import"),
        ('importlib.import_module(".QtCore", "PyQt6", package="PyQt5")', "dynamic-binding-import"),
    ],
)
def test_relative_dynamic_import_packages_are_resolved_or_refused(tmp_path, call, rule):
    source = f"import importlib\nmodule = {call}\n"
    with pytest.raises(MigrationRefused):
        migrate_source(source, filename="relative-import.py")
    candidate = tmp_path / "relative-import.py"
    candidate.write_text(source, encoding="utf-8")
    assert [item.rule for item in scan_paths([candidate], root=tmp_path)] == [rule]


def test_repository_mechanical_cutover_retains_auditable_behavioral_handoffs():
    inventory = json.loads(
        (ROOT / "docs/verification/pre-qt6-baseline/qt-port-inventory.json").read_text(
            encoding="utf-8"
        )
    )
    report = json.loads(
        (ROOT / "docs/verification/qt6-codemod-report.json").read_text(
            encoding="utf-8"
        )
    )
    second_run = json.loads(
        (ROOT / "docs/verification/qt6-codemod-second-run.json").read_text(
            encoding="utf-8"
        )
    )
    handoffs = json.loads(
        (ROOT / "config/qt6-behavioral-handoffs.json").read_text(encoding="utf-8")
    )
    snapshot = json.loads(
        (ROOT / "config/qt6-strict-source-backlog.json").read_text(encoding="utf-8")
    )

    assert len(report["transformations"]) >= 400
    assert report["refusals"] == []
    assert second_run == {
        "changed_files": [],
        "refusals": [],
        "schema_version": 1,
        "transformations": [],
    }
    assert len(handoffs["resolved_codemod_refusals"]) == 10
    assert {item["owner_issue"] for item in handoffs["resolved_codemod_refusals"]} <= {
        333,
        335,
        336,
        338,
    }
    assert snapshot["finding_count"] == 0
    assert snapshot["counts_by_rule"] == {}
    assert not any((ROOT / path).exists() for path in inventory["generated_modules"])
