# showroom_gz_sim

Gazebo Harmonic world for the 50 m × 35 m technology showroom. The metric
geometry is transcribed from `demo_stage/tools/generate_showroom_assets.py`, so
the existing semantic landmarks, route coordinates, and Nav2 occupancy-map
origin remain valid.

The simulation package contains the environment and a parameterized robot
model used by both showroom robots:

- outer shell and entrance corridor;
- vision, robotics, tunnel, dance, and lounge partitions;
- coffee bar, exhibition islands, panels, furniture, and plants;
- colored floor zones for visual orientation;
- one dynamic orange test obstacle at `(-2.0, -12.5)`;
- Gazebo physics, sensor, user-command, and scene-broadcast systems;
- blue guide and green coffee-service differential-drive robots matching the
  Stage dimensions;
- 270-degree, 540-sample LiDAR with the Stage range limits;
- a centralized bridge for `/clock`, command velocity, odometry, scan, joint
  states, and TF.

Generate and validate the world:

```bash
python3 scripts/generate_showroom_world.py
python3 test/test_showroom_world.py
```

Build and launch the world by itself:

```bash
source /opt/ros/jazzy/setup.bash
cd /home/xxl/ros2_ws
colcon build --packages-select showroom_gz_sim --symlink-install
source install/setup.bash
ros2 launch showroom_gz_sim showroom_gz.launch.py
```

Launch the accepted milestone with the guide robot:

```bash
colcon build --packages-select \
  showroom_description showroom_gz_sim showroom_bringup --symlink-install
source install/setup.bash
ros2 launch showroom_bringup single_robot.launch.py
```

The initial robot pose is `(0.0, -14.5, 90 deg)`, matching Stage. Its ROS
interfaces are:

```text
/robot_0/cmd_vel
/robot_0/odom
/robot_0/scan
/robot_0/joint_states
/tf
/tf_static
```

For a short manual motion check:

```bash
ros2 topic pub /robot_0/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.2}, angular: {z: 0.0}}" -r 10
```

The launch file enables `LIBGL_ALWAYS_SOFTWARE=1` by default because VMware's
virtual OpenGL driver flickers with the Gazebo GUI. On a physical machine with
stable hardware acceleration it can be disabled explicitly:

```bash
ros2 launch showroom_gz_sim showroom_gz.launch.py software_rendering:=false
```

Gazebo Transport is isolated as `showroom_domain_$ROS_DOMAIN_ID`, so a second
Gazebo process in another ROS Domain cannot publish into this world's clock or
services.

Run the single-robot simulation without the Gazebo GUI:

```bash
ros2 launch showroom_bringup single_robot.launch.py headless:=true
```

The Stage contract and migration acceptance notes are in
`migration/STAGE_BASELINE.md`. The top-level dual-robot launch is provided by
`showroom_bringup`.
