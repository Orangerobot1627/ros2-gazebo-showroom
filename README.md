# ROS 2 Gazebo Showroom

Gazebo Harmonic migration of the two-robot technology-showroom project. The
Stage implementation remains the accepted business baseline while simulation,
robot dynamics, localization, and navigation are replaced in controlled
milestones.

Current completed milestones:

1. The Stage route, task, policy, robot, and business-event contracts are frozen
   in `showroom_gz_sim/migration/stage_baseline.json` and protected by hashes.
2. The blue guide robot runs in Gazebo with differential drive, wheel joint
   states, 270-degree LiDAR, odometry, TF, and a centralized `ros_gz_bridge`.
3. The accepted Stage occupancy map is served by Nav2 and AMCL localizes the
   guide robot with the frame chain
   `map -> robot_0/odom -> robot_0/base_footprint -> robot_0/base_link`.
4. The guide robot accepts Nav2 `NavigateToPose` goals. NavFn A* supplies the
   global path, Regulated Pure Pursuit tracks it, laser-backed costmaps insert
   dynamic obstacles, and the behavior tree performs controlled recovery.
5. The accepted 65-waypoint Stage guide route now runs through a
   simulator-independent semantic layer. A business request is validated and
   optimized by the route gateway, then the robot adapter executes each
   semantic target with Nav2 and publishes result-driven business events.
6. The green coffee-service robot now runs beside the guide robot with its own
   Gazebo entity, ROS namespace, LiDAR, odometry, TF tree, AMCL instance, Nav2
   stack, semantic adapter, and collision monitor. Both robots share only the
   global map and business event topics.
7. The validated natural-language and voice adapters now live in the
   simulator-independent `showroom_interaction` package. Text commands can use
   Ollama, an OpenAI-compatible endpoint, or the deterministic mock backend;
   Whisper ASR and Piper TTS remain optional.
8. `showroom_interfaces` now generates stable ROS messages, services, and
   actions. The monitor publishes one typed `RobotStatus` per robot while the
   existing JSON topics remain available for compatibility.
9. `/showroom/reset_robot_pose` now safely replaces the Stage reset operation.
   It cancels the active route, commands zero velocity, moves the Gazebo model,
   and reinitializes the corresponding namespaced AMCL pose.
10. The accepted routes are visible in both Gazebo and RViz. Gazebo renders all
    65 guide waypoints, 19 coffee-service waypoints, connecting route lines,
    and a moving beacon for each robot's current semantic target. RViz also
    distinguishes remaining, current, and completed waypoints.
11. Every waypoint has a stable operator code (`G01..G65` or `C01..C19`).
    RViz shows the codes on the full route and the current semantic label;
    Gazebo shows the current code and live mission progress beside the beacon.

Package responsibilities:

- `showroom_description`: ROS URDF and Gazebo SDF xacro robot models.
- `showroom_gz_sim`: metric world, robot spawn, bridge, and migration baseline.
- `showroom_navigation`: semantic routes, graph planning, Nav2 adapter, and
  the default guide mission.
- `showroom_core`: simulator-independent task manager, action policy,
  multi-step plan execution, and aggregate runtime monitor.
- `showroom_interaction`: validated LLM commands, prompt grounding, Whisper
  ASR, and Piper TTS adapters.
- `showroom_bringup`: top-level launch, localization, and Nav2 configuration.
- `showroom_interfaces`: typed robot status, pose reset service, and showroom
  task action contracts.

Build the current migration workspace:

```bash
source /opt/ros/jazzy/setup.bash
cd /home/xxl/ros2_ws
colcon build --packages-select \
  showroom_interfaces showroom_description showroom_gz_sim showroom_navigation \
  showroom_core showroom_interaction showroom_bringup --symlink-install
source install/setup.bash
ros2 run showroom_bringup showroom
```

After the first build, the repository wrapper automatically loads ROS and the
workspace environment. This is the shortest normal entry point:

```bash
cd /home/xxl/ros2_ws/src/showroom_gz
./start_showroom.sh
./start_showroom.sh demo
```

The first command opens Gazebo at the entrance, where both robot models are
visible, and enables local voice commands. Say `开始` or `开始导览` after the
terminal reports `ASR LISTENING: Whisper 已就绪`. The route then starts in
Gazebo; RViz is only used by the `navigation` debugging profile. Select a
ready-made startup profile by adding one short name. The equivalent installed
command is:

```bash
ros2 run showroom_bringup showroom demo
```

Available profiles:

| Profile | Starts |
| --- | --- |
| `manual` | Gazebo with both robots and local voice commands; waits for “开始” (default) |
| `demo` | Gazebo with the full two-robot guide scenario started automatically, local voice commands enabled |
| `headless` | Both robots without Gazebo or RViz windows |
| `mock` | Headless system with the deterministic Mock LLM |
| `llm` | Both robots, RViz and Ollama text interaction |
| `voice` | Both robots, RViz, Ollama, Whisper and Piper |
| `navigation` | Gazebo and RViz for two-robot Nav2 development without the business layer |
| `single` | One guide robot in Gazebo |
| `single_headless` | One guide robot without GUI windows |

