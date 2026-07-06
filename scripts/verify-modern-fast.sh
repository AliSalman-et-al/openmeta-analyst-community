#!/usr/bin/env bash
set -euo pipefail

recreate_venv=0
sync=0
require_r_evidence=0
strict_taxonomy=0
fast_workers="${RCMS_FAST_WORKERS:-4}"
rscript=""
r_runtime_root=""
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
    --strict-taxonomy)
      strict_taxonomy=1
      shift
      ;;
    --rscript)
      if [ "$#" -lt 2 ]; then
        echo "--rscript requires a path or command name" >&2
        exit 2
      fi
      rscript="$2"
      shift 2
      ;;
    --r-runtime-root)
      if [ "$#" -lt 2 ]; then
        echo "--r-runtime-root requires an R runtime root" >&2
        exit 2
      fi
      r_runtime_root="$2"
      shift 2
      ;;
    --fast-workers)
      if [ "$#" -lt 2 ]; then
        echo "--fast-workers requires a worker count" >&2
        exit 2
      fi
      fast_workers="$2"
      shift 2
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
r_default_package_cache_root="$repo_root/artifacts/r-default-library-cache"

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
  step "Skipping dependency sync for warm local verification"
fi

step "Validating Comprehensive Golden Baseline manifests"
uv run python scripts/validate_golden_baseline_manifests.py

step "Checking modern test taxonomy"
taxonomy_args=(scripts/validate_test_taxonomy.py)
if [ "$strict_taxonomy" -eq 1 ]; then
  taxonomy_args+=(--strict)
fi
uv run python "${taxonomy_args[@]}"

step "Running parallel fast verification pytest lanes"
fast_pytest_args=(tests/modern/fast tests/modern/golden tests/modern/packaging_contract)
if [ -n "$fast_workers" ] && [ "$fast_workers" != "0" ] && [ "$fast_workers" != "1" ]; then
  fast_pytest_args+=(--dist loadfile -n "$fast_workers")
fi
uv run pytest "${fast_pytest_args[@]}"

step "Verifying Default R Evidence"
r_evidence_args=(scripts/verify_rcmetar_r_default.py)
if [ -n "$rscript" ]; then
  r_evidence_args+=(--rscript "$rscript")
elif [ -n "$r_runtime_root" ]; then
  r_evidence_args+=(--rscript "$r_runtime_root/bin/Rscript")
fi
if [ "$require_r_evidence" -eq 1 ]; then
  r_evidence_args+=(--require-r --require-installed-packages --install-missing --r-library-cache-root "$r_default_package_cache_root")
fi
uv run python "${r_evidence_args[@]}"

step "Fast Verification Lane complete"
