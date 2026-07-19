import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tomllib

import pytest

from rc_metastudio import qt6_build, qt6_resources


ROOT = Path(__file__).resolve().parents[3]
BUILD_SCRIPT = ROOT / "scripts" / "build_qt6.py"


def _run_build(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    return subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), *arguments],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_qt6_runtime_and_verification_tools_are_exactly_locked(tmp_path, monkeypatch):
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    dependencies = set(metadata["project"]["dependencies"])
    development = set(metadata["dependency-groups"]["dev"])
    locked_versions = {
        package["name"].lower(): package["version"] for package in lock["package"]
    }

    assert metadata["project"]["requires-python"] == ">=3.11,<3.12"
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.11.9"
    assert "PyQt6==6.11.0" in dependencies
    assert "pyinstaller==6.21.0" in dependencies
    assert not any(
        requirement.lower().startswith("pyqt5") for requirement in dependencies
    )
    assert "ty==0.0.18" in development
    assert "py7zr==1.1.3" in development
    assert locked_versions["pyqt6"] == "6.11.0"
    assert locked_versions["pyqt6-qt6"] == "6.11.1"
    assert locked_versions["pyqt6-sip"] == "13.11.1"
    assert "pyqt5" not in locked_versions

    scripts_directory = tmp_path / ("Scripts" if os.name == "nt" else "bin")
    interpreter = scripts_directory / ("python.exe" if os.name == "nt" else "python")
    pyuic6 = scripts_directory / ("pyuic6.exe" if os.name == "nt" else "pyuic6")
    scripts_directory.mkdir(parents=True)
    interpreter.write_bytes(b"locked interpreter")
    pyuic6.write_bytes(b"locked entrypoint")
    monkeypatch.setattr(qt6_build.sys, "executable", str(interpreter))
    monkeypatch.setattr(qt6_build.shutil, "which", lambda _name: None)

    assert qt6_build._resolve_pyuic6() == str(pyuic6)

    pyuic6.unlink()
    with pytest.raises(RuntimeError, match="not available from the locked"):
        qt6_build._resolve_pyuic6()

    outside = tmp_path / "unselected" / pyuic6.name
    outside.parent.mkdir()
    outside.write_bytes(b"other entrypoint")
    monkeypatch.setattr(qt6_build.shutil, "which", lambda _name: str(outside))
    with pytest.raises(RuntimeError, match="outside the selected locked"):
        qt6_build._resolve_pyuic6()

    pyuic6.write_bytes(b"adjacent reparse fixture")
    original_resolve = Path.resolve
    outside_resolved = outside.resolve()

    def resolve_as_foreign_target(path, *args, **kwargs):
        if path == pyuic6:
            return outside_resolved
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_as_foreign_target)
    with pytest.raises(RuntimeError, match="adjacent.*resolves outside"):
        qt6_build._resolve_pyuic6()


def _official_rcc() -> Path:
    _run_build("generate", "--build-root", str(ROOT / "build/test-qt6-rcc"))
    return ROOT / "build/qt-rcc/6.11.1/msvc2022_64/bin/rcc.exe"


WINDOWS_RCC_TEST = pytest.mark.skipif(
    sys.platform != "win32",
    reason="validates the pinned Windows PE rcc package",
)


@WINDOWS_RCC_TEST
def test_matching_official_rcc_identity_is_accepted():
    qt6_build.validate_rcc(_official_rcc())
    archive = ROOT / "build/qt-rcc/cache" / qt6_build.QT_RCC_PACKAGE
    assert qt6_build.QT_RCC_PACKAGE_SIZE == 39_469_569
    assert archive.stat().st_size == qt6_build.QT_RCC_PACKAGE_SIZE


@WINDOWS_RCC_TEST
def test_rcc_digest_and_configured_tool_identity_fail_closed(tmp_path, monkeypatch):
    official = _official_rcc()
    candidate = tmp_path / "bin/rcc.exe"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(official.read_bytes() + b"tampered")
    candidate.with_name("Qt6Core.dll").write_bytes(
        official.with_name("Qt6Core.dll").read_bytes()
    )

    with pytest.raises(RuntimeError, match="digest mismatch"):
        qt6_build.validate_rcc(candidate)
    monkeypatch.setenv("RCMS_QT6_RCC", str(candidate))
    with pytest.raises(RuntimeError, match="digest mismatch"):
        qt6_build._resolve_rcc()


