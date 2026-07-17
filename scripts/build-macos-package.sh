#!/usr/bin/env bash
set -euo pipefail

artifact_name=""
archive_root_name=""
architecture=""
python_exe=""
r_runtime_root="${RCMS_R_HOME:-${R_HOME:-}}"
r_package_cache_root=""
bundle_identifier="org.researchconsultancy.rc-metastudio"
skip_dependency_install=0
skip_clean=0
skip_smoke=0
capture_adaptive_layout_evidence=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --artifact-name)
      artifact_name="$2"
      shift 2
      ;;
    --archive-root-name)
      archive_root_name="$2"
      shift 2
      ;;
    --architecture)
      architecture="$2"
      shift 2
      ;;
    --python-exe)
      python_exe="$2"
      shift 2
      ;;
    --r-runtime-root)
      r_runtime_root="$2"
      shift 2
      ;;
    --r-package-cache-root)
      r_package_cache_root="$2"
      shift 2
      ;;
    --bundle-identifier)
      bundle_identifier="$2"
      shift 2
      ;;
    --skip-dependency-install)
      skip_dependency_install=1
      shift
      ;;
    --skip-clean)
      skip_clean=1
      shift
      ;;
    --skip-smoke)
      skip_smoke=1
      shift
      ;;
    --capture-adaptive-layout-evidence)
      capture_adaptive_layout_evidence=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
artifact_dir="$repo_root/artifacts"

step() {
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$1"
}

require_free_space_gb() {
  local path="$1"
  local required_gb="$2"
  local available_kb
  available_kb="$(df -Pk "$path" | awk 'NR==2 {print $4}')"
  local required_kb=$((required_gb * 1024 * 1024))
  if [ -z "$available_kb" ] || [ "$available_kb" -lt "$required_kb" ]; then
    echo "At least ${required_gb}GB of free disk space is required under $path." >&2
    df -h "$path" >&2 || true
    exit 1
  fi
}

repo_path() {
  local path="$1"
  case "$path" in
    /*)
      printf '%s\n' "$path"
      ;;
    */*)
      printf '%s\n' "$repo_root/$path"
      ;;
    *)
      if command -v "$path" >/dev/null 2>&1; then
        command -v "$path"
      else
        echo "Command was not found on PATH: $path" >&2
        exit 1
      fi
      ;;
  esac
}

project_version() {
  "$python_exe" - "$repo_root/pyproject.toml" <<'PY'
import pathlib
import sys
import tomllib

print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["project"]["version"])
PY
}

resolve_existing_dir() {
  local path="$1"
  local description="$2"
  if [ -z "$path" ] || [ ! -d "$path" ]; then
    echo "$description was not found at $path." >&2
    exit 1
  fi
  (cd "$path" && pwd -P)
}

copy_tree() {
  local source="$1"
  local destination="$2"
  if [ ! -d "$source" ]; then
    echo "Source directory was not found: $source" >&2
    exit 1
  fi
  rm -rf "$destination"
  mkdir -p "$(dirname "$destination")"
  if command -v rsync >/dev/null 2>&1; then
    mkdir -p "$destination"
    rsync -a --delete "$source"/ "$destination"/
  else
    mkdir -p "$destination"
    (cd "$source" && tar -cf - .) | (cd "$destination" && tar -xf -)
  fi
}

if [ "$(uname -s)" != "Darwin" ]; then
  echo "macOS packaging must run on macOS." >&2
  exit 1
fi

host_machine="$(uname -m)"
case "${architecture:-}" in
  x64)
    expected_machine="x86_64"
    pyinstaller_target_architecture="x86_64"
    default_artifact="RCMetaStudio-macos-x64"
    ;;
  arm64)
    expected_machine="arm64"
    pyinstaller_target_architecture="arm64"
    default_artifact="RCMetaStudio-macos-arm64"
    ;;
  "")
    if [ "$host_machine" = "arm64" ]; then
      architecture="arm64"
      expected_machine="arm64"
      pyinstaller_target_architecture="arm64"
      default_artifact="RCMetaStudio-macos-arm64"
    else
      architecture="x64"
      expected_machine="x86_64"
      pyinstaller_target_architecture="x86_64"
      default_artifact="RCMetaStudio-macos-x64"
    fi
    ;;
  *)
    echo "--architecture must be x64 or arm64." >&2
    exit 1
    ;;
