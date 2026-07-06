#!/usr/bin/env bash
set -euo pipefail

artifact_name=""
archive_root_name=""
architecture=""
python_exe=""
r_runtime_root="${RCMS_R_HOME:-${R_HOME:-}}"
r_package_cache_root=""
bundle_identifier="org.researchconsultancy.rc-metastudio"
skip_dependency_install=0
skip_clean=0
skip_smoke=0

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
    --r-package-cache-root)
      r_package_cache_root="$2"
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
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
app_source_dir="$repo_root/src/rc_metastudio"
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
case "${architecture:-}" in
  x64)
    expected_machine="x86_64"
    pyinstaller_target_architecture="x86_64"
    default_artifact="RCMetaStudio-macos-x64"
    ;;
  arm64)
    expected_machine="arm64"
    pyinstaller_target_architecture="arm64"
    default_artifact="RCMetaStudio-macos-arm64"
    ;;
  "")
    if [ "$host_machine" = "arm64" ]; then
      architecture="arm64"
      expected_machine="arm64"
      pyinstaller_target_architecture="arm64"
      default_artifact="RCMetaStudio-macos-arm64"
    else
      architecture="x64"
      expected_machine="x86_64"
      pyinstaller_target_architecture="x86_64"
      default_artifact="RCMetaStudio-macos-x64"
    fi
    ;;
  *)
    echo "--architecture must be x64 or arm64." >&2
    exit 1
    ;;
esac

if [ "$host_machine" != "$expected_machine" ]; then
  echo "Requested $architecture build requires $expected_machine host, but this host is $host_machine." >&2
  exit 1
fi

artifact_name="${artifact_name:-$default_artifact}"
dist_root="$repo_root/build/macos-package/$architecture/dist"
work_root="$repo_root/build/macos-package/$architecture/work"
app_bundle="$dist_root/RCMetaStudio.app"
app_root="$app_bundle/Contents/MacOS"
archive_root_name="${archive_root_name:-$artifact_name}"
if [[ -z "$archive_root_name" || "$archive_root_name" == *"/"* || "$archive_root_name" == *"\\"* ]]; then
  echo "--archive-root-name must be a single portable directory name." >&2
  exit 2
fi
archive_staging_root="$work_root/zip-staging"
archive_root_dir="$archive_staging_root/$archive_root_name"
zip_path="$artifact_dir/$artifact_name.zip"
tmp_zip_path="$zip_path.tmp"
r_package_cache_root="${r_package_cache_root:-$artifact_dir/r-library-cache}"

if [ "$skip_dependency_install" -eq 0 ]; then
  step "Syncing locked verification environment"
  (cd "$repo_root" && uv sync --locked)
  python_exe="$repo_root/.venv/bin/python"
fi

python_exe="${python_exe:-$repo_root/.venv/bin/python}"
python_exe="$(repo_path "$python_exe")"
if [ ! -x "$python_exe" ]; then
  echo "Python executable was not found or is not executable: $python_exe" >&2
  exit 1
fi

"$python_exe" - <<'PY'
import PyInstaller
import sys
if sys.version_info[:2] != (3, 11):
    raise SystemExit("macOS packaging requires Python 3.11.")
if PyInstaller.__version__ != "6.21.0":
    raise SystemExit("macOS packaging requires PyInstaller 6.21.0.")
PY

if [ -z "$r_runtime_root" ]; then
  r_runtime_root="$(R RHOME)"
fi
if [ -z "$r_runtime_root" ]; then
  echo "No source R runtime was found. Pass --r-runtime-root or set RCMS_R_HOME/R_HOME." >&2
  exit 1
fi
r_runtime_root="$(resolve_existing_dir "$r_runtime_root" "Source R runtime")"
if [ ! -d "$r_runtime_root/bin" ]; then
  echo "Source R runtime is missing bin under $r_runtime_root." >&2
  exit 1
fi

if [ "$skip_clean" -eq 0 ]; then
  rm -rf "$dist_root" "$work_root"
fi
rm -rf "$zip_path" "$tmp_zip_path"
mkdir -p "$artifact_dir"
require_free_space_gb "$repo_root" 6

