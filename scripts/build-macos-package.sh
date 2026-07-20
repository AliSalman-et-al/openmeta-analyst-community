#!/usr/bin/env bash
set -euo pipefail

artifact_name=""
archive_root_name=""
architecture=""
python_exe=""
r_runtime_root="${RCMS_R_HOME:-${R_HOME:-}}"
bundle_identifier="org.researchconsultancy.rc-metastudio"
skip_dependency_install=0
skip_clean=0
skip_smoke=0
capture_adaptive_layout_evidence=0
stop_after_r_substrate=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --artifact-name)
      artifact_name="$2"
      shift 2
      ;;
    --archive-root-name)
      archive_root_name="$2"
      shift 2
      ;;
    --architecture)
      architecture="$2"
      shift 2
      ;;
    --python-exe)
      python_exe="$2"
      shift 2
      ;;
    --r-runtime-root)
      r_runtime_root="$2"
      shift 2
      ;;
    --bundle-identifier)
      bundle_identifier="$2"
      shift 2
      ;;
    --skip-dependency-install)
      skip_dependency_install=1
      shift
      ;;
    --skip-clean)
      skip_clean=1
      shift
      ;;
    --skip-smoke)
      skip_smoke=1
      shift
      ;;
    --capture-adaptive-layout-evidence)
      capture_adaptive_layout_evidence=1
      shift
      ;;
    --stop-after-r-substrate)
      stop_after_r_substrate=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
artifact_dir="$repo_root/artifacts"

step() {
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$1"
}

require_free_space_gb() {
  local path="$1"
  local required_gb="$2"
  local available_kb
  available_kb="$(df -Pk "$path" | awk 'NR==2 {print $4}')"
  local required_kb=$((required_gb * 1024 * 1024))
  if [ -z "$available_kb" ] || [ "$available_kb" -lt "$required_kb" ]; then
    echo "At least ${required_gb}GB of free disk space is required under $path." >&2
    df -h "$path" >&2 || true
    exit 1
  fi
}

repo_path() {
  local path="$1"
  case "$path" in
    /*)
      printf '%s\n' "$path"
      ;;
    */*)
      printf '%s\n' "$repo_root/$path"
      ;;
    *)
      if command -v "$path" >/dev/null 2>&1; then
        command -v "$path"
      else
        echo "Command was not found on PATH: $path" >&2
        exit 1
      fi
      ;;
  esac
}

project_version() {
  "$python_exe" - "$repo_root/pyproject.toml" <<'PY'
import pathlib
import sys
import tomllib

print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["project"]["version"])
PY
}

resolve_existing_dir() {
  local path="$1"
  local description="$2"
  if [ -z "$path" ] || [ ! -d "$path" ]; then
    echo "$description was not found at $path." >&2
    exit 1
  fi
  (cd "$path" && pwd -P)
}

copy_tree() {
  local source="$1"
  local destination="$2"
  if [ ! -d "$source" ]; then
    echo "Source directory was not found: $source" >&2
    exit 1
  fi
  rm -rf "$destination"
  mkdir -p "$(dirname "$destination")"
  if command -v rsync >/dev/null 2>&1; then
    mkdir -p "$destination"
    rsync -a --delete "$source"/ "$destination"/
  else
    mkdir -p "$destination"
    (cd "$source" && tar -cf - .) | (cd "$destination" && tar -xf -)
  fi
}

if [ "$(uname -s)" != "Darwin" ]; then
  echo "macOS packaging must run on macOS." >&2
  exit 1
fi

host_machine="$(uname -m)"
if [ -z "$architecture" ]; then
  [ "$host_machine" = "arm64" ] && architecture="arm64" || architecture="x64"
fi
case "$architecture" in x64|arm64) ;; *) echo "--architecture must be x64 or arm64." >&2; exit 1 ;; esac
target_python="$(command -v python3 || true)"
[ -n "$target_python" ] || { echo "macOS packaging requires python3 to resolve its target manifest." >&2; exit 1; }
eval "$("$target_python" "$repo_root/scripts/resolve_macos_package_target.py" "$architecture" --format shell)"
expected_machine="$machine"
pyinstaller_target_architecture="$machine"
default_artifact="$artifact"
minimum_macos_version="$minimum_macos"

if [ "$host_machine" != "$expected_machine" ]; then
  echo "Requested $architecture build requires $expected_machine host, but this host is $host_machine." >&2
  exit 1
fi

# Native wheels and R source packages compiled on the runner must not inherit
# the runner image's newer deployment floor.
export MACOSX_DEPLOYMENT_TARGET="$minimum_macos_version"

artifact_name="${artifact_name:-$default_artifact}"
dist_root="$repo_root/build/macos-package/$architecture/dist"
work_root="$repo_root/build/macos-package/$architecture/work"
app_bundle="$dist_root/RCMetaStudio.app"
app_root="$app_bundle/Contents/MacOS"
archive_staging_root="$work_root/zip-staging"
zip_path="$artifact_dir/$artifact_name.zip"
tmp_zip_path="$zip_path.tmp"
qualification_root="$work_root/qualification"
runtime_probe_path="$qualification_root/runtime-probe.json"
runtime_stdout_path="$qualification_root/runtime-probe.stdout.log"
runtime_stderr_path="$qualification_root/runtime-probe.stderr.log"
deployment_manifest_path="$qualification_root/deployment-manifest.json"
smoke_evidence_path="$qualification_root/packaged-smoke.json"
smoke_log_path="$qualification_root/packaged-smoke.log"
smoke_stdout_path="$qualification_root/packaged-smoke.stdout.log"
smoke_stderr_path="$qualification_root/packaged-smoke.stderr.log"
hang_trace_path="$qualification_root/packaged-smoke.hang-trace.log"
launch_stdout_path="$qualification_root/launchservices.stdout.log"
launch_stderr_path="$qualification_root/launchservices.stderr.log"
launchservices_marker_path="$qualification_root/launchservices-completion.json"
launchservices_pid_path="$qualification_root/launchservices.pid"
signing_inventory_path="$qualification_root/ad-hoc-signing-inventory.json"
post_sign_native_inventory_path="$qualification_root/post-sign-native-inventory.json"
r_runtime_profile_path="$qualification_root/embedded-r-runtime-profile.json"
quarantine_profile_path="$qualification_root/embedded-r-runtime-quarantine.json"
r_substrate_probe_path="$qualification_root/r-substrate-probe.json"
r_direct_build_manifest_path="$qualification_root/direct-r-build-manifest.json"
ppm_archive_root="$qualification_root/ppm-archives"
hsroc_archive_path="$qualification_root/HSROC_2.1.9.tar.gz"
rcmetar_archive_path="$qualification_root/RCMetaR-0.2.0-source.tar.gz"
runner_environment_path="$qualification_root/runner-environment.json"
official_r_signature_path="$qualification_root/official-r-signature.json"
adapter_audit_path="$qualification_root/direct-r-pre-normalization-audit.json"
adapter_map_path="$qualification_root/direct-r-adapter.json"
adapter_toc_path="$qualification_root/direct-r-toc.json"
rpy2_build_path="$qualification_root/rpy2-api-build.json"
pre_sign_graph_path="$qualification_root/pre-sign-native-graph.json"
preflight_report_path="$qualification_root/macos-r-pyinstaller-toc-preflight.json"
archive_inspection_path="$artifact_dir/$artifact_name-archive-inspection.json"
qualification_evidence_path="$artifact_dir/$artifact_name-evidence.json"
pinned_cran_repo="https://packagemanager.posit.co/cran/2026-07-16"
cran_repo="${RCMS_CRAN_REPO:-$pinned_cran_repo}"
if [ "$cran_repo" != "$pinned_cran_repo" ]; then
  echo "RCMS_CRAN_REPO must match the manifest snapshot: $pinned_cran_repo" >&2
  exit 1
