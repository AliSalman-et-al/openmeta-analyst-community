#!/usr/bin/env bash
set -euo pipefail

mode=""
input_archive=""
output_archive=""
signing_identity=""
signing_inventory=""
submission_result=""
notarization_result=""
verification_result=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode) mode="$2"; shift 2 ;;
    --input-archive) input_archive="$2"; shift 2 ;;
    --output-archive) output_archive="$2"; shift 2 ;;
    --signing-identity) signing_identity="$2"; shift 2 ;;
    --signing-inventory) signing_inventory="$2"; shift 2 ;;
    --submission-result) submission_result="$2"; shift 2 ;;
    --notarization-result) notarization_result="$2"; shift 2 ;;
    --verification-result) verification_result="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ "$mode" != "sign-and-submit" ] && [ "$mode" != "finalize" ]; then
  echo "--mode must be sign-and-submit or finalize." >&2
  exit 2
fi

required=(input_archive output_archive)
if [ "$mode" = "sign-and-submit" ]; then
  required+=(signing_identity signing_inventory submission_result)
else
  required+=(submission_result notarization_result verification_result)
fi
for name in "${required[@]}"; do
  if [ -z "${!name}" ]; then
    echo "--${name//_/-} is required for $mode." >&2
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
mkdir -p "$(dirname "$output_archive")"
output_parent="$(cd "$(dirname "$output_archive")" && pwd)"
output_archive="$output_parent/$(basename "$output_archive")"
if [ "$input_archive" = "$output_archive" ]; then
  echo "The output archive must not overwrite its input archive." >&2
  exit 2
fi
if [ ! -s "$input_archive" ]; then
  echo "Input archive is missing or empty: $input_archive" >&2
  exit 2
fi

for result in "$signing_inventory" "$submission_result" "$notarization_result" "$verification_result"; do
  if [ -n "$result" ]; then
    mkdir -p "$(dirname "$result")"
  fi
done

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
  echo "Archive does not contain RCMetaStudio.app and qualification evidence." >&2
  exit 1
fi

qualify_signed_app() {
  local phase="$1"
  local executable="$app/Contents/MacOS/RCMetaStudio"
  local sample="$app/Contents/Resources/sample_projects/BCG.rcms"
  local r_home="$app/Contents/Frameworks/R.framework/Resources"
  local runtime_probe="$qualification/${phase}-runtime-probe.json"
  local wizard_probe="$qualification/${phase}-startup-wizard-smoke.json"
  local stdout_path="$qualification/${phase}-runtime.stdout.log"
  local stderr_path="$qualification/${phase}-runtime.stderr.log"

  env -u QT_QPA_PLATFORM RCMS_REQUIRE_IN_PROCESS_RPY2=1 RPY2_CFFI_MODE=API \
    RCMS_R_HOME="$r_home" RCMS_R_LIBS="$r_home/library" \
    uv run --no-project --python 3.11.9 python \
      "$repo_root/scripts/run_bounded_process.py" --timeout-seconds 900 \
      --stdout "$stdout_path" --stderr "$stderr_path" -- \
      "$executable" --automation-package-runtime-probe "$runtime_probe"
  env -u QT_QPA_PLATFORM RCMS_REQUIRE_IN_PROCESS_RPY2=1 RPY2_CFFI_MODE=API \
    RCMS_R_HOME="$r_home" RCMS_R_LIBS="$r_home/library" \
    uv run --no-project --python 3.11.9 python \
      "$repo_root/scripts/run_bounded_process.py" --timeout-seconds 900 \
      --stdout "$qualification/${phase}-wizard.stdout.log" \
      --stderr "$qualification/${phase}-wizard.stderr.log" -- \
      "$executable" --automation-startup-wizard-smoke "$wizard_probe" "$sample"
  python3 - "$runtime_probe" "$wizard_probe" <<'PY'
import json
import sys

runtime = json.load(open(sys.argv[1], encoding="utf-8"))
wizard = json.load(open(sys.argv[2], encoding="utf-8"))
if not runtime.get("frozen") or runtime.get("qt", {}).get("platform_plugin") != "cocoa":
    raise SystemExit("Signed runtime probe did not use the frozen Cocoa runtime.")
if not runtime.get("rpy2", {}).get("api_bridge_loaded"):
    raise SystemExit("Signed runtime probe did not load the bundled rpy2 API bridge.")
if wizard.get("platform_plugin") != "cocoa" or not wizard.get("passed"):
    raise SystemExit("Signed startup wizard smoke failed: %s" % wizard)
PY
  codesign --verify --deep --strict --verbose=4 "$app"
}

auth=(
  --apple-id "$APPLE_ID"
  --password "$APPLE_APP_SPECIFIC_PASSWORD"
  --team-id "$APPLE_TEAM_ID"
)

if [ "$mode" = "sign-and-submit" ]; then
  PYTHONPATH="$repo_root/src" uv run --no-project --python 3.11.9 python \
    "$repo_root/scripts/sign_macos_app.py" "$app" \
    --identity "$signing_identity" \
    --inventory-output "$signing_inventory"
  cp "$signing_inventory" "$qualification/developer-id-signing-inventory.json"
  codesign --verify --deep --strict --verbose=4 "$app"
  qualify_signed_app "developer-id"

  notary_submission="$work_root/RCMetaStudio-notary-submission.zip"
  ditto -c -k --norsrc --keepParent "$app" "$notary_submission"
  xcrun notarytool submit "$notary_submission" \
    "${auth[@]}" \
    --output-format json > "$submission_result"
  python3 - "$submission_result" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    result = json.load(stream)
if not result.get("id"):
    raise SystemExit("Apple notarization submission did not return an ID")
if result.get("status") not in {None, "In Progress", "Accepted"}:
    raise SystemExit(f"Apple rejected notarization submission: {result.get('status')!r}")
PY
  cp "$submission_result" "$qualification/notarization-submission.json"

  ditto -c -k --norsrc --keepParent "$archive_root" "$tmp_output"
  mv "$tmp_output" "$output_archive"
  echo "Created resumable signed artifact and submitted it to Apple: $output_archive"
  exit 0
fi

submission_id="$(python3 - "$submission_result" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    result = json.load(stream)
identifier = result.get("id")
if not identifier:
    raise SystemExit("Saved Apple notarization submission does not contain an ID")
print(identifier)
PY
)"

xcrun notarytool wait "$submission_id" \
  "${auth[@]}" \
  --output-format json > "$notarization_result"
python3 - "$notarization_result" "$submission_id" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    result = json.load(stream)
if result.get("id") != sys.argv[2]:
    raise SystemExit("Apple notarization result does not match the saved submission ID")
if result.get("status") != "Accepted":
    raise SystemExit(f"Apple notarization was not accepted: {result.get('status')!r}")
PY
cp "$notarization_result" "$qualification/notarization-result.json"

xcrun stapler staple "$app"
qualify_signed_app "notarized"
{
  codesign --verify --deep --strict --verbose=4 "$app"
  xcrun stapler validate "$app"
  spctl --assess --type execute --verbose=4 "$app"
} > "$verification_result" 2>&1
cp "$verification_result" "$qualification/gatekeeper-verification.txt"

ditto -c -k --norsrc --keepParent "$archive_root" "$tmp_output"
mv "$tmp_output" "$output_archive"
echo "Created signed, notarized, and stapled artifact: $output_archive"
