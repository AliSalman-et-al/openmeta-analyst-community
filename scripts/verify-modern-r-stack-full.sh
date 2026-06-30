#!/usr/bin/env bash
set -euo pipefail

rscript="Rscript"
r_package_cache_root=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --rscript)
      rscript="$2"
      shift 2
      ;;
    --r-package-cache-root)
      r_package_cache_root="$2"
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
r_package_cache_root="${r_package_cache_root:-$repo_root/artifacts/r-library-cache}"

cd "$repo_root"
uv sync --locked
uv run python scripts/verify_openmetar_r_stack.py --rscript "$rscript" --r-library-cache-root "$r_package_cache_root"