@WINDOWS_RCC_TEST
def test_rcc_wrong_architecture_is_rejected_even_with_matching_digest(tmp_path):
    official = _official_rcc()
    candidate = tmp_path / "bin/rcc.exe"
    candidate.parent.mkdir(parents=True)
    payload = bytearray(official.read_bytes())
    pe_offset = int.from_bytes(payload[0x3C:0x40], "little")
    payload[pe_offset + 4 : pe_offset + 6] = (0xAA64).to_bytes(2, "little")
    candidate.write_bytes(payload)
    candidate.with_name("Qt6Core.dll").write_bytes(
        official.with_name("Qt6Core.dll").read_bytes()
    )

    digest = hashlib.sha256(payload).hexdigest()
    with pytest.raises(RuntimeError, match="architecture mismatch"):
        qt6_build.validate_rcc(candidate, expected_digest=digest)


@WINDOWS_RCC_TEST
def test_rcc_wrong_version_is_rejected():
    with pytest.raises(RuntimeError, match="version mismatch"):
        qt6_build.validate_rcc(_official_rcc(), expected_version="6.11.0")


def test_macos_official_rcc_requires_pinned_version_and_host_slice(
    tmp_path, monkeypatch
):
    rcc = tmp_path / "Qt SDK" / "libexec" / "rcc"
    rcc.parent.mkdir(parents=True)
    rcc.write_bytes(b"official macOS rcc fixture")
    responses = {
        "version": "rcc 6.11.1",
        "architectures": "arm64 x86_64",
    }

    def completed(command, **_kwargs):
        stdout = (
            responses["architectures"]
            if str(command[0]).endswith("lipo")
            else responses["version"]
        )
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(qt6_build.subprocess, "run", completed)
    monkeypatch.setattr(qt6_build.platform, "machine", lambda: "arm64")

    qt6_build.validate_macos_rcc(rcc)

    responses["version"] = "rcc 6.11.0"
    with pytest.raises(RuntimeError, match="version mismatch"):
        qt6_build.validate_macos_rcc(rcc)

    responses["version"] = "rcc 6.11.1"
    responses["architectures"] = "x86_64"
    with pytest.raises(RuntimeError, match="architecture mismatch"):
        qt6_build.validate_macos_rcc(rcc)


class _DownloadResponse:
    def __init__(self, chunks, content_length=None):
        self._chunks = iter(chunks)
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self.read_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info):
        return False

    def read(self, _size):
        self.read_count += 1
        return next(self._chunks, b"")


def test_official_archive_rejects_oversized_content_length_before_writing(
    tmp_path, monkeypatch
):
    response = _DownloadResponse([b"abcde"], content_length=5)
    monkeypatch.setattr(qt6_build.urllib.request, "urlopen", lambda *_a, **_k: response)
    destination = tmp_path / "qt.7z"

    with pytest.raises(RuntimeError, match="Content-Length exceeds"):
        qt6_build.download_pinned_archive(
            "https://download.qt.io/pinned.7z",
            destination,
            expected_size=4,
            expected_digest="unused",
        )

    assert response.read_count == 0
    assert not destination.exists()
    assert not destination.with_suffix(".download").exists()


def test_official_archive_stops_streaming_at_the_pinned_byte_ceiling(
    tmp_path, monkeypatch
):
    response = _DownloadResponse([b"abc", b"de", b"more"])
    monkeypatch.setattr(qt6_build.urllib.request, "urlopen", lambda *_a, **_k: response)
    destination = tmp_path / "qt.7z"

    with pytest.raises(RuntimeError, match="stream exceeds"):
        qt6_build.download_pinned_archive(
            "https://download.qt.io/pinned.7z",
            destination,
            expected_size=4,
            expected_digest="unused",
        )

    assert response.read_count == 2
    assert not destination.exists()
    assert not destination.with_suffix(".download").exists()


def test_official_archive_rejects_short_download_before_digest(tmp_path, monkeypatch):
    response = _DownloadResponse([b"abc"], content_length=3)
    monkeypatch.setattr(qt6_build.urllib.request, "urlopen", lambda *_a, **_k: response)
    destination = tmp_path / "qt.7z"

    with pytest.raises(RuntimeError, match="byte count mismatch"):
        qt6_build.download_pinned_archive(
            "https://download.qt.io/pinned.7z",
            destination,
            expected_size=4,
            expected_digest=hashlib.sha256(b"abc").hexdigest(),
        )

    assert not destination.exists()
    assert not destination.with_suffix(".download").exists()


