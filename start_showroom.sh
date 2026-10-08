#!/usr/bin/env bash
# One-command entry point for the Gazebo showroom.

set -eo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd -- "${script_dir}/../.." && pwd)"
ros_setup="/opt/ros/jazzy/setup.bash"
workspace_setup="${workspace_dir}/install/setup.bash"

if [[ ! -r "${ros_setup}" ]]; then
  echo "ROS 2 Jazzy environment not found: ${ros_setup}" >&2
  exit 1
fi

if [[ ! -r "${workspace_setup}" ]]; then
  echo "Workspace is not built: ${workspace_setup}" >&2
  echo "Run colcon build in ${workspace_dir} first." >&2
  exit 1
fi

source "${ros_setup}"
source "${workspace_setup}"
exec ros2 run showroom_bringup showroom "$@"
