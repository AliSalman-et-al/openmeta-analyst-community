import hashlib
import json
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from ._workflow import load_module_from_path, load_workflow


ROOT = Path(__file__).resolve().parents[3]


def _load_source_provenance():
    spec = importlib.util.spec_from_file_location(
        "source_provenance", ROOT / "scripts" / "source_provenance.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_package_input_policy():
    path = ROOT / "scripts" / "package_input_policy.py"
    spec = importlib.util.spec_from_file_location("package_input_policy", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_metadata_version_only_needs_no_ambient_rscript(tmp_path):
    output = tmp_path / "github-output.txt"
    env = {**os.environ, "GITHUB_OUTPUT": str(output), "PATH": ""}
    script = ROOT / "scripts" / "resolve_package_ci_metadata.py"
    version_only = subprocess.run(
        [sys.executable, str(script), "--version-only"],
        env=env,
        text=True,
        capture_output=True,
    )
    assert version_only.returncode == 0, version_only.stderr
    project_version = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    assert output.read_text(encoding="utf-8") == f"version={project_version}\n"
    default = subprocess.run(
        [sys.executable, str(script)], env=env, text=True, capture_output=True
    )
    assert default.returncode != 0
    assert "Rscript is not available on PATH." in default.stderr


def read_repo_text(*parts):
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def ps_contract(*parts):
    text = read_repo_text(*parts)
    return {
        "text": text,
        "params": set(re.findall(r"\[(?:string|switch)\]\$([A-Za-z0-9_]+)", text)),
        "functions": set(re.findall(r"(?m)^function\s+([A-Za-z0-9_-]+)", text)),
        "commands": set(
            re.findall(
                r"(?m)^\s*(?:\$[A-Za-z0-9_]+\s+=\s+)?(uv|robocopy|Start-Process|Move-Item|Copy-Item)\b",
                text,
            )
        ),
        "env_writes": set(re.findall(r"\$env:([A-Za-z0-9_]+)\s*=", text)),
        "paths": set(
            re.findall(
                r'"([^"]+(?:\.(?:rcms|html|exe|dll|bat|ps1|py|json|R|sh)|DESCRIPTION))"',
                text,
            )
        ),
        "hidden_imports": set(re.findall(r'"--hidden-import",\s+"([^"]+)"', text)),
    }


def sh_contract(*parts):
    text = read_repo_text(*parts)
    return {
        "text": text,
        "case_options": set(re.findall(r"(?m)^\s+(--[a-z0-9-]+)\)", text)),
        "functions": set(re.findall(r"(?m)^([a-zA-Z0-9_]+)\(\)\s+\{", text)),
        "env_names": set(re.findall(r"\b([A-Z][A-Z0-9_]+)=", text)),
        "pyinstaller_options": set(
            re.findall(r"^\s+(--[a-z0-9-]+)(?:\s|$)", text, re.MULTILINE)
        ),
        "paths": set(re.findall(r'"([^"]+\.(?:oma|html|app|command|sh|R|zip))"', text)),
        "app_paths": set(re.findall(r'"\$app_root/([^"]+)"', text)),
    }


def relative_order(text, *needles):
    positions = [text.index(needle) for needle in needles]
    return positions == sorted(positions)


def test_windows_distributable_contract_is_declared():
    script = ps_contract("scripts", "build-windows-package.ps1")
    spec = read_repo_text("packaging", "pyinstaller", "rc-metastudio.spec")

    assert {
        "PythonExe",
        "RRuntimeRoot",
    } <= script["params"]
    assert {"SkipDependencyInstall", "SkipClean", "SkipSmoke"} <= script["params"]
    assert {
        "Resolve-CommandOrRepoPath",
        "Copy-DirectoryTree",
        "Assert-AppLayout",
        "Invoke-PackagedAppSmokeTest",
        "Invoke-PackagedWizardLayoutSmokeTest",
        "Get-ProjectVersion",
        "Test-BundledRPackages",
        "Assert-RCMetaRSummaryFormatting",
        "Install-LocalRPackagesFromSource",
        "Install-BundledRPackages",
    } <= script["functions"]
    assert {"robocopy", "Start-Process", "Move-Item"} <= script["commands"]
    assert {
        "RCMS_REQUIRE_IN_PROCESS_RPY2",
        "RCMS_STARTUP_PROJECT_SMOKE",
        "RPY2_CFFI_MODE",
    } <= script["env_writes"]
    assert all(name in spec for name in ("rpy2.robjects", "rpy2.rinterface"))
    assert '"icons_rc"' not in spec
    assert {
        "RCMetaStudio.exe",
        "sample_projects\\BCG.rcms",
        "sample_projects\\amino.rcms",
        "R\\bin\\x64\\R.dll",
        "R\\library\\RCMetaR\\DESCRIPTION",
        "LaunchRCMetaStudio.bat",
        "scripts\\install-r-deps.R",
    } <= script["paths"]
    assert "doc\\openMA_help.html" not in script["paths"]
    assert "Bundled help" not in script["text"]
    assert "packaging\\pyinstaller\\rc-metastudio.spec" in script["text"]
    assert "__main__.py" in spec
    assert (
        'icon=[str(app_source / "images" / "rc-metastudio-app-icon-rounded.ico")]'
        in spec
    )
    assert (
        ROOT / "src" / "rc_metastudio" / "images" / "rc-metastudio-app-icon-rounded.ico"
    ).is_file()
    assert (ROOT / "packaging" / "pyinstaller" / "rc-metastudio.spec").exists()
    assert "sole authoritative" in script["text"]
    assert "src\\rc_metastudio\\launch.py" not in script["text"]
    assert "tomllib.loads" in script["text"]
    assert (
        '$artifactName = "RCMetaStudio-$projectVersion-windows-x64"' in script["text"]
    )
    assert "$archiveRootName = $artifactName" in script["text"]
    assert '$archiveStagingRoot = Join-Path $workRoot "zip-staging"' in script["text"]
    assert (
        "Copy-DirectoryTree -Source $SourceDirectory -Destination $ArchiveRootDirectory"
        in script["text"]
    )
    assert "CreateFromDirectory($ArchiveStagingRoot, $tmpZipPath" in script["text"]
    assert (
        "Assert-ZipLayout -Path $zipPath -ArchiveRootName $archiveRootName"
        in script["text"]
    )
    assert 'if (-not $entryName.StartsWith("$ArchiveRootName\\"))' in script["text"]
    assert "$ArchiveRootName\\_internal\\PyQt6\\" in script["text"]


def test_windows_build_never_reuses_an_installed_r_library_tree():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert "r-library-cache" not in script
    assert "Copy-RLibraryPackages" not in script
    assert (
        "Installing locked bundled R package dependencies from immutable downloads"
        in script
    )


def test_windows_archive_is_version_derived_and_requalified_after_extraction():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]
    workflow = load_workflow(".github", "workflows", "package-windows.yml")

    assert '$artifactName = "RCMetaStudio-$projectVersion-windows-x64"' in script
    assert "$archiveRootName = $artifactName" in script
    assert "Expand-AndQualifyExactArchive" in script
    assert "ExtractToDirectory($Archive, $qualificationRoot)" in script
    assert (
        "Running exact-archive packaged smoke through the normal user entry point"
        in script
    )
    assert "Invoke-PackagedAppSmokeTest -Root $extractedApp" in script
    upload = next(
        step
        for step in workflow["jobs"]["package"]["steps"]
        if step.get("name") == "Upload package and qualification evidence"
    )
    assert "steps.package-metadata.outputs.version" in upload["with"]["name"]


def test_packaged_smoke_launches_with_positional_project_argument():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert relative_order(
        script,
        '$env:RCMS_STARTUP_PROJECT_SMOKE = "1"',
        "Invoke-BoundedPackageProcess -FilePath $exePath -ArgumentList @($quotedSamplePath)",
    )


def test_packaged_smoke_launches_visual_wizard_layout_gate():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert relative_order(
        script,
        "function Invoke-PackagedAppSmokeTest",
        "function Invoke-PackagedWizardLayoutSmokeTest",
        "Invoke-PackagedAppSmokeTest -Root $appDir",
        "Invoke-PackagedWizardLayoutSmokeTest -Root $appDir",
    )
    assert (
        'Invoke-BoundedPackageProcess -FilePath $exePath -ArgumentList @("--automation-wizard-layout-smoke")'
        in script
    )
    assert '$env:QT_QPA_PLATFORM = "offscreen"' in script
    assert '$startArguments.WindowStyle = "Hidden"' in script
    assert "RCMS_AUTOMATION_SMOKE_LOG = $env:RCMS_AUTOMATION_SMOKE_LOG" in script
    assert "$env:RCMS_AUTOMATION_SMOKE_LOG = $smokeLogPath" in script
    assert "automation-wizard-layout-smoke.log" in script
    assert "QT_QPA_PLATFORM = $env:QT_QPA_PLATFORM" in script


def test_fast_workflow_keeps_required_platforms_and_pins_external_actions():
    workflow = load_workflow(".github", "workflows", "fast-verification.yml")
    jobs = workflow["jobs"]

    assert {
        "change-classifier",
        "qt6-verification",
        "remaining-surface-verification",
        "source-fast-targets",
        "full-r-stack",
        "windows-package-qualification",
        "packaging-contract",
        "packaging-contract-macos",
        "fast-verification-gate",
    } <= set(jobs)
    assert set(jobs["fast-verification-gate"]["needs"]) == {
        "change-classifier",
        "qt6-verification",
        "remaining-surface-verification",
        "source-fast-targets",
        "full-r-stack",
        "windows-package-qualification",
        "packaging-contract",
        "packaging-contract-macos",
    }
    assert set(workflow["on"]) == {"workflow_dispatch", "push", "pull_request"}
    assert workflow["on"]["push"]["branches"] == ["master"]
    assert jobs["source-fast-targets"]["strategy"]["matrix"]["include"] == [
        {"target": "windows-x64", "runner": "windows-latest", "platform": "windows"},
        {"target": "macos-arm64", "runner": "macos-15", "platform": "macos"},
    ]
    refs = []

    def collect(value):
        if isinstance(value, dict):
            if "uses" in value:
                refs.append(value["uses"])
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(workflow)
    assert all(
        ref.startswith("./") or re.fullmatch(r"[0-9a-f]{40}", ref.rsplit("@", 1)[-1])
        for ref in refs
    )


def test_package_policy_covers_direct_release_call_graph():
    policy = _load_package_input_policy()
    entrypoints = (
        ".github/workflows/candidate.yml",
        ".github/workflows/community-release-candidate.yml",
        ".github/workflows/macos-trusted-release-candidate.yml",
        ".github/workflows/notarization-status.yml",
        ".github/workflows/package-target.yml",
        ".github/workflows/package-verification.yml",
        ".github/workflows/package-windows.yml",
        ".github/workflows/promote.yml",
        "scripts/build-macos-package.sh",
        "scripts/build-windows-package.ps1",
        "scripts/package-macos.sh",
        "scripts/package-windows.ps1",
    )
    script_reference = re.compile(r"scripts[/\\][A-Za-z0-9_.-]+\.(?:py|ps1|sh|R)")
    path_reference = re.compile(
        r"Path\([\"']scripts[\"']\)\s*/\s*[\"']([A-Za-z0-9_.-]+)[\"']"
    )
    direct_inputs = set()
    pending = list(entrypoints)
    visited = set()
    while pending:
        entrypoint = pending.pop()
        if entrypoint in visited:
            continue
        visited.add(entrypoint)
        source = read_repo_text(*entrypoint.split("/"))
        references = {
            match.replace("\\", "/") for match in script_reference.findall(source)
        }
        references.update(
            f"scripts/{match}" for match in path_reference.findall(source)
        )
        direct_inputs.update(references)
        pending.extend(
            reference
            for reference in references
            if reference not in visited
            and ROOT.joinpath(*reference.split("/")).is_file()
        )
    missing = sorted(
        path
        for path in direct_inputs
        if not policy.requires_package_qualification([path])
    )

    assert not missing, f"unclassified direct package inputs: {missing}"


def test_reitsma_visual_qa_is_a_package_qualification_input():
    policy = _load_package_input_policy()

    assert policy.requires_package_qualification(
        ["scripts/verify_reitsma_visual_qa.R"]
    )


def test_package_workflow_builds_path_aware_artifacts():
    workflow = load_workflow(".github", "workflows", "package-verification.yml")
    target = load_workflow(".github", "workflows", "package-target.yml")
    workflow_jobs = workflow["jobs"]
    target_job = target["jobs"]["package"]

    assert {
        "windows-package",
        "macos-packages",
    } <= set(workflow_jobs)
    assert (
        target["env"]["RCMS_CRAN_REPO"]
        == "https://packagemanager.posit.co/cran/2026-07-16"
    )
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert [
        {key: item[key] for key in ("target", "architecture", "runner")}
        for item in target_job["strategy"]["matrix"]["include"]
    ] == [
        {"target": "macos-arm64", "architecture": "arm64", "runner": "macos-15"},
    ]
    assert target_job["timeout-minutes"] == 90
    checkout = next(
        step
        for step in target_job["steps"]
        if step.get("name") == "Check out exact source"
    )
    assert checkout["with"]["fetch-depth"] == 0
    package = next(
        step
        for step in target_job["steps"]
        if step.get("name") == "Build and run the first-green packaged workflow"
    )
    assert "steps.package-metadata.outputs.version" in package["run"]
    assert not Path(".github/workflows/r-integration-kit-producer.yml").exists()
    assert workflow_jobs["windows-package"]["if"] == "${{ inputs.build_windows }}"
    assert workflow_jobs["macos-packages"]["if"] == "${{ inputs.build_macos }}"
    assert workflow.get("permissions", {}).get("contents") != "write"


def test_macos_distributable_contract_is_declared():
    script = sh_contract("scripts", "build-macos-package.sh")
    local_script = sh_contract("scripts", "package-macos.sh")

    assert {
        "--architecture",
        "--archive-root-name",
        "--bundle-identifier",
    } <= script["case_options"]
    assert {
        "require_free_space_gb",
        "repo_path",
        "resolve_existing_dir",
        "project_version",
        "copy_tree",
    } <= script["functions"]
    macos_spec = read_repo_text("packaging", "pyinstaller", "rc-metastudio-macos.spec")
    assert "BUNDLE(" in macos_spec
    assert (
        'target_arch=os.environ.get("RCMS_TARGET_ARCHITECTURE", "arm64")' in macos_spec
    )
    assert "RCMS_BUNDLE_IDENTIFIER" in macos_spec
    assert {
        "RCMS_REQUIRE_IN_PROCESS_RPY2",
        "RCMS_STARTUP_PROJECT_SMOKE",
        "RPY2_CFFI_MODE",
    } <= script["env_names"]
    assert "env -u QT_QPA_PLATFORM" in script["text"]
    assert "$sample_root/amino.rcms" in script["text"]
    assert "$resources_root/LaunchRCMetaStudio.command" in script["text"]
    assert "$app_bundle/Contents/Frameworks/R.framework" in script["text"]
    assert "$r_home/library/RCMetaR/DESCRIPTION" in script["text"]
    assert "doc/openMA_help.html" not in script["app_paths"]
    assert "Bundling sample projects, help, and R runtime" not in script["text"]
    assert "scripts/install-r-deps.R" in script["text"]
    assert 'app_source / "__main__.py"' in macos_spec
    assert "src/rc_metastudio/launch.py" not in script["text"]
    assert 'bundle_identifier="org.researchconsultancy.rc-metastudio"' in script["text"]
    assert 'inspect_macos_deployment.py" validate-root' in script["text"]
    assert "archive root must be one portable directory name" in read_repo_text(
        "scripts", "inspect_macos_deployment.py"
    )
    assert "tomllib.loads" in script["text"]
    assert (
        'archive_root_name="${archive_root_name:-RCMetaStudio-$resolved_project_version-macos-$architecture}"'
        in script["text"]
    )
    assert 'archive_staging_root="$work_root/zip-staging"' in script["text"]
    assert (
        'copy_tree "$app_bundle" "$archive_root_dir/RCMetaStudio.app"' in script["text"]
    )
    assert (
        'ditto -c -k --norsrc --keepParent "$archive_root_dir" "$tmp_zip_path"'
        in script["text"]
    )
    assert (
        'name for name in names if name and not name.startswith(f"{archive_root_name}/")'
        in script["text"]
    )
    assert (
        'f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/RCMetaStudio"'
        in script["text"]
    )
    assert (
        'bundle_identifier="org.researchconsultancy.rc-metastudio"'
        in local_script["text"]
    )
    assert "org.RCMetaStudio.community" not in script["text"]
    assert "org.RCMetaStudio.community" not in local_script["text"]


def test_local_macos_package_script_uses_shared_build_script():
    script = sh_contract("scripts", "package-macos.sh")

    assert {
        "--architecture",
        "--archive-root-name",
        "--artifact-name",
        "--bundle-identifier",
    } <= script["case_options"]
    assert relative_order(
        script["text"],
        "uv sync --locked",
        'build_args+=(--archive-root-name "$archive_root_name")',
        'bash "$repo_root/scripts/build-macos-package.sh"',
    )


def test_shared_r_dependency_installer_is_used_by_packagers():
    installer = read_repo_text("scripts", "install-r-deps.R")
    policy_runtime = read_repo_text("scripts", "r_binary_policy.R")
    policy_loader = read_repo_text("scripts", "r_dependency_policy.py")
    windows = ps_contract("scripts", "build-windows-package.ps1")
    macos = sh_contract("scripts", "build-macos-package.sh")

    assert "load_rcms_r_binary_policy" in installer
    assert "install_rcms_binary_packages" in installer
    assert "install_rcms_source_exception" not in installer
    assert 'type = "binary"' in policy_runtime
    assert 'type = "source"' not in policy_runtime
    assert 'type = "both"' not in policy_runtime
    assert "available.packages" in policy_runtime
    assert "Required native R binaries unavailable" in policy_runtime
    assert 'install.packages.compile.from.source = "never"' in policy_runtime
    assert "HSROC" not in policy_runtime
    assert "HSROC" not in policy_loader
    assert "meta" in windows["text"]
    assert "getElement(packageDescription('meta'), 'Version')" in windows["text"]
    assert "meta" in macos["text"]
    assert "getElement(packageDescription('meta'), 'Version')" in macos["text"]
    assert "packageVersion('mada')" in windows["text"]
    assert "packageVersion('mada')" in macos["text"]
    assert "https://packagemanager.posit.co/cran/2026-07-16" in policy_loader
    assert {
        "Invoke-StrictRDependencyPolicy",
        "Test-RDependencyPackages",
    } <= windows["functions"]
    assert "RCMetaR/DESCRIPTION" in macos["text"]
    assert "RCMS_CRAN_REPO" in windows["text"]
    assert "RCMS_CRAN_REPO" in macos["text"]
    assert "RCMS_POLICY_PYTHON" in windows["text"]
    assert "RCMS_POLICY_PYTHON" in macos["text"]
    assert "RCMS_CRAN_REPO must match the manifest snapshot" in windows["text"]
    assert "RCMS_CRAN_REPO must match the manifest snapshot" in macos["text"]
    assert "r-library-cache" not in windows["text"]
    assert (
        "Invoke-StrictRDependencyPolicy -RscriptExe $rscriptExe -Library $rLibrary"
        in windows["text"]
    )
    assert 'run_strict_r_dependency_policy "$r_lib"' in macos["text"]
    assert "r-library-cache" not in macos["text"]


def test_macos_packager_resolves_relative_python_before_changing_directory():
    script = sh_contract("scripts", "build-macos-package.sh")["text"]

    assert relative_order(
        script,
        'python_exe="$(repo_path "$python_exe")"',
        'cd "$repo_root"\n  qt6_package_build_root=',
        "pyinstaller_args=(",
        '"$python_exe" -m PyInstaller',
    )


def test_macos_packager_copies_resolved_r_runtime_contents():
    script = sh_contract("scripts", "build-macos-package.sh")["text"]

    assert relative_order(
        script,
        'source_r_runtime_input="$r_runtime_root"',
        'copy_tree "$source_r_framework" "$private_r_framework"',
        'r_framework="$private_r_framework"',
        'if [ ! -x "$rscript" ] || [ ! -x "$r_binary" ]; then',
    )


def test_macos_packager_relocates_every_bundled_r_macho_before_use():
    script = sh_contract("scripts", "build-macos-package.sh")["text"]
    relocator = read_repo_text("scripts", "relocate_macos_r_runtime.sh")
    assert "relocate_bundled_r_runtime" not in script
    assert 'cp -p "$dependency" "$target"' not in relocator
    assert "External R runtime dependency closure exceeded 16 passes" not in relocator
    assert '"$python_exe" "$normalizer"' in relocator


def test_windows_runtime_probe_does_not_apply_macos_r_product_policy():
    automation = read_repo_text("tests", "python", "gui", "support", "automation_scenarios.py")
    probe = automation.split("def start_package_runtime_probe", 1)[1].split(
        "def _exercise_packaged_project_workflow", 1
    )[0]
    assert 'if sys.platform == "darwin":' in probe
    assert '"macos_product_profile": macos_r_policy' in probe
    assert 'importlib.import_module("_rinterface_cffi_api")' in probe
    assert "import _rinterface_cffi_api" not in probe


def test_windows_packager_restores_smoke_environment():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert relative_order(
        script,
        "$previousEnv = @{",
        "Invoke-BoundedPackageProcess -FilePath $exePath",
        "foreach ($name in $previousEnv.Keys)",
    )


def test_windows_packager_uses_clean_directory_copies_for_incremental_builds():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]

    assert relative_order(
        script,
        "function Copy-DirectoryTree",
        'Copy-DirectoryTree -Source (Join-Path $repoRoot "sample_projects")',
    )


