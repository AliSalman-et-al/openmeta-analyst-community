#!/usr/bin/env bash
set -euo pipefail

target="${1:?target}"; r_home="${2:?R home}"; python="${3:?python}"; official_artifact="${4:?official R pkg}"; official_url="${5:?official URL}"; signature="${6:?signature identity}"
rpy2_sdist="${7:?rpy2 sdist}"; rpy2_url="${8:?rpy2 URL}"; rpy2_rinterface_sdist="${9:?rpy2-rinterface sdist}"; rpy2_rinterface_url="${10:?rpy2-rinterface URL}"
rpy2_robjects_sdist="${11:?rpy2-robjects sdist}"; rpy2_robjects_url="${12:?rpy2-robjects URL}"; output="${13:?output}"
case "$target" in macos-x64) arch=x86_64; deployment_target=13.0; package_type=mac.binary; contrib=bin/macosx/big-sur-x86_64/contrib/4.6 ;; macos-arm64) arch=arm64; deployment_target=14.0; package_type=mac.binary; contrib=bin/macosx/sonoma-arm64/contrib/4.6 ;; *) exit 2 ;; esac
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$repo/build/r-kit-producer/$target"; stage="$work/R.framework"; archives="$work/ppm-archives"; logs="$work/logs"
rm -rf "$work" "$output"; mkdir -p "$work" "$archives" "$logs"
framework="$($python - "$r_home" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]).resolve()
print(next(parent for parent in p.parents if parent.name == "R.framework"))
PY
)"
ditto "$framework" "$stage"
staged_home="$stage/Resources"; library="$staged_home/library"; rscript="$staged_home/bin/Rscript"
export R_HOME="$staged_home" R_LIBS="$library" R_LIBS_USER="$library" MACOSX_DEPLOYMENT_TARGET="$deployment_target" RCMS_CRAN_REPO="https://packagemanager.posit.co/cran/2026-07-16" RCMS_R_PACKAGE_ARCHIVE_DIR="$archives" RCMS_HSROC_ARCHIVE="$work/HSROC_2.1.9.tar.gz"
"$rscript" "$repo/scripts/install-r-deps.R" 2>&1 | tee "$logs/r-packages.log"
commit="$(git -C "$repo" rev-parse HEAD)"; rc_url="https://github.com/AliSalman-et-al/rc-metastudio/archive/$commit.tar.gz"; rc_archive="$work/rc-metastudio-$commit.tar.gz"
curl --fail --location --proto '=https' --tlsv1.2 "$rc_url" --output "$rc_archive"
mkdir "$work/rc-source"; tar -xzf "$rc_archive" -C "$work/rc-source"; rc_package="$(find "$work/rc-source" -path '*/r/RCMetaR/DESCRIPTION' -print -quit | xargs dirname)"
"$rscript" "$repo/scripts/install-rcmetar-source.R" "$rc_package" "$library" 2>&1 | tee "$logs/rcmetar.log"
profile="$work/runtime-profile.json"
"$python" "$repo/scripts/profile_macos_embedded_r_runtime.py" --resources "$staged_home" --evidence "$profile" --dependency-manifest "$repo/config/r-dependencies.json" --r-version 4.6.1 --architecture "$arch" --source-resources "$r_home"
"$python" "$repo/scripts/relocate_macos_r_kit.py" --framework "$stage" --source-resources "$r_home" --version 4.6
"$python" - "$staged_home/bin/R" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
replacements = {
    'R_HOME_DIR="/Library/Frameworks/R.framework/Resources"':
        'R_HOME_DIR="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"',
    'R_SHARE_DIR="/Library/Frameworks/R.framework/Resources/share"':
        'R_SHARE_DIR="${R_HOME_DIR}/share"',
    'R_INCLUDE_DIR="/Library/Frameworks/R.framework/Resources/include"':
        'R_INCLUDE_DIR="${R_HOME_DIR}/include"',
    'R_DOC_DIR="/Library/Frameworks/R.framework/Resources/doc"':
        'R_DOC_DIR="${R_HOME_DIR}/doc"',
}
for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f"official R launcher is missing expected path: {old}")
    text = text.replace(old, new)
