#!/usr/bin/env bash
set -euo pipefail

architecture=""
artifact_name=""
archive_root_name=""
r_package_cache_root=""
r_runtime_root="${RCMS_R_HOME:-${R_HOME:-}}"
recreate_venv=0
skip_tests=0
skip_clean=0
skip_smoke=0
capture_adaptive_layout_evidence=0
bundle_identifier="org.researchconsultancy.rc-metastudio"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --architecture)
      architecture="$2"
      shift 2
      ;;
    --artifact-name)
      artifact_name="$2"
      shift 2
      ;;
    --archive-root-name)
      archive_root_name="$2"
      shift 2
      ;;
    --r-package-cache-root)
      r_package_cache_root="$2"
      shift 2
      ;;
    --r-runtime-root)
      r_runtime_root="$2"
      shift 2
      ;;
    --bundle-identifier)
      bundle_identifier="$2"
      shift 2
      ;;
    --recreate-venv)
      recreate_venv=1
      shift
      ;;
    --skip-tests)
      skip_tests=1
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
venv_root="$repo_root/.venv"
python_exe="$venv_root/bin/python"
r_package_cache_root="${r_package_cache_root:-$repo_root/artifacts/r-library-cache}"

step() {
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$1"
}

if [ "$(uname -s)" != "Darwin" ]; then
  echo "package-macos.sh must run on macOS." >&2
  exit 1
fi

case "${architecture:-}" in
  x64)
    default_artifact="RCMetaStudio-macos-x64"
    ;;
  arm64)
    default_artifact="RCMetaStudio-macos-arm64"
    ;;
  "")
    echo "--architecture is required and must be x64 or arm64." >&2
    exit 2
    ;;
  *)
    echo "--architecture must be x64 or arm64." >&2
    exit 2
    ;;
esac

artifact_name="${artifact_name:-$default_artifact}"

if [ -z "$r_runtime_root" ]; then
  r_runtime_root="$(R RHOME)"
fi
if [ -z "$r_runtime_root" ] || [ ! -d "$r_runtime_root" ]; then
  echo "No source R runtime was found. Pass --r-runtime-root or set RCMS_R_HOME/R_HOME." >&2
  exit 1
fi
r_runtime_root="$(cd "$r_runtime_root" && pwd -P)"

cd "$repo_root"

if [ "$recreate_venv" -eq 1 ] && [ -d "$venv_root" ]; then
  step "Removing existing uv environment at .venv"
  rm -rf "$venv_root"
fi

step "Syncing locked verification environment with uv"
uv sync --locked

if [ "$skip_tests" -eq 0 ]; then
  step "Running shared release-package verification"
  "$python_exe" scripts/verify_package_release.py \
    --rscript "$r_runtime_root/bin/Rscript" \
    --r-library-cache-root "$r_package_cache_root"
fi

build_args=(
  --architecture "$architecture"
  --artifact-name "$artifact_name"
  --bundle-identifier "$bundle_identifier"
  --python-exe "$python_exe"
  --r-runtime-root "$r_runtime_root"
  --r-package-cache-root "$r_package_cache_root"
  --skip-dependency-install
)
if [ -n "$archive_root_name" ]; then
  build_args+=(--archive-root-name "$archive_root_name")
fi
if [ "$skip_clean" -eq 1 ]; then
  build_args+=(--skip-clean)
fi
if [ "$skip_smoke" -eq 1 ]; then
  build_args+=(--skip-smoke)
fi
if [ "$capture_adaptive_layout_evidence" -eq 1 ]; then
  build_args+=(--capture-adaptive-layout-evidence)
fi

step "Building ad-hoc macOS package artifact"
bash "$repo_root/scripts/build-macos-package.sh" "${build_args[@]}"
step "macOS package complete: artifacts/$artifact_name.zip"
