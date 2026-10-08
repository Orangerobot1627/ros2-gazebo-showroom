#!/usr/bin/env bash
# Voice / LLM acceptance runner for the showroom interaction layer.
#
#   ./run_voice_acceptance.sh                          # Mock (fully offline)
#   ./run_voice_acceptance.sh --backend qwen           # local Ollama / Qwen
#   ./run_voice_acceptance.sh --backend offline        # Ollama unreachable
#
# It starts the simulator-independent business stack plus the LLM bridge
# (no Gazebo needed), feeds the fixed command set through /showroom/user_text,
# and writes logs/acceptance/voice_<backend>.json with the recognised intent,
# dispatch decision, task acknowledgement and latency for every line.
set -o pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd -- "${script_dir}/../.." && pwd)"
ros_setup="/opt/ros/jazzy/setup.bash"
workspace_setup="${workspace_dir}/install/setup.bash"

backend='mock'
endpoint='http://192.168.23.1:11434'
model='qwen3.5:4b'
cases=''
report=''
domain="${ROS_DOMAIN_ID:-42}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend) backend="$2"; shift 2 ;;
    --endpoint) endpoint="$2"; shift 2 ;;
    --model) model="$2"; shift 2 ;;
    --cases) cases="$2"; shift 2 ;;
    --report) report="$2"; shift 2 ;;
    --domain) domain="$2"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

case "${backend}" in
  mock) llm_backend='mock' ;;
  qwen) llm_backend='ollama' ;;
  offline) llm_backend='ollama'; endpoint='http://127.0.0.1:9' ;;
  *) echo "backend must be mock|qwen|offline" >&2; exit 2 ;;
esac

source "${ros_setup}"
source "${workspace_setup}"
export ROS_DOMAIN_ID="${domain}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-$(mktemp -d -t showroom_ros_log_XXXXXX)}"
[[ -n "${report}" ]] || report="${script_dir}/logs/acceptance/voice_${backend}.json"
mkdir -p "$(dirname "${report}")"

echo ">> backend=${backend} (${llm_backend}) endpoint=${endpoint} domain=${domain}"

ros2 launch showroom_core business.launch.py \
  auto_start:=false enable_monitor:=false use_sim_time:=false \
  > "${script_dir}/logs/acceptance/voice_${backend}_business.log" 2>&1 &
business_pid=$!
ros2 launch showroom_interaction interaction.launch.py \
  enable_llm:=true enable_voice:=false \
  llm_backend:="${llm_backend}" llm_endpoint:="${endpoint}" \
  llm_model:="${model}" use_sim_time:=false \
  > "${script_dir}/logs/acceptance/voice_${backend}_llm.log" 2>&1 &
llm_pid=$!

cleanup() {
  kill "${business_pid}" "${llm_pid}" >/dev/null 2>&1 || true
  pkill -f showroom_llm_bridge.py >/dev/null 2>&1 || true
  pkill -f showroom_task_manager.py >/dev/null 2>&1 || true
  pkill -f showroom_monitor.py >/dev/null 2>&1 || true
  sleep 2
}
trap cleanup EXIT

# Wait for the LLM bridge to advertise its assistant topic.
ready=0
for _ in $(seq 1 40); do
  if ros2 topic list 2>/dev/null | grep -q '/showroom/assistant_text'; then
    ready=1
    break
  fi
  sleep 1
done
if [[ ${ready} -ne 1 ]]; then
  echo "!! LLM bridge did not start" >&2
  exit 1
fi
sleep 2

report_args=(--backend-label "${backend}" --report "${report}")
[[ -n "${cases}" ]] && report_args+=(--cases "${cases}")

ros2 run showroom_interaction showroom_voice_acceptance.py "${report_args[@]}"
status=$?
echo ">> report: ${report}"
exit ${status}
