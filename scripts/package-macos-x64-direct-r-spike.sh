#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$repo/build/macos-direct-r-spike"
stage="$work/staged/R.framework"
resources="$stage/Versions/4.6/Resources"
dist="$work/dist"
pyinstaller_work="$work/pyinstaller"
evidence="$work/evidence"
artifact="$repo/artifacts/RCMetaStudio-macos-x64-direct-r-spike.zip"
pkg="$work/R-4.6.1-x86_64.pkg"
official_url="https://cloud.r-project.org/bin/macosx/big-sur-x86_64/base/R-4.6.1-x86_64.pkg"
official_sha256="612bb00cb4c627721d6d80b0f5224227c0fcdefb4a5b6c917511480361c16571"
source_version_root="/Library/Frameworks/R.framework/Versions/4.6-x86_64"

step() { printf '[direct-r-spike] %s\n' "$1"; }
fail() { echo "Direct macOS R spike failed: $1" >&2; exit 1; }
require_x64() {
  local observed
  observed="$(lipo -archs "$1" 2>/dev/null || true)"
  [ "$observed" = "x86_64" ] || fail "$1 must be x86_64-only, found: ${observed:-non-Mach-O}"
}

[ "$(uname -s)" = Darwin ] || fail "requires macOS"
[ "$(uname -m)" = x86_64 ] || fail "requires a native Intel runner"
[ ! -e /opt/X11 ] || fail "clean feasibility runner unexpectedly contains /opt/X11"
rm -rf "$work" "$artifact"
mkdir -p "$work" "$evidence" "$repo/artifacts"

step "Authenticating official R 4.6.1 Intel package"
curl --fail --location --proto '=https' --tlsv1.2 "$official_url" --output "$pkg"
observed_sha256="$(shasum -a 256 "$pkg" | awk '{print $1}')"
[ "$observed_sha256" = "$official_sha256" ] || fail "official R SHA-256 mismatch"
signature_report="$(pkgutil --check-signature "$pkg" 2>&1)"
grep -q 'VZLD955F6P' <<<"$signature_report" || fail "official R package signer mismatch"
printf '%s\n' "$signature_report" > "$evidence/official-r-signature.txt"
sudo installer -pkg "$pkg" -target /

step "Staging the canonical target-native R.framework root"
[ -d "$source_version_root/Resources" ] || fail "official target-native framework root is absent"
resolved_source="$(cd "$source_version_root" && pwd -P)"
[ "$resolved_source" = "$source_version_root" ] || fail "target-native framework root must be canonical"
mkdir -p "$stage/Versions"
ditto "$source_version_root" "$stage/Versions/4.6"
ln -s "4.6" "$stage/Versions/Current"
ln -s "Versions/Current/Resources" "$stage/Resources"
ln -s "Versions/Current/R" "$stage/R"
[ -f "$resources/lib/libR.dylib" ] && [ ! -L "$resources/lib/libR.dylib" ] \
  || fail "target-native libR must be the official framework Mach-O"
require_x64 "$resources/lib/libR.dylib"
[ -L "$stage/Versions/4.6/R" ] \
  && [ "$(readlink "$stage/Versions/4.6/R")" = "Resources/lib/libR.dylib" ] \
  || fail "target-native version R symlink is not canonical"
[ -L "$resources/R" ] && [ "$(readlink "$resources/R")" = "bin/R" ] \
  || fail "target-native Resources/R symlink is not canonical"
require_x64 "$resources/bin/exec/R"
if otool -L "$resources/bin/R" >/dev/null 2>&1; then
  fail "target-native Resources/bin/R must be the official script launcher"
fi
head -c 2 "$resources/bin/R" | grep -q '^#!' || fail "official R launcher lacks a shebang"

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
"$resources/bin/Rscript" "$repo/scripts/install-rcmetar-source.R" \
  "$repo/r/RCMetaR" "$resources/library" 2>&1 | tee "$evidence/rcmetar.log"
"$python" "$repo/scripts/profile_macos_embedded_r_runtime.py" \
  --resources "$resources" --source-resources "$resources" \
  --evidence "$evidence/embedded-r-runtime-profile.json" \
  --dependency-manifest "$repo/docs/verification/RCMetaR-r-dependencies.json" \
  --r-version 4.6.1 --architecture x86_64

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

step "Resolving the pinned official Qt rcc"
qt_sdk="$repo/build/qt-sdk/6.11.1/macos"
if [ ! -d "$qt_sdk" ]; then
  (cd "$repo" && uv run aqt install-qt mac desktop 6.11.1 clang_64 --outputdir "$repo/build/qt-sdk")
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
export RCMS_PYINSTALLER_R_FRAMEWORK="$stage"
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

step "Signing and exercising the direct frozen application"
signing="$evidence/ad-hoc-signing-inventory.json"
"$python" "$repo/scripts/sign_macos_app.py" "$app" --identity - --inventory-output "$signing"
codesign --force --options runtime --sign - "$app"
codesign --verify --strict --deep "$app"
runtime_probe="$evidence/runtime-probe.json"
smoke="$evidence/packaged-smoke.json"
smoke_log="$evidence/packaged-smoke.log"
stdout_log="$evidence/packaged-smoke.stdout.log"
stderr_log="$evidence/packaged-smoke.stderr.log"
run_frozen() {
  env -u QT_QPA_PLATFORM RCMS_DIRECT_R_SPIKE=1 RCMS_REQUIRE_IN_PROCESS_RPY2=1 \
    RPY2_CFFI_MODE=API "$python" "$repo/scripts/run_bounded_process.py" \
    --timeout-seconds 900 --stdout "$stdout_log" --stderr "$stderr_log" -- "$@"
}
export RCMS_AUTOMATION_SMOKE_LOG="$smoke_log"
run_frozen \
  "$app/Contents/MacOS/RCMetaStudio" --automation-package-runtime-probe "$runtime_probe"
export RCMS_PACKAGE_SMOKE_EVIDENCE="$smoke"
run_frozen "$app/Contents/MacOS/RCMetaStudio" --automation-native-smoke \
  "$repo/sample_projects/amino.rcms"
"$python" "$repo/scripts/inspect_macos_deployment.py" finalize-smoke \
  --smoke-evidence "$smoke" --smoke-log "$smoke_log"

step "Running final architecture, closure, framework, and API-mode inspection"
source_commit="$(git -C "$repo" rev-parse HEAD)"
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
ditto -c -k --norsrc --keepParent "$app" "$artifact"
shasum -a 256 "$artifact" > "$evidence/artifact.sha256"
echo "Direct macOS x64 R/PyInstaller feasibility spike passed: $artifact"
