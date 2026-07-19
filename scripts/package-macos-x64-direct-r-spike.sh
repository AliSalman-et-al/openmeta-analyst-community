#!/usr/bin/env bash
# Compatibility entry point retained for the feasibility workflow.  The
# release packager owns the complete private-R pipeline; duplicating it here
# previously installed CRAN R into /Library and made the result runner-state
# dependent.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$repo/scripts/build-macos-package.sh" \
  --architecture x64 \
  --artifact-name RCMetaStudio-macos-x64-direct-r-spike \
  "$@"