fi
export RCMS_CRAN_REPO="$pinned_cran_repo"

if [ "$skip_dependency_install" -eq 0 ]; then
  step "Syncing locked verification environment"
  (cd "$repo_root" && uv sync --locked)
  python_exe="$repo_root/.venv/bin/python"
fi

python_exe="${python_exe:-$repo_root/.venv/bin/python}"

if [ -z "$r_runtime_root" ]; then
  r_download_cache="$artifact_dir/download-cache/macos-$architecture"
  r_pkg="$r_download_cache/$(basename "$r_url")"
  r_pkg_tmp="$r_pkg.partial"
  mkdir -p "$r_download_cache"
  if [ ! -f "$r_pkg" ] || { [ -n "$r_sha256" ] && [ "$(shasum -a 256 "$r_pkg" | awk '{print $1}')" != "$r_sha256" ]; }; then
    rm -f "$r_pkg" "$r_pkg_tmp"
    step "Downloading authenticated official $architecture R into the immutable cache"
    curl --fail --location --proto '=https' --tlsv1.2 "$r_url" --output "$r_pkg_tmp"
    if [ -n "$r_sha256" ]; then
      [ "$(shasum -a 256 "$r_pkg_tmp" | awk '{print $1}')" = "$r_sha256" ] || { rm -f "$r_pkg_tmp"; echo "Official R package SHA-256 mismatch." >&2; exit 1; }
    fi
    mv "$r_pkg_tmp" "$r_pkg"
  fi
  signature_stdout="$r_pkg.signature.stdout"; signature_stderr="$r_pkg.signature.stderr"
  set +e; pkgutil --check-signature "$r_pkg" >"$signature_stdout" 2>"$signature_stderr"; signature_status=$?; set -e
  [ "$signature_status" -eq 0 ] && grep -q 'VZLD955F6P' "$signature_stdout" || { echo "Official R package signature is not the R for macOS signer." >&2; exit 1; }
  step "Extracting the authenticated official $architecture R.framework into private staging"
  r_pkg_expanded="$repo_root/build/macos-package/$architecture/official-r-pkg"
  r_stage_parent="$(dirname "$r_pkg_expanded")"
  mkdir -p "$r_stage_parent"
  [ -d "$r_stage_parent" ] || { echo "Private R staging parent was not created: $r_stage_parent" >&2; exit 1; }
  rm -rf "$r_pkg_expanded"
  [ ! -e "$r_pkg_expanded" ] || { echo "pkgutil expansion target must be absent: $r_pkg_expanded" >&2; exit 1; }
  pkgutil --expand-full "$r_pkg" "$r_pkg_expanded"
  r_pkg_framework="$("$python_exe" "$repo_root/scripts/resolve_macos_r_framework_component.py" --expanded-root "$r_pkg_expanded" --expected-version "$r_version" --identifier "$r_component_identifier")"
  [ -d "$r_pkg_framework" ] || { echo "Official R framework component resolver returned no directory." >&2; exit 1; }
  r_runtime_root="$r_pkg_framework/Resources"
fi
source_r_runtime_input="$r_runtime_root"
r_runtime_root="$(resolve_existing_dir "$source_r_runtime_input" "Source R runtime")"
if [ ! -d "$r_runtime_root/bin" ]; then
  echo "Source R runtime is missing bin under $r_runtime_root." >&2
  exit 1