esac

if [ "$host_machine" != "$expected_machine" ]; then
  echo "Requested $architecture build requires $expected_machine host, but this host is $host_machine." >&2
  exit 1
fi

artifact_name="${artifact_name:-$default_artifact}"
dist_root="$repo_root/build/macos-package/$architecture/dist"
work_root="$repo_root/build/macos-package/$architecture/work"
app_bundle="$dist_root/RCMetaStudio.app"
app_root="$app_bundle/Contents/MacOS"
archive_staging_root="$work_root/zip-staging"
zip_path="$artifact_dir/$artifact_name.zip"
tmp_zip_path="$zip_path.tmp"
qualification_root="$work_root/qualification"
runtime_probe_path="$qualification_root/runtime-probe.json"
deployment_manifest_path="$qualification_root/deployment-manifest.json"
smoke_evidence_path="$qualification_root/packaged-smoke.json"
smoke_log_path="$qualification_root/packaged-smoke.log"
smoke_stdout_path="$qualification_root/packaged-smoke.stdout.log"
smoke_stderr_path="$qualification_root/packaged-smoke.stderr.log"
hang_trace_path="$qualification_root/packaged-smoke.hang-trace.log"
launchservices_marker_path="$qualification_root/launchservices-completion.json"
launchservices_pid_path="$qualification_root/launchservices.pid"
archive_inspection_path="$artifact_dir/$artifact_name-archive-inspection.json"
qualification_evidence_path="$artifact_dir/$artifact_name-evidence.json"
r_package_cache_root="${r_package_cache_root:-$artifact_dir/r-library-cache}"
pinned_cran_repo="https://packagemanager.posit.co/cran/2026-07-16"
cran_repo="${RCMS_CRAN_REPO:-$pinned_cran_repo}"
if [ "$cran_repo" != "$pinned_cran_repo" ]; then
  echo "RCMS_CRAN_REPO must match the manifest snapshot: $pinned_cran_repo" >&2
  exit 1
fi
export RCMS_CRAN_REPO="$pinned_cran_repo"

if [ "$skip_dependency_install" -eq 0 ]; then
  step "Syncing locked verification environment"
  (cd "$repo_root" && uv sync --locked)
  python_exe="$repo_root/.venv/bin/python"
fi

python_exe="${python_exe:-$repo_root/.venv/bin/python}"
python_exe="$(repo_path "$python_exe")"
if [ ! -x "$python_exe" ]; then
  echo "Python executable was not found or is not executable: $python_exe" >&2
  exit 1
fi

resolved_project_version="$(project_version)"
archive_root_name="${archive_root_name:-RCMetaStudio-$resolved_project_version-macos-$architecture}"
"$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" validate-root \
  --archive-root-name "$archive_root_name"
archive_root_dir="$archive_staging_root/$archive_root_name"

"$python_exe" - <<'PY'
import PyInstaller
import sys
if sys.version_info[:2] != (3, 11):
    raise SystemExit("macOS packaging requires Python 3.11.")
if PyInstaller.__version__ != "6.21.0":
    raise SystemExit("macOS packaging requires PyInstaller 6.21.0.")
PY

if [ -z "$r_runtime_root" ]; then
  r_runtime_root="$(R RHOME)"
fi
if [ -z "$r_runtime_root" ]; then
  echo "No source R runtime was found. Pass --r-runtime-root or set RCMS_R_HOME/R_HOME." >&2
  exit 1
fi
r_runtime_root="$(resolve_existing_dir "$r_runtime_root" "Source R runtime")"
if [ ! -d "$r_runtime_root/bin" ]; then
  echo "Source R runtime is missing bin under $r_runtime_root." >&2
  exit 1
