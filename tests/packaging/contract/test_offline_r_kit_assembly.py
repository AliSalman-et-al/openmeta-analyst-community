"""Contracts for the trusted-kit/offline-assembler delivery boundary."""

from pathlib import Path


def test_release_assemblers_accept_only_prebuilt_authenticated_kits():
    windows = Path("scripts/assemble-windows-package.ps1").read_text(encoding="utf-8")
    macos = Path("scripts/assemble-macos-package.sh").read_text(encoding="utf-8")
    forbidden = (
        "install.packages",
        "R CMD INSTALL",
        "uv pip install",
        "pip install",
        "rpy2-rinterface==",
        "HSROC_",
        "RCMetaR/DESCRIPTION",
        "RCMS_CRAN_REPO",
        "uv sync",
        "uv python",
        "Invoke-WebRequest",
        "curl ",
        "aqt install",
    )
    assert not any(token in windows for token in forbidden)
    assert not any(token in macos for token in forbidden)
    for text in (windows, macos):
        assert "RIntegrationKit" in text or "r-integration-kit" in text
        assert (
            "ExpectedRIntegrationKitSha256" in text
            or "expected-r-integration-kit-sha256" in text
        )


def test_macos_ci_runs_one_direct_target_native_build():
    workflow = Path(".github/workflows/package-target.yml").read_text(encoding="utf-8")
    assert "produce-r-integration-kit" not in workflow
    assert "download-artifact" not in workflow
    assert "macos-15-intel" in workflow
    assert 'scripts/package-macos.sh --architecture "${{ matrix.architecture }}"' in workflow
    assert "target: macos-x64" in workflow
    assert "target: macos-arm64" in workflow
    assert "uv sync --locked" not in workflow
    assert workflow.index("Install official Qt SDK") < workflow.index(
        "Build and run the first-green packaged workflow"
    )


def test_windows_public_command_stages_authenticated_r_without_a_promoted_kit():
    wrapper = Path("scripts/package-windows.ps1").read_text(encoding="utf-8")
    assert "Stage-AuthenticatedOfficialR" in wrapper
    assert "Get-AuthenticodeSignature" in wrapper
    assert "artifacts\\download-cache\\windows-x64" in wrapper
    assert "RIntegrationKit" not in wrapper
    assert "ExpectedRIntegrationKitSha256" not in wrapper


def test_macos_public_command_is_self_contained_direct_native_build():
    wrapper = Path("scripts/package-macos.sh").read_text(encoding="utf-8")
    assert "r-integration-kit" not in wrapper
    assert "uv sync --locked" in wrapper
    assert "Xcode Command Line Tools" in wrapper


def test_obsolete_integration_kit_workflow_is_removed():
    assert not Path(".github/workflows/r-integration-kit-producer.yml").exists()
    workflow = Path(".github/workflows/package-target.yml").read_text(encoding="utf-8")
    assert "r-integration-kit" not in workflow
    assert "scripts/package-macos.sh" in workflow