fi
source_r_runtime_root="$r_runtime_root"
case "$source_r_runtime_root" in
  /Library/Frameworks/R.framework/*|/opt/R/*)
    echo "System R is not a permitted macOS package input: $source_r_runtime_root" >&2
    exit 1
    ;;
esac
source_r_framework="$("$python_exe" - "$source_r_runtime_root" <<'PY'
from pathlib import Path
import sys

resources = Path(sys.argv[1]).resolve(strict=True)
if resources.name != "Resources":
    raise SystemExit(f"Source R runtime must end in Resources: {resources}")
framework = next((parent for parent in (resources, *resources.parents)
                  if parent.name == "R.framework"), None)
if framework is None:
    raise SystemExit(f"Source R Resources is not within an R.framework: {resources}")
print(framework)
PY
)"
private_r_framework="$repo_root/build/macos-package/$architecture/staged/R.framework"
if [ "$(cd "$source_r_framework" && pwd -P)" = "$(cd "$private_r_framework" 2>/dev/null && pwd -P || true)" ]; then
  echo "Source R framework must not be the private staging destination: $source_r_framework" >&2
  exit 1
fi
rm -rf "$private_r_framework"
mkdir -p "$(dirname "$private_r_framework")"
copy_tree "$source_r_framework" "$private_r_framework"
r_runtime_root="$private_r_framework/Resources"
[ -d "$r_runtime_root/bin" ] || { echo "Private staged R runtime is incomplete." >&2; exit 1; }

# The profile evidence must survive the later bundle build, so establish its
# qualification directory before touching the private runtime.
if [ "$skip_clean" -eq 0 ]; then
  rm -rf "$dist_root" "$work_root"
fi
rm -rf "$qualification_root"
mkdir -p "$qualification_root"
r_version="4.6.1"
"$python_exe" - "$private_r_framework" "$r_version" <<'PY'
from pathlib import Path
import sys

framework = Path(sys.argv[1])
version = sys.argv[2]
if not any(path.name.startswith("4.6") for path in (framework / "Versions").glob("*")):
    raise SystemExit("private R.framework layout does not contain the locked 4.6 version")
PY
step "Applying the explicit non-X11 embedded R product profile to private staged R"
"$python_exe" "$repo_root/scripts/profile_macos_embedded_r_runtime.py" quarantine \
  --resources "$r_runtime_root" --evidence "$quarantine_profile_path" \
  --dependency-manifest "$repo_root/docs/verification/RCMetaR-r-dependencies.json" \
  --r-version "$r_version" --architecture "$expected_machine" \
  --source-resources "$source_r_runtime_root"

step "Configuring private staged R launchers before native bridge build"
"$python_exe" "$repo_root/scripts/configure_macos_r_launchers.py" --resources "$r_runtime_root" --architecture "$expected_machine"
step "Relocating private staged R dependencies before native bridge build"
bash "$repo_root/scripts/relocate_macos_r_runtime.sh" --resources "$r_runtime_root" --architecture "$expected_machine" \
  --python "$python_exe" --allowed-root "$repo_root/build/macos-package/$architecture" \
  --normalizer "$repo_root/scripts/normalize_macos_macho.py"
step "Probing the self-contained staged R substrate"
run_staged_r_config() {
  local config_flag="$1" output
  if ! output="$(R_HOME="$r_runtime_root" "$r_runtime_root/bin/R" CMD config "$config_flag" 2>&1)"; then
    echo "Private staged R preflight failed: R CMD config $config_flag ($r_runtime_root)" >&2
    printf '%s\n' "$output" >&2
    exit 1
  fi
  if printf '%s\n' "$output" | grep -F '/Library/Frameworks/R.framework/' >/dev/null; then
    echo "Private staged R preflight leaked a system framework path: R CMD config $config_flag" >&2
    printf '%s\n' "$output" >&2
    exit 1
  fi
}
run_staged_r_config --ldflags
run_staged_r_config --cppflags
actual_r_version="$(R_HOME="$r_runtime_root" "$r_runtime_root/bin/Rscript" -e 'cat(as.character(getRversion()))')"
[ "$actual_r_version" = "$r_version" ] || { echo "Private staged R version mismatch: expected $r_version, got $actual_r_version" >&2; exit 1; }
R_HOME="$r_runtime_root" "$r_runtime_root/bin/R" RHOME | grep -Fx "$r_runtime_root" >/dev/null \
  || { echo "Private staged R does not report its private RHOME." >&2; exit 1; }
R_HOME="$r_runtime_root" "$r_runtime_root/bin/Rscript" -e 'stopifnot(identical(R.home(), Sys.getenv("R_HOME"))); stopifnot(identical(Sys.getenv("RHOME"), Sys.getenv("R_HOME"))); stopifnot(!capabilities("X11")); cat("staged-r-ok\\n")' \
  | grep -Fx 'staged-r-ok' >/dev/null \
  || { echo "Private staged R capability probe failed." >&2; exit 1; }
"$python_exe" - "$r_substrate_probe_path" "$r_runtime_root" "$r_version" "$quarantine_profile_path" <<'PY'
import hashlib, json, sys
from pathlib import Path

output, home, version, quarantine = map(Path, sys.argv[1:])
output.write_text(json.dumps({
    "schema_version": 1,
    "phase": "staged-r-substrate",
    "r_home": str(home),
    "r_version": str(version),
    "launcher": "bin/R",
    "rscript": "bin/Rscript (native wrapper)",
    "probes": ["R RHOME", "R CMD config --ldflags", "R CMD config --cppflags", "Rscript private R.home", "non-X11 capability"],
    "quarantine_evidence_sha256": hashlib.sha256(quarantine.read_bytes()).hexdigest(),
}, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
PY
if [ "$stop_after_r_substrate" -eq 1 ]; then
  step "Staged R substrate gate passed"
  exit 0
fi

python_exe="$(repo_path "$python_exe")"
if [ ! -x "$python_exe" ]; then
  echo "Python executable was not found or is not executable: $python_exe" >&2
  exit 1
fi

resolved_project_version="$(project_version)"
archive_root_name="${archive_root_name:-RCMetaStudio-$resolved_project_version-macos-$architecture}"
"$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" validate-root \
  --archive-root-name "$archive_root_name"
archive_root_dir="$archive_staging_root/$archive_root_name"

"$python_exe" - <<'PY'
import PyInstaller
import sys
if sys.version_info[:2] != (3, 11):
    raise SystemExit("macOS packaging requires Python 3.11.")
if PyInstaller.__version__ != "6.21.0":
    raise SystemExit("macOS packaging requires PyInstaller 6.21.0.")
PY

rm -rf "$zip_path" "$tmp_zip_path" "$archive_inspection_path" "$qualification_evidence_path"
mkdir -p "$artifact_dir"
if [ -n "${signature_stdout:-}" ]; then
  "$python_exe" "$repo_root/scripts/macos_pkg_signature.py" \
    --stdout "$signature_stdout" --stderr "$signature_stderr" \
    --status "$signature_status" --output "$official_r_signature_path"
fi
require_free_space_gb "$repo_root" 6

# Complete and prove the one private framework before PyInstaller sees it.
# No R member is populated or mutated in the generated app bundle.
r_framework="$private_r_framework"
r_framework_version="$(readlink "$r_framework/Versions/Current")"
case "$r_framework_version" in
  [0-9]*.[0-9]*|[0-9]*.[0-9]*-*) ;;
  *) echo "Cannot derive the bundled R framework version." >&2; exit 1 ;;
esac
r_home="$r_framework/Resources"
r_lib="$r_home/library"
rscript="$r_home/bin/Rscript"
r_binary="$r_home/bin/R"
r_makevars="$work_root/private-r.Makevars"
printf 'LDFLAGS = -L%s/lib\nLIBR = -L%s/lib -lR\n' "$r_home" "$r_home" > "$r_makevars"

if [ ! -x "$rscript" ] || [ ! -x "$r_binary" ]; then
  echo "Bundled R runtime is missing R or Rscript under $r_home/bin." >&2
  exit 1
fi
"$python_exe" - "$r_home/Info.plist" <<'PY'
from pathlib import Path
import plistlib
import sys

info_path = Path(sys.argv[1]).resolve(strict=True)
with info_path.open("rb") as stream:
    info = plistlib.load(stream)
existing = info.get("CFBundleExecutable")
if existing not in (None, "R"):
    raise SystemExit(f"unexpected R framework executable identity: {existing!r}")
info["CFBundleExecutable"] = "R"
with info_path.open("wb") as stream:
    plistlib.dump(info, stream, sort_keys=True)
PY

run_strict_r_dependency_policy() {
  local library="$1"
  mkdir -p "$library"
  R_HOME="$r_home" R_LIBS="$library" R_LIBS_USER="$library" R_MAKEVARS_USER="$r_makevars" \
    RCMS_CRAN_REPO="$pinned_cran_repo" RCMS_POLICY_PYTHON="$python_exe" \
    RCMS_R_PACKAGE_ARCHIVE_DIR="$ppm_archive_root" RCMS_HSROC_ARCHIVE="$hsroc_archive_path" \
    "$rscript" "$repo_root/scripts/install-r-deps.R"
}

test_bundled_r_packages() {
  local library="$1"
  [ -d "$library" ] || return 1
  R_HOME="$r_home" R_LIBS="$library" R_LIBS_USER="$library" "$rscript" -e "lib <- normalizePath('$library', winslash='/'); .libPaths(c(lib, .libPaths())); pkgs <- c('HSROC','RCMetaR','metafor','lme4','pdftools','rsvg','svglite','tiff','xml2','igraph','mice','Hmisc'); ok <- vapply(pkgs, requireNamespace, logical(1), quietly=TRUE); if (!all(ok)) quit(status=1); if (as.character(packageVersion('HSROC')) != '2.1.9') quit(status=1)" >/dev/null 2>&1
}

install_local_r_packages() {
  local package_build_root="$work_root/r-package-build"
  rm -rf "$package_build_root"
  mkdir -p "$package_build_root"
  cp -R "$repo_root/r/RCMetaR" "$package_build_root/RCMetaR"
  find "$package_build_root" \( -name '*.o' -o -name '*.so' -o -name '*.dll' \) -delete

  (cd "$package_build_root" && R_HOME="$r_home" "$r_binary" CMD build RCMetaR >/dev/null)
  local built_archive
  built_archive="$(find "$package_build_root" -maxdepth 1 -type f -name 'RCMetaR_*.tar.gz' -print -quit)"
  [ -n "$built_archive" ] || { echo "RCMetaR source archive was not built." >&2; exit 1; }
  cp "$built_archive" "$rcmetar_archive_path"

  R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" R_MAKEVARS_USER="$r_makevars" \
    "$r_binary" CMD INSTALL --library="$r_lib" "$rcmetar_archive_path"
}

step "Installing bundled R package dependencies into this private staged runtime"
run_strict_r_dependency_policy "$r_lib"

step "Installing local RCMetaR package"
install_local_r_packages
R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" "$rscript" -e "pkgs <- c('HSROC','RCMetaR','metafor','lme4','pdftools','rsvg','svglite','tiff','xml2','igraph','mice','Hmisc'); ok <- vapply(pkgs, require, logical(1), character.only=TRUE); print(ok); if (!all(ok)) quit(status=1); if (as.character(packageVersion('HSROC')) != '2.1.9') quit(status=1)"

if ! test_bundled_r_packages "$r_lib"; then
  echo "Bundled R package verification failed after local RCMetaR install." >&2
  exit 1
fi

step "Finalizing the embedded R product profile after package installation"
"$python_exe" "$repo_root/scripts/profile_macos_embedded_r_runtime.py" finalize \
  --resources "$r_home" --evidence "$r_runtime_profile_path" \
  --dependency-manifest "$repo_root/docs/verification/RCMetaR-r-dependencies.json" \
  --r-version "$r_version" --architecture "$expected_machine" \
  --quarantine-evidence "$quarantine_profile_path"

step "Relocating completed bundled R runtime dependencies"
bash "$repo_root/scripts/relocate_macos_r_runtime.sh" --resources "$r_home" --architecture "$expected_machine" \
  --python "$python_exe" --allowed-root "$repo_root/build/macos-package/$architecture" \
  --normalizer "$repo_root/scripts/normalize_macos_macho.py"

step "Building the target-native rpy2 API bridge against completed staged R"
R_HOME="$r_home" PATH="$r_home/bin:$PATH" RPY2_CFFI_MODE=API uv pip install \
  --python "$python_exe" --reinstall --no-binary rpy2-rinterface \
  "rpy2-rinterface==3.6.6"

step "Proving and relocating the rpy2 API bridge against staged R"
rpy2_api_bridge="$($python_exe - <<'PY'
from pathlib import Path
import sysconfig

matches = list(Path(sysconfig.get_paths()["platlib"]).glob("_rinterface_cffi_api*.so"))
if len(matches) != 1:
    raise SystemExit(f"expected exactly one rpy2 API bridge, found {matches}")
print(matches[0].resolve(strict=True))
PY
)"
[ -f "$rpy2_api_bridge" ] || { echo "rpy2 API bridge is absent after source build." >&2; exit 1; }
[ "$(find "$(dirname "$rpy2_api_bridge")" -maxdepth 1 -name '_rinterface_cffi_api*.so' | wc -l | tr -d ' ')" = 1 ] \
  || { echo "rpy2 API build must contain exactly one API extension." >&2; exit 1; }
if "$python_exe" -c 'import importlib.util,sys; sys.exit(importlib.util.find_spec("_rinterface_cffi_abi") is not None)'; then
  :
else
  echo "rpy2 ABI bridge is present in the strict API environment." >&2; exit 1
fi
relocate_rpy2_api_bridge() {
  local bridge="$1"
  local dependency source_relative target relative_target
  while IFS= read -r dependency; do
  case "$dependency" in
    @loader_path/*.dylib)
      source_relative="lib/${dependency#@loader_path/}"
      ;;
    @rpath/lib/libR.dylib)
      source_relative="lib/libR.dylib"
      ;;
    @rpath/*.dylib)
      source_relative="lib/${dependency#@rpath/}"
      ;;
    "$r_runtime_root"/*)
      source_relative="${dependency#"$r_runtime_root"/}"
      ;;
    /Library/Frameworks/R.framework/Versions/*/Resources/*)
      source_relative="${dependency#*/Resources/}"
      ;;
    /Library/Frameworks/R.framework/Resources/*)
      source_relative="${dependency#/Library/Frameworks/R.framework/Resources/}"
      ;;
    /Library/Frameworks/R.framework/R|/Library/Frameworks/R.framework/Versions/*/R)
      source_relative="lib/libR.dylib"
      ;;
    *) continue ;;
  esac
  target="$r_home/$source_relative"
  [ -f "$target" ] || { echo "rpy2 API bridge dependency has no staged R target: $dependency -> $target" >&2; exit 1; }
  relative_target="$($python_exe - "$(dirname "$bridge")" "$target" <<'PY'
