#!/usr/bin/env bash
set -euo pipefail

input_archive=""
output_archive=""
signing_identity=""
signing_inventory=""
notarization_result=""
verification_result=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --input-archive) input_archive="$2"; shift 2 ;;
    --output-archive) output_archive="$2"; shift 2 ;;
    --signing-identity) signing_identity="$2"; shift 2 ;;
    --signing-inventory) signing_inventory="$2"; shift 2 ;;
    --notarization-result) notarization_result="$2"; shift 2 ;;
    --verification-result) verification_result="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

for required in input_archive output_archive signing_identity signing_inventory notarization_result verification_result; do
  if [ -z "${!required}" ]; then
    echo "--${required//_/-} is required." >&2
    exit 2
  fi
done
for secret in APPLE_ID APPLE_APP_SPECIFIC_PASSWORD APPLE_TEAM_ID; do
  if [ -z "${!secret:-}" ]; then
    echo "$secret is required." >&2
    exit 2
  fi
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
input_archive="$(cd "$(dirname "$input_archive")" && pwd)/$(basename "$input_archive")"
output_parent="$(cd "$(dirname "$output_archive")" && pwd)"
output_archive="$output_parent/$(basename "$output_archive")"
if [ "$input_archive" = "$output_archive" ]; then
  echo "The signed output archive must not overwrite the unsigned input archive." >&2
  exit 2
fi
if [ ! -s "$input_archive" ]; then
  echo "Unsigned input archive is missing or empty: $input_archive" >&2
  exit 2
fi

mkdir -p \
  "$(dirname "$signing_inventory")" \
  "$(dirname "$notarization_result")" \
  "$(dirname "$verification_result")"
work_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/rcms-macos-trust.XXXXXX")"
tmp_output="$output_archive.tmp"
cleanup() {
  rm -rf "$work_root"
  rm -f "$tmp_output"
}
trap cleanup EXIT

extracted_root="$work_root/extracted"
mkdir -p "$extracted_root"
ditto -x -k "$input_archive" "$extracted_root"
shopt -s nullglob dotglob
archive_roots=("$extracted_root"/*)
shopt -u nullglob dotglob
if [ "${#archive_roots[@]}" -ne 1 ] || [ ! -d "${archive_roots[0]}" ]; then
  echo "Expected exactly one top-level directory in $input_archive." >&2
  exit 1
fi
archive_root="${archive_roots[0]}"
app="$archive_root/RCMetaStudio.app"
qualification="$archive_root/qualification"
if [ ! -d "$app" ] || [ ! -d "$qualification" ]; then
  echo "Candidate archive does not contain RCMetaStudio.app and qualification evidence." >&2
  exit 1
fi

PYTHONPATH="$repo_root/src" uv run --no-project --python 3.11.9 python \
  "$repo_root/scripts/sign_macos_app.py" "$app" \
  --identity "$signing_identity" \
  --inventory-output "$signing_inventory"
cp "$signing_inventory" "$qualification/developer-id-signing-inventory.json"

notary_submission="$work_root/RCMetaStudio-notary-submission.zip"
ditto -c -k --norsrc --keepParent "$app" "$notary_submission"
xcrun notarytool submit "$notary_submission" \
  --apple-id "$APPLE_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD" \
  --team-id "$APPLE_TEAM_ID" \
  --wait \
  --output-format json > "$notarization_result"
python3 - "$notarization_result" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    result = json.load(stream)
if result.get("status") != "Accepted":
    raise SystemExit(f"Apple notarization was not accepted: {result.get('status')!r}")
if not result.get("id"):
    raise SystemExit("Apple notarization did not return a submission ID")
PY
cp "$notarization_result" "$qualification/notarization-result.json"

xcrun stapler staple "$app"
{
  codesign --verify --deep --strict --verbose=4 "$app"
  xcrun stapler validate "$app"
  spctl --assess --type execute --verbose=4 "$app"
} > "$verification_result" 2>&1
cp "$verification_result" "$qualification/gatekeeper-verification.txt"

ditto -c -k --norsrc --keepParent "$archive_root" "$tmp_output"
mv "$tmp_output" "$output_archive"
echo "Created signed, notarized, and stapled artifact: $output_archive"
