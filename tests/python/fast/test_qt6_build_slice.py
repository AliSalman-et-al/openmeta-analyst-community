import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

from rc_metastudio import qt6_build


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


def test_qt6_runtime_and_verification_tools_are_exactly_locked():
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
    assert not any(requirement.lower().startswith("pyqt5") for requirement in dependencies)
    assert "ty==0.0.18" in development
    assert "py7zr==1.1.3" in development
    assert locked_versions["pyqt6"] == "6.11.0"
    assert locked_versions["pyqt6-qt6"] == "6.11.1"
    assert locked_versions["pyqt6-sip"] == "13.11.1"
    assert "pyqt5" not in locked_versions


def _official_rcc() -> Path:
    _run_build("generate", "--build-root", str(ROOT / "build/test-qt6-rcc"))
    return ROOT / "build/qt-rcc/6.11.1/msvc2022_64/bin/rcc.exe"


def test_matching_official_rcc_identity_is_accepted():
    qt6_build.validate_rcc(_official_rcc())
    archive = ROOT / "build/qt-rcc/cache" / qt6_build.QT_RCC_PACKAGE
    assert qt6_build.QT_RCC_PACKAGE_SIZE == 39_469_569
    assert archive.stat().st_size == qt6_build.QT_RCC_PACKAGE_SIZE


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


def test_rcc_wrong_version_is_rejected():
    with pytest.raises(RuntimeError, match="version mismatch"):
        qt6_build.validate_rcc(_official_rcc(), expected_version="6.11.0")


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


def test_official_archive_rejects_short_download_before_digest(
    tmp_path, monkeypatch
):
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
    assert "project_format.py" in workflow
    assert "project_domain.py" in workflow
    assert "project_evidence.py" in workflow
    assert "test_project_format.py" in workflow
    assert "--require-covered" in workflow
    assert "native-smoke" in workflow
    assert "Remove-Item Env:QT_QPA_PLATFORM" in workflow

    hosted = (ROOT / ".github/workflows/fast-verification.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts\\verify-qt6.ps1 -Sync" in hosted
    assert ".python-version|pyproject.toml" in hosted
    assert "scripts/validate_test_taxonomy.py" in hosted
    assert "scripts\\verify-smoke.ps1" not in hosted
    assert "scripts\\verify-fast.ps1" not in hosted