List these choices from the installed command, or preview the underlying ROS
command without starting it:

```bash
./start_showroom.sh --list
./start_showroom.sh voice --dry-run
```

The same profiles are also available through a conventional launch command:

```bash
ros2 launch showroom_bringup showroom.launch.py profile:=demo
```

Use `dual_robot.launch.py` or `single_robot.launch.py` directly only when an
advanced launch argument needs to be overridden. The older `guide_autostart`
argument remains available there for semantic-navigation smoke tests; leave it
disabled when `business_auto_start` is enabled.

The interaction layer is disabled by default. Its deterministic backend gives
an offline text-to-business smoke test without Ollama or audio models:

```bash
ros2 run showroom_bringup showroom mock
```

Publish visitor text on `/showroom/user_text`; validated replies appear on
`/showroom/assistant_text`, and allowed business intents are dispatched on
`/showroom/command`:

```bash
ros2 topic pub --once /showroom/user_text std_msgs/msg/String \
  "{data: '开始导览，不需要咖啡'}"
```

Use `llm_backend:=ollama` with `llm_endpoint` and `llm_model` for the local
model service. Add `enable_voice:=true` after the configured faster-whisper and
Piper model paths and PipeWire devices are available.

The microphone front end filters noise before dispatch. It requires a wake word
(`开始`, `开始导览`, `你好机器人`, or `未来科技展馆`) to open a 25 s command
session, rejects short, hallucinated, or high no-speech transcripts, raises its
energy threshold above the measured ambient noise floor, and drops a command
repeated within 6 s. Set `wake_words:=` to empty to forward every utterance.

The two motion pipelines are isolated as
`cmd_vel_nav -> velocity_smoother -> speed_profile -> collision_monitor ->
cmd_vel`. Each collision monitor consumes its robot's own scan and publishes a
namespaced state topic for the business health monitor.

`showroom_core/showroom_speed_profile.py` shapes the smoothed command into a
smooth accelerate/decelerate profile: linear and angular rate limits on the way
up and down, a velocity clamp, and a turn-dependent forward-speed reduction so
the robot eases through corners instead of lurching. Disable it with
`enable_speed_profile:=false` (the monitor then reads `cmd_vel_smoothed`
directly).

Semantic routing uses a validated graph with pluggable edge-cost profiles. The
`shortest` profile is the accepted tour; the `smart` profile adds a turn penalty
(so the route does not double back) and a mild preference for the map-checked
central connectors. Human-initiated missions — temporary visits and guide
edits such as skip or visit-only — set `allow_shortcuts` and run on `smart`, so
they take a visible short cut while still using only build-time-validated
corridors. Enable `learned` edge costs recorded from real runs on top with:

```bash
ros2 launch showroom_bringup single_robot.launch.py \
  enable_edge_learning:=true edge_times_file:=/tmp/showroom_edge_times.yaml
```

The recorder learns an exponential moving average of the seconds each
directed edge takes and the gateway folds it into the `learned` profile.

The collision-monitor stop polygon is a front-focused safety box. It is off by
default because the accepted guide route passes close to the exhibit walls, so a
wide side margin makes the robot pause on the panels while Nav2's costmap
already avoids obstacles. Enable it for a blocked/clearance demonstration with
`safety_stop_enabled:=true`:

```bash
ros2 launch showroom_bringup single_robot.launch.py \
  headless:=true guide_autostart:=true safety_stop_enabled:=true
```

The accepted Stage behaviour is preserved and covered by tests: the 65-waypoint
itinerary and seven task units, human override leases, event-driven coffee
dispatch, task editing, temporary venue visits, and the blocked/clearance
recovery state machine (`test_nav2_health.py`). A full guide run has completed
end to end in Gazebo both with the stop polygon disabled and enabled; with it
enabled, an occasional close panel approach can briefly pause the robot before
it resumes.

Route colors in Gazebo identify the seven guide task units; the green route is
reserved for coffee delivery. The yellow guide beacon and magenta service
beacon move to the current target automatically. Their labels use `G01..G65`
and `C01..C19` and show the active mission's reached/total count. Advanced
launches can hide these visuals with `enable_route_visualization:=false`.

Typed consumers can subscribe to both robots on one durable topic:

```bash
ros2 topic echo /showroom/robot_status \
  showroom_interfaces/msg/RobotStatus
```

Each message contains the robot id, global 2D pose, command velocity, LiDAR
clearance, route progress, blocked duration, recovery state, and Nav2 feedback.
For a live human-readable view, render the durable monitor stream in a terminal:

```bash
ros2 run showroom_core showroom_panel.py          # continuous Chinese panel
ros2 run showroom_core showroom_panel.py --once   # one frame and exit
ros2 run showroom_core showroom_panel.py --detail # raw monitor JSON
```

The `/showroom/status` document also carries a `control_priority` snapshot that
makes the task-tree arbitration explicit: `IDLE`, `DEFAULT_ITINERARY`,
`TEMPORARY_VISIT`, or `HUMAN_OVERRIDE`. A higher level suspends the one below —
a human override or temporary visit pauses the accepted itinerary and the task
manager restores it when the override lease expires or the visit ends.

Reset either robot to a validated map-frame pose with:

```bash
ros2 service call /showroom/reset_robot_pose \
  showroom_interfaces/srv/ResetRobotPose \
  "{robot_id: robot_1, pose: {x: 3.3, y: -14.5, theta: 1.5708}}"
```

The reset proxy rejects unknown robot IDs, non-finite coordinates, and poses
outside the showroom bounds. Disable it with `enable_pose_reset:=false`.

The task manager exposes the typed `ExecuteShowroomTask` action on
`/showroom/execute_task`. It is a typed front end for the same validated command
path as `/showroom/command`: it carries a high-level intent (or a validated JSON
plan), never velocities or coordinates, streams `state`, `current_task`,
`progress`, and `detail` feedback while a mission runs, and returns `accepted`,
`detail`, and `final_state`. The JSON topics stay available for compatibility:

```bash
ros2 action send_goal /showroom/execute_task \
  showroom_interfaces/action/ExecuteShowroomTask \
  "{intent: 'start_tour', coffee: true}" --feedback
```

The launch defaults to `LIBGL_ALWAYS_SOFTWARE=1` for VMware. Use
`headless:=true` for automated checks. Add `rviz:=true` to open the map,
LiDAR, global path, local costmap, and Nav2 control panel:

```bash
ros2 launch showroom_bringup single_robot.launch.py rviz:=true
```

Localization starts automatically with the single-robot launch. In another
terminal, inspect it with:

```bash
source /opt/ros/jazzy/setup.bash
source /home/xxl/ros2_ws/install/setup.bash
ros2 lifecycle get /map_server
ros2 lifecycle get /robot_0/amcl
ros2 topic echo /robot_0/amcl_pose --once
ros2 run tf2_ros tf2_echo map robot_0/base_link
```

Send a navigation goal from a terminal with the same `ROS_DOMAIN_ID`:

```bash
ros2 action send_goal /robot_0/navigate_to_pose \
  nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: map}, pose: {position: {x: 0.0, y: -10.5}, orientation: {z: 0.70710678, w: 0.70710678}}}}"
```

This example drives from the entrance to the accepted Stage waypoint
`stairs_clearance`. Use `navigation:=false` for localization-only tests, or
`localization:=false navigation:=false` for the raw Gazebo robot.

The semantic navigation layer starts by default but waits for a business
request. Start the complete accepted guide itinerary automatically with:

```bash
ros2 launch showroom_bringup single_robot.launch.py \
  rviz:=true guide_autostart:=true
```

The default request contains the seven task units in their accepted order:
reception, technology history, computer vision, robotics, time tunnel, dance,
and lounge. Nav2 plans the collision-aware path between all 64 targets after
the initial `entrance` point. The initial point is omitted because the robot is
already there.

For a short manual smoke test, publish only the reception task. The request
topic deliberately uses reliable, transient-local QoS, so the CLI command must
use the same durability:

```bash
ros2 topic pub --once \
  --qos-reliability reliable \
  --qos-durability transient_local \
  /showroom/navigation_requests std_msgs/msg/String \
  "{data: '{\"request_type\":\"guide_itinerary\",\"robot_id\":\"robot_0\",\"mission_id\":\"manual-reception\",\"start\":\"entrance\",\"task_ids\":[\"reception\"]}'}"
```

Monitor the business result stream in another terminal:

```bash
ros2 topic echo /showroom/robot_events --field data \
  --qos-reliability reliable \
  --qos-durability transient_local
```

A successful task reports `route_started`, one or more `waypoint_reached`
events, and finally `route_completed`. Pause, resume, and cancel remain
business commands on `/showroom/route_commands`; the adapter keeps the current
semantic target and asks Nav2 to replan from the robot's new pose on resume.

With `dual_robot.launch.py` running, dispatch a coffee delivery to the robotics
hall with the same durable QoS contract:

```bash
ros2 topic pub --once \
  --qos-reliability reliable \
  --qos-durability transient_local \
  /showroom/navigation_requests std_msgs/msg/String \
  "{data: '{\"request_type\":\"delivery\",\"robot_id\":\"robot_1\",\"mission_id\":\"manual-coffee-1\",\"service_target\":\"robotics_hall\",\"beverage\":\"coffee\"}'}"
```
