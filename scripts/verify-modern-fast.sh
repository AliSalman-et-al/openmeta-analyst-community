#!/usr/bin/env bash
set -euo pipefail

recreate_venv=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --recreate-venv)
      recreate_venv=1
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

step() {
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$1"
}

cd "$repo_root"

if [ "$recreate_venv" -eq 1 ] && [ -d "$venv_root" ]; then
  step "Removing existing uv environment at .venv"
  rm -rf "$venv_root"
fi

step "Syncing locked modern environment with uv"
uv sync --locked

step "Validating Comprehensive Golden Baseline manifests"
uv run python scripts/validate_golden_baseline_manifests.py

step "Checking modern test taxonomy"
uv run python scripts/validate_test_taxonomy.py

step "Running fast pytest lanes"
uv run pytest tests/modern -m "fast or golden or packaging_contract"

step "Verifying Default R Evidence"
uv run python scripts/verify_openmetar_r_default.py

step "Fast Verification Lane complete"
