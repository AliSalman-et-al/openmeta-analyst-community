#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo/scripts/macos_host_r_isolation.sh"
work="$repo/build/macos-direct-r-spike"
stage="$work/staged/R.framework"
resources="$stage/Resources"
dist="$work/dist"
pyinstaller_work="$work/pyinstaller"
evidence="$work/evidence"
artifact="$repo/artifacts/RCMetaStudio-macos-x64-direct-r-spike.zip"
pkg="$work/R-4.6.1-x86_64.pkg"
official_url="https://cloud.r-project.org/bin/macosx/big-sur-x86_64/base/R-4.6.1-x86_64.pkg"
official_sha256="612bb00cb4c627721d6d80b0f5224227c0fcdefb4a5b6c917511480361c16571"
hsroc_url="https://cran.r-project.org/src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz"
hsroc_sha256="5476fa76d7723717e203925a1da442813e3645790ef9b633a145cbc04a08b874"
installed_framework="/Library/Frameworks/R.framework"

step() { printf '[direct-r-spike] %s\n' "$1"; }
fail() { echo "Direct macOS R spike failed: $1" >&2; exit 1; }
require_x64() {
  local observed
  observed="$(lipo -archs "$1" 2>/dev/null || true)"
  [ "$observed" = "x86_64" ] || fail "$1 must be x86_64-only, found: ${observed:-non-Mach-O}"
}
framework_symlinks() {
  local framework="$1"
  find "$framework" -type l -print0 \
    | while IFS= read -r -d '' link; do
        printf '%s -> %s\n' "${link#"$framework"/}" "$(readlink "$link")"
      done \
    | LC_ALL=C sort
}
validate_official_framework() {
  local framework="$1" report="$2" snapshot="$3" current version_root home raw
  current="$(readlink "$framework/Versions/Current")"
  case "$current" in
    ""|/*|*/*|.|..) fail "Versions/Current has an unsafe target: $current" ;;
  esac
  version_root="$framework/Versions/$current"
  home="$framework/Resources"
  [ "$(readlink "$framework/Resources")" = "Versions/Current/Resources" ] \
    || fail "official top-level Resources link is not canonical"
  [ "$(readlink "$framework/R")" = "Versions/Current/R" ] \
    || fail "official top-level R link is not canonical"
  [ "$(readlink "$version_root/R")" = "Resources/lib/libR.dylib" ] \
    || fail "official version R link is not canonical"
  [ "$(readlink "$home/R")" = "bin/R" ] \
    || fail "official Resources/R link is not canonical"
  [ -f "$home/bin/R" ] && [ -x "$home/bin/R" ] \
    || fail "official bin/R shell front-end is absent or not executable"
  [ "$(head -n 1 "$home/bin/R")" = "#!/bin/sh" ] \
    || fail "official bin/R shell front-end lacks its canonical shebang"
  require_x64 "$home/bin/Rscript"
  require_x64 "$home/bin/exec/R"
  require_x64 "$home/lib/libR.dylib"
  raw="${snapshot}.raw"
  {
    echo '== R identities =='
    "$home/bin/R" RHOME
    "$home/bin/Rscript" -e \
      'cat(R.home(), "\n", R.version$arch, "\n", R.version.string, "\n", sep="")'
    echo '== Mach-O load commands =='
    otool -L "$home/bin/Rscript"
    otool -L "$home/bin/exec/R"
    otool -D "$home/lib/libR.dylib"
    otool -L "$home/lib/libR.dylib"
  } > "$raw" 2>&1
  sed \
    -e "s#${framework}#<FRAMEWORK>#g" \
    -e 's#/Library/Frameworks/R.framework#<FRAMEWORK>#g' \
    "$raw" > "$snapshot"
  {
    printf 'framework=%s\nVersions/Current=%s\n' "$framework" "$current"
    file "$home/bin/R" "$home/bin/Rscript" "$home/bin/exec/R" \
      "$home/lib/libR.dylib"
    printf 'bin/R shebang='; head -n 1 "$home/bin/R"
    printf 'bin/Rscript architectures='; lipo -archs "$home/bin/Rscript"
    printf 'bin/exec/R architectures='; lipo -archs "$home/bin/exec/R"
    printf 'libR architectures='; lipo -archs "$home/lib/libR.dylib"
    cat "$raw"
    framework_symlinks "$framework"
  } > "$report"
  rm -f "$raw"
}

