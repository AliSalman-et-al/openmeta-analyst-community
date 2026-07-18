"""Focused contract tests for the explicit macOS embedded-R product profile."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def load_profile():
    path = Path("scripts/profile_macos_embedded_r_runtime.py")
    spec = importlib.util.spec_from_file_location("embedded_r_profile", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_runtime(tmp_path: Path) -> Path:
    root = tmp_path / "Resources"
    launcher = root / "bin/R"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_bytes(b'#!/bin/sh\nexec "$(dirname "$0")/exec/R" "$@"\n')
    executable = root / "bin/exec/R"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"Mach-O R executable")
    library = root / "lib/libR.dylib"
    library.parent.mkdir(parents=True, exist_ok=True)
    library.write_bytes(b"Mach-O libR")
    for relative in ("library/tcltk/libs/tcltk.so", "modules/R_X11.so", "modules/R_de.so", "library/grDevices/libs/cairo.so"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode())
    return root


def configure_machos(monkeypatch, profile, root: Path, *, fifth: bool = False, non_tcl_opt_r: bool = False):
    records = {
        "bin/exec/R": [],
        "lib/libR.dylib": [],
        "library/tcltk/libs/tcltk.so": ["/opt/R/x86_64/lib/libtcl8.6.dylib", "/opt/R/x86_64/lib/libtk8.6.dylib", "/opt/X11/lib/libX11.6.dylib", "/opt/X11/lib/libXss.1.dylib", "/opt/X11/lib/libXext.6.dylib"],
        "modules/R_X11.so": [f"/opt/X11/lib/lib{name}.6.dylib" for name in ("SM", "ICE", "X11", "Xext", "Xrender", "Xt", "Xmu")],
        "modules/R_de.so": [f"/opt/X11/lib/lib{name}.6.dylib" for name in ("SM", "ICE", "X11", "Xext", "Xrender", "Xt", "Xmu")],
        "library/grDevices/libs/cairo.so": [f"/opt/X11/lib/lib{name}.6.dylib" for name in ("Xrender", "SM", "ICE", "X11", "Xext")],
    }
    if fifth:
        extra = root / "library/extra/libs/extra.so"
        extra.parent.mkdir(parents=True)
        extra.write_bytes(b"extra")
        records["library/extra/libs/extra.so"] = ["/opt/X11/lib/libX11.6.dylib"]
    if non_tcl_opt_r:
        extra = root / "library/extra/libs/extra.so"
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_bytes(b"extra")
        records["library/extra/libs/extra.so"] = ["/opt/R/x86_64/lib/libgfortran.5.dylib"]
    monkeypatch.setattr(profile, "is_macho", lambda path: path.relative_to(root).as_posix() in records)
    monkeypatch.setattr(profile, "macho_record", lambda path, _: {
        "relative_path": path.relative_to(root).as_posix(), "sha256": "a" * 64,
        "architectures": ["x86_64"], "install_id": None,
        "load_commands": records[path.relative_to(root).as_posix()],
    })
    monkeypatch.setattr(profile, "hard_dependency_closure", lambda *_: ["RCMetaR"])
    monkeypatch.setattr(profile, "manifest_roots", lambda _: (["RCMetaR"], set(), "b" * 64))


def configure_official_launcher(
    monkeypatch, profile, root: Path, *, macho: bool = True, architecture: str = "x86_64"
):
    (root / "R").symlink_to("bin/R")
    launcher = root / "bin/R"
    original_is_macho = profile.is_macho
    original_macho_record = profile.macho_record
    monkeypatch.setattr(
        profile,
        "is_macho",
        lambda path: macho if path == launcher else original_is_macho(path),
    )
    monkeypatch.setattr(
        profile,
        "macho_record",
        lambda path, parent: (
            {
                "relative_path": "bin/R",
                "sha256": "c" * 64,
                "architectures": [architecture],
                "install_id": None,
                "load_commands": [],
            }
            if path == launcher
            else original_macho_record(path, parent)
        ),
    )


def test_profile_removes_exact_surfaces_and_records_evidence(monkeypatch, tmp_path):
    profile = load_profile()
    root = fixture_runtime(tmp_path)
    evidence = tmp_path / "profile.json"
    configure_machos(monkeypatch, profile, root)
    profile.profile(root, evidence, tmp_path / "manifest.json", "4.6.1", "x86_64")
    data = json.loads(evidence.read_text())
    assert data["post_profile_exclusions"] == ["library/grDevices/libs/cairo.so", "library/tcltk", "modules/R_X11.so", "modules/R_de.so"]
    assert not (root / "library/tcltk").exists()
    assert len(data["excluded_surfaces"]) == 4


def test_profile_rejects_unexpected_x11_owner(monkeypatch, tmp_path):
    profile = load_profile()
    root = fixture_runtime(tmp_path)
    configure_machos(monkeypatch, profile, root, fifth=True)
    with pytest.raises(profile.ProfileError, match="unexpected optional-R"):
        profile.profile(root, tmp_path / "profile.json", tmp_path / "manifest.json", "4.6.1", "x86_64")


def test_profile_allows_non_tcl_opt_r_for_relocation(monkeypatch, tmp_path):
    profile = load_profile()
    root = fixture_runtime(tmp_path)
    evidence = tmp_path / "profile.json"
    configure_machos(monkeypatch, profile, root, non_tcl_opt_r=True)
    profile.profile(root, evidence, tmp_path / "manifest.json", "4.6.1", "x86_64")
    assert "library/extra/libs/extra.so" in json.loads(evidence.read_text())["allowed_non_tcl_opt_r_dependencies"]


def test_profile_rejects_missing_hard_dependency(tmp_path):
    profile = load_profile()
    library = tmp_path / "library"
    library.mkdir()
    with pytest.raises(profile.ProfileError, match="required package roots are absent"):
        profile.hard_dependency_closure(library, ["not-installed"], set())


@pytest.mark.parametrize("missing_library", ["libXss", "libXext"])
def test_profile_rejects_changed_exclusion_dependency_family(monkeypatch, tmp_path, missing_library):
    profile = load_profile()
    root = fixture_runtime(tmp_path)
    configure_machos(monkeypatch, profile, root)
    original = profile.macho_record
    monkeypatch.setattr(profile, "macho_record", lambda path, parent: {
        **original(path, parent),
        "load_commands": (
            [command for command in original(path, parent)["load_commands"] if missing_library not in command]
            if path.name == "tcltk.so" else original(path, parent)["load_commands"]
        ),
    })
    with pytest.raises(profile.ProfileError, match="changed dependency families"):
        profile.profile(root, tmp_path / "profile.json", tmp_path / "manifest.json", "4.6.1", "x86_64")


def test_tree_identity_authenticates_content_and_symlink_targets(tmp_path):
    profile = load_profile()
    root = tmp_path / "tree"
    root.mkdir()
    content = root / "payload"
    content.write_bytes(b"same-size")
    link = root / "link"
    link.symlink_to("payload")
    initial = profile.sha256_tree_identity(root)
    content.write_bytes(b"same-SIZE")
    assert profile.sha256_tree_identity(root) != initial
    content.write_bytes(b"same-size")
    link.unlink()
    link.symlink_to("other-target")
    assert profile.sha256_tree_identity(root) != initial


def test_profile_rejects_non_thin_excluded_macho(monkeypatch, tmp_path):
    profile = load_profile()
    root = fixture_runtime(tmp_path)
    configure_machos(monkeypatch, profile, root)
    original = profile.macho_record
    monkeypatch.setattr(profile, "macho_record", lambda path, parent: {
        **original(path, parent),
        "architectures": (["x86_64", "arm64"] if path.name == "R_de.so" else original(path, parent)["architectures"]),
    })
    with pytest.raises(profile.ProfileError, match="not x86_64-only"):
        profile.profile(root, tmp_path / "profile.json", tmp_path / "manifest.json", "4.6.1", "x86_64")


def test_profile_classifies_launcher_separately_from_canonical_lib_r(monkeypatch, tmp_path):
    profile = load_profile()
    root = fixture_runtime(tmp_path)
    configure_machos(monkeypatch, profile, root)
    evidence = tmp_path / "profile.json"
    profile.profile(root, evidence, tmp_path / "manifest.json", "4.6.1", "x86_64")
    source = json.loads(evidence.read_text())["source_framework"]
    assert source["canonical_macho"]["relative_path"] == "lib/libR.dylib"
    assert source["canonical_macho"]["architectures"] == ["x86_64"]
    assert source["executable_macho"]["relative_path"] == "bin/exec/R"
    assert source["executable_macho"]["architectures"] == ["x86_64"]
    assert source["launcher"]["relative_path"] == "bin/R"
    assert source["launcher"]["kind"] == "script"

    official_root = fixture_runtime(tmp_path / "official")
    configure_machos(monkeypatch, profile, official_root)
    configure_official_launcher(monkeypatch, profile, official_root)
    official_evidence = tmp_path / "official-profile.json"
    profile.profile(
        official_root,
        official_evidence,
        tmp_path / "manifest.json",
        "4.6.1",
        "x86_64",
        official_framework_layout=True,
    )
    official_launcher = json.loads(official_evidence.read_text())["source_framework"][
        "launcher"
    ]
    assert official_launcher["kind"] == "mach-o"
    assert official_launcher["architectures"] == ["x86_64"]
    assert official_launcher["resources_alias"] == {
        "relative_path": "R",
        "link_target": "bin/R",
        "resolved_path": "bin/R",
    }


def test_profile_rejects_official_layout_without_canonical_lib_r(monkeypatch, tmp_path):
    profile = load_profile()
    root = fixture_runtime(tmp_path)
    (root / "lib/libR.dylib").unlink()
    configure_machos(monkeypatch, profile, root)
    with pytest.raises(profile.ProfileError, match="canonical source lib/libR.dylib"):
        profile.profile(root, tmp_path / "profile.json", tmp_path / "manifest.json", "4.6.1", "x86_64")


def test_profile_rejects_reversed_launcher_and_executable_classification(monkeypatch, tmp_path):
    profile = load_profile()
    root = fixture_runtime(tmp_path)
    configure_machos(monkeypatch, profile, root)
    original = profile.is_macho
    monkeypatch.setattr(profile, "is_macho", lambda path: True if path == root / "bin/R" else original(path))
    with pytest.raises(profile.ProfileError, match="bin/R must be the expected non-Mach-O launcher"):
        profile.profile(root, tmp_path / "profile.json", tmp_path / "manifest.json", "4.6.1", "x86_64")

    official_root = fixture_runtime(tmp_path / "official-non-macho")
    configure_machos(monkeypatch, profile, official_root)
    configure_official_launcher(monkeypatch, profile, official_root, macho=False)
    with pytest.raises(
        profile.ProfileError, match="official source bin/R launcher.*not Mach-O"
    ):
        profile.profile(
            official_root,
            tmp_path / "official-profile.json",
            tmp_path / "manifest.json",
            "4.6.1",
            "x86_64",
            official_framework_layout=True,
        )

    wrong_alias_root = fixture_runtime(tmp_path / "official-wrong-alias")
    configure_machos(monkeypatch, profile, wrong_alias_root)
    configure_official_launcher(monkeypatch, profile, wrong_alias_root)
    (wrong_alias_root / "R").unlink()
    (wrong_alias_root / "R").symlink_to("bin/exec/R")
    with pytest.raises(
        profile.ProfileError, match="Resources/R must be the canonical bin/R symlink"
    ):
        profile.profile(
            wrong_alias_root,
            tmp_path / "wrong-alias-profile.json",
            tmp_path / "manifest.json",
            "4.6.1",
            "x86_64",
            official_framework_layout=True,
        )


def test_profile_rejects_wrong_architecture_r_executable(monkeypatch, tmp_path):
    profile = load_profile()
    root = fixture_runtime(tmp_path)
    configure_machos(monkeypatch, profile, root)
    original = profile.macho_record
    monkeypatch.setattr(profile, "macho_record", lambda path, parent: {
        **original(path, parent),
        "architectures": (["arm64"] if path == root / "bin/exec/R" else original(path, parent)["architectures"]),
    })
    with pytest.raises(profile.ProfileError, match="bin/exec/R executable must be x86_64-only"):
        profile.profile(root, tmp_path / "profile.json", tmp_path / "manifest.json", "4.6.1", "x86_64")

    official_root = fixture_runtime(tmp_path / "official-wrong-arch")
    configure_machos(monkeypatch, profile, official_root)
    configure_official_launcher(
        monkeypatch, profile, official_root, architecture="arm64"
    )
    with pytest.raises(
        profile.ProfileError, match="official source bin/R launcher must be x86_64-only"
    ):
        profile.profile(
            official_root,
            tmp_path / "official-profile.json",
            tmp_path / "manifest.json",
            "4.6.1",
            "x86_64",
            official_framework_layout=True,
        )
