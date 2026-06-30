#!/usr/bin/env bash
set -euo pipefail

rscript="Rscript"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --rscript)
      rscript="$2"
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

cd "$repo_root"
uv sync --locked
uv run python scripts/verify_openmetar_r_stack.py --rscript "$rscript"
