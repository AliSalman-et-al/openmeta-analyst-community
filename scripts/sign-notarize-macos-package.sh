#!/usr/bin/env bash
set -euo pipefail

package="${1:?unsigned package path is required}"
output="${2:?signed package output path is required}"
: "${RCMS_APPLE_SIGNING_IDENTITY:?RCMS_APPLE_SIGNING_IDENTITY is required}"
: "${RCMS_APPLE_NOTARY_KEY_ID:?RCMS_APPLE_NOTARY_KEY_ID is required}"
: "${RCMS_APPLE_NOTARY_ISSUER:?RCMS_APPLE_NOTARY_ISSUER is required}"
: "${RCMS_APPLE_NOTARY_KEY_FILE:?RCMS_APPLE_NOTARY_KEY_FILE is required}"

workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT
signing_inventory="${output}.signing-inventory.json"
mkdir -p "$(dirname "$output")"
ditto -x -k "$package" "$workspace"
app="$(find "$workspace" -maxdepth 3 -type d -name '*.app' -print -quit)"
test -n "$app" || { echo "No .app bundle found." >&2; exit 2; }

uv run python scripts/sign_macos_app.py "$app" \
  --identity "$RCMS_APPLE_SIGNING_IDENTITY" \
  --timestamp \
  --inventory-output "$signing_inventory"

app_root="$app/Contents/MacOS"
derivation="$app/Contents/Resources/r-integration-kit/derivation.json"
test -f "$derivation"
api_bridge="$(uv run python scripts/r_kit_derivation.py resolve-final --app-root "$app_root" --derivation "$derivation" --name api_bridge)"
r_shared_library="$(uv run python scripts/r_kit_derivation.py resolve-final --app-root "$app_root" --derivation "$derivation" --name r_shared_library)"
test -f "$api_bridge" && test -e "$r_shared_library"
uv run python scripts/r_kit_derivation.py finalize \
  --app-root "$app_root" --api-bridge "$api_bridge" \
  --r-shared-library "$r_shared_library" --derivation "$derivation"
codesign --force --options runtime --timestamp --sign "$RCMS_APPLE_SIGNING_IDENTITY" "$app"
codesign --verify --strict --deep "$app"

submission="$workspace/notarization.zip"
ditto -c -k --keepParent "$app" "$submission"
xcrun notarytool submit "$submission" --key "$RCMS_APPLE_NOTARY_KEY_FILE" --key-id "$RCMS_APPLE_NOTARY_KEY_ID" --issuer "$RCMS_APPLE_NOTARY_ISSUER" --wait
xcrun stapler staple "$app"
xcrun stapler validate "$app"
spctl --assess --type execute --verbose=2 "$app"
ditto -c -k --keepParent "$app" "$output"
