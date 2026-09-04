#!/usr/bin/env bash
set -euo pipefail

architecture=""
artifact_name=""
archive_root_name=""
recreate_venv=0
skip_clean=0
skip_smoke=0
stop_after_r_substrate=0
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
    --stop-after-r-substrate)
      stop_after_r_substrate=1
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

if ! command -v uv >/dev/null 2>&1; then
  echo "macOS packaging requires uv. Install it from https://docs.astral.sh/uv/." >&2
  exit 1
fi
if ! xcode-select -p >/dev/null 2>&1 || ! command -v clang >/dev/null 2>&1; then
  echo "macOS packaging requires the Xcode Command Line Tools. Run: xcode-select --install" >&2
  exit 1
fi
macos_major="$(sw_vers -productVersion | awk -F. '{print $1}')"
if [ "$macos_major" -lt 13 ]; then
  echo "macOS packaging requires macOS 13 or later; found $(sw_vers -productVersion)." >&2
  exit 1
fi

case "${architecture:-}" in
  arm64) ;;
  "")
    echo "--architecture arm64 is required." >&2
    exit 2
    ;;
  *)
    echo "--architecture must be arm64." >&2
    exit 2
    ;;
esac

target_python="$(command -v python3 || true)"
[ -n "$target_python" ] || { echo "macOS packaging requires python3 to resolve its target manifest." >&2; exit 1; }
eval "$("$target_python" "$repo_root/scripts/resolve_macos_package_target.py" "$architecture" --format shell)"
default_artifact="$artifact"
if [ "$(uname -m)" != "$machine" ]; then
  echo "macOS $architecture packaging requires a native $machine host; found $(uname -m)." >&2
  exit 2
fi
artifact_name="${artifact_name:-$default_artifact}"

cd "$repo_root"

if [ "$recreate_venv" -eq 1 ] && [ -d "$venv_root" ]; then
  step "Removing existing uv environment at .venv"
  rm -rf "$venv_root"
fi

step "Syncing the locked Python environment"
uv python install 3.11.9
uv sync --locked

build_args=(
  --architecture "$architecture"
  --artifact-name "$artifact_name"
  --bundle-identifier "$bundle_identifier"
  --python-exe "$python_exe"
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
if [ "$stop_after_r_substrate" -eq 1 ]; then
  build_args+=(--stop-after-r-substrate)
fi

step "Building ad-hoc macOS package artifact"
bash "$repo_root/scripts/build-macos-package.sh" "${build_args[@]}"
step "macOS package complete: artifacts/$artifact_name.zip"
