#!/usr/bin/env bash
# One-command entry point for the Gazebo showroom.
#
#   ./start_showroom.sh [profile] [extra launch args...]
#
# Environment management:
#   * refuses to start a second live showroom on this machine,
#   * picks an isolated ROS_DOMAIN_ID when the caller has not set one,
#   * records the session (domain + process group) under $SHOWROOM_STATE_DIR,
#   * launches the whole stack in its own session so ./stop_showroom.sh can end
#     exactly this instance and nothing else.
set -eo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd -- "${script_dir}/../.." && pwd)"
ros_setup="/opt/ros/jazzy/setup.bash"
workspace_setup="${workspace_dir}/install/setup.bash"
state_dir="${SHOWROOM_STATE_DIR:-${XDG_RUNTIME_DIR:-/tmp}/showroom}"
session="${state_dir}/session.env"

if [[ ! -r "${ros_setup}" ]]; then
  echo "ROS 2 Jazzy environment not found: ${ros_setup}" >&2
  exit 1
fi
if [[ ! -r "${workspace_setup}" ]]; then
  echo "Workspace is not built: ${workspace_setup}" >&2
  echo "Run colcon build in ${workspace_dir} first." >&2
  exit 1
fi

mkdir -p "${state_dir}"

# Refuse a second live instance; clear a stale record otherwise.
if [[ -f "${session}" ]]; then
  # shellcheck disable=SC1090
  source "${session}"
  if [[ -n "${SHOWROOM_PGID:-}" ]] && kill -0 -"${SHOWROOM_PGID}" 2>/dev/null; then
    echo "A showroom session is already running " \
         "(domain ${SHOWROOM_DOMAIN_ID:-?}, pgid ${SHOWROOM_PGID})." >&2
    echo "Run ./stop_showroom.sh first." >&2
    exit 1
  fi
  rm -f "${session}"
fi

source "${ros_setup}"
source "${workspace_setup}"

# Auto-allocate an isolated ROS domain unless the caller chose one.
if [[ -z "${ROS_DOMAIN_ID:-}" ]]; then
  ROS_DOMAIN_ID=$(( (RANDOM % 71) + 20 ))
fi
export ROS_DOMAIN_ID
export GZ_PARTITION="showroom_domain_${ROS_DOMAIN_ID}"

echo ">> Starting the showroom on ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"
# Own session/process group so the stop script can end exactly this instance.
setsid ros2 run showroom_bringup showroom "$@" &
SHOWROOM_PGID=$!
printf 'SHOWROOM_DOMAIN_ID=%s\nSHOWROOM_PGID=%s\nSHOWROOM_STARTED_AT=%s\n' \
  "${ROS_DOMAIN_ID}" "${SHOWROOM_PGID}" "$(date -Is)" > "${session}"
echo ">> Session pgid ${SHOWROOM_PGID} recorded in ${session}"
echo ">> Stop it with: ${script_dir}/stop_showroom.sh"

trap '"${script_dir}/stop_showroom.sh" >/dev/null 2>&1 || true' EXIT
wait "${SHOWROOM_PGID}"