[ "$(uname -s)" = Darwin ] || fail "requires macOS"
[ "$(uname -m)" = x86_64 ] || fail "requires a native Intel runner"
[ ! -e /opt/X11 ] || fail "clean feasibility runner unexpectedly contains /opt/X11"
source_commit="$(git -C "$repo" rev-parse HEAD)"
preflight_report="$repo/build/macos-r-pyinstaller-toc-preflight.json"
python3 - "$preflight_report" "$source_commit" <<'PY'
import json
from pathlib import Path
import sys

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload != {
    "schema_version": 1,
    "source_commit": sys.argv[2],
    "pyinstaller_version": "6.21.0",
    "system": "Darwin",
    "machine": "x86_64",
    "aliases": {
        "Versions/Current": "4.6-x86_64",
        "Resources": "Versions/Current/Resources",
        "R": "Versions/Current/R",
        "Versions/4.6-x86_64/R": "Resources/lib/libR.dylib",
        "Versions/4.6-x86_64/Resources/R": "bin/R",
    },
    "passed": True,
}:
    raise SystemExit("macOS R.framework PyInstaller preflight evidence is invalid")
PY
rm -rf "$work" "$artifact"
mkdir -p "$work" "$evidence" "$repo/artifacts"
[ -z "$(git -C "$repo" status --porcelain -- r/RCMetaR)" ] \
  || fail "RCMetaR working source differs from the recorded commit"
rcmetar_source_archive="$work/RCMetaR-0.1.2-source.tar.gz"
git -C "$repo" archive --format=tar.gz --prefix=RCMetaR/ \
  -o "$rcmetar_source_archive" "$source_commit:r/RCMetaR"
rcmetar_source_sha256="$(shasum -a 256 "$rcmetar_source_archive" | awk '{print $1}')"
rcmetar_version="$(sed -n 's/^Version:[[:space:]]*//p' "$repo/r/RCMetaR/DESCRIPTION")"
[ "$rcmetar_version" = "0.1.2" ] || fail "RCMetaR source version is not 0.1.2"

step "Authenticating official R 4.6.1 Intel package"
curl --fail --location --proto '=https' --tlsv1.2 "$official_url" --output "$pkg"
observed_sha256="$(shasum -a 256 "$pkg" | awk '{print $1}')"
[ "$observed_sha256" = "$official_sha256" ] || fail "official R SHA-256 mismatch"
signature_report="$(pkgutil --check-signature "$pkg" 2>&1)"
grep -q 'VZLD955F6P' <<<"$signature_report" || fail "official R package signer mismatch"
printf '%s\n' "$signature_report" > "$evidence/official-r-signature.txt"
sudo installer -pkg "$pkg" -target /

step "Inspecting and staging the complete official R.framework"
[ -d "$installed_framework/Versions" ] \
  || fail "official target-native framework root is absent"
validate_official_framework \
  "$installed_framework" "$evidence/installed-r-framework.txt" \
  "$evidence/installed-r-identity.txt"
framework_symlinks "$installed_framework" > "$evidence/installed-r-symlinks.txt"
ditto "$installed_framework" "$stage"
validate_official_framework \
  "$stage" "$evidence/staged-r-framework.txt" \
  "$evidence/staged-r-identity.txt"
framework_symlinks "$stage" > "$evidence/staged-r-symlinks.txt"
if ! diff -u "$evidence/installed-r-symlinks.txt" \
  "$evidence/staged-r-symlinks.txt" > "$evidence/staged-r-symlinks.diff"; then
  fail "staging changed the official R.framework symlink topology"
fi
if ! diff -u "$evidence/installed-r-identity.txt" \
  "$evidence/staged-r-identity.txt" > "$evidence/staged-r-identity.diff"; then
  fail "staging changed the official R.framework identities or load commands"
fi

export R_HOME="$resources"
export R_LIBS="$resources/library"
export R_LIBS_USER="$resources/library"
export RPY2_CFFI_MODE=API
export MACOSX_DEPLOYMENT_TARGET=13.0
export RCMS_CRAN_REPO="https://packagemanager.posit.co/cran/2026-07-16"
export RCMS_R_PACKAGE_ARCHIVE_DIR="$work/ppm-archives"
export RCMS_HSROC_ARCHIVE="$work/HSROC_2.1.9.tar.gz"
mkdir -p "$RCMS_R_PACKAGE_ARCHIVE_DIR"

step "Creating the locked Python environment against staged R"
(cd "$repo" && uv sync --locked)
python="$repo/.venv/bin/python"
export RCMS_POLICY_PYTHON="$python"