fi

if [ "$skip_clean" -eq 0 ]; then
  rm -rf "$dist_root" "$work_root"
fi
rm -rf "$qualification_root"
rm -rf "$zip_path" "$tmp_zip_path" "$archive_inspection_path" "$qualification_evidence_path"
mkdir -p "$artifact_dir"
mkdir -p "$qualification_root"
require_free_space_gb "$repo_root" 6

(
  cd "$repo_root"
  qt6_package_build_root="$work_root/qt6-input"
  "$python_exe" scripts/build_qt6.py generate --build-root "$qt6_package_build_root"
  export RCMS_QT6_BUILD_ROOT="$qt6_package_build_root"
  export RCMS_BUNDLE_IDENTIFIER="$bundle_identifier"
  export RCMS_PROJECT_VERSION="$resolved_project_version"
  export RCMS_TARGET_ARCHITECTURE="$pyinstaller_target_architecture"
  export RPY2_CFFI_MODE=ABI
  pyinstaller_args=(
    --noconfirm
    --distpath "$dist_root"
    --workpath "$work_root"
    "packaging/pyinstaller/rc-metastudio-macos.spec"
  )
  if [ "$skip_clean" -eq 0 ]; then
    pyinstaller_args=(--clean "${pyinstaller_args[@]}")
  fi
  # The spec is the sole collection definition. This wrapper supplies only
  # deterministic build/output roots and the locked generated Qt inputs.
  step "Building ad-hoc macOS app bundle with the authoritative PyInstaller spec"
  R_HOME="$r_runtime_root" RPY2_CFFI_MODE=ABI "$python_exe" -m PyInstaller "${pyinstaller_args[@]}"
)

if [ ! -x "$app_root/RCMetaStudio" ]; then
  echo "RCMetaStudio executable was not created at $app_root/RCMetaStudio." >&2
  exit 1
fi

step "Bundling sample projects and R runtime"
copy_tree "$repo_root/sample_projects" "$app_root/sample_projects"
copy_tree "$r_runtime_root" "$app_root/R"

r_home="$app_root/R"
r_lib="$r_home/library"
rscript="$r_home/bin/Rscript"
r_binary="$r_home/bin/R"

if [ ! -x "$rscript" ] || [ ! -x "$r_binary" ]; then
  echo "Bundled R runtime is missing R or Rscript under $r_home/bin." >&2
  exit 1
fi

relocate_bundled_r_runtime() {
  local binary dylib_id dependency source_relative target loader_dir relative_target
  local macho_manifest="$work_root/bundled-r-mach-o-files.list"

  # Spawning `file` for every file in a complete R installation is extremely
  # expensive on GitHub's macOS runners. Scan the tree once in one process,
  # using the Mach-O and universal-binary magic numbers, then reuse the
  # resulting NUL-delimited manifest for both mutation and verification.
  "$python_exe" - "$r_home" > "$macho_manifest" <<'PY'
import os
from pathlib import Path
import stat
import sys

MACH_O_MAGICS = {
    b"\xfe\xed\xfa\xce",  # MH_MAGIC
    b"\xce\xfa\xed\xfe",  # MH_CIGAM
    b"\xfe\xed\xfa\xcf",  # MH_MAGIC_64
    b"\xcf\xfa\xed\xfe",  # MH_CIGAM_64
    b"\xca\xfe\xba\xbe",  # FAT_MAGIC
    b"\xbe\xba\xfe\xca",  # FAT_CIGAM
    b"\xca\xfe\xba\xbf",  # FAT_MAGIC_64
    b"\xbf\xba\xfe\xca",  # FAT_CIGAM_64
}

root = Path(sys.argv[1])
for directory, _, filenames in os.walk(root):
    for filename in filenames:
        path = Path(directory, filename)
        if not stat.S_ISREG(path.lstat().st_mode):
            continue
        with path.open("rb") as handle:
            if handle.read(4) in MACH_O_MAGICS:
                sys.stdout.buffer.write(os.fsencode(path) + b"\0")
PY

  local macho_count=0
  while IFS= read -r -d '' binary; do
    macho_count=$((macho_count + 1))
    dylib_id="$(otool -D "$binary" 2>/dev/null | awk 'NR > 1 && $1 ~ /^\// { print $1; exit }' || true)"
    case "$dylib_id" in
      "$r_runtime_root"/*)
        source_relative="${dylib_id#"$r_runtime_root"/}"
        install_name_tool -id "@rpath/$source_relative" "$binary"
        ;;
      /Library/Frameworks/R.framework/Versions/*/Resources/*)
        source_relative="${dylib_id#*/Resources/}"
        install_name_tool -id "@rpath/$source_relative" "$binary"
        ;;
    esac
    while IFS= read -r dependency; do
      case "$dependency" in
        "$r_runtime_root"/*)
          source_relative="${dependency#"$r_runtime_root"/}"
          ;;
        /Library/Frameworks/R.framework/Versions/*/Resources/*)
          source_relative="${dependency#*/Resources/}"
          ;;
        *)
          continue
          ;;
      esac
      target="$r_home/$source_relative"
      if [ ! -e "$target" ]; then
        echo "Bundled R dependency target is missing for $binary: $dependency" >&2
        exit 1
      fi
      loader_dir="$(dirname "$binary")"
      relative_target="$("$python_exe" - "$loader_dir" "$target" <<'PY'
