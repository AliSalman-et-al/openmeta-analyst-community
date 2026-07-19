#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
architecture=""; artifact=""; archive_root=""; kit=""; digest=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --architecture) architecture="$2"; shift 2 ;;
    --artifact-name) artifact="$2"; shift 2 ;;
    --archive-root-name) archive_root="$2"; shift 2 ;;
    --r-integration-kit) kit="$2"; shift 2 ;;
    --expected-r-integration-kit-sha256) digest="$2"; shift 2 ;;
    *) echo "Unknown offline assembly argument: $1" >&2; exit 2 ;;
  esac
done
: "${architecture:?--architecture is required}"
: "${artifact:?--artifact-name is required}"
: "${archive_root:?--archive-root-name is required}"
: "${kit:?--r-integration-kit is required}"
: "${digest:?--expected-r-integration-kit-sha256 is required}"
test -x "$repo/.venv/bin/python"
exec bash "$repo/scripts/build-macos-package.sh" --architecture "$architecture" --artifact-name "$artifact" --archive-root-name "$archive_root" --python-exe "$repo/.venv/bin/python" --r-integration-kit "$kit" --expected-r-integration-kit-sha256 "$digest" --skip-dependency-install
