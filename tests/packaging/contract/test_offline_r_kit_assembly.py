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
    assert "scripts/package-macos.sh --architecture x64" in workflow
    assert "uv sync --locked" not in workflow
    assert workflow.index("Install official Qt SDK on macOS") < workflow.index(
        "Build, inspect, smoke, archive, and requalify macOS Intel package"
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


def test_producer_populates_a_clean_dedicated_uv_cache_from_the_exact_lock():
    workflow = Path(".github/workflows/r-integration-kit-producer.yml").read_text(
        encoding="utf-8"
    )
    top_level_env = workflow.split("jobs:", 1)[0]
    assert "UV_CACHE_DIR: ${{ github.workspace }}/build/r-kit-uv-cache" in top_level_env
    assert "${{ runner." not in top_level_env
    assert "with: {enable-cache: false}" in workflow
    clean = workflow.index("Initialize dedicated immutable-kit uv cache")
    locked_sync = workflow.index("uv sync --locked")
    windows_build = workflow.index("Produce Windows x64 kit")
    macos_build = workflow.index("Produce macOS kit")
    assert clean < locked_sync < windows_build < macos_build
    assert "uv cache clean" in workflow[clean:locked_sync]
    assert "uv cache dir" in workflow[clean:locked_sync]
    assert "--uv-cache $uvCache" in Path(
        "scripts/produce-r-integration-kit.ps1"
    ).read_text(encoding="utf-8")
    assert '--uv-cache "$uv_cache"' in Path(
        "scripts/produce-r-integration-kit-macos.sh"
    ).read_text(encoding="utf-8")
    for value in (
        "C5424C40CD70EF85765A55D2FF96BB602B5F30ED536938FF004F14DB5DB3C2DF",
        "CN=Martyn Plummer, O=Martyn Plummer, S=West Midlands, C=GB",
        "F356FC6CD245D722F4A82697473DA5995CB42975",
        "$signature.Status -ne 'Valid'",
        "-not $signature.TimeStamperCertificate",
        "status=$($signature.Status)",
        "subject=$($signature.SignerCertificate.Subject)",
        "sha256=$hash",
    ):
        assert value in workflow
    windows_producer = Path("scripts/produce-r-integration-kit.ps1").read_text(
        encoding="utf-8"
    )
    for parameter in (
        "$OfficialRSignerThumbprint",
        "$OfficialRSignatureStatus",
        "$OfficialRTimestamped",
        "--official-r-signer-thumbprint",
        "--official-r-signature-status",
        "--official-r-timestamped",
    ):
        assert parameter in windows_producer
    macos_producer = Path("scripts/produce-r-integration-kit-macos.sh").read_text(
        encoding="utf-8"
    )
    rcmetar_installer = Path("scripts/install-rcmetar-source.R").read_text(
        encoding="utf-8"
    )
    for producer in (windows_producer, macos_producer):
        assert "scripts/install-rcmetar-source.R" in producer.replace("\\", "/")
        assert " -e " not in producer
        assert " --args " not in producer
    assert "commandArgs(trailingOnly = TRUE)" in rcmetar_installer
    assert "length(args) != 2L" in rcmetar_installer
    assert 'file.path(library, "RCMetaR", "DESCRIPTION")' in rcmetar_installer
    for contract in (
        'ErrorActionPreference = "Continue"',
        "$exitCode = $LASTEXITCODE",
        "$ErrorActionPreference = $previousPreference",
        "$null -eq $exitCode -or $exitCode -ne 0",
    ):
        assert contract in windows_producer
    assert windows_producer.count("Invoke-NativeLogged -FilePath") == 3