import os
import sys
print(os.path.relpath(sys.argv[2], sys.argv[1]))
PY
)"
      install_name_tool -change "$dependency" "@loader_path/$relative_target" "$binary"
    done < <(otool -L "$binary" | awk 'NR > 1 { print $1 }')
  done < "$macho_manifest"

  local dependency_report
  dependency_report="$(while IFS= read -r -d '' binary; do
    otool -L "$binary"
  done < "$macho_manifest")"
  if printf '%s\n' "$dependency_report" | grep -F "$r_runtime_root/" \
    || printf '%s\n' "$dependency_report" | grep -E '/Library/Frameworks/R\.framework/.*/Resources|R\.framework/Resources'; then
    echo "Bundled R runtime retains an absolute source-framework dependency." >&2
    exit 1
  fi
  echo "Relocated and verified $macho_count bundled R Mach-O files."
}

configure_relocatable_r_launchers() {
  "$python_exe" - "$r_binary" <<'PY'
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
        raise SystemExit(f"Bundled R launcher is missing expected path: {old}")
    text = text.replace(old, new)
path.write_text(text)
PY

  rm -f "$rscript"
  cat > "$rscript" <<'SH'
#!/bin/sh
set -eu
R_HOME="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
export R_HOME
export R_SHARE_DIR="$R_HOME/share"
export R_INCLUDE_DIR="$R_HOME/include"
export R_DOC_DIR="$R_HOME/doc"
exec "$R_HOME/bin/exec/R" --no-echo --no-restore "$@"
SH
  chmod +x "$rscript"

  if grep -aE '/Library/Frameworks/R\.framework/.*/Resources|/Library/Frameworks/R\.framework/Resources' "$r_binary" "$rscript"; then
    echo "Bundled R launchers retain an absolute source-framework path." >&2
    exit 1
  fi
}

r_version_cache_key="$("$rscript" -e "cat(paste0('R-', getRversion()))")"
sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

sha256_stdin_12() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print substr($1, 1, 12)}'
  else
    shasum -a 256 | awk '{print substr($1, 1, 12)}'
  fi
}

r_dependency_policy_hash="$({
  printf '%s' "$(sha256_file "$repo_root/scripts/install-r-deps.R")"
  printf '%s' "$(sha256_file "$repo_root/scripts/r_binary_policy.R")"
  printf '%s' "$(sha256_file "$repo_root/scripts/r_dependency_policy.py")"
  printf '%s' "$(sha256_file "$repo_root/docs/verification/RCMetaR-r-dependencies.json")"
  printf '%s' "$(sha256_file "$repo_root/r/RCMetaR/DESCRIPTION")"
  printf '%s' "$RCMS_CRAN_REPO"
} | sha256_stdin_12)"
r_package_cache_key="${r_version_cache_key}-${architecture}-rdeps-v2-${r_dependency_policy_hash}"
cache_library="$r_package_cache_root/$r_package_cache_key/library"

