"""Executable contracts for immutable target-native R integration kits."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types
from typing import Any

import pytest


def module():
    path = Path("scripts/r_integration_kit.py")
    spec = importlib.util.spec_from_file_location("r_integration_kit", path)
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def build_args(tmp_path: Path, kit=None) -> argparse.Namespace:
    runtime = tmp_path / "R"
    library = runtime / "library"
    runtime.mkdir()
    (runtime / "COPYING").write_text("R test license\n", encoding="utf-8")
    versions = {"RCMetaR": "0.2.0", "HSROC": "2.1.9", "metafor": "4.8-0"}
    for name, version in versions.items():
        package = library / name
        package.mkdir(parents=True)
        (package / "DESCRIPTION").write_text(
            f"Package: {name}\nVersion: {version}\nLicense: GPL-2\n", encoding="utf-8"
        )
    (library / "RCMetaR" / "LICENSE").write_text("test license\n", encoding="utf-8")
    bridge = tmp_path / "_rinterface_cffi_api.pyd"
    bridge.write_bytes(b"api-bridge")
    source_payload = tmp_path / "source-payload"
    source_payload.mkdir()
    payloads = {}
    for name in ("HSROC", "RCMetaR", "rpy2", "rpy2-rinterface", "rpy2-robjects"):
        archive = source_payload / f"{name}.tar.gz"
        archive.write_bytes(f"source:{name}".encode())
        payloads[name] = hashlib.sha256(archive.read_bytes()).hexdigest()
    if kit is not None:
        kit.HSROC_SHA256 = payloads["HSROC"]
    provenance = tmp_path / "provenance.json"
    sha = "a" * 64
    provenance.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target": "windows-x64",
                "official_r": {
                    "url": "https://cloud.r-project.org/bin/windows/base/R-4.6.1-win.exe",
                    "sha256": "c5424c40cd70ef85765a55d2ff96bb602b5f30ed536938ff004f14db5db3c2df",
                    "signature_identity": (
                        "CN=Martyn Plummer, O=Martyn Plummer, S=West Midlands, C=GB"
                    ),
                    "signer_thumbprint": "f356fc6cd245d722f4a82697473da5995cb42975",
                    "signature_status": "Valid",
                    "timestamped": True,
                    "artifact_type": "installer",
                },
                "ppm_packages": [
                    {
                        "name": "metafor",
                        "version": "4.8-0",
                        "package_type": "win.binary",
                        "url": "https://packagemanager.posit.co/cran/2026-07-16/bin/windows/contrib/4.6/metafor.zip",
                        "sha256": sha,
                        "license_files": [],
                        "license": "GPL-2",
                    }
                ],
                "source_packages": [
                    {
                        "name": name,
                        "version": version,
                        "package_type": "source",
                        "url": url,
                        "sha256": payloads[name],
                        "toolchain": "R CMD INSTALL",
                        "build_log_sha256": sha,
                        "license": "GPL-2",
                    }
                    for name, version, url in (
                        (
                            "HSROC",
                            "2.1.9",
                            "https://cran.r-project.org/src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz",
                        ),
                        (
                            "RCMetaR",
                            "0.2.0",
                            f"https://github.com/AliSalman-et-al/rc-metastudio/archive/{'c' * 40}.tar.gz",
                        ),
                    )
                ],
                "rpy2": {
                    "version": "3.6.7",
                    "sdist_distribution": "rpy2-rinterface",
                    "sdist_version": "3.6.6",
                    "robjects_version": "3.6.5",
                    "sdist_url": "https://files.pythonhosted.org/rpy2-rinterface.tar.gz",
                    "sdist_sha256": payloads["rpy2-rinterface"],
                    "toolchain": "uv build",
                    "build_log_sha256": sha,
                    "bridge_sha256": hashlib.sha256(bridge.read_bytes()).hexdigest(),
                    "license": "GPL-2.0-or-later",
                    "source_archives": [
                        {
                            "distribution": name,
                            "version": version,
                            "url": f"https://files.pythonhosted.org/{name}.tar.gz",
                            "sha256": payloads[name],
                            "license_files": [
                                {"path": f"{name}/LICENSE", "sha256": sha}
                            ],
                        }
                        for name, version in (
                            ("rpy2", "3.6.7"),
                            ("rpy2-rinterface", "3.6.6"),
                            ("rpy2-robjects", "3.6.5"),
                        )
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    uv_cache = tmp_path / "uv-cache"
    uv_cache.mkdir()
    (uv_cache / "authenticated-wheel").write_bytes(b"wheel")
    uv_lock = tmp_path / "uv.lock"
    uv_lock.write_text("version = 1\n", encoding="utf-8")
    return argparse.Namespace(
        target="windows-x64",
        runtime=runtime,
        library=library,
        api_bridge=bridge,
        output=tmp_path / "kit",
        provenance_manifest=provenance,
        runtime_profile=None,
        package_lock_sha256="b" * 64,
        source_commit="c" * 40,
        uv_cache=uv_cache,
        uv_lock=uv_lock,
        uv_lock_sha256=hashlib.sha256(uv_lock.read_bytes()).hexdigest(),
        source_payload=source_payload,
    )


@pytest.mark.skipif(sys.platform != "win32", reason="requires the Windows Python DLL")
def test_build_verify_and_consume_content_addressed_api_kit(monkeypatch, tmp_path):
    kit = module()
    monkeypatch.setattr(kit.platform, "system", lambda: "Windows")
    monkeypatch.setattr(kit.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(kit, "native_dependency_inventory", lambda *_: [])
    monkeypatch.setattr(
        kit.subprocess,
        "run",
        lambda *_args, **_kwargs: types.SimpleNamespace(
            returncode=0, stdout="4.6.1", stderr=""
        ),
    )
    args = build_args(tmp_path, kit)
    manifest = kit.build(args)
    assert manifest["cffi_mode"] == "API"
    assert (args.output / "licenses/RCMetaR/LICENSE").read_text() == "test license\n"
    assert kit.verify(args.output)["kit_sha256"] == manifest["kit_sha256"]
    destination = tmp_path / "consumed"
    kit.consume(
        argparse.Namespace(
            kit=args.output, target="windows-x64", destination=destination
        )
    )
    assert (destination / manifest["api_bridge_path"]).is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="requires the Windows Python DLL")
def test_verification_rejects_tampering_and_abi_fallback(monkeypatch, tmp_path):
    kit = module()
    monkeypatch.setattr(kit.platform, "system", lambda: "Windows")
    monkeypatch.setattr(kit.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(kit, "native_dependency_inventory", lambda *_: [])
    monkeypatch.setattr(
        kit.subprocess,
        "run",
        lambda *_args, **_kwargs: types.SimpleNamespace(
            returncode=0, stdout="4.6.1", stderr=""
        ),
    )
    args = build_args(tmp_path, kit)
    kit.build(args)
    (args.output / "runtime/library/RCMetaR/DESCRIPTION").write_text(
        "tampered", encoding="utf-8"
    )
    with pytest.raises(kit.KitError, match="content differs"):
        kit.verify(args.output)


def test_builder_rejects_abi_bridge(monkeypatch, tmp_path):
    kit = module()
    monkeypatch.setattr(kit.platform, "system", lambda: "Windows")
    monkeypatch.setattr(kit.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(kit, "native_dependency_inventory", lambda *_: [])
    monkeypatch.setattr(
        kit.subprocess,
        "run",
        lambda *_args, **_kwargs: types.SimpleNamespace(
            returncode=0, stdout="4.6.1", stderr=""
        ),
    )
    args = build_args(tmp_path, kit)
    abi = tmp_path / "_rinterface_cffi_abi.py"
    abi.write_text("ffi = object()", encoding="utf-8")
    args.api_bridge = abi
    with pytest.raises(kit.KitError, match="API-only"):
        kit.build(args)


def test_arm64_kit_requires_macos_14(monkeypatch, tmp_path):
    kit = module()
    monkeypatch.setattr(kit.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(kit.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(kit, "native_dependency_inventory", lambda *_: [])
    monkeypatch.setattr(
        kit.subprocess,
        "run",
        lambda *_args, **_kwargs: types.SimpleNamespace(
            returncode=0, stdout="4.6.1", stderr=""
        ),
    )
    args = build_args(tmp_path, kit)
    args.target = "macos-arm64"
    args.api_bridge = tmp_path / "_rinterface_cffi_api.cpython-311-darwin.so"
    args.api_bridge.write_bytes(b"api")
    provenance = json.loads(args.provenance_manifest.read_text(encoding="utf-8"))
    provenance["target"] = "macos-arm64"
    provenance["official_r"].update(
        {
            "url": "https://cloud.r-project.org/bin/macosx/sonoma-arm64/base/R-4.6.1-arm64.pkg",
            "signature_identity": "Developer ID Installer: Simon Urbanek (VZLD955F6P)",
            "artifact_type": "pkg",
        }
    )
    provenance["ppm_packages"][0]["package_type"] = "mac.binary"
    provenance["ppm_packages"][0]["url"] = (
        "https://packagemanager.posit.co/cran/2026-07-16/bin/macosx/sonoma-arm64/contrib/4.6/metafor.tgz"
    )
    provenance["rpy2"]["bridge_sha256"] = hashlib.sha256(
        args.api_bridge.read_bytes()
    ).hexdigest()
    args.provenance_manifest.write_text(json.dumps(provenance), encoding="utf-8")
    args.runtime_profile = tmp_path / "runtime-profile.json"
    args.runtime_profile.write_text("{}", encoding="utf-8")
    assert kit.build(args)["minimum_os"] == "14.0"


def test_windows_closure_records_normal_delay_and_system_imports():
    kit = module()
    dependency: dict[str, Any] = {
        "path": "runtime/bin/x64/dependency.dll",
        "sha256": "d" * 64,
        "_imports": [],
    }
    owner: dict[str, Any] = {
        "path": "bridge/api.pyd",
        "sha256": "a" * 64,
        "_imports": [
            {"name": "dependency.dll", "kind": "normal"},
            {"name": "KERNEL32.dll", "kind": "delay"},
        ],
    }
    records = [owner, dependency]
    kit._resolve_windows_closure(records)
    assert owner["imports"] == [
        {
            "name": "dependency.dll",
            "kind": "normal",
            "resolution": "kit",
            "resolved_path": dependency["path"],
            "resolved_sha256": dependency["sha256"],
        },
        {"name": "KERNEL32.dll", "kind": "delay", "resolution": "system"},
    ]


def test_macos_deployment_versions_normalize_trailing_zero_components():
    kit = module()
    assert kit._macos_version("13.0") == kit._macos_version("13.0.0")
    assert kit._macos_version("13.0.1") > kit._macos_version("13.0")


def test_windows_msvc_runtime_is_not_classified_as_a_system_import():
    kit = module()
    runtime: dict[str, Any] = {
        "path": "native/vcruntime140.dll",
        "sha256": "d" * 64,
        "_imports": [],
    }
    owner: dict[str, Any] = {
        "path": "bridge/api.pyd",
        "sha256": "a" * 64,
        "_imports": [{"name": "VCRUNTIME140.dll", "kind": "delay"}],
    }
    kit._resolve_windows_closure([runtime, owner])
    assert owner["imports"][0]["resolution"] == "kit"
    assert owner["imports"][0]["resolved_path"] == "native/vcruntime140.dll"


@pytest.mark.parametrize("matches", [0, 2])
def test_windows_closure_rejects_missing_or_ambiguous_import(matches):
    kit = module()
    owner = {
        "path": "bridge/api.pyd",
        "sha256": "a" * 64,
        "_imports": [{"name": "private.dll", "kind": "delay"}],
    }
    records = [owner] + [
        {
            "path": f"runtime/{index}/private.dll",
            "sha256": str(index) * 64,
            "_imports": [],
        }
        for index in range(matches)
    ]
    with pytest.raises(kit.KitError, match="unresolved or ambiguous"):
        kit._resolve_windows_closure(records)


def test_macos_closure_resolves_loader_path_and_rejects_forbidden_prefix(tmp_path):
    kit = module()
    owner_path = tmp_path / "bridge/api.so"
    dependency_path = tmp_path / "runtime/lib/libR.dylib"
    owner_path.parent.mkdir(parents=True)
    dependency_path.parent.mkdir(parents=True)
    owner_path.write_bytes(b"owner")
    dependency_path.write_bytes(b"dependency")
    dependency: dict[str, Any] = {
        "path": "runtime/lib/libR.dylib",
        "sha256": "d" * 64,
        "install_id": "@rpath/libR.dylib",
        "rpaths": [],
        "_imports": [],
    }
    owner: dict[str, Any] = {
        "path": "bridge/api.so",
        "sha256": "a" * 64,
        "install_id": None,
        "rpaths": [],
        "_imports": ["@loader_path/../runtime/lib/libR.dylib"],
    }
    kit._resolve_macos_closure([owner, dependency], tmp_path)
    assert owner["imports"][0]["resolved_path"] == dependency["path"]
    owner["_imports"] = ["/opt/X11/lib/libX11.6.dylib"]
    owner.pop("imports")
    with pytest.raises(kit.KitError, match="forbidden external"):
        kit._resolve_macos_closure([owner, dependency], tmp_path)


def test_provenance_rejects_pseudo_urls(tmp_path):
    kit = module()
    args = build_args(tmp_path, kit)
    provenance = json.loads(args.provenance_manifest.read_text(encoding="utf-8"))
    provenance["official_r"]["url"] = "installed-cran-r://R-4.6.1"
    args.provenance_manifest.write_text(json.dumps(provenance), encoding="utf-8")
    with pytest.raises(kit.KitError, match="provenance"):
        kit.load_provenance(args.provenance_manifest, "windows-x64", args.api_bridge)


def test_provenance_rejects_missing_package_declared_license_file(tmp_path):
    kit = module()
    args = build_args(tmp_path, kit)
    provenance = json.loads(args.provenance_manifest.read_text(encoding="utf-8"))
    provenance["ppm_packages"][0]["license"] = "GPL-2 + file LICENSE"
    provenance["ppm_packages"][0]["license_files"] = []
    args.provenance_manifest.write_text(json.dumps(provenance), encoding="utf-8")
    with pytest.raises(kit.KitError, match="provenance"):
        kit.load_provenance(args.provenance_manifest, "windows-x64", args.api_bridge)


@pytest.mark.parametrize("distribution", ["rpy2", "rpy2-rinterface", "rpy2-robjects"])
def test_provenance_requires_each_rpy2_split_license_payload(tmp_path, distribution):
    kit = module()
    args = build_args(tmp_path, kit)
    provenance = json.loads(args.provenance_manifest.read_text(encoding="utf-8"))
    record = next(
        item
        for item in provenance["rpy2"]["source_archives"]
        if item["distribution"] == distribution
    )
    record["license_files"] = []
    args.provenance_manifest.write_text(json.dumps(provenance), encoding="utf-8")
    with pytest.raises(kit.KitError, match="license provenance"):
        kit.load_provenance(args.provenance_manifest, "windows-x64", args.api_bridge)


@pytest.mark.parametrize(
    "archive_name", ["HSROC", "RCMetaR", "rpy2", "rpy2-rinterface", "rpy2-robjects"]
)
def test_source_payload_requires_each_exact_retained_archive(tmp_path, archive_name):
    kit = module()
    args = build_args(tmp_path, kit)
    provenance = json.loads(args.provenance_manifest.read_text(encoding="utf-8"))
    (args.source_payload / f"{archive_name}.tar.gz").unlink()
    with pytest.raises(kit.KitError, match="exactly the five retained archives"):
        kit.copy_source_payload(
            args.source_payload, provenance, tmp_path / "retained-sources"
        )


def test_signed_derivation_requires_bound_non_unsigned_signer_evidence(tmp_path):
    app = tmp_path / "app"
    bridge = app / "_internal/api.pyd"
    shared_r = app / "R/bin/x64/R.dll"
    bridge.parent.mkdir(parents=True)
    shared_r.parent.mkdir(parents=True)
    bridge.write_bytes(b"signed-api")
    shared_r.write_bytes(b"signed-r")
    derivation = app / "r-integration-kit/derivation.json"
    derivation.parent.mkdir()
    derivation.write_text("{}", encoding="utf-8")
    evidence = tmp_path / "signing.json"

    def member(path):
        return {
            "path": path.relative_to(app).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "status": "Valid",
            "signer_subject": "CN=RC MetaStudio Release",
            "signer_thumbprint": "a" * 40,
            "timestamp_subject": "CN=RFC3161 Timestamp",
            "timestamp_thumbprint": "b" * 40,
        }

    payload = {
        "schema_version": 1,
        "members": {
            "api_bridge": member(bridge),
            "r_shared_library": member(shared_r),
        },
    }
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    command = [
        sys.executable,
        "scripts/r_kit_derivation.py",
        "finalize",
        "--app-root",
        str(app),
        "--api-bridge",
        str(bridge),
        "--r-shared-library",
        str(shared_r),
        "--derivation",
        str(derivation),
        "--signing-evidence",
        str(evidence),
        "--require-signed",
    ]
    subprocess.run(command, check=True)
    final = json.loads(derivation.read_text(encoding="utf-8"))["final"]
    assert {record["signing_identity"] for record in final.values()} == {
        "CN=RC MetaStudio Release"
    }

    payload["members"]["api_bridge"]["signer_subject"] = "unsigned"
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    rejected = subprocess.run(command, capture_output=True, text=True, check=False)
    assert rejected.returncode == 1
    assert "signed-file evidence is invalid" in rejected.stderr


def test_provenance_rejects_wrong_locked_artifact_identities(tmp_path):
    kit = module()
    args = build_args(tmp_path, kit)
    original = json.loads(args.provenance_manifest.read_text(encoding="utf-8"))
    mutations = (
        lambda value: value["official_r"].update(
            {"url": "https://cloud.r-project.org/bin/windows/base/R-4.6.0-win.exe"}
        ),
        lambda value: value["ppm_packages"][0].update(
            {"url": "https://cran.r-project.org/bin/windows/contrib/4.6/metafor.zip"}
        ),
        lambda value: value["source_packages"][0].update({"sha256": "0" * 64}),
        lambda value: value["official_r"].update({"sha256": "0" * 64}),
        lambda value: value["official_r"].update(
            {"signature_identity": "CN=R Core Team"}
        ),
        lambda value: value["official_r"].update({"signer_thumbprint": "0" * 40}),
        lambda value: value["official_r"].update({"signature_status": "UnknownError"}),
        lambda value: value["official_r"].update({"timestamped": False}),
    )
    for mutate in mutations:
        candidate = json.loads(json.dumps(original))
        mutate(candidate)
        args.provenance_manifest.write_text(json.dumps(candidate), encoding="utf-8")
        with pytest.raises(kit.KitError, match="provenance|HSROC"):
            kit.load_provenance(
                args.provenance_manifest, "windows-x64", args.api_bridge
            )


def test_installed_package_inventory_rejects_unclaimed_non_base_package():
    kit = module()
    provenance = {
        "ppm_packages": [{"name": "metafor", "version": "4.8-0"}],
        "source_packages": [
            {"name": "HSROC", "version": "2.1.9"},
            {"name": "RCMetaR", "version": "0.2.0"},
        ],
    }
    installed = [
        {"name": name, "version": version, "priority": None}
        for name, version in (
            ("metafor", "4.8-0"),
            ("HSROC", "2.1.9"),
            ("RCMetaR", "0.2.0"),
            ("ambientPackage", "1.0"),
        )
    ]
    with pytest.raises(kit.KitError, match="lacks exact provenance"):
        kit.validate_installed_provenance(installed, provenance)