(
  cd "$repo_root"
  pyinstaller_args=(
    --noconfirm
    --windowed
    --name RCMetaStudio
    --target-architecture "$pyinstaller_target_architecture"
    --osx-bundle-identifier "$bundle_identifier"
    --distpath "$dist_root"
    --workpath "$work_root"
    --paths "$app_source_dir"
    --paths "$app_source_dir/forms"
    --hidden-import icons_rc
    --hidden-import rpy2.robjects
    --hidden-import rpy2.rinterface
    "src/rc_metastudio/__main__.py"
  )
  if [ "$skip_clean" -eq 0 ]; then
    pyinstaller_args=(--clean "${pyinstaller_args[@]}")
  fi
  step "Building ad-hoc macOS app bundle with PyInstaller"
  R_HOME="$r_runtime_root" RPY2_CFFI_MODE=ABI "$python_exe" -m PyInstaller "${pyinstaller_args[@]}"
)

if [ ! -x "$app_root/RCMetaStudio" ]; then
  echo "RCMetaStudio executable was not created at $app_root/RCMetaStudio." >&2
  exit 1
fi

step "Bundling sample projects and R runtime"
copy_tree "$repo_root/sample_projects" "$app_root/sample_projects"
copy_tree "$r_runtime_root" "$app_root/R"

r_home="$app_root/R"
r_lib="$r_home/library"
rscript="$r_home/bin/Rscript"
r_binary="$r_home/bin/R"

if [ ! -x "$rscript" ] || [ ! -x "$r_binary" ]; then
  echo "Bundled R runtime is missing R or Rscript under $r_home/bin." >&2
  exit 1
fi

r_version_cache_key="$("$rscript" -e "cat(paste0('R-', getRversion()))")"
sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

sha256_stdin_12() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print substr($1, 1, 12)}'
  else
    shasum -a 256 | awk '{print substr($1, 1, 12)}'
  fi
}

r_dependency_policy_hash="$({
  printf '%s' "$(sha256_file "$repo_root/scripts/install-r-deps.R")"
  printf '%s' "$(sha256_file "$repo_root/docs/verification/RCMetaR-r-dependencies.json")"
  printf '%s' "$(sha256_file "$repo_root/r/RCMetaR/DESCRIPTION")"
  printf '%s' "${RCMS_CRAN_REPO:-https://cloud.r-project.org}"
} | sha256_stdin_12)"
r_package_cache_key="${r_version_cache_key}-rdeps-${r_dependency_policy_hash}"
cache_library="$r_package_cache_root/$r_package_cache_key/library"

test_r_dependency_packages() {
  local library="$1"
  [ -d "$library" ] || return 1
  R_HOME="$r_home" R_LIBS="$library" R_LIBS_USER="$library" "$rscript" -e "lib <- normalizePath('$library', winslash='/'); .libPaths(c(lib, .libPaths())); pkgs <- c('HSROC','metafor','lme4','pdftools','igraph','mice','Hmisc'); ok <- vapply(pkgs, requireNamespace, logical(1), quietly=TRUE); if (!all(ok)) quit(status=1); if (as.character(packageVersion('HSROC')) != '2.1.9') quit(status=1)" >/dev/null 2>&1
}

test_bundled_r_packages() {
  local library="$1"
  [ -d "$library" ] || return 1
  R_HOME="$r_home" R_LIBS="$library" R_LIBS_USER="$library" "$rscript" -e "lib <- normalizePath('$library', winslash='/'); .libPaths(c(lib, .libPaths())); pkgs <- c('HSROC','RCMetaR','metafor','lme4','pdftools','igraph','mice','Hmisc'); ok <- vapply(pkgs, requireNamespace, logical(1), quietly=TRUE); if (!all(ok)) quit(status=1); if (as.character(packageVersion('HSROC')) != '2.1.9') quit(status=1)" >/dev/null 2>&1
}

copy_r_library() {
  local source="$1"
  local destination="$2"
  copy_tree "$source" "$destination"
}

