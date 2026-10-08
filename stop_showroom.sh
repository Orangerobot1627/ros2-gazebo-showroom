#!/usr/bin/env bash
# Stop every showroom process, including the python nodes that `ros2 launch`
# can leave behind when a terminal is closed abruptly. Leftover nodes are the
# usual reason a stale robot or extra Gazebo model keeps showing up.

set +e

# Gazebo server/GUI.
pkill -x ruby
# Showroom python nodes (their process name is "python3", not the script name).
pkill -f 'showroom_(reset_pose|task_manager|speed_profile|monitor|panel|asr|tts|llm_bridge|route_visualizer|navigation_gateway|nav2_adapter|default_mission|edge_recorder)'
# Nav2 and bridge binaries.
for name in controller_serv smoother_server planner_server behavior_server \
            velocity_smooth collision_monit bt_navigator map_server amcl \
            lifecycle_manag robot_state_pub parameter_bridg ros2; do
  pkill -x "$name"
done

sleep 1
remaining=$(ps -eo comm,args 2>/dev/null \
  | grep -Ei 'gz sim|showroom_|controller_serv|planner_server|collision_monit|amcl' \
  | grep -v grep | wc -l)
if [[ "${remaining}" -eq 0 ]]; then
  echo "showroom stopped: no leftover processes"
else
  echo "showroom stopped, ${remaining} process(es) still reported" >&2
fi