import os, sys
print(os.path.relpath(sys.argv[2], sys.argv[1]))
PY
)"
    install_name_tool -change "$dependency" "@loader_path/$relative_target" "$bridge"
  done < <(otool -L "$bridge" | awk 'NR > 1 { print $1 }')
  if otool -L "$bridge" | grep -E '@rpath/|/Library/Frameworks/R\.framework/|/opt/R/'; then
    echo "rpy2 API bridge retains an external R dependency." >&2
    exit 1
  fi
}
relocate_rpy2_api_bridge "$rpy2_api_bridge"
R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" RPY2_CFFI_MODE=API \
  "$python_exe" - "$rpy2_api_bridge" "$machine" <<'PY'
import importlib.util
from pathlib import Path
import subprocess
import sys

bridge = Path(sys.argv[1]).resolve(strict=True)
expected_architecture = sys.argv[2]
if subprocess.check_output(["lipo", "-archs", str(bridge)], text=True).split() != [expected_architecture]:
    raise SystemExit(f"rpy2 API bridge is not {expected_architecture}-only")
loads = subprocess.check_output(["otool", "-L", str(bridge)], text=True).splitlines()[1:]
r_edges = [line for line in loads if "libR.dylib" in line or "/R " in line]
if len(r_edges) != 1:
    raise SystemExit(f"rpy2 API bridge must have exactly one R edge: {r_edges}")
if importlib.util.find_spec("_rinterface_cffi_abi") is not None:
    raise SystemExit("rpy2 ABI bridge is present")
from rpy2 import robjects
from rpy2.rinterface_lib import openrlib
if openrlib.cffi_mode.name != "API" or float(robjects.r("1 + 1")[0]) != 2.0:
    raise SystemExit("strict rpy2 API embedded calculation failed")
PY

step "Verifying the embedded R Quartz runtime policy"
R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" "$rscript" -e '
  if (requireNamespace("tcltk", quietly=TRUE)) stop("tcltk must be excluded")
  if ("tcltk" %in% loadedNamespaces()) stop("tcltk namespace must not load")
  if (!isTRUE(capabilities("aqua"))) stop("macOS R must provide Aqua")
  if (!identical(getOption("bitmapType"), "quartz")) stop("macOS bitmapType must be quartz")
  output <- tempfile(fileext=".png"); grDevices::png(output); graphics::plot(1, 1); grDevices::dev.off()
if (!file.exists(output) || file.info(output)$size <= 0) stop("default Quartz png probe failed")
  unlink(output)
'

canonicalize_r_framework() {
  local framework="$1"
  "$python_exe" - "$framework" <<'PY'
from pathlib import Path
import sys

framework = Path(sys.argv[1]).resolve(strict=True)
for development_alias in ("Headers", "Libraries", "PrivateHeaders"):
    alias = framework / development_alias
    if alias.is_symlink():
        alias.unlink()
    elif alias.exists():
        raise SystemExit(f"R framework root member is not a removable alias: {alias}")
root_members = {item.name for item in framework.iterdir()}
if root_members != {"R", "Resources", "Versions"}:
    raise SystemExit(f"R framework root is not minimal: {sorted(root_members)}")
version_root = (framework / "Versions/Current").resolve(strict=True)
main_executable = version_root / "R"
runtime_library = version_root / "Resources/lib/libR.dylib"
info_plist = version_root / "Resources/Info.plist"
if main_executable.is_symlink():
    if main_executable.resolve(strict=True) != runtime_library:
        raise SystemExit("R framework executable alias is not canonical")
    main_executable.unlink()
    runtime_library.replace(main_executable)
    main_executable.chmod(main_executable.stat().st_mode | 0o111)
    runtime_library.symlink_to(Path("../../R"))
if not main_executable.is_file() or main_executable.is_symlink():
    raise SystemExit("R framework main executable is not a regular file")
if not info_plist.is_file() or info_plist.is_symlink():
    raise SystemExit("R framework Info.plist is not a regular file")
if not runtime_library.is_symlink() or runtime_library.readlink() != Path("../../R"):
    raise SystemExit("R runtime library alias is not relative and canonical")
if runtime_library.resolve(strict=True) != main_executable:
    raise SystemExit("R runtime library alias does not resolve to the framework executable")
PY
}

