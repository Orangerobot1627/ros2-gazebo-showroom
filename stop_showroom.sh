#!/usr/bin/env bash
# Stop the recorded showroom session, and only that session.
#
#   ./stop_showroom.sh          stop the session recorded by start_showroom.sh
#   ./stop_showroom.sh --all    legacy global sweep of every showroom/ros2 node
#
# The session is recorded by start_showroom.sh under $SHOWROOM_STATE_DIR; this
# script signals only that process group, so other ROS 2 users on the machine
# are left alone. Use --all only when a hard terminal close left stray nodes.
set +e

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
state_dir="${SHOWROOM_STATE_DIR:-${XDG_RUNTIME_DIR:-/tmp}/showroom}"
session="${state_dir}/session.env"

stop_group() {
  local pgid="$1"
  [[ -n "${pgid}" ]] || return 0
  kill -TERM -"${pgid}" 2>/dev/null
  local attempt
  for attempt in $(seq 1 20); do
    kill -0 -"${pgid}" 2>/dev/null || return 0
    sleep 0.5
  done
  kill -KILL -"${pgid}" 2>/dev/null
  return 0
}

global_sweep() {
  # Legacy fallback: process names are shared, so this can end other ROS work.
  pkill -x ruby
  pkill -f 'showroom_(reset_pose|task_manager|speed_profile|monitor|panel|asr|tts|llm_bridge|route_visualizer|navigation_gateway|nav2_adapter|default_mission|edge_recorder|pedestrian|acceptance)'
  local name
  for name in controller_serv smoother_server planner_server behavior_server \
              velocity_smooth collision_monit bt_navigator map_server amcl \
              lifecycle_manag robot_state_pub parameter_bridg ros2; do
    pkill -x "${name}"
  done
  sleep 1
}

if [[ "${1:-}" == "--all" ]]; then
  global_sweep
  rm -f "${state_dir}"/session*.env 2>/dev/null
  echo "showroom stopped (global sweep)"
  exit 0
fi

if [[ ! -f "${session}" ]]; then
  echo "No recorded showroom session in ${state_dir}."
  echo "Use ./stop_showroom.sh --all to sweep every showroom/ros2 process." >&2
  exit 0
fi

# shellcheck disable=SC1090
source "${session}"
echo ">> Stopping showroom session " \
     "(domain ${SHOWROOM_DOMAIN_ID:-?}, pgid ${SHOWROOM_PGID:-?})"
stop_group "${SHOWROOM_PGID:-}"
rm -f "${session}"
echo "showroom stopped"
