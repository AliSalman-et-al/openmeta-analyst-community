#!/usr/bin/env bash
set -euo pipefail

recreate_venv=0
sync=0
require_r_evidence=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --sync)
      sync=1
      shift
      ;;
    --recreate-venv)
      recreate_venv=1
      sync=1
      shift
      ;;
    --require-r-evidence)
      require_r_evidence=1
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
r_package_cache_root="$repo_root/artifacts/r-library-cache"

step() {
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$1"
}

cd "$repo_root"

if [ "$recreate_venv" -eq 1 ] && [ -d "$venv_root" ]; then
  step "Removing existing uv environment at .venv"
  rm -rf "$venv_root"
fi

if [ "$sync" -eq 1 ]; then
  step "Syncing locked modern environment with uv"
  uv sync --locked
else
  step "Skipping dependency sync for warm local smoke verification"
fi

step "Collecting modern pytest nodes"
uv run pytest tests/modern --collect-only -q

step "Validating manifest sanity"
uv run python scripts/validate_golden_baseline_manifests.py

step "Running smoke pytest nodes"
uv run pytest \
  tests/modern/golden/test_modern_golden_compare.py::test_golden_summary_parser_reads_current_openmetar_summary_display \
  tests/modern/fast/test_project_pickle_loader.py::test_loader_opens_representative_qt4_project_without_pyqt4_module

step "Checking Default R Evidence prerequisites"
r_evidence_args=(scripts/verify_openmetar_r_default.py)
if [ "$require_r_evidence" -eq 1 ]; then
  r_evidence_args+=(--require-r --require-installed-packages --install-missing --r-library-cache-root "$r_package_cache_root")
fi
uv run python "${r_evidence_args[@]}"

step "Smoke Verification Lane complete"
