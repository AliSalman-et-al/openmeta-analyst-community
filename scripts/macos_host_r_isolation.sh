#!/usr/bin/env bash
# Stateful, same-filesystem isolation of the build host's installed R.framework.

RCMS_HOST_R_STATE="idle"
RCMS_HOST_R_SOURCE=""
RCMS_HOST_R_BACKUP=""
RCMS_HOST_R_IDENTITY=""

rcms_host_r_identity() {
  local framework="$1" current lib node
  [ -d "$framework" ] && [ ! -L "$framework" ] || return 1
  current="$(readlink "$framework/Versions/Current")" || return 1
  lib="$framework/Versions/$current/Resources/lib/libR.dylib"
  [ -f "$lib" ] || return 1
  node="portable"
  if [ "$(uname -s)" = "Darwin" ]; then
    node="$(stat -f '%d:%i' "$framework")" || return 1
  fi
  printf '%s|%s|%s\n' "$node" "$current" "$(cksum "$lib" | awk '{print $1 ":" $2}')"
}

rcms_host_r_move() {
  if [ "${RCMS_HOST_R_USE_SUDO:-1}" = "1" ]; then
    sudo mv "$1" "$2"
  else
    mv "$1" "$2"
  fi
}

rcms_restore_host_r() {
  local observed
  case "$RCMS_HOST_R_STATE" in
    idle) return 0 ;;
    prepared)
      [ -d "$RCMS_HOST_R_SOURCE" ] && [ ! -e "$RCMS_HOST_R_BACKUP" ] \
        || { echo "Host R isolation is ambiguous before mutation." >&2; return 1; }
      ;;
    isolated)
      [ ! -e "$RCMS_HOST_R_SOURCE" ] && [ -d "$RCMS_HOST_R_BACKUP" ] \
        || { echo "Host R isolation is ambiguous during restoration." >&2; return 1; }
      rcms_host_r_move "$RCMS_HOST_R_BACKUP" "$RCMS_HOST_R_SOURCE"
      ;;
    *) echo "Unknown host R isolation state: $RCMS_HOST_R_STATE" >&2; return 1 ;;
  esac
  [ -d "$RCMS_HOST_R_SOURCE" ] && [ ! -e "$RCMS_HOST_R_BACKUP" ] \
    || { echo "Host R restoration did not converge." >&2; return 1; }
  observed="$(rcms_host_r_identity "$RCMS_HOST_R_SOURCE")" \
    || { echo "Restored host R identity cannot be read." >&2; return 1; }
  [ "$observed" = "$RCMS_HOST_R_IDENTITY" ] \
    || { echo "Restored host R identity changed." >&2; return 1; }
  RCMS_HOST_R_STATE="idle"
  trap - EXIT
}

rcms_isolate_host_r() {
  local source="$1" nonce candidate attempt
  [ "$RCMS_HOST_R_STATE" = "idle" ] \
    || { echo "Host R isolation is already active." >&2; return 1; }
  [ -d "$source" ] && [ ! -L "$source" ] \
    || { echo "Host R source is absent or not a concrete directory: $source" >&2; return 1; }
  RCMS_HOST_R_SOURCE="$source"
  RCMS_HOST_R_IDENTITY="$(rcms_host_r_identity "$source")" \
    || { echo "Host R source identity cannot be read." >&2; return 1; }
  nonce="${GITHUB_RUN_ID:-local}.${GITHUB_RUN_ATTEMPT:-0}.$$"
  candidate=""
  for attempt in 1 2 3 4 5; do
    candidate="${source}.rcms-isolated.${nonce}.${attempt}"
    [ -e "$candidate" ] || break
    candidate=""
  done
  [ -n "$candidate" ] \
    || { echo "No unique verified-absent host R backup path is available." >&2; return 1; }
  RCMS_HOST_R_BACKUP="$candidate"
  RCMS_HOST_R_STATE="prepared"
  trap rcms_restore_host_r EXIT
  rcms_host_r_move "$source" "$candidate"
  RCMS_HOST_R_STATE="isolated"
  [ ! -e "$source" ] && [ -d "$candidate" ] \
    || { echo "Host R isolation did not converge." >&2; return 1; }
  [ "$(rcms_host_r_identity "$candidate")" = "$RCMS_HOST_R_IDENTITY" ] \
    || { echo "Isolated host R identity changed." >&2; return 1; }
}