copy_r_library_packages() {
  local source="$1"
  local destination="$2"
  if [ ! -d "$source" ]; then
    echo "Source R library was not found: $source" >&2
    exit 1
  fi
  mkdir -p "$destination"
  for package in "$source"/*; do
    [ -d "$package" ] || continue
    copy_tree "$package" "$destination/$(basename "$package")"
  done
}

install_local_r_packages() {
  local package_build_root="$work_root/r-package-build"
  rm -rf "$package_build_root"
  mkdir -p "$package_build_root"
  cp -R "$repo_root/r/RCMetaR" "$package_build_root/RCMetaR"
  find "$package_build_root" \( -name '*.o' -o -name '*.so' -o -name '*.dll' \) -delete

  R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" "$r_binary" CMD INSTALL --library="$r_lib" "$package_build_root/RCMetaR"
}

if test_r_dependency_packages "$cache_library"; then
  echo "Using cached bundled R library from $cache_library"
  copy_r_library_packages "$cache_library" "$r_lib"
else
  step "Installing bundled R package dependencies"
  R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" "$rscript" "$repo_root/scripts/install-r-deps.R"
  if test_r_dependency_packages "$r_lib"; then
    echo "Caching bundled R dependency library at $cache_library"
    copy_r_library "$r_lib" "$cache_library"
  fi
fi

step "Installing local RCMetaR package"
install_local_r_packages
R_HOME="$r_home" R_LIBS="$r_lib" R_LIBS_USER="$r_lib" "$rscript" -e "pkgs <- c('HSROC','RCMetaR','metafor','lme4','pdftools','igraph','mice','Hmisc'); ok <- vapply(pkgs, require, logical(1), character.only=TRUE); print(ok); if (!all(ok)) quit(status=1); if (as.character(packageVersion('HSROC')) != '2.1.9') quit(status=1)"

if ! test_bundled_r_packages "$r_lib"; then
  echo "Bundled R package verification failed after local RCMetaR install." >&2
  exit 1
fi

cat > "$app_root/LaunchRCMetaStudio.command" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export RPY2_CFFI_MODE=ABI
export RCMS_R_HOME="$APP_DIR/R"
export RCMS_R_LIBS="$APP_DIR/R/library"
exec "$APP_DIR/RCMetaStudio" "$APP_DIR/sample_projects/amino.rcms"
SH
chmod +x "$app_root/LaunchRCMetaStudio.command"

for required_path in \
  "$app_root/RCMetaStudio" \
  "$app_root/sample_projects/BCG.rcms" \
  "$app_root/sample_projects/amino.rcms" \
  "$app_root/R/bin/Rscript" \
  "$app_root/R/library/RCMetaR/DESCRIPTION" \
  "$app_root/LaunchRCMetaStudio.command"
do
  if [ ! -e "$required_path" ]; then
    echo "Packaged macOS app is missing $required_path." >&2
    exit 1
  fi
done

if [ "$skip_smoke" -eq 0 ]; then
  sample_path="$app_root/sample_projects/amino.rcms"
  step "Running packaged macOS smoke checks"
  QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" RCMS_REQUIRE_IN_PROCESS_RPY2=1 RPY2_CFFI_MODE=ABI RCMS_R_HOME="$r_home" RCMS_R_LIBS="$r_lib" "$app_root/RCMetaStudio" --automation-smoke "$sample_path"
  QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" RCMS_STARTUP_PROJECT_SMOKE=1 RCMS_REQUIRE_IN_PROCESS_RPY2=1 RPY2_CFFI_MODE=ABI RCMS_R_HOME="$r_home" RCMS_R_LIBS="$r_lib" "$app_root/RCMetaStudio" "$sample_path"
fi

(
  step "Creating macOS artifact ZIP"
  rm -rf "$archive_staging_root"
  copy_tree "$app_bundle" "$archive_root_dir/RCMetaStudio.app"
  cd "$archive_staging_root"
  zip -qry "$tmp_zip_path" "$archive_root_name"
)
mv "$tmp_zip_path" "$zip_path"

python3 - "$zip_path" "$archive_root_name" <<'PY'
import sys
import zipfile

zip_path = sys.argv[1]
archive_root_name = sys.argv[2].rstrip("/")
required = [
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/RCMetaStudio",
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/sample_projects/BCG.rcms",
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/sample_projects/amino.rcms",
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/R/bin/Rscript",
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/R/library/RCMetaR/DESCRIPTION",
    f"{archive_root_name}/RCMetaStudio.app/Contents/MacOS/LaunchRCMetaStudio.command",
]
with zipfile.ZipFile(zip_path) as archive:
    names = set(archive.namelist())
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

echo "Created $zip_path"