path.write_text(text)
PY
rm -f "$staged_home/bin/Rscript"
cat > "$staged_home/bin/Rscript" <<'SH'
#!/bin/sh
set -eu
R_HOME="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
export R_HOME R_SHARE_DIR="$R_HOME/share" R_INCLUDE_DIR="$R_HOME/include" R_DOC_DIR="$R_HOME/doc"
exec "$R_HOME/bin/exec/R" --no-echo --no-restore "$@"
SH
chmod +x "$staged_home/bin/Rscript"
if grep -aE '/Library/Frameworks/R\.framework/.*/Resources|/Library/Frameworks/R\.framework/Resources' "$staged_home/bin/R" "$staged_home/bin/Rscript"; then
  echo 'Relocatable R launchers retain the source framework path.' >&2
  exit 1
fi
export RPY2_CFFI_MODE=API
uv pip install --python "$python" --reinstall "$rpy2_rinterface_sdist" 2>&1 | tee "$logs/rpy2.log"
platlib="$($python -c 'import sysconfig; print(sysconfig.get_paths()["platlib"])')"; bridge="$(find "$platlib" -name '_rinterface_cffi_api*.so' -print -quit)"; test -n "$bridge"
"$python" "$repo/scripts/index_r_binary_archives.py" --archives "$archives" --contrib-url "https://packagemanager.posit.co/cran/2026-07-16/$contrib" --package-type "$package_type" --library "$library" --output "$work/ppm-index.json"
"$python" "$repo/scripts/create_r_kit_provenance.py" --target "$target" --official-r-artifact "$official_artifact" --official-r-url "$official_url" --official-r-signature-identity "$signature" --official-r-artifact-type pkg --ppm-index "$work/ppm-index.json" --ppm-archive-root "$archives" --hsroc-archive "$RCMS_HSROC_ARCHIVE" --hsroc-url https://cran.r-project.org/src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz --hsroc-build-log "$logs/r-packages.log" --rcmetar-archive "$rc_archive" --rcmetar-url "$rc_url" --rcmetar-build-log "$logs/rcmetar.log" --rpy2-sdist "$rpy2_sdist" --rpy2-sdist-url "$rpy2_url" --rpy2-rinterface-sdist "$rpy2_rinterface_sdist" --rpy2-rinterface-sdist-url "$rpy2_rinterface_url" --rpy2-robjects-sdist "$rpy2_robjects_sdist" --rpy2-robjects-sdist-url "$rpy2_robjects_url" --rpy2-build-log "$logs/rpy2.log" --rpy2-api-bridge "$bridge" --toolchain "R 4.6.1; Python 3.11.9; clang; uv" --output "$work/provenance.json"
source_payload="$work/source-payload"; mkdir -p "$source_payload"
cp "$RCMS_HSROC_ARCHIVE" "$rc_archive" "$rpy2_sdist" "$rpy2_rinterface_sdist" "$rpy2_robjects_sdist" "$source_payload/"
lock="$($python "$repo/scripts/r_dependency_policy.py" --sha256 "$repo/config/r-dependencies.json")"
uv_lock_hash="$(shasum -a 256 "$repo/uv.lock" | awk '{print $1}')"
uv_cache="$(uv cache dir)"
"$python" "$repo/scripts/r_integration_kit.py" build --target "$target" --runtime "$stage" --library "$library" --api-bridge "$bridge" --output "$output" --provenance-manifest "$work/provenance.json" --runtime-profile "$profile" --package-lock-sha256 "$lock" --source-commit "$commit" --uv-cache "$uv_cache" --uv-lock "$repo/uv.lock" --uv-lock-sha256 "$uv_lock_hash" --source-payload "$source_payload"
