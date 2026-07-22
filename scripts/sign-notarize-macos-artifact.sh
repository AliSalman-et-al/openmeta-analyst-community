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
if [[ "$output_archive" = *.dmg ]]; then
  tmp_output="$output_archive.tmp.dmg"
else
  tmp_output="$output_archive.tmp"
fi
cleanup() {
  rm -rf "$work_root"
  rm -f "$tmp_output"
}
trap cleanup EXIT

app=""
qualification="$work_root/qualification"
mkdir -p "$qualification"

copy_app_from_dmg() {
  local dmg="$1"
  local destination="$2"
  local attach_plist="$work_root/attach.plist"
  local mount_point

  hdiutil verify "$dmg"
  hdiutil attach "$dmg" -readonly -nobrowse -plist > "$attach_plist"
  mount_point="$(python3 - "$attach_plist" <<'PY'
import plistlib
import sys

with open(sys.argv[1], "rb") as stream:
    payload = plistlib.load(stream)
points = [
    entity.get("mount-point")
    for entity in payload.get("system-entities", [])
    if entity.get("mount-point")
]
if len(points) != 1:
    raise SystemExit("Expected exactly one mounted DMG volume")
print(points[0])
PY
)"
  trap 'hdiutil detach "$mount_point" >/dev/null 2>&1 || true; cleanup' EXIT
  if [ ! -d "$mount_point/RCMetaStudio.app" ]; then
    echo "DMG does not contain RCMetaStudio.app." >&2
    exit 1
  fi
  mkdir -p "$destination"
  ditto "$mount_point/RCMetaStudio.app" "$destination/RCMetaStudio.app"
  hdiutil detach "$mount_point"
  trap cleanup EXIT
}

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
  case "$input_archive:$output_archive" in
    *.zip:*.dmg) ;;
    *) echo "sign-and-submit requires a ZIP candidate and DMG output." >&2; exit 2 ;;
  esac
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
  candidate_qualification="$archive_root/qualification"
  if [ ! -d "$app" ] || [ ! -d "$candidate_qualification" ]; then
    echo "Candidate ZIP does not contain RCMetaStudio.app and qualification evidence." >&2
    exit 1
  fi
  cp -R "$candidate_qualification/." "$qualification/"

  PYTHONPATH="$repo_root/src" uv run --no-project --python 3.11.9 python \
    "$repo_root/scripts/sign_macos_app.py" "$app" \
    --identity "$signing_identity" \
    --inventory-output "$signing_inventory"
  cp "$signing_inventory" "$qualification/developer-id-signing-inventory.json"
  codesign --verify --deep --strict --verbose=4 "$app"
  qualify_signed_app "developer-id"

  dmg_root="$work_root/dmg-root"
  mkdir -p "$dmg_root"
  ditto "$app" "$dmg_root/RCMetaStudio.app"
  ln -s /Applications "$dmg_root/Applications"
  hdiutil create -volname "RC MetaStudio" -srcfolder "$dmg_root" \
    -format UDZO -ov "$tmp_output"
  codesign --force --timestamp --sign "$signing_identity" \
    --identifier org.rcmetastudio.release "$tmp_output"
  codesign --verify --verbose=4 "$tmp_output"
  hdiutil verify "$tmp_output"
  xcrun notarytool submit "$tmp_output" \
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
  mv "$tmp_output" "$output_archive"
  echo "Created signed DMG and submitted its exact bytes to Apple: $output_archive"
  exit 0
fi

case "$input_archive:$output_archive" in
  *.dmg:*.dmg) ;;
  *) echo "finalize requires DMG input and output." >&2; exit 2 ;;
esac

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
cp "$input_archive" "$tmp_output"
xcrun stapler staple "$tmp_output"
xcrun stapler validate "$tmp_output"
codesign --verify --verbose=4 "$tmp_output"
hdiutil verify "$tmp_output"

installed_root="$work_root/installed"
copy_app_from_dmg "$tmp_output" "$installed_root"
app="$installed_root/RCMetaStudio.app"
qualify_signed_app "notarized"
{
  hdiutil verify "$tmp_output"
  codesign --verify --verbose=4 "$tmp_output"
  xcrun stapler validate "$tmp_output"
  spctl --assess --type open --context context:primary-signature --verbose=4 "$tmp_output"
  codesign --verify --deep --strict --verbose=4 "$app"
  spctl --assess --type execute --verbose=4 "$app"
} > "$verification_result" 2>&1
mv "$tmp_output" "$output_archive"
echo "Created signed, notarized, and stapled DMG: $output_archive"