def test_windows_packager_qualifies_qt6_deployment_and_packaged_surfaces():
    script = ps_contract("scripts", "build-windows-package.ps1")["text"]
    spec = read_repo_text("packaging", "pyinstaller", "rc-metastudio.spec")

    assert "windeployqt" not in script.lower()
    assert "inspect_windows_deployment.py inspect" in script
    assert "inspect_windows_deployment.py evidence" in script
    assert "qualification\\deployment-manifest.json" in script
    assert "qualification\\packaged-smoke.json" in script
    assert "RCMS_PACKAGE_SMOKE_EVIDENCE" in script
    assert "--automation-package-surface-smoke" in script
    runtime_probe_function = script.split("function Invoke-PackagedRuntimeProbe", 1)[
        1
    ].split("function Invoke-StrictRDependencyPolicy", 1)[0]
    assert relative_order(
        runtime_probe_function,
        "QT_SCALE_FACTOR = $env:QT_SCALE_FACTOR",
        'Remove-Item "Env:\\QT_SCALE_FACTOR" -ErrorAction SilentlyContinue',
        '"--automation-package-runtime-probe", $quotedProbePath',
        "foreach ($name in $previousEnv.Keys)",
    )
    assert "function Invoke-BoundedPackageProcess" in script
    assert "$processHandle = $process.Handle" in script
    assert "$process.Refresh()" in script
    assert "exited without a readable exit code" in script
    assert "test-bounded-package-process.ps1" in script
    assert "function Stop-BoundedPackageProcessTree" in script
    assert (
        "taskkill exceeded its $TimeoutMilliseconds-millisecond cleanup bound" in script
    )
    assert "-Wait -PassThru" not in script
    process_test = read_repo_text("scripts", "test-bounded-package-process.ps1")
    assert "Invoke-BoundedPackageProcess" in process_test
    assert "@(0, 7)" in process_test
    assert "Redirected stdout did not complete" in process_test
    assert "Redirected stderr did not complete" in process_test
    assert "exceeded its 1-second watchdog" in process_test
    assert "RcmsThrowingHandleProcess" in process_test
    assert "Handle acquisition failure did not trigger child cleanup" in process_test
    assert "$startArguments.RedirectStandardOutput = $StandardOutputPath" in script
    assert "$startArguments.RedirectStandardError = $StandardErrorPath" in script
    assert "RCMS_AUTOMATION_HANG_TRACE" in script
    assert "packaged-smoke.stdout.log" in script
    assert "packaged-smoke.stderr.log" in script
    assert "packaged-smoke.hang-trace.log" in script
    assert "packaged-smoke*.log" in read_repo_text(
        ".github", "workflows", "package-target.yml"
    )
    assert "function Remove-BundledRInstallerResidue" in script
    assert "(?i)^unins000\\..+$" in script
    assert "Remove-Item -LiteralPath $file.FullName -Force" in script
    assert "Windows R installer residue remained in the portable bundle" in script
    for required_r_file in (
        '"bin\\R.exe"',
        '"bin\\Rscript.exe"',
        '"bin\\x64\\R.dll"',
    ):
        assert required_r_file in script
    assert relative_order(
        script,
        "Copy-RRuntime -Root $resolvedRRuntimeRoot -DestinationRoot $appDir",
        "Remove-BundledRInstallerResidue -Root $appDir",
        "Install-BundledRPackages -Root $appDir",
        "Inspecting coherent Windows x64 deployment",
    )
    assert "WaitForExit($TimeoutSeconds * 1000)" in script
    assert "Start-Process -FilePath taskkill.exe" in script
    assert '"/PID", $ProcessId, "/T", "/F"' in script
    assert "watchdog cleanup failed" in script
    assert "$process.WaitForExit(30000)" in script
    for scale in ('"1.25"', '"1.50"', '"1.75"'):
        assert scale in script
    for plugin in (
        "platforms/qwindows.dll",
        "imageformats/qjpeg.dll",
        "imageformats/qsvg.dll",
        "iconengines/qsvgicon.dll",
        "styles/qmodernwindowsstyle.dll",
        "tls/qschannelbackend.dll",
    ):
        assert plugin in spec
    assert 'copy_metadata("rpy2")' in spec
    assert '(str(binary_resource), "resources")' in spec
    assert 'project_schema_root = app_source / "project_schemas" / "v1"' in spec
    assert 'project_schema_root.glob("*.schema.json")' in spec
    assert 'str(Path("rc_metastudio") / "project_schemas" / "v1")' in spec
    assert "generated_ui_collection.py" in spec
    assert "pyinstaller_module_entries(qt6_build_root)" in spec
    assert "a.pure.extend(generated_ui_modules)" in spec
    assert "def is_windows_system_runtime(entry):" in spec
    assert 'name.startswith("api-ms-win-")' in spec
    assert 'name.startswith("icudt")' in spec
    assert '"icuuc.dll"' in spec
    assert '"ucrtbase.dll"' in spec
    assert (
        "a.binaries = [entry for entry in a.binaries if not "
        "is_windows_system_runtime(entry)]"
    ) in spec
    assert "str(generated_package)" not in spec
    assert "str(generated_forms)" not in spec
    assert (
        'excludes=["PyQt5", "PySide2", "PySide6", "qtpy", "_rinterface_cffi_abi"]'
        in spec
    )
    assert '"_rinterface_cffi_api"' in spec
    assert spec.count("upx=False") == 2
    assert "upx=True" not in spec
    assert "upx_exclude" not in spec
    assert relative_order(
        script,
        "function Copy-DirectoryTree",
        'Copy-DirectoryTree -Source $Root -Destination (Join-Path $DestinationRoot "R")',
    )