test_r_dependency_packages() {
  local library="$1"
  [ -d "$library" ] || return 1
  R_HOME="$r_home" R_LIBS="$library" R_LIBS_USER="$library" "$rscript" -e "lib <- normalizePath('$library', winslash='/'); .libPaths(c(lib, .libPaths())); pkgs <- c('HSROC','metafor','lme4','pdftools','rsvg','svglite','tiff','xml2','igraph','mice','Hmisc'); ok <- vapply(pkgs, requireNamespace, logical(1), quietly=TRUE); if (!all(ok)) quit(status=1); if (as.character(packageVersion('HSROC')) != '2.1.9') quit(status=1)" >/dev/null 2>&1
}

run_strict_r_dependency_policy() {
  local library="$1"
  mkdir -p "$library"
  R_HOME="$r_home" R_LIBS="$library" R_LIBS_USER="$library" \
    RCMS_CRAN_REPO="$pinned_cran_repo" RCMS_POLICY_PYTHON="$python_exe" \
    "$rscript" "$repo_root/scripts/install-r-deps.R"
}

test_bundled_r_packages() {
  local library="$1"
  [ -d "$library" ] || return 1
  R_HOME="$r_home" R_LIBS="$library" R_LIBS_USER="$library" "$rscript" -e "lib <- normalizePath('$library', winslash='/'); .libPaths(c(lib, .libPaths())); pkgs <- c('HSROC','RCMetaR','metafor','lme4','pdftools','rsvg','svglite','tiff','xml2','igraph','mice','Hmisc'); ok <- vapply(pkgs, requireNamespace, logical(1), quietly=TRUE); if (!all(ok)) quit(status=1); if (as.character(packageVersion('HSROC')) != '2.1.9') quit(status=1)" >/dev/null 2>&1
}

copy_r_library() {
  local source="$1"
  local destination="$2"
  copy_tree "$source" "$destination"
}