relocate_canonical_r_framework_main() {
  local framework="$1"
  local framework_home="$framework/Resources"
  local framework_main="$framework/Versions/Current/R"
  local dependency dependency_name dependency_target install_id install_id_name
  install_id="$(otool -D "$framework_main" | awk 'NR == 2 { print $1 }')"
  case "$install_id" in
    @loader_path/*.dylib)
      install_id_name="${install_id#@loader_path/}"
      case "$install_id_name" in
        */*) ;;
        *) install_name_tool -id "@loader_path/Resources/lib/$install_id_name" "$framework_main" ;;
      esac
      ;;
  esac
  while IFS= read -r dependency; do
    case "$dependency" in
      @loader_path/*.dylib)
        dependency_name="${dependency#@loader_path/}"
        case "$dependency_name" in
          */*) continue ;;
        esac
        dependency_target="$framework_home/lib/$dependency_name"
        [ -f "$dependency_target" ] || { echo "canonical R framework dependency is absent: $dependency" >&2; exit 1; }
        install_name_tool -change "$dependency" "@loader_path/Resources/lib/$dependency_name" "$framework_main"
        ;;
    esac
  done < <(otool -L "$framework_main" | awk 'NR > 2 { print $1 }')
  if otool -L "$framework_main" | awk 'NR > 2 { print $1 }' | grep -E '^@loader_path/[^/]+\.dylib$'; then
    echo "canonical R framework main executable retains a pre-move loader edge." >&2
    exit 1
  fi
  if otool -D "$framework_main" | awk 'NR == 2 { print $1 }' | grep -E '^@loader_path/[^/]+\.dylib$'; then
    echo "canonical R framework main executable retains a pre-move install identity." >&2
    exit 1
  fi
}

