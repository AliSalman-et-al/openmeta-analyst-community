#!/usr/bin/env bash
set -euo pipefail

architecture=""
artifact_name=""
archive_root_name=""
recreate_venv=0
skip_clean=0
skip_smoke=0
capture_adaptive_layout_evidence=0
bundle_identifier="org.researchconsultancy.rc-metastudio"
r_integration_kit=""
expected_r_integration_kit_sha256=""

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
    --r-integration-kit)
      r_integration_kit="$2"
      shift 2
      ;;
    --expected-r-integration-kit-sha256)
      expected_r_integration_kit_sha256="$2"
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
if [ -z "$r_integration_kit" ] || [ -z "$expected_r_integration_kit_sha256" ]; then
  echo "Package assembly requires --r-integration-kit and --expected-r-integration-kit-sha256 from the native producer." >&2
  exit 2
fi

cd "$repo_root"

if [ "$recreate_venv" -eq 1 ] && [ -d "$venv_root" ]; then
  step "Removing existing uv environment at .venv"
  rm -rf "$venv_root"
fi

step "Authenticating the promoted kit before offline environment assembly"
uv run --no-project --offline --python 3.11.9 python scripts/r_integration_kit.py verify-content \
  --kit "$r_integration_kit" --target "macos-$architecture" --uv-lock uv.lock \
  --expected-kit-sha256 "$expected_r_integration_kit_sha256"
step "Syncing locked verification environment from the authenticated kit cache"
uv --cache-dir "$r_integration_kit/python/uv-cache" sync --locked --offline

build_args=(
  --architecture "$architecture"
  --artifact-name "$artifact_name"
  --bundle-identifier "$bundle_identifier"
  --python-exe "$python_exe"
  --skip-dependency-install
)
build_args+=(--r-integration-kit "$r_integration_kit" --expected-r-integration-kit-sha256 "$expected_r_integration_kit_sha256")
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