step "Installing PPM binaries, HSROC, and local RCMetaR into staged R"
"$resources/bin/Rscript" "$repo/scripts/install-r-deps.R" 2>&1 | tee "$evidence/r-packages.log"
[ "$(shasum -a 256 "$RCMS_HSROC_ARCHIVE" | awk '{print $1}')" = "$hsroc_sha256" ] \
  || fail "HSROC source exception hash changed"
"$resources/bin/Rscript" "$repo/scripts/install-rcmetar-source.R" \
  "$repo/r/RCMetaR" "$resources/library" 2>&1 | tee "$evidence/rcmetar.log"
"$python" "$repo/scripts/profile_macos_embedded_r_runtime.py" \
  --resources "$resources" --source-resources "$resources" \
  --evidence "$evidence/embedded-r-runtime-profile.json" \
  --dependency-manifest "$repo/docs/verification/RCMetaR-r-dependencies.json" \
  --r-version 4.6.1 --architecture x86_64 --official-framework-layout
adapter_map="$evidence/direct-r-adapter.json"
adapter_toc="$work/direct-r-toc.json"
adapter_audit="$evidence/direct-r-pre-normalization-audit.json"
"$python" "$repo/scripts/macos_embedded_r_adapter.py" audit \
  --framework "$stage" --architecture x86_64 --output "$adapter_audit"
"$python" "$repo/scripts/macos_embedded_r_adapter.py" normalize \
  --framework "$stage" --architecture x86_64 \
  --audit "$adapter_audit" --output "$adapter_map" --toc-output "$adapter_toc"

step "Rebuilding the locked rpy2 API bridge against staged R"
rpy2_sdist="$work/rpy2-rinterface-3.6.6.tar.gz"
"$python" - "$repo/uv.lock" "$rpy2_sdist" <<'PY'
import hashlib
from pathlib import Path
import sys
import tomllib
import urllib.request

lock = tomllib.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
record = next(item for item in lock["package"] if item["name"] == "rpy2-rinterface")
sdist = record["sdist"]
if record["version"] != "3.6.6" or not sdist["hash"].startswith("sha256:"):
    raise SystemExit("uv.lock does not contain the expected rpy2-rinterface sdist")
payload = urllib.request.urlopen(sdist["url"]).read()
if hashlib.sha256(payload).hexdigest() != sdist["hash"].split(":", 1)[1]:
    raise SystemExit("locked rpy2-rinterface sdist hash mismatch")
Path(sys.argv[2]).write_bytes(payload)
PY
uv pip install --python "$python" --reinstall --no-deps "$rpy2_sdist"
"$python" - <<'PY'
import importlib.util
from pathlib import Path
import _rinterface_cffi_api
from rpy2 import robjects
from rpy2.rinterface_lib import openrlib

bridge = Path(_rinterface_cffi_api.__file__).resolve()
if openrlib.cffi_mode.name != "API":
    raise SystemExit("rpy2 did not initialize in API mode")
if importlib.util.find_spec("_rinterface_cffi_abi") is not None:
    raise SystemExit("rpy2 ABI fallback is present in the direct build environment")
if float(robjects.r("1 + 1")[0]) != 2.0:
    raise SystemExit("staged in-process R calculation failed")
print(bridge)
PY
api_bridge="$($python -c 'from pathlib import Path; import _rinterface_cffi_api as m; print(Path(m.__file__).resolve())')"
require_x64 "$api_bridge"
api_bridge_sha256="$(shasum -a 256 "$api_bridge" | awk '{print $1}')"
"$python" - "$api_bridge" "$evidence/rpy2-api-build.json" <<'PY'
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

bridge = Path(sys.argv[1])
versions = {
    name: importlib.metadata.version(name)
    for name in ("rpy2", "rpy2-rinterface", "rpy2-robjects")
}
if versions != {"rpy2": "3.6.7", "rpy2-rinterface": "3.6.6", "rpy2-robjects": "3.6.5"}:
    raise SystemExit(f"unexpected rpy2 split versions: {versions}")