def test_canonical_form_generation_is_deterministic_and_importable(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _run_build("generate", "--build-root", str(first))
    _run_build("generate", "--build-root", str(second))

    relative_module = Path("generated/rc_metastudio/forms/ui_about_legal.py")
    first_module = first / relative_module
    second_module = second / relative_module
    assert first_module.read_bytes() == second_module.read_bytes()
    assert (first / "resources/icons.rcc").read_bytes() == (
        second / "resources/icons.rcc"
    ).read_bytes()

    generated = first_module.read_text(encoding="utf-8")
    assert "from PyQt6" in generated
    assert "connectSlotsByName" not in generated
    assert "loadUi" not in generated

    spec = importlib.util.spec_from_file_location("generated_about_legal", first_module)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.Ui_AboutLegalDialog.__name__ == "Ui_AboutLegalDialog"

    first_modules = sorted(
        path.relative_to(first / "generated").as_posix()
        for path in (first / "generated").rglob("ui_*.py")
    )
    second_modules = sorted(
        path.relative_to(second / "generated").as_posix()
        for path in (second / "generated").rglob("ui_*.py")
    )
    assert len(first_modules) == 29
    assert first_modules == second_modules
    for relative in first_modules:
        first_payload = (first / "generated" / relative).read_bytes()
        second_payload = (second / "generated" / relative).read_bytes()
        assert first_payload == second_payload
        rendered = first_payload.decode("utf-8")
        assert "from PyQt6" in rendered
        assert "connectSlotsByName" not in rendered
        assert "icons_rc" not in rendered


def test_canonical_form_manifest_fails_closed_on_drift_and_collisions():
    discovered = set(
        Path(path).relative_to(ROOT)
        for path in (ROOT / "src/rc_metastudio/forms").glob("*.ui")
    )
    qt6_build.validate_form_manifest(qt6_build.CANONICAL_FORMS, discovered)

    source, destination = next(iter(qt6_build.CANONICAL_FORMS.items()))
    missing = dict(qt6_build.CANONICAL_FORMS)
    missing.pop(source)
    with pytest.raises(RuntimeError, match="manifest does not match"):
        qt6_build.validate_form_manifest(missing, discovered)

    extra = dict(qt6_build.CANONICAL_FORMS)
    extra[Path("src/rc_metastudio/forms/not-canonical.ui")] = Path(
        "rc_metastudio/forms/ui_not_canonical.py"
    )
    with pytest.raises(RuntimeError, match="manifest does not match"):
        qt6_build.validate_form_manifest(extra, discovered)

    collision = dict(qt6_build.CANONICAL_FORMS)
    other = next(item for item in collision if item != source)
    collision[other] = destination
    with pytest.raises(RuntimeError, match="destination collision"):
        qt6_build.validate_form_manifest(collision, discovered)

    traversal = dict(qt6_build.CANONICAL_FORMS)
    traversal[source] = Path("../ui_escape.py")
    with pytest.raises(RuntimeError, match="non-canonical destination"):
        qt6_build.validate_form_manifest(traversal, discovered)


def test_generated_ui_bootstrap_imports_every_handwritten_qt_module(tmp_path):
    build_root = tmp_path / "qt6"
    _run_build("generate", "--build-root", str(build_root))
    inventory = json.loads(
        (ROOT / "docs/verification/pre-qt6-baseline/qt-port-inventory.json").read_text(
            encoding="utf-8"
        )
    )
    modules = [
        Path(path).stem
        for path in inventory["handwritten_qt_modules"]
        if (ROOT / path).is_file()
    ]
    script = """
import importlib
import json
import sys
import types
from pathlib import Path

root = Path(sys.argv[1])
build_root = Path(sys.argv[2])
modules = json.loads(sys.argv[3])
report_path = Path(sys.argv[4])
sys.path.insert(0, str(root / "src/rc_metastudio"))
from rc_metastudio.qt6_ui import prepare_generated_ui_imports
layout = prepare_generated_ui_imports(build_root)
# A later test or tool may prepend source paths. The bootstrap must already have
# bound the top-level forms package to generated Qt6 output.
sys.path.insert(0, str(root / "src/rc_metastudio/forms"))
sys.path.insert(0, str(root / "src/rc_metastudio"))
forms = importlib.import_module("forms")
if layout.package_root not in Path(forms.__file__).resolve().parents:
    raise RuntimeError("forms package escaped the generated Qt6 layout")
for name in modules:
    importlib.import_module(name)
fake_launch = types.ModuleType("launch")
fake_launch.start = lambda: 0
sys.modules["launch"] = fake_launch
from rc_metastudio.__main__ import main
startup_result = main()
report_path.write_text(
    json.dumps({
        "count": len(modules),
        "generated_root": str(layout.package_root),
        "startup_result": startup_result,
    }),
    encoding="utf-8",
)
"""
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["RCMS_QT6_BUILD_ROOT"] = str(build_root)
    report_path = tmp_path / "import-report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(ROOT),
            str(build_root),
            json.dumps(modules),
            str(report_path),
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, (
        "generated UI bootstrap failed\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["count"] == 35
    assert report["startup_result"] == 0
    assert Path(report["generated_root"]) == (build_root / "generated/rc_metastudio")


def test_generated_ui_bootstrap_rejects_missing_or_tampered_outputs(tmp_path):
    from rc_metastudio.qt6_ui import prepare_generated_ui_imports

    build_root = tmp_path / "qt6"
    _run_build("generate", "--build-root", str(build_root))
    target = build_root / "generated/rc_metastudio/forms/ui_about_legal.py"
    target.unlink()
    with pytest.raises(RuntimeError, match="generated form set"):
        prepare_generated_ui_imports(build_root)

    _run_build("generate", "--build-root", str(build_root))
    target.write_text("from PyQt5 import QtCore\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid generated Qt6 form"):
        prepare_generated_ui_imports(build_root)


def test_binary_resource_registers_and_exposes_icon_and_svg(tmp_path):
    build_root = tmp_path / "qt6"
    _run_build("generate", "--build-root", str(build_root))
    resource = build_root / "resources" / "icons.rcc"

    assert resource.is_file()
    assert resource.read_bytes().startswith(b"qres")

    from PyQt6 import QtCore

    assert QtCore.QResource.registerResource(str(resource))
    try:
        assert QtCore.QFile(":/misc/meta.png").exists()
        assert QtCore.QFile(":/icons/actions/about-legal.svg").exists()
    finally:
        assert QtCore.QResource.unregisterResource(str(resource))


def test_application_resource_loader_registers_only_the_binary_collection(tmp_path):
    build_root = tmp_path / "qt6"
    _run_build("generate", "--build-root", str(build_root))
    resource = build_root / "resources" / "icons.rcc"

    registration = qt6_resources.register_binary_resource(resource)
    try:
        from PyQt6 import QtCore

        assert registration.path == resource.resolve()
        assert QtCore.QFile(":/misc/meta.png").exists()
        assert QtCore.QFile(":/icons/actions/about-legal.svg").exists()
    finally:
        registration.close()


def test_minimal_qt6_window_reports_resources_and_exits_cleanly(tmp_path):
    completed = _run_build(
        "smoke",
        "--build-root",
        str(tmp_path / "qt6"),
        "--exit-after-ms",
        "1",
    )
    report = json.loads(completed.stdout)

    assert report["pyqt"] == "6.11.0"
    assert report["qt"] == "6.11.1"
    assert report["form"] == "AboutLegalDialog"
    assert report["app_icon"] is True
    assert report["svg_icon"] is True
    assert report["clean_exit"] is True


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native slice")
def test_native_windows_smoke_uses_qwindows_and_a_visible_dialog(tmp_path):
    environment = os.environ.copy()
    environment.pop("QT_QPA_PLATFORM", None)
    completed = subprocess.run(
        [
            sys.executable,
            str(BUILD_SCRIPT),
            "native-smoke",
            "--build-root",
            str(tmp_path / "native"),
            "--exit-after-ms",
            "25",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)

    assert report["qpa"] == "windows"
    assert report["native"] is True
    assert report["architecture"].lower() in {"amd64", "x86_64"}
    assert report["visible"] is True
    assert report["app_icon"] is True
    assert report["svg_icon"] is True
    assert report["clean_exit"] is True


def test_qt6_generation_and_type_checks_have_a_maintained_entry_point():
    workflow = (ROOT / "scripts" / "verify-qt6.ps1").read_text(encoding="utf-8")

    assert "uv sync --locked" in workflow
    assert "build_qt6.py" in workflow
    assert "ty check" in workflow
    assert "test_qt6_build_slice.py" in workflow
    assert "import_qt_modules.py --root . --list" in workflow
    assert "$qtModules" in workflow
    assert "test_project_format.py" in workflow
    assert "--require-covered" in workflow
    assert "native-smoke" in workflow
    assert "Remove-Item Env:QT_QPA_PLATFORM" in workflow
    assert "scripts/run_with_timeout.py" in workflow
    assert workflow.count("Invoke-NativeSmokeCommand -Label") == 11
    assert "[int]$TimeoutSeconds = 300" in workflow

    hosted = (ROOT / ".github/workflows/fast-verification.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts\\verify-qt6.ps1 -Sync" in hosted
    assert ".python-version|pyproject.toml" in hosted
    assert "config/*" in hosted
    assert "scripts/*" in hosted
    assert "docs/verification/*" in hosted
    assert "scripts\\verify-smoke.ps1" in hosted
    assert "scripts\\verify-fast.ps1" in hosted
    assert hosted.count("-RequireREvidence") == 2
    assert hosted.count("--require-r-evidence") == 2
    assert "macos-x64" in hosted
    assert "macos-arm64" in hosted
    assert "timeout-minutes: 45" in hosted
    assert "Rebuild and prove macOS rpy2 API bridge against installed R" in hosted
    rebuild = hosted.index(
        "Rebuild and prove macOS rpy2 API bridge against installed R"
    )
    macos_verify = hosted.index("Run source smoke and Fast Verification on macOS")
    assert rebuild < macos_verify
    assert 'export R_HOME="$(R RHOME)"' in hosted
    assert 'echo "R_HOME=$R_HOME" >> "$GITHUB_ENV"' in hosted
    assert 'echo "RPY2_CFFI_MODE=API" >> "$GITHUB_ENV"' in hosted
    assert "uv sync --locked --reinstall-package rpy2-rinterface" in hosted
    assert "--no-binary-package rpy2-rinterface" in hosted
    assert 'metadata.version("rpy2-rinterface")' in hosted
    assert 'lipo -archs "$bridge"' in hosted
    assert "otool -L" in hosted and "count + 0" in hosted
    assert 'openrlib.cffi_mode.name != "API"' in hosted
    macos_run = hosted[macos_verify : hosted.index("Prune uv cache", macos_verify)]
    assert "verify-smoke.sh --sync" not in macos_run

    for verification_script in (
        "scripts/verify-smoke.ps1",
        "scripts/verify-fast.ps1",
        "scripts/verify-smoke.sh",
        "scripts/verify-fast.sh",
    ):
        source = (ROOT / verification_script).read_text(encoding="utf-8")
        assert "build_qt6.py" in source
        assert "generate" in source
        assert "build/qt6-verification" in source.replace("\\", "/")
        assert "RCMS_QT6_BUILD_ROOT" in source
        assert "PYTHONPATH" in source


def test_native_smoke_timeout_runner_streams_output_and_fails_closed():
    runner = ROOT / "scripts" / "run_with_timeout.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--timeout-seconds",
            "1",
            "--label",
            "deterministic timeout smoke",
            "--",
            sys.executable,
            "-u",
            "-c",
            "import time; print('streamed-before-timeout', flush=True); time.sleep(30)",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 124
    assert "streamed-before-timeout" in completed.stdout
    assert "deterministic timeout smoke timed out after 1 seconds" in completed.stderr
    assert sys.executable in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows taskkill contract")
def test_timeout_runner_reports_taskkill_failure(monkeypatch):
    runner_path = ROOT / "scripts" / "run_with_timeout.py"
    spec = importlib.util.spec_from_file_location("timeout_runner_test", runner_path)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    class FakeProcess:
        pid = 424242

    def fail_taskkill(command, **_kwargs):
        return subprocess.CompletedProcess(command, 5, "", "Access is denied")

    monkeypatch.setattr(runner.subprocess, "run", fail_taskkill)
    with pytest.raises(RuntimeError, match="taskkill /T /F failed.*Access is denied"):
        runner._terminate_process_tree(FakeProcess())


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group teardown contract")
def test_timeout_runner_kills_sigterm_ignoring_grandchild(tmp_path):
    runner = ROOT / "scripts" / "run_with_timeout.py"
    marker = tmp_path / "escaped-grandchild.txt"
    grandchild = (
        "import pathlib,signal,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "time.sleep(2); "
        f"pathlib.Path({str(marker)!r}).write_text('escaped', encoding='utf-8')"
    )
    parent = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}]); "
        "time.sleep(0.5); print('grandchild-ready', flush=True); time.sleep(30)"
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--timeout-seconds",
            "1",
            "--label",
            "process group smoke",
            "--",
            sys.executable,
            "-u",
            "-c",
            parent,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 124
    assert "grandchild-ready" in completed.stdout
    deadline = time.monotonic() + 2.5
    while time.monotonic() < deadline and not marker.exists():
        time.sleep(0.05)
    assert not marker.exists()