def test_generated_ui_collection_matches_the_canonical_package_manifest(tmp_path):
    from scripts.qt6_build_impl import CANONICAL_FORMS

    build_root = tmp_path / "qt6"
    generated_root = build_root / "generated"
    for destination in CANONICAL_FORMS.values():
        generated = generated_root / destination
        generated.parent.mkdir(parents=True, exist_ok=True)
        generated.write_text("GENERATED_UI = True\n", encoding="utf-8")

    collection = load_module_from_path(
        "generated_ui_collection",
        ROOT / "packaging" / "pyinstaller" / "generated_ui_collection.py",
    )
    entries = collection.pyinstaller_module_entries(build_root)
    expected_names = {
        ".".join(destination.with_suffix("").parts)
        for destination in CANONICAL_FORMS.values()
    }

    assert {name for name, _path, typecode in entries if typecode == "PYMODULE"} == (
        expected_names
    )
    for name, path, typecode in entries:
        assert name.startswith("rc_metastudio.")
        assert not name.startswith("ui_")
        assert typecode == "PYMODULE"
        compile(Path(path).read_text(encoding="utf-8"), path, "exec")


def _load_windows_deployment_inspector():
    import importlib.util

    path = ROOT / "scripts" / "inspect_windows_deployment.py"
    spec = importlib.util.spec_from_file_location("inspect_windows_deployment", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_pe(path, machine=0x8664):
    import struct

    payload = bytearray(512)
    payload[0:2] = b"MZ"
    payload[0x3C:0x40] = struct.pack("<I", 0x80)
    payload[0x80:0x84] = b"PE\0\0"
    payload[0x84:0x98] = struct.pack("<HHIIIHH", machine, 0, 0, 0, 0, 0xF0, 0x2022)
    optional = 0x98
    payload[optional : optional + 2] = struct.pack("<H", 0x20B)
    payload[optional + 24 : optional + 32] = struct.pack("<Q", 0x140000000)
    payload[optional + 32 : optional + 40] = struct.pack("<II", 0x1000, 0x200)
    payload[optional + 56 : optional + 64] = struct.pack("<II", 0x1000, 0x200)
    payload[optional + 68 : optional + 70] = struct.pack("<H", 3)
    payload[optional + 108 : optional + 112] = struct.pack("<I", 16)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_frozen_windows_bootstrap_indexes_all_private_native_directories(tmp_path):
    from rc_metastudio import r_runtime

    r_home = tmp_path / "R"
    expected = {
        r_home / "bin" / "x64",
        r_home / "library" / "xml2" / "libs" / "x64",
    }
    for directory in expected:
        directory.mkdir(parents=True)
        (directory / "private.dll").write_bytes(b"dll")
    (r_home / "library" / "docs").mkdir(parents=True)
    (r_home / "library" / "docs" / "readme.txt").write_text("not native")

    observed = {
        Path(path) for path in r_runtime._private_windows_dll_directories(r_home)
    }
    assert observed == {path.resolve() for path in expected}


def test_frozen_direct_runtime_probe_validates_private_r_without_a_kit(
    monkeypatch, tmp_path
):
    from tests.python.gui.support import automation_scenarios as automation

    app = tmp_path / "RCMetaStudio"
    executable = app / "RCMetaStudio.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"exe")
    api_bridge = app / "_internal" / "_rinterface_cffi_api.pyd"
    api_bridge.parent.mkdir()
    api_bridge.write_bytes(b"api")
    r_home = app / "R"
    r_dll = r_home / "bin" / "x64" / "R.dll"
    r_dll.parent.mkdir(parents=True)
    r_dll.write_bytes(b"R")

    monkeypatch.setattr(automation.sys, "executable", str(executable))
    shared_library, direct_spike = automation._verified_frozen_runtime_shared_library(
        {"R_HOME": str(r_home), "derivation": {}, "direct_spike": False},
        api_bridge.resolve(),
    )

    assert shared_library == r_dll.resolve()
    assert direct_spike is False


def test_frozen_windows_runtime_bootstraps_without_a_kit(monkeypatch, tmp_path):
    from rc_metastudio import r_runtime

    app = tmp_path / "RCMetaStudio"
    r_home = app / "R"
    (r_home / "bin").mkdir(parents=True)
    (r_home / "library" / "RCMetaR").mkdir(parents=True)
    monkeypatch.setattr(r_runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(r_runtime.sys, "platform", "win32")
    monkeypatch.setattr(r_runtime, "_RUNTIME_IDENTITY", None)
    monkeypatch.setattr(r_runtime, "_BOOTSTRAP_THREAD_ID", None)
    monkeypatch.setattr(
        r_runtime,
        "_frozen_kit_identity",
        lambda _root: pytest.fail("Windows native packages must not read a kit"),
    )
    monkeypatch.setattr(
        r_runtime, "_configure_private_runtime_directories", lambda _root: None
    )
    monkeypatch.setattr(r_runtime, "_set_windows_dll_policy", lambda: None)
    monkeypatch.setattr(r_runtime, "_prepend_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(r_runtime, "_add_dll_directories", lambda *_args: None)
    monkeypatch.setattr(r_runtime.os, "environ", dict(r_runtime.os.environ))

    configured = r_runtime.configure_bundled_r_environment(str(app))

    assert Path(configured["R_HOME"]).resolve() == r_home.resolve()
    assert configured["kit_sha256"] is None
    assert configured["derivation"] is None


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows ctypes APIs")
def test_windows_dll_policy_fails_closed(monkeypatch):
    from rc_metastudio import r_runtime

    class Kernel32:
        @staticmethod
        def SetDefaultDllDirectories(_policy):
            return 0

    monkeypatch.setattr(r_runtime.sys, "platform", "win32")
    monkeypatch.setattr(
        r_runtime.ctypes, "WinDLL", lambda *_args, **_kwargs: Kernel32()
    )
    monkeypatch.setattr(r_runtime.ctypes, "get_last_error", lambda: 5)
    with pytest.raises(OSError, match="SetDefaultDllDirectories failed"):
        r_runtime._set_windows_dll_policy()


def _windows_deployment_fixture(tmp_path):
    app = tmp_path / "RCMetaStudio"
    qt = app / "_internal" / "PyQt6" / "Qt6"
    _write_pe(app / "RCMetaStudio.exe")
    api_bridge = app / "_internal" / "_rinterface_cffi_api.cp311-win_amd64.pyd"
    _write_pe(api_bridge)
    r_dll = app / "R" / "bin" / "x64" / "R.dll"
    _write_pe(r_dll)
    rcmetar = app / "R" / "library" / "RCMetaR" / "DESCRIPTION"
    rcmetar.parent.mkdir(parents=True)
    rcmetar.write_text("Package: RCMetaR\nVersion: 0.1.1\n", encoding="utf-8")
    kit_root = app / "r-integration-kit"
    kit_root.mkdir(parents=True)
    api_sha256 = hashlib.sha256(api_bridge.read_bytes()).hexdigest()
    r_sha256 = hashlib.sha256(r_dll.read_bytes()).hexdigest()
    (kit_root / "manifest.json").write_text(
        json.dumps(
            {
                "kind": "rc-metastudio-r-integration-kit",
                "target": "windows-x64",
                "architecture": "x86_64",
                "cffi_mode": "API",
                "kit_sha256": "a" * 64,
                "files": [
                    {
                        "path": "bridge/_rinterface_cffi_api.cp311-win_amd64.pyd",
                        "kind": "file",
                        "sha256": api_sha256,
                    },
                    {
                        "path": "runtime/bin/x64/R.dll",
                        "kind": "file",
                        "sha256": r_sha256,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (kit_root / "derivation.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target": "windows-x64",
                "kit_sha256": "a" * 64,
                "source": {
                    "api_bridge": {
                        "path": "bridge/_rinterface_cffi_api.cp311-win_amd64.pyd",
                        "sha256": api_sha256,
                    },
                    "r_shared_library": {
                        "path": "runtime/bin/x64/R.dll",
                        "sha256": r_sha256,
                    },
                },
                "pre_sign": {
                    "api_bridge": {
                        "path": api_bridge.relative_to(app).as_posix(),
                        "sha256": api_sha256,
                        "signing_identity": "unsigned",
                    },
                    "r_shared_library": {
                        "path": r_dll.relative_to(app).as_posix(),
                        "sha256": r_sha256,
                        "signing_identity": "unsigned",
                    },
                },
                "final": {
                    "api_bridge": {
                        "path": api_bridge.relative_to(app).as_posix(),
                        "sha256": api_sha256,
                        "signing_identity": "unsigned",
                    },
                    "r_shared_library": {
                        "path": r_dll.relative_to(app).as_posix(),
                        "sha256": r_sha256,
                        "signing_identity": "unsigned",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    for name in (
        "Qt6Core.dll",
        "Qt6Gui.dll",
        "Qt6Network.dll",
        "Qt6Svg.dll",
        "Qt6SvgWidgets.dll",
        "Qt6Widgets.dll",
    ):
        _write_pe(qt / "bin" / name)
    required = {
        "platforms": ("qwindows.dll",),
        "imageformats": ("qico.dll", "qjpeg.dll", "qsvg.dll"),
        "iconengines": ("qsvgicon.dll",),
        "styles": ("qmodernwindowsstyle.dll",),
        "tls": ("qschannelbackend.dll",),
    }
    for family, names in required.items():
        for name in names:
            _write_pe(qt / "plugins" / family / name)
    schema_root = app / "_internal" / "rc_metastudio" / "project_schemas" / "v1"
    source_schema_root = ROOT / "src" / "rc_metastudio" / "project_schemas" / "v1"
    schema_root.mkdir(parents=True)
    for source in source_schema_root.glob("*.schema.json"):
        (schema_root / source.name).write_bytes(source.read_bytes())
    return app


def _windows_runtime_probe(app):
    qt = app / "_internal" / "PyQt6" / "Qt6"
    api_bridge = app / "_internal" / "_rinterface_cffi_api.cp311-win_amd64.pyd"
    r_dll = app / "R" / "bin" / "x64" / "R.dll"
    return {
        "schema_version": 1,
        "frozen": True,
        "python": {
            "version": "3.11.9",
            "executable": str(app / "RCMetaStudio.exe"),
            "architecture": "AMD64",
            "bundle_root": str(app / "_internal"),
        },
        "qt": {
            "pyqt_version": "6.11.0",
            "compiled_qt_version": "6.11.0",
            "runtime_qt_version": "6.11.1",
            "sip_runtime_version": "6.15.2",
            "platform_plugin": "windows",
            "plugins_path": str(qt / "plugins"),
            "library_paths": [str(qt / "plugins")],
            "scale_factor_environment": None,
            "baseline_device_pixel_ratio": 1.0,
            "baseline_logical_dpi": 96.0,
        },
        "rpy2": {
            "distribution_version": "3.6.7",
            "cffi_mode": "API",
            "rinterface_distribution_version": "3.6.6",
            "robjects_distribution_version": "3.6.5",
            "loaded_cffi_mode": "API",
            "api_bridge_loaded": True,
            "api_bridge_path": str(api_bridge),
            "api_bridge_sha256": hashlib.sha256(api_bridge.read_bytes()).hexdigest(),
        },
        "project_schemas": {
            "version": 1,
            "validated_members": ["manifest.json", "project.json", "state.json"],
        },
        "r": {
            "version": "4.6.1",
            "home": str(app / "R"),
            "library_paths": [str(app / "R" / "library")],
            "configured_home": str(app / "R"),
            "configured_library": str(app / "R" / "library"),
            "shared_library_path": str(r_dll),
            "shared_library_sha256": hashlib.sha256(r_dll.read_bytes()).hexdigest(),
            "kit_sha256": "a" * 64,
            "lc_numeric": "C",
        },
    }


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows PE tooling")
def test_windows_runtime_probe_survives_relocation_but_rejects_tampering(tmp_path):
    inspector = _load_windows_deployment_inspector()
    original = _windows_deployment_fixture(tmp_path / "original")
    probe = _windows_runtime_probe(original)
    probe["r"].pop("kit_sha256")
    relocated = tmp_path / "extracted" / "RCMetaStudio-0.2.0-windows-x64"
    shutil.copytree(original, relocated)
    versions = dict(inspector.EXPECTED_VERSIONS)
    provenance = {
        "schema_version": 1,
        "head_sha": "a" * 40,
        "working_tree": "clean",
        "worktree_sha256": "b" * 64,
    }
    inspector.inspect_deployment(
        relocated,
        versions=versions,
        source_commit="a" * 40,
        source_provenance=provenance,
        runtime_probe=probe,
        locked_qt_root=relocated / "_internal" / "PyQt6" / "Qt6",
    )
    r_dll = relocated / "R" / "bin" / "x64" / "R.dll"
    r_dll.write_bytes(r_dll.read_bytes() + b"tampered")
    with pytest.raises(inspector.DeploymentInspectionError, match="frozen R runtime"):
        inspector.inspect_deployment(
            relocated,
            versions=versions,
            source_commit="a" * 40,
            source_provenance=provenance,
            runtime_probe=probe,
            locked_qt_root=relocated / "_internal" / "PyQt6" / "Qt6",
        )


def test_windows_deployment_inspector_resolves_wheel_private_libs_directory():
    inspector = _load_windows_deployment_inspector()
    records = [
        {
            "path": "_internal/numpy/_core/_multiarray_umath.pyd",
            "sha256": "extension",
            "_imports": [{"name": "libscipy_openblas64_example.dll", "kind": "normal"}],
        },
        {
            "path": "_internal/numpy.libs/libscipy_openblas64_example.dll",
            "sha256": "openblas",
            "_imports": [],
        },
    ]

    inspector._resolve_pe_closure(records)

    assert records[0]["imports"] == [
        {
            "name": "libscipy_openblas64_example.dll",
            "kind": "normal",
            "resolution": "app-local",
            "resolved_path": "_internal/numpy.libs/libscipy_openblas64_example.dll",
            "resolved_sha256": "openblas",
        }
    ]


def test_windows_deployment_inspector_recognizes_supported_os_imports():
    inspector = _load_windows_deployment_inspector()

    assert all(
        inspector._is_windows_system_import(name)
        for name in (
            "AUTHZ.dll",
            "DWrite.dll",
            "icuuc.dll",
            "pdh.dll",
            "UIAutomationCore.DLL",
            "WTSAPI32.dll",
        )
    )


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows PE tooling")
def test_windows_deployment_inspector_accepts_one_coherent_x64_qt6_stack(
    tmp_path, monkeypatch
):
    inspector = _load_windows_deployment_inspector()
    app = _windows_deployment_fixture(tmp_path)
    qt_root = app / "_internal" / "PyQt6" / "Qt6"
    _write_pe(qt_root / "plugins" / "imageformats" / "qpdf.dll")
    _write_pe(app / "R" / "library" / "qpdf" / "libs" / "x64" / "qpdf.dll")
    versions = {
        "python": "3.11.9",
        "pyqt6": "6.11.0",
        "qt": "6.11.1",
        "sip": "13.11.1",
        "sip_runtime": "6.15.2",
        "r": "4.6.1",
        "rpy2": "3.6.7",
        "pyinstaller": "6.21.0",
    }

    direct_runtime_probe = _windows_runtime_probe(app)
    direct_runtime_probe["r"].pop("kit_sha256")
    provenance = {
        "schema_version": 1,
        "head_sha": "a" * 40,
        "working_tree": "clean",
        "worktree_sha256": "b" * 64,
    }
    manifest = inspector.inspect_deployment(
        app,
        versions=versions,
        source_commit="a" * 40,
        source_provenance=provenance,
        runtime_probe=direct_runtime_probe,
        locked_qt_root=qt_root,
    )

    assert manifest["target"] == "windows-x64"
    assert manifest["minimum_os"] == "Windows 10 version 1809"
    assert manifest["collector"] == {
        "name": "PyInstaller",
        "version": "6.21.0",
        "provenance": "build-time-only",
        "definition": "packaging/pyinstaller/rc-metastudio.spec",
    }
    assert "r_integration_kit" not in manifest
    assert manifest["embedded_r"]["cffi_mode"] == "API"
    assert manifest["stack"] == versions
    assert manifest["plugins"]["platforms"] == ["qwindows.dll"]
    assert set(manifest["qt_plugins"]) == {
        "platforms/qwindows.dll",
        "imageformats/qico.dll",
        "imageformats/qjpeg.dll",
        "imageformats/qsvg.dll",
        "imageformats/qpdf.dll",
        "iconengines/qsvgicon.dll",
        "styles/qmodernwindowsstyle.dll",
        "tls/qschannelbackend.dll",
    }
    assert all(item["machine"] == "x86_64" for item in manifest["native_files"])
    assert all("imports" in item for item in manifest["native_files"])
    assert set(manifest["project_schema_resources"]) == {
        "manifest.schema.json",
        "project.schema.json",
        "state.schema.json",
    }
    missing_schema = (
        app
        / "_internal"
        / "rc_metastudio"
        / "project_schemas"
        / "v1"
        / "project.schema.json"
    )
    missing_schema.unlink()
    with pytest.raises(
        inspector.DeploymentInspectionError,
        match="missing required project schema resources",
    ):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=qt_root,
        )

    runtime_probe_path = tmp_path / "runtime-probe.json"
    runtime_probe_path.write_text(
        json.dumps(_windows_runtime_probe(app)), encoding="utf-8"
    )
    source_provenance_path = tmp_path / "source-provenance.json"
    source_provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    output = tmp_path / "deployment-manifest.json"
    captured = {}

    def inspect_from_cli(app_root, **kwargs):
        captured["app_root"] = app_root
        captured.update(kwargs)
        return {"target": "windows-x64", "stack": kwargs["versions"]}

    monkeypatch.setattr(inspector, "inspect_deployment", inspect_from_cli)
    monkeypatch.setattr(
        inspector.sys,
        "argv",
        [
            "inspect_windows_deployment.py",
            "inspect",
            "--app-root",
            str(app),
            "--output",
            str(output),
            "--source-commit",
            "a" * 40,
            "--source-provenance",
            str(source_provenance_path),
            "--runtime-probe",
            str(runtime_probe_path),
            "--locked-qt-root",
            str(app / "_internal" / "PyQt6" / "Qt6"),
            "--python-version",
            versions["python"],
            "--pyqt6-version",
            versions["pyqt6"],
            "--qt-version",
            versions["qt"],
            "--sip-version",
            versions["sip"],
            "--sip-runtime-version",
            versions["sip_runtime"],
            "--r-version",
            versions["r"],
            "--rpy2-version",
            versions["rpy2"],
            "--pyinstaller-version",
            versions["pyinstaller"],
        ],
    )

    assert inspector._main() == 0
    assert captured["versions"] == versions
    assert captured["runtime_probe"] == _windows_runtime_probe(app)
    assert json.loads(output.read_text(encoding="utf-8"))["stack"] == versions


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows PE tooling")
def test_windows_deployment_inspector_records_dirty_source_provenance(tmp_path):
    inspector = _load_windows_deployment_inspector()
    app = _windows_deployment_fixture(tmp_path)
    provenance = {
        "schema_version": 1,
        "head_sha": "a" * 40,
        "working_tree": "dirty",
        "worktree_sha256": "b" * 64,
    }
    manifest = inspector.inspect_deployment(
        app,
        versions=dict(inspector.EXPECTED_VERSIONS),
        source_commit="a" * 40,
        source_provenance=provenance,
        runtime_probe=_windows_runtime_probe(app),
        locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
    )
    assert manifest["source_provenance"] == provenance
    with pytest.raises(inspector.DeploymentInspectionError, match="source provenance"):
        inspector.inspect_deployment(
            app,
            versions=dict(inspector.EXPECTED_VERSIONS),
            source_commit="a" * 40,
            source_provenance=None,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )
    with pytest.raises(inspector.DeploymentInspectionError, match="source provenance"):
        inspector.inspect_deployment(
            app,
            versions=dict(inspector.EXPECTED_VERSIONS),
            source_commit="a" * 40,
            source_provenance={
                "schema_version": 1,
                "head_sha": "a" * 40,
                "working_tree": "dirty",
            },
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )


def test_source_provenance_frames_binary_untracked_paths_and_contents(tmp_path):
    provenance = _load_source_provenance()
    repo = tmp_path / "repository with spaces"
    repo.mkdir()
    for arguments in (
        ("init",),
        ("config", "user.email", "package@example.test"),
        ("config", "user.name", "Package Test"),
    ):
        subprocess.run(["git", *arguments], cwd=repo, check=True, capture_output=True)
    (repo / "tracked.txt").write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True
    )
    untracked = repo / "untracked file.bin"
    untracked.write_bytes(b"\x00binary\xff")
    first = provenance.collect_source_provenance(repo)
    assert first["working_tree"] == "dirty"
    untracked.write_bytes(b"\x00changed\xff")
    second = provenance.collect_source_provenance(repo)
    assert second["worktree_sha256"] != first["worktree_sha256"]
    untracked.unlink()
    (repo / "tracked.txt").write_text("changed", encoding="utf-8")
    assert (
        provenance.collect_source_provenance(repo)["worktree_sha256"]
        != first["worktree_sha256"]
    )


def test_windows_public_download_retry_is_powershell_51_compatible_and_atomic():
    wrapper = Path("scripts/package-windows.ps1").read_text(encoding="utf-8")
    assert "-MaximumRetryCount" not in wrapper
    assert "-RetryIntervalSec" not in wrapper
    assert "function Invoke-DownloadWithRetry" in wrapper
    assert "for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++)" in wrapper
    assert (
        "Move-Item -LiteralPath $partialInstaller -Destination $rInstaller" in wrapper
    )
    retry_test = Path("scripts/test-package-download-retry.ps1").read_text(
        encoding="utf-8"
    )
    assert "Package download retry self-test passed." in retry_test
    assert "terminal injected failure" in retry_test


def test_final_windows_pe_closure_requires_app_local_msvc_and_tracks_delay_imports():
    inspector = _load_windows_deployment_inspector()
    runtime = {
        "path": "_internal/vcruntime140.dll",
        "sha256": "d" * 64,
        "_imports": [],
    }
    bridge = {
        "path": "_internal/api.pyd",
        "sha256": "a" * 64,
        "_imports": [
            {"name": "VCRUNTIME140.dll", "kind": "delay"},
            {"name": "KERNEL32.dll", "kind": "normal"},
        ],
    }
    inspector._resolve_pe_closure([runtime, bridge])
    assert bridge["imports"] == [
        {
            "name": "VCRUNTIME140.dll",
            "kind": "delay",
            "resolution": "app-local",
            "resolved_path": "_internal/vcruntime140.dll",
            "resolved_sha256": "d" * 64,
        },
        {"name": "KERNEL32.dll", "kind": "normal", "resolution": "system"},
    ]


def test_final_windows_pe_closure_rejects_unique_but_unreachable_dependency():
    inspector = _load_windows_deployment_inspector()
    dependency = {
        "path": "unregistered/private.dll",
        "sha256": "d" * 64,
        "_imports": [],
    }
    owner = {
        "path": "_internal/api.pyd",
        "sha256": "a" * 64,
        "_imports": [{"name": "private.dll", "kind": "normal"}],
    }
    with pytest.raises(inspector.DeploymentInspectionError, match="unreachable"):
        inspector._resolve_pe_closure([dependency, owner])


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows PE tooling")
def test_windows_deployment_inspector_rejects_legacy_duplicate_and_wrong_architecture(
    tmp_path,
):
    import shutil

    inspector = _load_windows_deployment_inspector()
    versions = {
        "python": "3.11.9",
        "pyqt6": "6.11.0",
        "qt": "6.11.1",
        "sip": "13.11.1",
        "sip_runtime": "6.15.2",
        "r": "4.6.1",
        "rpy2": "3.6.7",
        "pyinstaller": "6.21.0",
    }

    app = _windows_deployment_fixture(tmp_path / "legacy")
    _write_pe(app / "_internal" / "PyQt5" / "Qt5Core.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="mixed or legacy"):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "duplicate")
    _write_pe(app / "other" / "Qt6Core.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="duplicate Qt6"):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "architecture")
    _write_pe(app / "bad.dll", machine=0x014C)
    with pytest.raises(inspector.DeploymentInspectionError, match="non-x64"):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    for binding in ("PySide2", "PySide6", "qtpy"):
        app = _windows_deployment_fixture(tmp_path / f"mixed-{binding}")
        _write_pe(app / "_internal" / binding / "binding.pyd")
        with pytest.raises(
            inspector.DeploymentInspectionError, match="mixed or legacy"
        ):
            inspector.inspect_deployment(
                app,
                versions=versions,
                source_commit="a" * 40,
                runtime_probe=_windows_runtime_probe(app),
                locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
            )

    required_plugin = {
        "platforms": "qwindows.dll",
        "imageformats": "qjpeg.dll",
        "iconengines": "qsvgicon.dll",
        "styles": "qmodernwindowsstyle.dll",
        "tls": "qschannelbackend.dll",
    }
    for family, name in required_plugin.items():
        app = _windows_deployment_fixture(tmp_path / f"missing-{family}")
        (app / "_internal" / "PyQt6" / "Qt6" / "plugins" / family / name).unlink()
        with pytest.raises(
            inspector.DeploymentInspectionError, match="missing required Qt"
        ):
            inspector.inspect_deployment(
                app,
                versions=versions,
                source_commit="a" * 40,
                runtime_probe=_windows_runtime_probe(app),
                locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
            )

    app = _windows_deployment_fixture(tmp_path / "duplicate-plugin")
    _write_pe(app / "_internal" / "plugins" / "qwindows.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="plugin root"):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    for generated in ("forms/ui_dialog.py", "icons_rc.pyc"):
        app = _windows_deployment_fixture(
            tmp_path / ("generated-" + generated.replace("/", "-"))
        )
        path = app / generated
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated", encoding="utf-8")
        with pytest.raises(
            inspector.DeploymentInspectionError, match="generated sources"
        ):
            inspector.inspect_deployment(
                app,
                versions=versions,
                source_commit="a" * 40,
                runtime_probe=_windows_runtime_probe(app),
                locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
            )

    app = _windows_deployment_fixture(tmp_path / "stack-mismatch")
    mismatched = dict(versions, qt="6.11.0")
    with pytest.raises(
        inspector.DeploymentInspectionError, match="differs from the locked"
    ):
        inspector.inspect_deployment(
            app,
            versions=mismatched,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "misplaced-library")
    source = app / "_internal" / "PyQt6" / "Qt6" / "bin" / "Qt6Network.dll"
    destination = app / "_internal" / "other" / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    with pytest.raises(
        inspector.DeploymentInspectionError, match="outside the authoritative"
    ):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "runtime-probe-mismatch")
    probe = _windows_runtime_probe(app)
    probe["qt"]["runtime_qt_version"] = "6.11.0"
    with pytest.raises(inspector.DeploymentInspectionError, match="frozen Qt runtime"):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=probe,
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "schema-runtime-probe-mismatch")
    probe = _windows_runtime_probe(app)
    probe["project_schemas"]["validated_members"].remove("state.json")
    with pytest.raises(
        inspector.DeploymentInspectionError,
        match="runtime did not validate the required project schemas",
    ):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=probe,
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "locked-identity-mismatch")
    locked_qt = tmp_path / "locked-qt"
    shutil.copytree(app / "_internal" / "PyQt6" / "Qt6", locked_qt)
    with (locked_qt / "bin" / "Qt6Core.dll").open("ab") as stream:
        stream.write(b"different")
    with pytest.raises(inspector.DeploymentInspectionError, match="identity differs"):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=locked_qt,
        )

    app = _windows_deployment_fixture(tmp_path / "locked-plugin-mismatch")
    locked_qt = tmp_path / "locked-plugin-qt"
    shutil.copytree(app / "_internal" / "PyQt6" / "Qt6", locked_qt)
    with (locked_qt / "plugins" / "platforms" / "qwindows.dll").open("ab") as stream:
        stream.write(b"different")
    with pytest.raises(
        inspector.DeploymentInspectionError, match="plugin identity differs"
    ):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=locked_qt,
        )

    app = _windows_deployment_fixture(tmp_path / "extra-qt-library")
    locked_qt = tmp_path / "extra-qt-library-locked"
    shutil.copytree(app / "_internal" / "PyQt6" / "Qt6", locked_qt)
    _write_pe(app / "_internal" / "PyQt6" / "Qt6" / "bin" / "Qt6Concurrent.dll")
    with pytest.raises(
        inspector.DeploymentInspectionError, match="library identity differs"
    ):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=locked_qt,
        )

    app = _windows_deployment_fixture(tmp_path / "extra-plugin")
    locked_qt = tmp_path / "extra-plugin-locked"
    shutil.copytree(app / "_internal" / "PyQt6" / "Qt6", locked_qt)
    _write_pe(
        app
        / "_internal"
        / "PyQt6"
        / "Qt6"
        / "plugins"
        / "networkinformation"
        / "qnetworklistmanager.dll"
    )
    with pytest.raises(
        inspector.DeploymentInspectionError, match="plugin identity differs"
    ):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=locked_qt,
        )

    app = _windows_deployment_fixture(tmp_path / "mismatched-non-required-plugin")
    locked_qt = tmp_path / "mismatched-non-required-plugin-locked"
    shutil.copytree(app / "_internal" / "PyQt6" / "Qt6", locked_qt)
    locked_extra = (
        locked_qt / "plugins" / "networkinformation" / "qnetworklistmanager.dll"
    )
    _write_pe(locked_extra)
    packaged_extra = (
        app
        / "_internal"
        / "PyQt6"
        / "Qt6"
        / "plugins"
        / "networkinformation"
        / "qnetworklistmanager.dll"
    )
    _write_pe(packaged_extra)
    with packaged_extra.open("ab") as stream:
        stream.write(b"different")
    with pytest.raises(
        inspector.DeploymentInspectionError, match="plugin identity differs"
    ):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=locked_qt,
        )

    app = _windows_deployment_fixture(tmp_path / "duplicate-non-required-plugin")
    locked_qt = tmp_path / "duplicate-non-required-plugin-locked"
    shutil.copytree(app / "_internal" / "PyQt6" / "Qt6", locked_qt)
    locked_extra = (
        locked_qt / "plugins" / "networkinformation" / "qnetworklistmanager.dll"
    )
    packaged_extra = (
        app
        / "_internal"
        / "PyQt6"
        / "Qt6"
        / "plugins"
        / "networkinformation"
        / "qnetworklistmanager.dll"
    )
    _write_pe(locked_extra)
    _write_pe(packaged_extra)
    _write_pe(app / "_internal" / "plugins" / "qnetworklistmanager.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="plugin root"):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=locked_qt,
        )

    app = _windows_deployment_fixture(tmp_path / "misplaced-unknown-plugin")
    _write_pe(app / "_internal" / "plugins" / "qcustomplugin.dll")
    with pytest.raises(
        inspector.DeploymentInspectionError, match="outside the authoritative plugin"
    ):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )

    app = _windows_deployment_fixture(tmp_path / "alternate-qpdf-plugin-tree")
    qt_root = app / "_internal" / "PyQt6" / "Qt6"
    _write_pe(qt_root / "plugins" / "imageformats" / "qpdf.dll")
    _write_pe(app / "_internal" / "plugins" / "imageformats" / "qpdf.dll")
    with pytest.raises(inspector.DeploymentInspectionError, match="plugin root"):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=_windows_runtime_probe(app),
            locked_qt_root=qt_root,
        )

    app = _windows_deployment_fixture(tmp_path / "scaled-runtime-probe")
    probe = _windows_runtime_probe(app)
    probe["qt"]["scale_factor_environment"] = "1.25"
    with pytest.raises(inspector.DeploymentInspectionError, match="frozen Qt runtime"):
        inspector.inspect_deployment(
            app,
            versions=versions,
            source_commit="a" * 40,
            runtime_probe=probe,
            locked_qt_root=app / "_internal" / "PyQt6" / "Qt6",
        )


def test_windows_qualification_evidence_authenticates_complete_packaged_smoke(tmp_path):
    import json
    import zipfile

    inspector = _load_windows_deployment_inspector()
    windows_accessibility = {
        "focus_before": None,
        "focus_after_tab": None,
        "accessible_name": "Packaged accessibility control",
        "accessible_description": "Verifies packaged Qt accessibility metadata.",
        "native": {},
    }
    assert inspector._valid_windows_accessibility(windows_accessibility)
    assert not inspector._valid_windows_accessibility(
        {
            **windows_accessibility,
            "accessible_description": "",
        }
    )
    windows_critical_dialog = {
        "dont_use_native_dialog": False,
        "application_dont_use_native_dialogs": False,
        "dont_show_on_screen_before_show": False,
        "dont_show_on_screen_after_show": False,
        "native_helper_active": False,
        "window_modality": "WindowModal",
        "visible_before_close": True,
        "critical_icon": True,
        "finished_signal": True,
        "result": 1,
        "accepted_value": 1,
        "timed_out": False,
        "timeout_ms": 5_000,
    }
    assert inspector._valid_windows_critical_dialog(windows_critical_dialog)
    assert not inspector._valid_windows_critical_dialog(
        {
            **windows_critical_dialog,
            "finished_signal": False,
        }
    )
    archive = tmp_path / "RCMetaStudio-windows-x64.zip"
    runtime_probe = tmp_path / "runtime-probe.json"
    runtime_value = {"frozen": True}
    runtime_probe.write_text(json.dumps(runtime_value), encoding="utf-8")
    runtime_canonical = (
        json.dumps(runtime_value, sort_keys=True, separators=(",", ":")) + "\n"
    )
    import hashlib

    deployment = tmp_path / "deployment-manifest.json"
    deployment.write_text(
        json.dumps(
            {
                "target": "windows-x64",
                "stack": inspector.EXPECTED_VERSIONS,
                "source_provenance": {
                    "schema_version": 1,
                    "head_sha": "a" * 40,
                    "working_tree": "clean",
                    "worktree_sha256": "d" * 64,
                },
                "runtime_probe_canonical_sha256": hashlib.sha256(
                    runtime_canonical.encode()
                ).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    smoke = tmp_path / "packaged-smoke.json"
    smoke_log = tmp_path / "packaged-smoke.log"
    smoke_log.write_text(
        "\n".join(
            (
                "packaged-workflow:evidence-written",
                "packaged-runtime-probe:passed",
                "packaged-workflow:shell-created",
                "packaged-workflow:project-open:start",
                "packaged-workflow:project-open:return",
                "packaged-workflow:paint:complete",
                "packaged-workflow:project-exercise:complete",
                "packaged-workflow:post-close",
                "packaged-surface:scale-1.25-passed",
                "packaged-surface:scale-1.50-passed",
                "packaged-surface:scale-1.75-passed",
                "startup-project:normal-entry-point-passed",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    smoke.write_text(
        json.dumps(
            {
                "passed": True,
                "workflows": {
                    "automation_entry_point": True,
                    "converted_sample": "amino.rcms",
                    "representative_edit": True,
                    "real_r_analysis": True,
                    "result_text": True,
                    "expected_normalized_summary_sha256": inspector.EXPECTED_SUMMARY_SHA256,
                    "raw_summary_sha256": "b" * 64,
                    "normalized_summary_sha256": inspector.EXPECTED_SUMMARY_SHA256,
                    "svg_sha256": {"Forest Plot": "a" * 64},
                    "locale_variants": [
                        {
                            "locale": "en_US",
                            "input": "7.0",
                            "canonical_value": 7.0,
                            "raw_summary_sha256": "b" * 64,
                            "normalized_summary_sha256": inspector.EXPECTED_SUMMARY_SHA256,
                            "svg_sha256": {"Forest Plot": "a" * 64},
                        },
                        {
                            "locale": "de_DE",
                            "input": "7,0",
                            "canonical_value": 7.0,
                            "raw_summary_sha256": "b" * 64,
                            "normalized_summary_sha256": inspector.EXPECTED_SUMMARY_SHA256,
                            "svg_sha256": {"Forest Plot": "a" * 64},
                        },
                    ],
                    "save_reopen": True,
                    "analysis_after_reopen": True,
                    "sample_projects": {
                        "passed": True,
                        "manifest_sha256": "c" * 64,
                        "projects": [
                            {
                                "project": "amino.rcms",
                                "sha256": "d" * 64,
                                "semantic_sha256": "e" * 64,
                                "opened_in_packaged_application": True,
                            }
                        ],
                    },
                },
                "execution": {
                    "automation_exit_code": 0,
                    "positional_user_entry_exit_code": 0,
                    "scale_exit_codes": {"1.25": 0, "1.50": 0, "1.75": 0},
                    "post_close_marker": True,
                    "clean_exit": True,
                },
                "scales": [
                    {
                        "requested": scale,
                        "qt_scale_factor": scale,
                        "device_pixel_ratio": float(scale),
                        "baseline_device_pixel_ratio": 1.0,
                        "expected_device_pixel_ratio": float(scale),
                        "dpr_tolerance": 0.05,
                        "clipboard": True,
                        "critical_dialog": windows_critical_dialog,
                        "binary_resources": True,
                        "locale": "de_DE",
                        "platform_plugin": "windows",
                        "accessibility": windows_accessibility,
                        "tls_backends": ["schannel"],
                        "active_style": "windows11",
                        "available_styles": ["Windows11", "Windows"],
                        "image_formats": ["ico", "jpeg", "svg"],
                    }
                    for scale in ("1.25", "1.50", "1.75")
                ],
            }
        ),
        encoding="utf-8",
    )
    root = "RCMetaStudio-0.2.0-windows-x64"
    embedded = {
        "qualification/deployment-manifest.json": deployment,
        "qualification/runtime-probe.json": runtime_probe,
        "qualification/packaged-smoke.json": smoke,
        "qualification/packaged-smoke.log": smoke_log,
    }
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(f"{root}/RCMetaStudio.exe", b"MZ")
        for relative, source in embedded.items():
            bundle.writestr(f"{root}/{relative}", source.read_bytes())
    archive_report = inspector.inspect_archive(
        archive, archive_root_name=root, embedded_files=embedded
    )
    archive_inspection = tmp_path / "archive-inspection.json"
    archive_inspection.write_text(json.dumps(archive_report), encoding="utf-8")
    extracted_deployment = tmp_path / "deployment-reinspection.json"
    extracted_deployment.write_bytes(deployment.read_bytes())
    extracted_smoke = tmp_path / "extracted-packaged-smoke.json"
    extracted_smoke.write_bytes(smoke.read_bytes())
    extracted_smoke_log = tmp_path / "extracted-packaged-smoke.log"
    extracted_smoke_log.write_bytes(smoke_log.read_bytes())

    evidence = inspector.write_qualification_evidence(
        archive=archive,
        deployment_manifest=deployment,
        smoke_evidence=smoke,
        smoke_log=smoke_log,
        runtime_probe=runtime_probe,
        archive_inspection=archive_inspection,
        extracted_deployment_manifest=extracted_deployment,
        extracted_smoke_evidence=extracted_smoke,
        extracted_smoke_log=extracted_smoke_log,
        output=tmp_path / "evidence.json",
    )

    assert evidence["passed"] is True
    assert evidence["artifact"]["sha256"] == inspector.sha256_file(archive)
    assert evidence["runner"]["runner_arch"]
    assert evidence["logs"][0]["sha256"] == inspector.sha256_file(smoke_log)
    assert evidence["exact_extracted_qualification"][
        "archive_sha256"
    ] == inspector.sha256_file(archive)
    assert evidence["source_provenance"]["working_tree"] == "clean"

    extracted_smoke.write_text("{}", encoding="utf-8")
    with pytest.raises(inspector.DeploymentInspectionError, match="exact-extracted"):
        inspector.write_qualification_evidence(
            archive=archive,
            deployment_manifest=deployment,
            smoke_evidence=smoke,
            smoke_log=smoke_log,
            runtime_probe=runtime_probe,
            archive_inspection=archive_inspection,
            extracted_deployment_manifest=extracted_deployment,
            extracted_smoke_evidence=extracted_smoke,
            extracted_smoke_log=extracted_smoke_log,
            output=tmp_path / "missing-extracted.json",
        )
    extracted_smoke.write_bytes(smoke.read_bytes())

    mutated = json.loads(smoke.read_text(encoding="utf-8"))
    mutated["scales"][0]["device_pixel_ratio"] = 1.0
    smoke.write_text(json.dumps(mutated), encoding="utf-8")
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(f"{root}/RCMetaStudio.exe", b"MZ")
        for relative, source in embedded.items():
            bundle.writestr(f"{root}/{relative}", source.read_bytes())
    archive_report = inspector.inspect_archive(
        archive, archive_root_name=root, embedded_files=embedded
    )
    archive_inspection.write_text(json.dumps(archive_report), encoding="utf-8")
    with pytest.raises(inspector.DeploymentInspectionError, match="incomplete"):
        inspector.write_qualification_evidence(
            archive=archive,
            deployment_manifest=deployment,
            smoke_evidence=smoke,
            smoke_log=smoke_log,
            runtime_probe=runtime_probe,
            archive_inspection=archive_inspection,
            extracted_deployment_manifest=extracted_deployment,
            extracted_smoke_evidence=extracted_smoke,
            extracted_smoke_log=extracted_smoke_log,
            output=tmp_path / "mutated.json",
        )

    for member_names in (
        (f"{root}/../escape.txt",),
        (f"{root}\\qualification\\runtime-probe.json",),
        (f"{root}/A.txt", f"{root}/a.txt"),
    ):
        bad_archive = tmp_path / ("bad-" + str(len(member_names)) + ".zip")
        with zipfile.ZipFile(bad_archive, "w") as bundle:
            for name in member_names:
                bundle.writestr(name, b"bad")
        with pytest.raises(inspector.DeploymentInspectionError):
            inspector.inspect_archive(
                bad_archive, archive_root_name=root, embedded_files=embedded
            )

