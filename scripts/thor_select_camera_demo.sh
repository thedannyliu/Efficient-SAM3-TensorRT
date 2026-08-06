#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-}"
if [[ "$MODE" != "wired" && "$MODE" != "wifi" ]]; then
  echo "usage: $0 wired|wifi [unified launch arguments...]" >&2
  exit 2
fi
shift

NAME="${GI_CONTAINER_NAME:-instinctsam-unified}"
IMAGE="${GI_UNIFIED_IMAGE:-instinctsam:thor-r39-unified-api}"
desired_source=""
if [[ "$MODE" == "wifi" ]]; then
  desired_source="${GI_WIFI_CAMERA_URL:-}"
  if [[ -z "$desired_source" ]]; then
    echo "Set GI_WIFI_CAMERA_URL to the RTSP or HTTP camera URL" >&2
    exit 2
  fi
  export GI_CAMERA_URI="$desired_source"
else
  unset GI_CAMERA_URI
fi

current_image="$(
  docker inspect --format '{{.Config.Image}}' "$NAME" 2>/dev/null || true
)"
current_environment="$(
  docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' \
    "$NAME" 2>/dev/null || true
)"
current_source="$(
  sed -n 's/^SOURCE=//p' <<<"$current_environment" | head -1
)"
source_matches=false
if [[ "$MODE" == "wired" && "$current_source" == /dev/* ]]; then
  source_matches=true
elif [[ "$MODE" == "wifi" && "$current_source" == "$desired_source" ]]; then
  source_matches=true
fi
if [[ -n "$current_image" &&
  ("$current_image" != "$IMAGE" || "$source_matches" != true) ]]; then
  echo "Replacing the existing GI runtime for the selected camera source"
  docker rm -f "$NAME" >/dev/null
fi

export SAM3_REPOSITORY_ROOT="$REPO_ROOT"
exec bash "$REPO_ROOT/scripts/thor_restart_unified_desktop.sh" "$@"