copy_r_library_packages() {
  local source="$1"
  local destination="$2"
  if [ ! -d "$source" ]; then
    echo "Source R library was not found: $source" >&2
    exit 1
  fi
  mkdir -p "$destination"
  for package in "$source"/*; do
    [ -d "$package" ] || continue
    copy_tree "$package" "$destination/$(basename "$package")"
  done
}

install_local_r_packages() {
  local package_build_root="$work_root/r-package-build"
  rm -rf "$package_build_root"
  mkdir -p "$package_build_root"
  cp -R "$repo_root/r/RCMetaR" "$package_build_root/RCMetaR"
  find "$package_build_root" \( -name '*.o' -o -name '*.so' -o -name '*.dll' \) -delete

  R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" "$r_binary" CMD INSTALL --library="$r_lib" "$package_build_root/RCMetaR"
}

if [ -d "$cache_library" ]; then
  step "Validating cached bundled R dependencies with the strict shared policy"
  run_strict_r_dependency_policy "$cache_library"
  echo "Using cached bundled R library from $cache_library"
  copy_r_library_packages "$cache_library" "$r_lib"
else
  step "Installing bundled R package dependencies"
  run_strict_r_dependency_policy "$r_lib"
  if test_r_dependency_packages "$r_lib"; then
    echo "Caching bundled R dependency library at $cache_library"
    copy_r_library "$r_lib" "$cache_library"
  fi
fi

step "Installing local RCMetaR package"
install_local_r_packages
R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" "$rscript" -e "pkgs <- c('HSROC','RCMetaR','metafor','lme4','pdftools','rsvg','svglite','tiff','xml2','igraph','mice','Hmisc'); ok <- vapply(pkgs, require, logical(1), character.only=TRUE); print(ok); if (!all(ok)) quit(status=1); if (as.character(packageVersion('HSROC')) != '2.1.9') quit(status=1)"

if ! test_bundled_r_packages "$r_lib"; then
  echo "Bundled R package verification failed after local RCMetaR install." >&2
  exit 1
fi

step "Configuring relocatable bundled R launchers"
configure_relocatable_r_launchers
step "Relocating completed bundled R runtime dependencies"
relocate_bundled_r_runtime

cat > "$app_root/LaunchRCMetaStudio.command" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export RPY2_CFFI_MODE=ABI
export RCMS_R_HOME="$APP_DIR/R"
export RCMS_R_LIBS="$APP_DIR/R/library"
exec "$APP_DIR/RCMetaStudio" "$APP_DIR/sample_projects/amino.rcms"
SH
chmod +x "$app_root/LaunchRCMetaStudio.command"

for required_path in \
  "$app_root/RCMetaStudio" \
  "$app_root/sample_projects/BCG.rcms" \
  "$app_root/sample_projects/amino.rcms" \
  "$app_root/R/bin/Rscript" \
  "$app_root/R/library/RCMetaR/DESCRIPTION" \
  "$app_root/LaunchRCMetaStudio.command"
do
  if [ ! -e "$required_path" ]; then
    echo "Packaged macOS app is missing $required_path." >&2
    exit 1
  fi
done

run_adaptive_layout_evidence() {
  local evidence_root="$repo_root/build/macos-package/$architecture/adaptive-layout-evidence/macos-$architecture"
  local sample_path="$app_root/sample_projects/amino.rcms"
  rm -rf "$evidence_root"
  mkdir -p "$evidence_root"
  for scale in "1.0" "1.5"; do
    local scale_label
    case "$scale" in
      1.0) scale_label="100" ;;
      1.5) scale_label="150" ;;
      *) echo "Unsupported adaptive-layout evidence scale: $scale" >&2; exit 2 ;;
    esac
    local output_dir="$evidence_root/scale-$scale_label"
    local log_path="$output_dir/automation-adaptive-layout-evidence.log"
    mkdir -p "$output_dir"
    env -u QT_QPA_PLATFORM \
      QT_SCALE_FACTOR="$scale" \
      RCMS_REQUIRE_IN_PROCESS_RPY2=1 \
      RCMS_ADAPTIVE_LAYOUT_EVIDENCE_LOG="$log_path" \
      RPY2_CFFI_MODE=ABI \
      RCMS_R_HOME="$r_home" \
      RCMS_R_LIBS="$r_lib" \
      "$app_root/RCMetaStudio" \
        --automation-adaptive-layout-evidence "$output_dir" "$sample_path"
    "$python_exe" "$repo_root/scripts/validate_adaptive_layout_evidence.py" \
      --root "$output_dir" --platform-plugin cocoa --scale-factor "$scale"
  done
}

run_packaged_process() {
  env -u QT_QPA_PLATFORM \
    RCMS_REQUIRE_IN_PROCESS_RPY2=1 \
    RPY2_CFFI_MODE=ABI \
    RCMS_R_HOME="$r_home" \
    RCMS_R_LIBS="$r_lib" \
    "$python_exe" "$repo_root/scripts/run_bounded_process.py" \
      --timeout-seconds 900 \
      --stdout "$smoke_stdout_path" \
      --stderr "$smoke_stderr_path" \
      -- "$@"
}

step "Applying and verifying the replaceable ad-hoc app-bundle signature"
codesign --force --deep --options runtime --sign - "$app_bundle"
codesign --verify --deep --strict --verbose=2 "$app_bundle"

step "Probing the frozen macOS runtime"
RCMS_AUTOMATION_SMOKE_LOG="$smoke_log_path" \
  run_packaged_process "$app_root/RCMetaStudio" \
    --automation-package-runtime-probe "$runtime_probe_path"
if [ ! -s "$runtime_probe_path" ]; then
  echo "Frozen macOS runtime probe did not produce evidence." >&2
  exit 1
fi

if [ "$skip_smoke" -eq 0 ]; then
  sample_path="$app_root/sample_projects/amino.rcms"
  baseline_dpr="$("$python_exe" - "$runtime_probe_path" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["qt"]["baseline_device_pixel_ratio"])
PY
)"
  step "Running packaged macOS workflow smoke"
  QT_SCALE_FACTOR=1.25 \
    RCMS_PACKAGE_BASELINE_DPR="$baseline_dpr" \
    RCMS_PACKAGE_SMOKE_EVIDENCE="$smoke_evidence_path" \
    RCMS_AUTOMATION_SMOKE_LOG="$smoke_log_path" \
    RCMS_AUTOMATION_HANG_TRACE="$hang_trace_path" \
    run_packaged_process "$app_root/RCMetaStudio" --automation-native-smoke "$sample_path"

  for scale in "1.25" "1.50" "1.75"; do
    step "Running packaged Cocoa surface smoke at scale $scale"
    QT_SCALE_FACTOR="$scale" \
      RCMS_PACKAGE_BASELINE_DPR="$baseline_dpr" \
      RCMS_AUTOMATION_SMOKE_LOG="$smoke_log_path" \
      run_packaged_process "$app_root/RCMetaStudio" \
        --automation-package-surface-smoke "$smoke_evidence_path" "$scale"
  done

  step "Opening the converted sample through the normal LaunchServices app entry point"
  rm -f "$launchservices_marker_path" "$launchservices_pid_path"
  env -u QT_QPA_PLATFORM \
    RCMS_REQUIRE_IN_PROCESS_RPY2=1 \
    RPY2_CFFI_MODE=ABI \
    RCMS_R_HOME="$r_home" \
    RCMS_R_LIBS="$r_lib" \
    RCMS_STARTUP_PROJECT_SMOKE=1 \
    RCMS_AUTOMATION_SMOKE_LOG="$smoke_log_path" \
    RCMS_STARTUP_COMPLETION_MARKER="$launchservices_marker_path" \
    RCMS_AUTOMATION_PID_FILE="$launchservices_pid_path" \
    "$python_exe" "$repo_root/scripts/run_bounded_process.py" \
      --timeout-seconds 900 \
      --stdout "$smoke_stdout_path" --stderr "$smoke_stderr_path" \
      --owned-pid-file "$launchservices_pid_path" \
      -- open -W -n "$app_bundle" --args \
        --automation-startup-project-smoke \
        --automation-startup-completion-marker "$launchservices_marker_path" \
        --automation-pid-file "$launchservices_pid_path" \
        --automation-smoke-log "$smoke_log_path" \
        "$sample_path"
  "$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" finalize-smoke \
    --smoke-evidence "$smoke_evidence_path" --smoke-log "$smoke_log_path" \
    --launchservices-marker "$launchservices_marker_path"
  rm -f "$launchservices_pid_path"
fi
if [ "$capture_adaptive_layout_evidence" -eq 1 ]; then
  if [ "$architecture" != "x64" ]; then
    echo "Controlled adaptive-layout evidence is supported only for macOS Intel." >&2
    exit 2
  fi
  step "Capturing controlled native macOS adaptive-layout evidence"
  run_adaptive_layout_evidence
fi

source_commit="$(git rev-parse HEAD)"
python_version="$("$python_exe" -c 'import platform; print(platform.python_version())')"
pyqt6_version="$("$python_exe" -c 'import importlib.metadata as m; print(m.version("PyQt6"))')"
qt_version="$("$python_exe" -c 'import importlib.metadata as m; print(m.version("PyQt6-Qt6"))')"
sip_version="$("$python_exe" -c 'import importlib.metadata as m; print(m.version("PyQt6-sip"))')"
sip_runtime_version="$("$python_exe" -c 'from PyQt6 import sip; print(sip.SIP_VERSION_STR)')"
rpy2_version="$("$python_exe" -c 'import importlib.metadata as m; print(m.version("rpy2"))')"
r_version="$("$rscript" -e 'cat(as.character(getRversion()))')"
locked_qt_root="$("$python_exe" -c 'from pathlib import Path; import PyQt6; print(Path(PyQt6.__file__).resolve().parent / "Qt6")')"
step "Inspecting the coherent Intel-only macOS deployment"
"$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" inspect \
  --app-root "$app_bundle" --output "$deployment_manifest_path" \
  --source-commit "$source_commit" --runtime-probe "$runtime_probe_path" \
  --locked-qt-root "$locked_qt_root" \
  --python-version "$python_version" --pyqt6-version "$pyqt6_version" \
  --qt-version "$qt_version" --sip-version "$sip_version" \
  --sip-runtime-version "$sip_runtime_version" --r-version "$r_version" \
  --rpy2-version "$rpy2_version" --pyinstaller-version 6.21.0

(
  step "Creating macOS artifact ZIP"
  rm -rf "$archive_staging_root"
  copy_tree "$app_bundle" "$archive_root_dir/RCMetaStudio.app"
  copy_tree "$qualification_root" "$archive_root_dir/qualification"
  ditto -c -k --norsrc --keepParent "$archive_root_dir" "$tmp_zip_path"
)
mv "$tmp_zip_path" "$zip_path"

python3 - "$zip_path" "$archive_root_name" "$skip_smoke" <<'PY'
import sys
import zipfile

zip_path = sys.argv[1]
archive_root_name = sys.argv[2].rstrip("/")
skip_smoke = sys.argv[3] == "1"
required = [
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/RCMetaStudio",
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/sample_projects/BCG.rcms",
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/sample_projects/amino.rcms",
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/R/bin/Rscript",
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/R/library/RCMetaR/DESCRIPTION",
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/LaunchRCMetaStudio.command",
    f"{archive_root_name}/qualification/deployment-manifest.json",
    f"{archive_root_name}/qualification/runtime-probe.json",
]
if not skip_smoke:
    required.extend([
        f"{archive_root_name}/qualification/packaged-smoke.json",
        f"{archive_root_name}/qualification/packaged-smoke.log",
        f"{archive_root_name}/qualification/launchservices-completion.json",
        f"{archive_root_name}/qualification/packaged-smoke.stdout.log",
        f"{archive_root_name}/qualification/packaged-smoke.stderr.log",
        f"{archive_root_name}/qualification/packaged-smoke.hang-trace.log",
    ])
with zipfile.ZipFile(zip_path) as archive:
    names = set(archive.namelist())
outside_root = [
    name for name in names if name and not name.startswith(f"{archive_root_name}/")
]
if outside_root:
    raise SystemExit(
        "Created ZIP has entries outside "
        f"{archive_root_name}: " + ", ".join(sorted(outside_root)[:10])
    )
missing = [path for path in required if path not in names]
if missing:
    raise SystemExit("Created ZIP is missing: " + ", ".join(missing))
PY

if [ "$skip_smoke" -eq 0 ]; then
  "$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" archive \
    --archive "$zip_path" --archive-root-name "$archive_root_name" \
    --deployment-manifest "$deployment_manifest_path" \
    --runtime-probe "$runtime_probe_path" \
    --smoke-evidence "$smoke_evidence_path" --smoke-log "$smoke_log_path" \
    --smoke-stdout "$smoke_stdout_path" --smoke-stderr "$smoke_stderr_path" \
    --hang-trace "$hang_trace_path" \
    --launchservices-marker "$launchservices_marker_path" \
    --output "$archive_inspection_path"
  "$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" evidence \
    --archive "$zip_path" --deployment-manifest "$deployment_manifest_path" \
    --runtime-probe "$runtime_probe_path" \
    --smoke-evidence "$smoke_evidence_path" --smoke-log "$smoke_log_path" \
    --smoke-stdout "$smoke_stdout_path" --smoke-stderr "$smoke_stderr_path" \
    --hang-trace "$hang_trace_path" \
    --launchservices-marker "$launchservices_marker_path" \
    --archive-inspection "$archive_inspection_path" \
    --output "$qualification_evidence_path"
fi

echo "Created $zip_path"
