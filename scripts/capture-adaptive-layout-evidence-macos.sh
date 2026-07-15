#!/usr/bin/env bash
set -euo pipefail

package="${1:?package ZIP is required}"
output="${2:-artifacts/controlled-layout-evidence/macos-x64}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
package="$(cd "$(dirname "$package")" && pwd)/$(basename "$package")"
output="$repo_root/$output"
workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"; unset QT_SCALE_FACTOR' EXIT
ditto -x -k "$package" "$workspace"
executable="$(find "$workspace" -path '*.app/Contents/MacOS/RCMetaStudio' -print -quit)"
sample="$(find "$workspace" -path '*/sample_projects/amino.rcms' -print -quit)"
test -n "$executable" && test -n "$sample"
env -u QT_QPA_PLATFORM RCMS_REQUIRE_IN_PROCESS_RPY2=1 "$executable" --automation-native-smoke "$sample"
for scale in 1.0 1.5; do
  case "$scale" in 1.0) label=100 ;; 1.5) label=150 ;; esac
  target="$output/scale-$label"
  mkdir -p "$target"
  env -u QT_QPA_PLATFORM QT_SCALE_FACTOR="$scale" RCMS_REQUIRE_IN_PROCESS_RPY2=1 \
    "$executable" --automation-adaptive-layout-evidence "$target" "$sample"
  uv run python scripts/validate_adaptive_layout_evidence.py \
    --root "$target" --platform-plugin cocoa --scale-factor "$scale"
done
hash="$(shasum -a 256 "$package" | awk '{print $1}')"
printf '%s  %s\n' "$hash" "$(basename "$package")" > "$output/PACKAGE_SHA256"
printf 'Controlled macOS evidence captured for package SHA-256 %s at %s\n' "$hash" "$output"