# These retained records are the authoritative acquisition/build inputs for the
# direct native production manifest; no installed library tree is reused.
[ -s "$hsroc_archive_path" ] || { echo "HSROC acquisition archive was not retained." >&2; exit 1; }
[ -s "$rcmetar_archive_path" ] || { echo "RCMetaR source archive was not retained." >&2; exit 1; }
[ "$(shasum -a 256 "$hsroc_archive_path" | awk '{print $1}')" = "5476fa76d7723717e203925a1da442813e3645790ef9b633a145cbc04a08b874" ] || { echo "HSROC archive digest changed." >&2; exit 1; }
step "Canonicalizing the staged R framework before PyInstaller signing"
canonicalize_r_framework "$r_framework"
relocate_canonical_r_framework_main "$r_framework"
"$python_exe" "$repo_root/scripts/macos_embedded_r_adapter.py" finalize-toc --framework "$r_framework" --architecture "$expected_machine" --output "$adapter_map_path" --toc-output "$adapter_toc_path"
cp "$adapter_map_path" "$adapter_audit_path"
"$python_exe" - "$rpy2_api_bridge" "$rpy2_build_path" <<'PY'
import hashlib, importlib.metadata, json, subprocess, sys
from pathlib import Path
bridge, output = map(Path, sys.argv[1:])
output.write_text(json.dumps({"schema_version": 1, "versions": {name: importlib.metadata.version(name) for name in ("rpy2", "rpy2-rinterface", "rpy2-robjects")}, "bridge": str(bridge), "sha256": hashlib.sha256(bridge.read_bytes()).hexdigest(), "dependencies": subprocess.run(["otool", "-L", str(bridge)], check=True, capture_output=True, text=True).stdout.splitlines()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

step "Building the app from the completed staged R framework"
(
  cd "$repo_root"
  qt6_package_build_root="$work_root/qt6-input"
  "$python_exe" scripts/build_qt6.py generate --build-root "$qt6_package_build_root"
  export RCMS_QT6_BUILD_ROOT="$qt6_package_build_root"
  export RCMS_BUNDLE_IDENTIFIER="$bundle_identifier"
  export RCMS_PROJECT_VERSION="$resolved_project_version"
  export RCMS_TARGET_ARCHITECTURE="$pyinstaller_target_architecture"
  export RCMS_MINIMUM_MACOS_VERSION="$minimum_macos_version"
  export RCMS_PYINSTALLER_R_TOC="$adapter_toc_path"
  export RCMS_PYINSTALLER_R_MAP="$adapter_map_path"
  export RCMS_STAGED_R_FRAMEWORK="$r_framework"
  export RCMS_RPY2_API_BRIDGE_SHA256="$(shasum -a 256 "$rpy2_api_bridge" | awk '{print $1}')"
  pyinstaller_args=(--noconfirm --distpath "$dist_root" --workpath "$work_root" "packaging/pyinstaller/rc-metastudio-macos.spec")
  [ "$skip_clean" -eq 1 ] || pyinstaller_args=(--clean "${pyinstaller_args[@]}")
  R_HOME="$r_home" RPY2_CFFI_MODE=API "$python_exe" -m PyInstaller "${pyinstaller_args[@]}"
)
[ -x "$app_root/RCMetaStudio" ] || { echo "PyInstaller did not create the app executable." >&2; exit 1; }
find "$app_bundle" -name '_rinterface_cffi_abi*' -print -quit | grep -q . \
  && { echo "PyInstaller collected the forbidden ABI bridge." >&2; exit 1; }
rpy2_api_bridge="$(find "$app_bundle" -type f -name '_rinterface_cffi_api*.so' -print -quit)"
[ -n "$rpy2_api_bridge" ] || { echo "PyInstaller did not collect the API bridge." >&2; exit 1; }
resources_root="$app_bundle/Contents/Resources"
sample_root="$resources_root/sample_projects"
copy_tree "$repo_root/sample_projects" "$sample_root"
staged_r_framework="$r_framework"
r_framework="$app_bundle/Contents/Frameworks/R.framework"
[ ! -e "$r_framework" ] && [ ! -L "$r_framework" ] || { echo "PyInstaller unexpectedly collected R.framework." >&2; exit 1; }
step "Injecting the completed R framework after PyInstaller"
copy_tree "$staged_r_framework" "$r_framework"
r_home="$r_framework/Resources"
r_lib="$r_home/library"
rscript="$r_home/bin/Rscript"
r_binary="$r_home/bin/R"
relocate_rpy2_api_bridge "$rpy2_api_bridge"
"$python_exe" "$repo_root/scripts/macos_embedded_r_adapter.py" post-app \
  --app "$app_bundle" --architecture "$expected_machine" \
  --output "$qualification_root/post-injection-r-gate.json"
"$python_exe" - "$preflight_report_path" "$(git rev-parse HEAD)" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({
    "schema_version": 1,
    "source_commit": sys.argv[2],
    "pyinstaller_version": "6.21.0",
    "system": "Darwin",
    "machine": __import__("platform").machine(),
    "aliases": {
        "Versions/Current": "4.6-x86_64",
        "Resources": "Versions/Current/Resources",
        "R": "Versions/Current/R",
        "Versions/4.6-x86_64/R": "Resources/lib/libR.dylib",
        "Versions/4.6-x86_64/Resources/R": "bin/R",
    },
    "passed": True,
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
"$python_exe" - "$runner_environment_path" <<'PY'
import json, os, platform, subprocess, sys
from pathlib import Path
run = lambda *args: subprocess.check_output(args, text=True).strip()
Path(sys.argv[1]).write_text(json.dumps({"schema_version": 1, "github_actions": os.environ.get("GITHUB_ACTIONS", "false"), "runner_label": os.environ.get("RCMS_RUNNER_LABEL", "local"), "runner_image": os.environ.get("ImageOS", "local"), "runner_os": os.environ.get("RUNNER_OS", platform.system()), "runner_arch": os.environ.get("RUNNER_ARCH", platform.machine()), "macos_version": run("sw_vers", "-productVersion"), "macos_build": run("sw_vers", "-buildVersion"), "uname_system": run("uname", "-s"), "uname_machine": run("uname", "-m"), "python_machine": platform.machine()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
"$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" native-graph --app "$app_bundle" --target "macos-$architecture" --output "$pre_sign_graph_path"


cat > "$resources_root/LaunchRCMetaStudio.command" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R_DIR="$APP_DIR/../Frameworks/R.framework/Resources"
export RPY2_CFFI_MODE=API
export RCMS_R_HOME="$R_DIR"
export RCMS_R_LIBS="$R_DIR/library"
exec "$APP_DIR/../MacOS/RCMetaStudio" "$APP_DIR/sample_projects/amino.rcms"
SH
chmod +x "$resources_root/LaunchRCMetaStudio.command"

for required_path in \
  "$app_root/RCMetaStudio" \
  "$sample_root/BCG.rcms" \
  "$sample_root/amino.rcms" \
  "$r_home/bin/Rscript" \
  "$r_home/library/RCMetaR/DESCRIPTION" \
  "$resources_root/LaunchRCMetaStudio.command"
do
  if [ ! -e "$required_path" ]; then
    echo "Packaged macOS app is missing $required_path." >&2
    exit 1
  fi
done

run_adaptive_layout_evidence() {
  local evidence_root="$repo_root/build/macos-package/$architecture/adaptive-layout-evidence/macos-$architecture"
  local sample_path="$sample_root/amino.rcms"
  rm -rf "$evidence_root"
  mkdir -p "$evidence_root"
  for scale in "1.0" "1.5"; do
    local scale_label
    case "$scale" in
      1.0) scale_label="100" ;;
      1.5) scale_label="150" ;;
      *) echo "Unsupported adaptive-layout evidence scale: $scale" >&2; exit 2 ;;
    esac
    local output_dir="$evidence_root/scale-$scale_label"
    local log_path="$output_dir/automation-adaptive-layout-evidence.log"
    mkdir -p "$output_dir"
    env -u QT_QPA_PLATFORM \
      QT_SCALE_FACTOR="$scale" \
      RCMS_REQUIRE_IN_PROCESS_RPY2=1 \
      RCMS_ADAPTIVE_LAYOUT_EVIDENCE_LOG="$log_path" \
      RPY2_CFFI_MODE=API \
      RCMS_R_HOME="$r_home" \
      RCMS_R_LIBS="$r_lib" \
      "$app_root/RCMetaStudio" \
        --automation-adaptive-layout-evidence "$output_dir" "$sample_path"
    "$python_exe" "$repo_root/scripts/validate_adaptive_layout_evidence.py" \
      --root "$output_dir" --platform-plugin cocoa --scale-factor "$scale"
  done
}

run_packaged_process() {
  local timeout_seconds="${RCMS_PACKAGED_PROCESS_TIMEOUT_SECONDS:-900}"
  local stdout_path="${RCMS_PACKAGED_STDOUT_PATH:-$smoke_stdout_path}"
  local stderr_path="${RCMS_PACKAGED_STDERR_PATH:-$smoke_stderr_path}"
  env -u QT_QPA_PLATFORM \
    RCMS_REQUIRE_IN_PROCESS_RPY2=1 \
    RPY2_CFFI_MODE=API \
    RCMS_R_HOME="$r_home" \
    RCMS_R_LIBS="$r_lib" \
    "$python_exe" "$repo_root/scripts/run_bounded_process.py" \
      --timeout-seconds "$timeout_seconds" \
      --stdout "$stdout_path" \
      --stderr "$stderr_path" \
      -- "$@"
}

step "Applying and verifying the replaceable ad-hoc app-bundle signature"
"$python_exe" "$repo_root/scripts/sign_macos_app.py" "$app_bundle" \
  --identity - \
  --inventory-output "$signing_inventory_path"
codesign --verify --strict --deep --verbose=2 "$app_bundle"
# Re-enumerate after the outer signature is finalized; this is deliberately
# not a copy of the pre-final signing inventory.
"$python_exe" "$repo_root/scripts/sign_macos_app.py" "$app_bundle" \
  --inventory-only --inventory-output "$post_sign_native_inventory_path"

step "Probing the frozen macOS runtime"
RCMS_AUTOMATION_SMOKE_LOG="$smoke_log_path" \
  RCMS_PACKAGED_STDOUT_PATH="$runtime_stdout_path" \
  RCMS_PACKAGED_STDERR_PATH="$runtime_stderr_path" \
  run_packaged_process "$app_root/RCMetaStudio" \
    --automation-package-runtime-probe "$runtime_probe_path"
if [ ! -s "$runtime_probe_path" ]; then
  echo "Frozen macOS runtime probe did not produce evidence." >&2
  exit 1
fi

if [ "$skip_smoke" -eq 0 ]; then
  sample_path="$sample_root/BCG.rcms"
  baseline_dpr="$("$python_exe" - "$runtime_probe_path" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["qt"]["baseline_device_pixel_ratio"])
PY
)"
  step "Running packaged macOS workflow smoke"
  QT_SCALE_FACTOR=1.25 \
    RCMS_PACKAGE_BASELINE_DPR="$baseline_dpr" \
    RCMS_PACKAGE_SMOKE_EVIDENCE="$smoke_evidence_path" \
    RCMS_AUTOMATION_SMOKE_LOG="$smoke_log_path" \
    RCMS_AUTOMATION_HANG_TRACE="$hang_trace_path" \
    env -u QT_QPA_PLATFORM RCMS_REQUIRE_IN_PROCESS_RPY2=1 RPY2_CFFI_MODE=API \
      RCMS_R_HOME="$r_home" RCMS_R_LIBS="$r_lib" \
      "$python_exe" "$repo_root/scripts/run_bounded_process.py" --timeout-seconds 900 \
      --stdout "$smoke_stdout_path" --stderr "$smoke_stderr_path" \
      --completion-log "$smoke_log_path" -- \
      "$app_root/RCMetaStudio" --automation-native-smoke "$sample_path"

  for scale in "1.25" "1.50" "1.75"; do
    step "Running packaged Cocoa surface smoke at scale $scale"
    QT_SCALE_FACTOR="$scale" \
      RCMS_PACKAGE_BASELINE_DPR="$baseline_dpr" \
      RCMS_AUTOMATION_SMOKE_LOG="$smoke_log_path" \
      RCMS_PACKAGED_PROCESS_TIMEOUT_SECONDS=60 \
      RCMS_PACKAGED_STDOUT_PATH="$qualification_root/packaged-surface-${scale/./}.stdout.log" \
      RCMS_PACKAGED_STDERR_PATH="$qualification_root/packaged-surface-${scale/./}.stderr.log" \
      run_packaged_process "$app_root/RCMetaStudio" \
        --automation-package-surface-smoke "$smoke_evidence_path" "$scale"
  done

  step "Opening the converted sample through the normal LaunchServices app entry point"
  rm -f "$launchservices_marker_path" "$launchservices_pid_path"
  env -u QT_QPA_PLATFORM \
    RCMS_REQUIRE_IN_PROCESS_RPY2=1 \
    RPY2_CFFI_MODE=API \
    RCMS_R_HOME="$r_home" \
    RCMS_R_LIBS="$r_lib" \
    RCMS_STARTUP_PROJECT_SMOKE=1 \
    RCMS_AUTOMATION_SMOKE_LOG="$smoke_log_path" \
    RCMS_STARTUP_COMPLETION_MARKER="$launchservices_marker_path" \
    RCMS_AUTOMATION_PID_FILE="$launchservices_pid_path" \
    "$python_exe" "$repo_root/scripts/run_bounded_process.py" \
      --timeout-seconds 900 \
      --stdout "$launch_stdout_path" --stderr "$launch_stderr_path" \
      --owned-pid-file "$launchservices_pid_path" \
      -- open -W -n "$app_bundle" --args \
        --automation-startup-project-smoke \
        --automation-startup-completion-marker "$launchservices_marker_path" \
        --automation-pid-file "$launchservices_pid_path" \
        --automation-smoke-log "$smoke_log_path" \
        "$sample_path"
  "$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" finalize-smoke \
    --smoke-evidence "$smoke_evidence_path" --smoke-log "$smoke_log_path" \
    --launchservices-marker "$launchservices_marker_path"
  rm -f "$launchservices_pid_path"
fi
if [ "$capture_adaptive_layout_evidence" -eq 1 ]; then
  if [ "$architecture" != "x64" ]; then
    echo "Controlled adaptive-layout evidence is supported only for macOS Intel." >&2
    exit 2
  fi
  step "Capturing controlled native macOS adaptive-layout evidence"
  run_adaptive_layout_evidence
fi

source_commit="$(git rev-parse HEAD)"
python_version="$("$python_exe" -c 'import platform; print(platform.python_version())')"
pyqt6_version="$("$python_exe" -c 'import importlib.metadata as m; print(m.version("PyQt6"))')"
qt_version="$("$python_exe" -c 'import importlib.metadata as m; print(m.version("PyQt6-Qt6"))')"
sip_version="$("$python_exe" -c 'import importlib.metadata as m; print(m.version("PyQt6-sip"))')"
sip_runtime_version="$("$python_exe" -c 'from PyQt6 import sip; print(sip.SIP_VERSION_STR)')"
rpy2_version="$("$python_exe" -c 'import importlib.metadata as m; print(m.version("rpy2"))')"
locked_qt_root="$("$python_exe" -c 'from pathlib import Path; import PyQt6; print(Path(PyQt6.__file__).resolve().parent / "Qt6")')"
step "Inspecting the coherent target-native macOS deployment"
"$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" inspect \
  --target "macos-$architecture" \
  --app-root "$app_bundle" --output "$deployment_manifest_path" \
  --source-commit "$source_commit" --runtime-probe "$runtime_probe_path" \
  --signing-inventory "$signing_inventory_path" \
  --locked-qt-root "$locked_qt_root" \
  --python-version "$python_version" --pyqt6-version "$pyqt6_version" \
  --qt-version "$qt_version" --sip-version "$sip_version" \
  --sip-runtime-version "$sip_runtime_version" --r-version "$r_version" \
  --rpy2-version "$rpy2_version" --pyinstaller-version 6.21.0

step "Recording canonical direct target-native production provenance"
cp "$repo_root/scripts/macos_embedded_r_adapter.py" "$qualification_root/embedded-r-adapter.py"
cp "$repo_root/scripts/macos_host_r_isolation.sh" "$qualification_root/macos-host-r-isolation.sh"
cp "$repo_root/scripts/verify_macos_r_pyinstaller_toc.py" "$qualification_root/verify-macos-r-pyinstaller-toc.py"
ppm_contrib_path="$("$python_exe" -c 'import json,sys; p=json.load(open(sys.argv[1])); print(p["binary_package_policy"]["platforms"][sys.argv[2]]["contrib_path"])' "$repo_root/docs/verification/RCMetaR-r-dependencies.json" "macos-$architecture")"
[ -n "$ppm_contrib_path" ] || { echo "Locked PPM contribution path is empty." >&2; exit 1; }
"$python_exe" "$repo_root/scripts/build_macos_direct_provenance.py" \
  --qualification-root "$qualification_root" --ppm-root "$ppm_archive_root" \
  --target "macos-$architecture" --official-r-url "$r_url" \
  --official-r-sha256 "$r_sha256" \
  --ppm-contrib-path "$ppm_contrib_path" \
  --source-commit "$source_commit" --bridge "$rpy2_api_bridge" \
  --output "$r_direct_build_manifest_path"

(
  step "Creating macOS artifact ZIP"
  rm -rf "$archive_staging_root"
  copy_tree "$app_bundle" "$archive_root_dir/RCMetaStudio.app"
  copy_tree "$qualification_root" "$archive_root_dir/qualification"
  ditto -c -k --norsrc --keepParent "$archive_root_dir" "$tmp_zip_path"
)
mv "$tmp_zip_path" "$zip_path"

python3 - "$zip_path" "$archive_root_name" "$skip_smoke" "$r_framework_version" <<'PY'
import stat
import sys
import zipfile

zip_path = sys.argv[1]
archive_root_name = sys.argv[2].rstrip("/")
skip_smoke = sys.argv[3] == "1"
framework_version = sys.argv[4]
framework = f"{archive_root_name}/RCMetaStudio.app/Contents/Frameworks/R.framework"
version_root = f"{framework}/Versions/{framework_version}"
resources = f"{version_root}/Resources"
required = [
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/RCMetaStudio",
    f"{archive_root_name}/RCMetaStudio.app/Contents/Resources/sample_projects/BCG.rcms",
    f"{archive_root_name}/RCMetaStudio.app/Contents/Resources/sample_projects/amino.rcms",
    f"{resources}/bin/Rscript",
    f"{resources}/library/RCMetaR/DESCRIPTION",
    f"{resources}/Info.plist",
    f"{version_root}/R",
    f"{archive_root_name}/qualification/ad-hoc-signing-inventory.json",
    f"{archive_root_name}/RCMetaStudio.app/Contents/Resources/LaunchRCMetaStudio.command",
    f"{archive_root_name}/qualification/deployment-manifest.json",
    f"{archive_root_name}/qualification/runtime-probe.json",
    f"{archive_root_name}/qualification/embedded-r-runtime-profile.json",
    f"{archive_root_name}/qualification/direct-r-build-manifest.json",
]
expected_links = {
    f"{framework}/Versions/Current": framework_version,
    f"{framework}/Resources": "Versions/Current/Resources",
    f"{resources}/lib/libR.dylib": "../../R",
    f"{framework}/R": "Versions/Current/R",
}
required.extend(expected_links)
if not skip_smoke:
    required.extend([
        f"{archive_root_name}/qualification/packaged-smoke.json",
        f"{archive_root_name}/qualification/packaged-smoke.log",
        f"{archive_root_name}/qualification/launchservices-completion.json",
        f"{archive_root_name}/qualification/packaged-smoke.stdout.log",
        f"{archive_root_name}/qualification/packaged-smoke.stderr.log",
        f"{archive_root_name}/qualification/packaged-smoke.hang-trace.log",
    ])
with zipfile.ZipFile(zip_path) as archive:
    names = set(archive.namelist())
    info_by_name = {info.filename: info for info in archive.infolist()}
    for path, target in expected_links.items():
        if path not in info_by_name:
            continue
        info = info_by_name[path]
        mode = info.external_attr >> 16
        if (
            not stat.S_ISLNK(mode)
            or archive.read(path).decode("utf-8") != target
        ):
            raise SystemExit(f"Created ZIP has a noncanonical R framework alias: {path}")
outside_root = [
    name for name in names if name and not name.startswith(f"{archive_root_name}/")
]
if outside_root:
    raise SystemExit(
        "Created ZIP has entries outside "
        f"{archive_root_name}: " + ", ".join(sorted(outside_root)[:10])
    )
missing = [path for path in required if path not in names]
if missing:
    raise SystemExit("Created ZIP is missing: " + ", ".join(missing))
PY

if [ "$skip_smoke" -eq 0 ]; then
  "$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" archive \
    --target "macos-$architecture" \
    --archive "$zip_path" --archive-root-name "$archive_root_name" \
    --deployment-manifest "$deployment_manifest_path" \
    --signing-inventory "$signing_inventory_path" \
    --runtime-probe "$runtime_probe_path" \
    --runtime-stdout "$runtime_stdout_path" --runtime-stderr "$runtime_stderr_path" \
    --r-runtime-profile "$r_runtime_profile_path" \
    --direct-build-manifest "$r_direct_build_manifest_path" \
    --smoke-evidence "$smoke_evidence_path" --smoke-log "$smoke_log_path" \
    --smoke-stdout "$smoke_stdout_path" --smoke-stderr "$smoke_stderr_path" \
    --hang-trace "$hang_trace_path" \
    --launchservices-marker "$launchservices_marker_path" \
    --output "$archive_inspection_path"
fi

if [ "$skip_smoke" -eq 0 ]; then
  step "Extracting the exact ZIP and requalifying its normal app entry"
  extracted_root="$work_root/extracted-qualification"
  rm -rf "$extracted_root"
  mkdir -p "$extracted_root"
  ditto -x -k "$zip_path" "$extracted_root"
  extracted_app="$extracted_root/$archive_root_name/RCMetaStudio.app"
  extracted_probe="$qualification_root/extracted-runtime-probe.json"
  extracted_manifest="$qualification_root/extracted-deployment-manifest.json"
  extracted_smoke="$qualification_root/extracted-packaged-smoke.json"
  extracted_smoke_log="$qualification_root/extracted-packaged-smoke.log"
  extracted_stdout="$qualification_root/extracted-packaged-smoke.stdout.log"
  extracted_stderr="$qualification_root/extracted-packaged-smoke.stderr.log"
  extracted_hang_trace="$qualification_root/extracted-packaged-smoke.hang-trace.log"
  extracted_marker="$qualification_root/extracted-launchservices-completion.json"
  extracted_pid="$qualification_root/extracted-launchservices.pid"
  extracted_r_home="$extracted_app/Contents/Frameworks/R.framework/Resources"
  extracted_r_lib="$extracted_r_home/library"
  [ -x "$extracted_app/Contents/MacOS/RCMetaStudio" ] || { echo "Exact ZIP extraction lacks the app entry executable." >&2; exit 1; }
  [ -x "$extracted_r_home/bin/Rscript" ] || { echo "Exact ZIP extraction lacks private R." >&2; exit 1; }
  run_extracted() {
    env -u QT_QPA_PLATFORM RCMS_REQUIRE_IN_PROCESS_RPY2=1 RPY2_CFFI_MODE=API \
      RCMS_R_HOME="$extracted_r_home" RCMS_R_LIBS="$extracted_r_lib" \
      "$python_exe" "$repo_root/scripts/run_bounded_process.py" --timeout-seconds 900 \
      --stdout "$extracted_stdout" --stderr "$extracted_stderr" -- "$@"
  }
  : > "$extracted_hang_trace"
  run_extracted "$extracted_app/Contents/MacOS/RCMetaStudio" --automation-package-runtime-probe "$extracted_probe"
  QT_SCALE_FACTOR=1.25 RCMS_PACKAGE_BASELINE_DPR="$("$python_exe" -c 'import json,sys; print(json.load(open(sys.argv[1]))["qt"]["baseline_device_pixel_ratio"])' "$extracted_probe")" \
    RCMS_PACKAGE_SMOKE_EVIDENCE="$extracted_smoke" RCMS_AUTOMATION_SMOKE_LOG="$extracted_smoke_log" RCMS_AUTOMATION_HANG_TRACE="$extracted_hang_trace" \
    env -u QT_QPA_PLATFORM RCMS_REQUIRE_IN_PROCESS_RPY2=1 RPY2_CFFI_MODE=API \
      RCMS_R_HOME="$extracted_r_home" RCMS_R_LIBS="$extracted_r_lib" \
      "$python_exe" "$repo_root/scripts/run_bounded_process.py" --timeout-seconds 900 \
      --stdout "$extracted_stdout" --stderr "$extracted_stderr" \
      --completion-log "$extracted_smoke_log" -- \
      "$extracted_app/Contents/MacOS/RCMetaStudio" --automation-native-smoke "$extracted_app/Contents/Resources/sample_projects/BCG.rcms"
  for scale in "1.25" "1.50" "1.75"; do
    QT_SCALE_FACTOR="$scale" RCMS_PACKAGE_BASELINE_DPR="$("$python_exe" -c 'import json,sys; print(json.load(open(sys.argv[1]))["qt"]["baseline_device_pixel_ratio"])' "$extracted_probe")" \
      RCMS_AUTOMATION_SMOKE_LOG="$extracted_smoke_log" RCMS_PACKAGED_PROCESS_TIMEOUT_SECONDS=60 \
      run_extracted "$extracted_app/Contents/MacOS/RCMetaStudio" --automation-package-surface-smoke "$extracted_smoke" "$scale"
  done
  rm -f "$extracted_marker" "$extracted_pid"
  env -u QT_QPA_PLATFORM RCMS_REQUIRE_IN_PROCESS_RPY2=1 RPY2_CFFI_MODE=API \
    RCMS_R_HOME="$extracted_r_home" RCMS_R_LIBS="$extracted_r_lib" RCMS_STARTUP_PROJECT_SMOKE=1 \
    RCMS_AUTOMATION_SMOKE_LOG="$extracted_smoke_log" RCMS_STARTUP_COMPLETION_MARKER="$extracted_marker" \
    RCMS_AUTOMATION_PID_FILE="$extracted_pid" "$python_exe" "$repo_root/scripts/run_bounded_process.py" \
      --timeout-seconds 900 --stdout "$extracted_stdout" --stderr "$extracted_stderr" --owned-pid-file "$extracted_pid" -- \
      open -W -n "$extracted_app" --args --automation-startup-project-smoke \
        --automation-startup-completion-marker "$extracted_marker" --automation-pid-file "$extracted_pid" \
        --automation-smoke-log "$extracted_smoke_log" "$extracted_app/Contents/Resources/sample_projects/BCG.rcms"
  "$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" finalize-smoke \
    --smoke-evidence "$extracted_smoke" --smoke-log "$extracted_smoke_log" --launchservices-marker "$extracted_marker" \
    --require-direct-teardown
  rm -f "$extracted_pid"
  "$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" inspect \
    --target "macos-$architecture" --app-root "$extracted_app" \
    --output "$extracted_manifest" --source-commit "$source_commit" \
    --runtime-probe "$extracted_probe" --signing-inventory "$signing_inventory_path" \
    --locked-qt-root "$locked_qt_root" --python-version "$python_version" \
    --pyqt6-version "$pyqt6_version" --qt-version "$qt_version" \
    --sip-version "$sip_version" --sip-runtime-version "$sip_runtime_version" \
    --r-version "$r_version" --rpy2-version "$rpy2_version" --pyinstaller-version 6.21.0
  "$python_exe" "$repo_root/scripts/inspect_macos_deployment.py" evidence \
    --target "macos-$architecture" --archive "$zip_path" \
    --deployment-manifest "$deployment_manifest_path" --signing-inventory "$signing_inventory_path" \
    --runtime-probe "$runtime_probe_path" --r-runtime-profile "$r_runtime_profile_path" \
    --direct-build-manifest "$r_direct_build_manifest_path" \
    --smoke-evidence "$smoke_evidence_path" --smoke-log "$smoke_log_path" \
    --smoke-stdout "$smoke_stdout_path" --smoke-stderr "$smoke_stderr_path" \
    --hang-trace "$hang_trace_path" --launchservices-marker "$launchservices_marker_path" \
    --extracted-runtime-probe "$extracted_probe" --extracted-deployment-manifest "$extracted_manifest" \
    --extracted-smoke-evidence "$extracted_smoke" --extracted-smoke-log "$extracted_smoke_log" \
    --extracted-smoke-stdout "$extracted_stdout" --extracted-smoke-stderr "$extracted_stderr" \
    --extracted-hang-trace "$extracted_hang_trace" --extracted-launchservices-marker "$extracted_marker" \
    --archive-inspection "$archive_inspection_path" --output "$qualification_evidence_path"
fi

echo "Created $zip_path"
