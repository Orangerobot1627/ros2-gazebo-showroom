#!/usr/bin/env bash
# Headless acceptance runner for the Gazebo showroom.
#
#   ./run_acceptance.sh                 one guided run for robot_0
#   ./run_acceptance.sh --runs 10       ten runs, then report the success rate
#   ./run_acceptance.sh --robot robot_1 \
#       --command '{"intent":"deliver_drink","drink":"coffee","target":"lounge"}'
#
# Each run: clean -> launch (headless) -> wait for the Nav2 stacks -> record one
# mission with showroom_core/showroom_acceptance -> stop. The per-run JSON
# reports land in logs/acceptance/ and a summary is printed at the end.
set -o pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd -- "${script_dir}/../.." && pwd)"
ros_setup="/opt/ros/jazzy/setup.bash"
workspace_setup="${workspace_dir}/install/setup.bash"

runs=1
robot='robot_0'
command='{"intent":"start_tour"}'
timeout_sec=900
ready_lines=5
ready_timeout=150
rtf='1.0'
launch_file='dual_robot.launch.py'
launch_args=(headless:=true rviz:=false business_auto_start:=false enable_llm:=false)
min_success=''
stamp="$(date +%Y%m%d-%H%M%S)"
report_dir="${script_dir}/logs/acceptance"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runs) runs="$2"; shift 2 ;;
    --robot) robot="$2"; shift 2 ;;
    --command) command="$2"; shift 2 ;;
    --timeout) timeout_sec="$2"; shift 2 ;;
    --ready-lines) ready_lines="$2"; shift 2 ;;
    --ready-timeout) ready_timeout="$2"; shift 2 ;;
    --rtf) rtf="$2"; shift 2 ;;
    --launch) launch_file="$2"; shift 2 ;;
    --launch-arg) launch_args+=("$2"); shift 2 ;;
    --min-success-rate) min_success="$2"; shift 2 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

source "${ros_setup}"
source "${workspace_setup}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-$(mktemp -d -t showroom_ros_log_XXXXXX)}"
# Isolated domain + session record so cleanup ends only this run's processes.
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-$(( (RANDOM % 71) + 20 ))}"
export GZ_PARTITION="showroom_domain_${ROS_DOMAIN_ID}"
state_dir="${SHOWROOM_STATE_DIR:-${XDG_RUNTIME_DIR:-/tmp}/showroom}"
session="${state_dir}/session.env"
mkdir -p "${state_dir}"
echo ">> ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"

mkdir -p "${report_dir}"

# Optional faster-than-real-time soak: point Gazebo at a copy of the world
# whose <real_time_factor> is raised. Nav2 still plans in simulation time, so
# the route behaves identically while the wall clock shrinks.
if awk "BEGIN{exit !(${rtf} > 1.0)}"; then
  base_world="$(ros2 pkg prefix showroom_gz_sim 2>/dev/null)/share/showroom_gz_sim/worlds/showroom.sdf"
  fast_world="${report_dir}/showroom_rtf${rtf}.sdf"
  sed "s#<real_time_factor>[0-9.]*</real_time_factor>#<real_time_factor>${rtf}</real_time_factor>#" \
    "${base_world}" > "${fast_world}"
  launch_args+=("world_file:=${fast_world}")
fi
echo ">> real_time_factor=${rtf}"

stop_showroom() {
  # Best-effort cleanup; the workspace ships stop_showroom.sh for this.
  "${script_dir}/stop_showroom.sh" >/dev/null 2>&1 || true
  sleep 3
}

wait_ready() {
  local log="$1" waited=0
  while [[ ${waited} -lt ${ready_timeout} ]]; do
    if [[ "$(grep -cE 'Managed nodes are active' "${log}" 2>/dev/null)" \
          -ge ${ready_lines} ]]; then
      sleep 3
      return 0
    fi
    sleep 2
    waited=$((waited + 2))
  done
  return 1
}

success=0
completed=0
declare -a run_results

for i in $(seq 1 "${runs}"); do
  echo "=============================================================="
  echo " Run ${i}/${runs}  robot=${robot}  command=${command}"
  echo "=============================================================="
  stop_showroom
  launch_log="${report_dir}/launch_${stamp}_run${i}.log"
  report="${report_dir}/run_${stamp}_${i}.json"

  setsid ros2 launch showroom_bringup "${launch_file}" "${launch_args[@]}" \
    > "${launch_log}" 2>&1 &
  launch_pid=$!
  printf 'SHOWROOM_DOMAIN_ID=%s\nSHOWROOM_PGID=%s\nSHOWROOM_STARTED_AT=%s\n' \
    "${ROS_DOMAIN_ID}" "${launch_pid}" "$(date -Is)" > "${session}"

  if ! wait_ready "${launch_log}"; then
    echo "  !! Nav2 stacks did not become ready in ${ready_timeout}s"
    run_results+=("run : NOT_READY")
    stop_showroom
    continue
  fi

  ros2 run showroom_core showroom_acceptance.py \
    --robot "${robot}" \
    --command "${command}" \
    --timeout-sec "${timeout_sec}" \
    --report "${report}"
  status=$?

  if [[ ${status} -eq 0 ]]; then
    success=$((success + 1))
    run_results+=("run ${i}: COMPLETED")
  else
    run_results+=("run ${i}: FAILED")
  fi
  completed=$((completed + 1))

  stop_showroom
done

echo
echo "=============================================================="
echo " Acceptance summary (${completed}/${runs} runs executed)"
echo "=============================================================="
printf '  %s\n' "${run_results[@]}"
rate=0
if [[ ${completed} -gt 0 ]]; then
  rate=$(( success * 100 / completed ))
fi
echo "  route_completed: ${success}/${completed}  (${rate}%)"
echo "  reports: ${report_dir}"
echo "=============================================================="

if [[ -n "${min_success}" && ${rate} -lt ${min_success} ]]; then
  echo "Success rate ${rate}% is below the required ${min_success}%." >&2
  exit 1
fi
