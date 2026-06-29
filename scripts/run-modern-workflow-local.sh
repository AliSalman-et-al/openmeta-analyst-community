#!/usr/bin/env bash
set -euo pipefail

target="macos"
artifact_name=""
recreate_venv=0
skip_tests=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      target="$2"
      shift 2
      ;;
    --artifact-name)
      artifact_name="$2"
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
  echo "run-modern-workflow-local.sh currently supports macOS targets. Use run-modern-workflow-local.ps1 on Windows." >&2
  exit 1
fi

case "$target" in
  macos|macos-intel|macos-x64)
    architecture="x64"
    default_artifact="OpenMetaAnalyst-modern-macos-x64"
    ;;
  macos-arm64|macos-apple-silicon)
    architecture="arm64"
    default_artifact="OpenMetaAnalyst-modern-macos-arm64"
    ;;
  *)
    echo "--target must be macos, macos-intel, macos-x64, macos-arm64, or macos-apple-silicon." >&2
    exit 2
    ;;
esac

artifact_name="${artifact_name:-$default_artifact}"

cd "$repo_root"

if [ "$recreate_venv" -eq 1 ] && [ -d "$venv_root" ]; then
  step "Removing existing uv environment at .venv"
  rm -rf "$venv_root"
fi

step "Syncing locked modern environment with uv"
uv sync --locked

if [ "$skip_tests" -eq 0 ]; then
  step "Running modern full-app automation tests"
  uv run pytest tests/modern/test_metaform_automation_launch.py

  step "Running remaining modern pytest suite"
  uv run pytest tests/modern --ignore=tests/modern/test_metaform_automation_launch.py
fi

step "Building modern macOS artifact with PyInstaller"
bash "$repo_root/scripts/build-modern-macos-binary.sh" \
  --architecture "$architecture" \
  --artifact-name "$artifact_name" \
  --python-exe "$python_exe" \
  --skip-dependency-install

step "Modern macOS workflow complete: artifacts/$artifact_name.zip"