Path(sys.argv[2]).write_text(json.dumps({
    "schema_version": 1,
    "versions": versions,
    "bridge": str(bridge),
    "sha256": hashlib.sha256(bridge.read_bytes()).hexdigest(),
    "dependencies": subprocess.run(["otool", "-L", str(bridge)], check=True, capture_output=True, text=True).stdout.splitlines(),
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

step "Resolving the pinned official Qt rcc"
qt_sdk="$repo/build/qt-sdk/6.11.1/macos"
if [ ! -d "$qt_sdk" ]; then
  (cd "$repo" && uv run --no-sync aqt install-qt mac desktop 6.11.1 clang_64 --outputdir "$repo/build/qt-sdk")
fi
qt_env="$work/qt.env"
"$python" "$repo/scripts/qt6_macos_feasibility.py" resolve-rcc \
  --sdk-root "$qt_sdk" --github-env "$qt_env" --diagnostic "$evidence/qt-rcc.json"
source "$qt_env"
export RCMS_QT6_RCC

step "Collecting staged R directly through the authoritative PyInstaller spec"
qt_input="$work/qt6-input"
(cd "$repo" && "$python" scripts/build_qt6.py generate --build-root "$qt_input")
export RCMS_QT6_BUILD_ROOT="$qt_input"
export RCMS_BUNDLE_IDENTIFIER="org.researchconsultancy.rc-metastudio"
export RCMS_PROJECT_VERSION="0.1.2"
export RCMS_TARGET_ARCHITECTURE=x86_64
export RCMS_MINIMUM_MACOS_VERSION=13.0
export RCMS_PYINSTALLER_R_TOC="$adapter_toc"
export RCMS_PYINSTALLER_R_MAP="$adapter_map"
export RCMS_RPY2_API_BRIDGE_SHA256="$api_bridge_sha256"
(cd "$repo" && "$python" -m PyInstaller --clean --noconfirm \
  --distpath "$dist" --workpath "$pyinstaller_work" \
  packaging/pyinstaller/rc-metastudio-macos.spec)
app="$dist/RCMetaStudio.app"
[ -x "$app/Contents/MacOS/RCMetaStudio" ] || fail "PyInstaller did not create the app"
[ "$(find "$app" -type f -name '_rinterface_cffi_api*.so' | wc -l | tr -d ' ')" = 1 ] \
  || fail "final app must contain exactly one rpy2 API bridge"
if find "$app" -name '_rinterface_cffi_abi*' -print -quit | grep -q .; then
  fail "final app contains the rpy2 ABI fallback"
fi
final_api_bridge="$(find "$app" -type f -name '_rinterface_cffi_api*.so' -print -quit)"
"$python" "$repo/scripts/macos_embedded_r_adapter.py" relocate-bridge \
  --framework "$app/Contents/Frameworks/R.framework" \
  --bridge "$final_api_bridge" --architecture x86_64 \
  --output "$evidence/final-rpy2-api-bridge.json"
"$python" "$repo/scripts/macos_embedded_r_adapter.py" post-app \
  --app "$app" --architecture x86_64 \
  --output "$evidence/pre-sign-direct-r-gate.json"
"$python" "$repo/scripts/inspect_macos_deployment.py" native-graph \
  --app "$app" --target macos-x64 \
  --output "$evidence/pre-sign-native-graph.json"

step "Signing and exercising the direct frozen application"
signing="$evidence/ad-hoc-signing-inventory.json"
"$python" "$repo/scripts/sign_macos_app.py" "$app" --identity - --inventory-output "$signing"
codesign --verify --strict --deep "$app"
runtime_probe="$evidence/runtime-probe.json"
smoke="$evidence/packaged-smoke.json"
smoke_log="$evidence/packaged-smoke.log"
hang_trace="$evidence/packaged-smoke.hang-trace.log"
: > "$hang_trace"
runtime_stdout="$evidence/runtime-probe.stdout.log"
runtime_stderr="$evidence/runtime-probe.stderr.log"
smoke_stdout="$evidence/packaged-smoke.stdout.log"
smoke_stderr="$evidence/packaged-smoke.stderr.log"
run_frozen() {
  local timeout="$1" stdout="$2" stderr="$3"
  shift 3
  env -u QT_QPA_PLATFORM -u R_HOME -u R_LIBS -u R_LIBS_USER \
    -u R_PROFILE -u R_ENVIRON \
    -u DYLD_LIBRARY_PATH -u DYLD_FALLBACK_LIBRARY_PATH \
    RCMS_DIRECT_R_SPIKE=1 RCMS_REQUIRE_IN_PROCESS_RPY2=1 RPY2_CFFI_MODE=API \
    "$python" "$repo/scripts/run_bounded_process.py" \
    --timeout-seconds "$timeout" --stdout "$stdout" --stderr "$stderr" -- "$@"
}
rcms_isolate_host_r "$installed_framework"
export RCMS_AUTOMATION_SMOKE_LOG="$smoke_log"
export RCMS_AUTOMATION_HANG_TRACE="$hang_trace"
run_frozen 180 "$runtime_stdout" "$runtime_stderr" \
  "$app/Contents/MacOS/RCMetaStudio" --automation-package-runtime-probe "$runtime_probe"
printf 'runtime-probe:process-exit:0\n' >> "$runtime_stdout"
export RCMS_PACKAGE_SMOKE_EVIDENCE="$smoke"
run_frozen 600 "$smoke_stdout" "$smoke_stderr" \
  "$app/Contents/MacOS/RCMetaStudio" --automation-native-smoke \
  "$repo/sample_projects/amino.rcms"
printf 'packaged-workflow:process-exit:0\n' >> "$smoke_log"
baseline_dpr="$($python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["qt"]["baseline_device_pixel_ratio"])' "$runtime_probe")"
for scale in 1.25 1.50 1.75; do
  surface_label="${scale/./}"
  QT_SCALE_FACTOR="$scale" RCMS_PACKAGE_BASELINE_DPR="$baseline_dpr" \
    run_frozen 60 "$evidence/packaged-surface-${surface_label}.stdout.log" \
      "$evidence/packaged-surface-${surface_label}.stderr.log" \
      "$app/Contents/MacOS/RCMetaStudio" \
      --automation-package-surface-smoke "$smoke" "$scale"
done
launch_marker="$evidence/launchservices-completion.json"
launch_pid="$evidence/launchservices.pid"
rm -f "$launch_marker" "$launch_pid"
env -u QT_QPA_PLATFORM -u R_HOME -u R_LIBS -u R_LIBS_USER \
  -u R_PROFILE -u R_ENVIRON -u DYLD_LIBRARY_PATH -u DYLD_FALLBACK_LIBRARY_PATH \
  RCMS_DIRECT_R_SPIKE=1 RCMS_REQUIRE_IN_PROCESS_RPY2=1 RPY2_CFFI_MODE=API \
  RCMS_STARTUP_PROJECT_SMOKE=1 RCMS_AUTOMATION_SMOKE_LOG="$smoke_log" \
  RCMS_STARTUP_COMPLETION_MARKER="$launch_marker" \
  RCMS_AUTOMATION_PID_FILE="$launch_pid" \
  "$python" "$repo/scripts/run_bounded_process.py" --timeout-seconds 180 \
    --stdout "$evidence/launchservices.stdout.log" \
    --stderr "$evidence/launchservices.stderr.log" \
    --owned-pid-file "$launch_pid" -- open -W -n "$app" --args \
      --automation-startup-project-smoke \
      --automation-startup-completion-marker "$launch_marker" \
      --automation-pid-file "$launch_pid" --automation-smoke-log "$smoke_log" \
      "$repo/sample_projects/amino.rcms"
rm -f "$launch_pid"
rcms_restore_host_r
"$python" "$repo/scripts/inspect_macos_deployment.py" finalize-smoke \
  --smoke-evidence "$smoke" --smoke-log "$smoke_log" \
  --launchservices-marker "$launch_marker" --require-direct-teardown

step "Running final architecture, closure, framework, and API-mode inspection"
locked_qt_root="$($python -c 'from pathlib import Path; import PyQt6; print(Path(PyQt6.__file__).resolve().parent / "Qt6")')"
"$python" "$repo/scripts/inspect_macos_deployment.py" inspect \
  --target macos-x64 --app-root "$app" --output "$evidence/deployment-manifest.json" \
  --source-commit "$source_commit" --runtime-probe "$runtime_probe" \
  --signing-inventory "$signing" --locked-qt-root "$locked_qt_root" \
  --python-version "$($python -c 'import platform; print(platform.python_version())')" \
  --pyqt6-version "$($python -c 'import importlib.metadata as m; print(m.version("PyQt6"))')" \
  --qt-version "$($python -c 'import importlib.metadata as m; print(m.version("PyQt6-Qt6"))')" \
  --sip-version "$($python -c 'import importlib.metadata as m; print(m.version("PyQt6-sip"))')" \
  --sip-runtime-version "$($python -c 'from PyQt6 import sip; print(sip.SIP_VERSION_STR)')" \
  --r-version 4.6.1 --rpy2-version 3.6.7 --pyinstaller-version 6.21.0

step "Archiving non-release feasibility evidence"
archive_root="$work/archive-root/RCMetaStudio-macos-x64-direct-r-spike"
mkdir -p "$archive_root/qualification"
direct_build_manifest="$evidence/direct-build-manifest.json"
"$python" - "$evidence/runner-environment.json" <<'PY'
import json
import os
import platform
from pathlib import Path
import subprocess
import sys

def run(*command):
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip()

Path(sys.argv[1]).write_text(json.dumps({
    "schema_version": 1,
    "github_actions": os.environ.get("GITHUB_ACTIONS"),
    "runner_image": os.environ.get("ImageOS") or os.environ.get("RUNNER_IMAGE"),
    "runner_os": os.environ.get("RUNNER_OS"),
    "runner_arch": os.environ.get("RUNNER_ARCH"),
    "macos_version": run("sw_vers", "-productVersion"),
    "macos_build": run("sw_vers", "-buildVersion"),
    "uname_system": run("uname", "-s"),
    "uname_machine": run("uname", "-m"),
    "python_machine": platform.machine(),
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
"$python" - "$direct_build_manifest" "$evidence/ppm-archive-inventory.json" \
  "$api_bridge_sha256" "$source_commit" \
  "$official_url" "$official_sha256" "$RCMS_CRAN_REPO" \
  "$RCMS_R_PACKAGE_ARCHIVE_DIR" "$hsroc_url" "$hsroc_sha256" \
  "$RCMS_HSROC_ARCHIVE" "$rcmetar_version" "$rcmetar_source_archive" \
  "$rcmetar_source_sha256" \
  "$repo/scripts/macos_embedded_r_adapter.py" "$adapter_audit" "$adapter_map" \
  "$repo/scripts/macos_host_r_isolation.sh" \
  "$repo/scripts/verify_macos_r_pyinstaller_toc.py" \
  "$preflight_report" \
  "$adapter_toc" "$evidence/rpy2-api-build.json" \
  "$evidence/pre-sign-native-graph.json" "$signing" "$signing" \
  "$evidence/ppm-archive-inventory.json" \
  "$RCMS_HSROC_ARCHIVE" "$rcmetar_source_archive" \
  "$evidence/embedded-r-runtime-profile.json" "$runtime_probe" \
  "$runtime_stdout" "$runtime_stderr" "$evidence/deployment-manifest.json" \
  "$smoke" "$smoke_log" "$smoke_stdout" "$smoke_stderr" "$hang_trace" \
  "$launch_marker" "$evidence/launchservices.stdout.log" \
  "$evidence/launchservices.stderr.log" "$evidence/runner-environment.json" \
  "$evidence/packaged-surface-125.stdout.log" \
  "$evidence/packaged-surface-125.stderr.log" \
  "$evidence/packaged-surface-150.stdout.log" \
  "$evidence/packaged-surface-150.stderr.log" \
  "$evidence/packaged-surface-175.stdout.log" \
  "$evidence/packaged-surface-175.stderr.log" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

(
    output,
    ppm_inventory_output,
    bridge_sha,
    source_commit,
    r_url,
    r_sha,
    ppm,
    ppm_root,
    hsroc_url,
    hsroc_sha,
    hsroc_archive,
    rcmetar_version,
    rcmetar_archive,
    rcmetar_sha,
    *input_names,
) = sys.argv[1:]

def record(path):
    path = Path(path)
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size": path.stat().st_size,
    }

ppm_root = Path(ppm_root)
ppm_archives = [
    {"path": str(path.relative_to(ppm_root)), **record(path)}
    for path in sorted(ppm_root.rglob("*"))
    if path.is_file()
]
if not ppm_archives:
    raise SystemExit("PPM archive inventory is empty")
Path(ppm_inventory_output).write_text(json.dumps({
    "schema_version": 1,
    "repository": ppm,
    "archives": ppm_archives,
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
input_labels = (
    "adapter_script",
    "pre_normalization_audit",
    "normalized_adapter_map",
    "host_r_isolation_script",
    "pyinstaller_toc_preflight",
    "pyinstaller_toc_preflight_report",
    "explicit_r_toc",
    "rpy2_api_build",
    "pre_sign_native_graph",
    "post_sign_native_inventory",
    "signing_inventory",
    "ppm_archive_inventory",
    "hsroc_source_archive",
    "rcmetar_source_archive",
    "r_runtime_profile",
    "runtime_probe",
    "runtime_stdout",
    "runtime_stderr",
    "deployment_manifest",
    "smoke_evidence",
    "smoke_log",
    "smoke_stdout",
    "smoke_stderr",
    "hang_trace",
    "launchservices_marker",
    "launchservices_stdout",
    "launchservices_stderr",
    "runner_environment",
    "surface_125_stdout",
    "surface_125_stderr",
    "surface_150_stdout",
    "surface_150_stderr",
    "surface_175_stdout",
    "surface_175_stderr",
)
Path(output).write_text(json.dumps({
    "schema_version": 1,
    "kind": "rc-metastudio-direct-macos-target-build",
    "target": "macos-x64",
    "source_commit": source_commit,
    "official_r": {"url": r_url, "sha256": r_sha},
    "ppm_snapshot": ppm,
    "ppm_archives": ppm_archives,
    "hsroc_source_exception": {
        "name": "HSROC", "version": "2.1.9", "install_type": "source",
        "url": hsroc_url, "sha256": hsroc_sha, "archive": record(hsroc_archive),
    },
    "rcmetar_source": {
        "name": "RCMetaR", "version": rcmetar_version,
        "source_commit": source_commit, "archive_sha256": rcmetar_sha,
        "archive": record(rcmetar_archive),
    },
    "rpy2_api_bridge_source_sha256": bridge_sha,
    "inputs": {
        label: record(path) for label, path in zip(input_labels, input_names, strict=True)
    },
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
ditto "$app" "$archive_root/RCMetaStudio.app"
cp "$evidence/deployment-manifest.json" "$archive_root/qualification/deployment-manifest.json"
cp "$signing" "$archive_root/qualification/ad-hoc-signing-inventory.json"
cp "$runtime_probe" "$archive_root/qualification/runtime-probe.json"
cp "$runtime_stdout" "$archive_root/qualification/runtime-probe.stdout.log"
cp "$runtime_stderr" "$archive_root/qualification/runtime-probe.stderr.log"
cp "$evidence/embedded-r-runtime-profile.json" "$archive_root/qualification/embedded-r-runtime-profile.json"
cp "$direct_build_manifest" "$archive_root/qualification/direct-build-manifest.json"
cp "$smoke" "$archive_root/qualification/packaged-smoke.json"
cp "$smoke_log" "$archive_root/qualification/packaged-smoke.log"
cp "$smoke_stdout" "$archive_root/qualification/packaged-smoke.stdout.log"
cp "$smoke_stderr" "$archive_root/qualification/packaged-smoke.stderr.log"
cp "$hang_trace" "$archive_root/qualification/packaged-smoke.hang-trace.log"
cp "$repo/scripts/macos_embedded_r_adapter.py" "$archive_root/qualification/embedded-r-adapter.py"
cp "$repo/scripts/macos_host_r_isolation.sh" "$archive_root/qualification/macos-host-r-isolation.sh"
cp "$repo/scripts/verify_macos_r_pyinstaller_toc.py" "$archive_root/qualification/verify-macos-r-pyinstaller-toc.py"
cp "$preflight_report" "$archive_root/qualification/macos-r-pyinstaller-toc-preflight.json"
cp "$adapter_audit" "$archive_root/qualification/direct-r-pre-normalization-audit.json"
cp "$adapter_map" "$archive_root/qualification/direct-r-adapter.json"
cp "$adapter_toc" "$archive_root/qualification/direct-r-toc.json"
cp "$evidence/rpy2-api-build.json" "$archive_root/qualification/rpy2-api-build.json"
cp "$evidence/pre-sign-native-graph.json" "$archive_root/qualification/pre-sign-native-graph.json"
cp "$evidence/ppm-archive-inventory.json" "$archive_root/qualification/ppm-archive-inventory.json"
cp "$RCMS_HSROC_ARCHIVE" "$archive_root/qualification/HSROC_2.1.9.tar.gz"
cp "$rcmetar_source_archive" "$archive_root/qualification/RCMetaR-0.1.2-source.tar.gz"
cp "$launch_marker" "$archive_root/qualification/launchservices-completion.json"
cp "$evidence/launchservices.stdout.log" "$archive_root/qualification/launchservices.stdout.log"
cp "$evidence/launchservices.stderr.log" "$archive_root/qualification/launchservices.stderr.log"
cp "$evidence/runner-environment.json" "$archive_root/qualification/runner-environment.json"
for scale_label in 125 150 175; do
  cp "$evidence/packaged-surface-${scale_label}.stdout.log" \
    "$archive_root/qualification/packaged-surface-${scale_label}.stdout.log"
  cp "$evidence/packaged-surface-${scale_label}.stderr.log" \
    "$archive_root/qualification/packaged-surface-${scale_label}.stderr.log"
done
ditto -c -k --norsrc --keepParent "$archive_root" "$artifact"
shasum -a 256 "$artifact" > "$evidence/artifact.sha256"
"$python" "$repo/scripts/inspect_macos_deployment.py" archive \
  --target macos-x64 --archive "$artifact" \
  --archive-root-name RCMetaStudio-macos-x64-direct-r-spike \
  --deployment-manifest "$evidence/deployment-manifest.json" \
  --runtime-probe "$runtime_probe" --runtime-stdout "$runtime_stdout" \
  --runtime-stderr "$runtime_stderr" --smoke-evidence "$smoke" \
  --smoke-log "$smoke_log" --smoke-stdout "$smoke_stdout" \
  --smoke-stderr "$smoke_stderr" --hang-trace "$hang_trace" \
  --signing-inventory "$signing" \
  --r-runtime-profile "$evidence/embedded-r-runtime-profile.json" \
  --launchservices-marker "$launch_marker" \
  --direct-build-manifest "$direct_build_manifest" \
  --output "$evidence/archive-inspection.json"
"$python" - "$artifact" "$evidence/archive-inspection.json" \
  "$evidence/post-archive-evidence.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

archive, inspection, output = map(Path, sys.argv[1:])
inspection_payload = json.loads(inspection.read_text(encoding="utf-8"))
archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
if inspection_payload.get("archive_sha256") != archive_sha:
    raise SystemExit("archive inspector SHA differs from retained artifact")
output.write_text(json.dumps({
    "schema_version": 1,
    "archive": {"sha256": archive_sha, "size": archive.stat().st_size},
    "inspection": {
        "sha256": hashlib.sha256(inspection.read_bytes()).hexdigest(),
        "size": inspection.stat().st_size,
    },
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
extracted="$work/extracted"
mkdir -p "$extracted"
ditto -x -k "$artifact" "$extracted"
extracted_app="$extracted/RCMetaStudio-macos-x64-direct-r-spike/RCMetaStudio.app"
"$python" - "$extracted_app" "$evidence/extracted-codesign-verification.json" <<'PY'
import json
from pathlib import Path
import subprocess
import sys

completed = subprocess.run(
    ["codesign", "--verify", "--strict", "--deep", sys.argv[1]],
    capture_output=True,
    text=True,
)
Path(sys.argv[2]).write_text(json.dumps({
    "schema_version": 1,
    "command": ["codesign", "--verify", "--strict", "--deep"],
    "exit_code": completed.returncode,
    "stdout": completed.stdout,
    "stderr": completed.stderr,
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
completed.check_returncode()
PY
"$python" "$repo/scripts/macos_embedded_r_adapter.py" post-app \
  --app "$extracted_app" --architecture x86_64 \
  --output "$evidence/extracted-direct-r-gate.json"
rcms_isolate_host_r "$installed_framework"
run_frozen 180 "$evidence/extracted-runtime-probe.stdout.log" \
  "$evidence/extracted-runtime-probe.stderr.log" \
  "$extracted_app/Contents/MacOS/RCMetaStudio" \
  --automation-package-runtime-probe "$evidence/extracted-runtime-probe.json"
printf 'runtime-probe:process-exit:0\n' \
  >> "$evidence/extracted-runtime-probe.stdout.log"
rcms_restore_host_r
"$python" "$repo/scripts/inspect_macos_deployment.py" inspect \
  --target macos-x64 --app-root "$extracted_app" \
  --output "$evidence/extracted-deployment-manifest.json" \
  --source-commit "$source_commit" \
  --runtime-probe "$evidence/extracted-runtime-probe.json" \
  --signing-inventory "$signing" --locked-qt-root "$locked_qt_root" \
  --python-version "$($python -c 'import platform; print(platform.python_version())')" \
  --pyqt6-version "$($python -c 'import importlib.metadata as m; print(m.version("PyQt6"))')" \
  --qt-version "$($python -c 'import importlib.metadata as m; print(m.version("PyQt6-Qt6"))')" \
  --sip-version "$($python -c 'import importlib.metadata as m; print(m.version("PyQt6-sip"))')" \
  --sip-runtime-version "$($python -c 'from PyQt6 import sip; print(sip.SIP_VERSION_STR)')" \
  --r-version 4.6.1 --rpy2-version 3.6.7 --pyinstaller-version 6.21.0
echo "Direct macOS x64 R/PyInstaller feasibility spike passed: $artifact"
