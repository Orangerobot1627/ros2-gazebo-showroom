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

`start_showroom.sh` refuses to start a second live instance, picks an isolated
`ROS_DOMAIN_ID` when the caller has not set one, and records the session
(domain + process group) under `$SHOWROOM_STATE_DIR`
(default `${XDG_RUNTIME_DIR:-/tmp}/showroom`). The stop script then ends exactly
that session, so a hard terminal close no longer leaves an extra robot behind
and other ROS 2 users are left alone:

```bash
./stop_showroom.sh          # stop the recorded session only
./stop_showroom.sh --all    # legacy sweep of every showroom/ros2 process
```

The default command (`manual`) is the main mode: it opens Gazebo at the entrance,
where both robot models are visible, and enables local voice commands. Say
`开始` or `开始导览` after the terminal reports `ASR LISTENING: Whisper 已就绪`;
the full default tour then runs in Gazebo. While it runs you can keep talking —
skip or go straight to a hall, stay longer, ask for a drink — and each command
takes over as a higher-priority task and the default itinerary resumes when it
ends. With no further commands the run is exactly the automatic demonstration.
RViz is only used by the debugging profiles. The equivalent installed command is:

```bash
ros2 run showroom_bringup showroom demo
```

Available profiles:

| Profile | Starts |
| --- | --- |
| `manual` | **Main mode**: voice control plus the default route; waits for “开始”, then runs the full tour and accepts commands (default) |
| `demo` | Gazebo with the full two-robot guide scenario started automatically, local voice commands enabled |
| `qwen` | Main mode backed by the local Qwen model (Ollama) instead of Mock |
| `headless` | Both robots without Gazebo or RViz windows |
| `mock` | Headless system with the deterministic Mock LLM |
| `llm` | Both robots, RViz and Ollama text interaction |
| `voice` | Both robots, RViz, Ollama, Whisper and Piper |
| `navigation` | Gazebo and RViz for two-robot Nav2 development without the business layer |
| `single` | One guide robot in Gazebo |
| `single_headless` | One guide robot without GUI windows |

The default keeps the offline Mock backend. `qwen` is the same main mode backed
by the local Qwen model; the dedicated `showroom_qwen.launch.py` also accepts
`llm_endpoint:=` and `llm_model:=` for another local service:

```bash
ros2 launch showroom_bringup showroom_qwen.launch.py \
  llm_endpoint:=http://127.0.0.1:11434 llm_model:=qwen3.5:4b
```

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

The collision monitor runs a two-layer forward safety strip by default:

- `Slowdown` (0.75 m ahead, about 50% speed): eases past a close obstacle
  instead of stopping.
- `SafetyStop` (0.38 m ahead): stops before contact.

Both polygons are deliberately forward-only strips. A footprint-sized box
false-stopped the guide route because the robot brushes past exhibit panels to
within about 0.24 m, so the wide side edge caught them; the forward strip keeps
the front protection without the side false stops. Turn a layer off with
`safety_slowdown_enabled:=false` / `safety_stop_enabled:=false`:

```bash
ros2 launch showroom_bringup single_robot.launch.py \
  headless:=true guide_autostart:=true safety_stop_enabled:=false
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

## Acceptance and continuous integration

Three repository-level entry points make the demo reproducible:

```bash
./run_tests.sh            # every functional test script
./run_tests.sh --lint     # plus the ament flake8 / pep257 / copyright checks
./run_tests.sh --build    # colcon build first, then test

./run_acceptance.sh                      # one guided run for robot_0
./run_acceptance.sh --runs 10            # ten runs + success-rate summary
./run_acceptance.sh --runs 10 --rtf 3    # ten runs faster than real time
./run_acceptance.sh --robot robot_1 \
  --command '{"intent":"deliver_drink","drink":"coffee","target":"lounge"}'

./run_voice_acceptance.sh                    # Mock (fully offline)
./run_voice_acceptance.sh --backend qwen     # local Ollama / Qwen
./run_voice_acceptance.sh --backend offline  # Ollama unreachable
```

`run_acceptance.sh` records each run with
`showroom_core/showroom_acceptance.py` and writes a JSON report under
`logs/acceptance/` with the metrics the acceptance checklist asks for:
waypoints reached, failed targets, Nav2 recoveries, safety interventions,
duration, minimum lidar clearance, and whether `route_completed` was seen.
The recorder exits 0 only on a completed route, so a loop can measure the
success rate directly. Because a run is finally limited by Gazebo's real time,
`--rtf N` loads a copy of the world with a higher `<real_time_factor>`: Nav2
still plans in simulation time, so the route is identical while the wall clock
shrinks (about 3x at `--rtf 3`).

`run_voice_acceptance.sh` drives a fixed command set through
`/showroom/user_text` and records the recognised intent, the whitelist
dispatch decision, the task acknowledgement, and the first-response latency
for Mock, Qwen, and the Ollama-unavailable path.

`.github/workflows/ci.yml` builds the seven packages on `ros:jazzy-ros-base`
and runs the same functional and lint tests on every push and pull request.

### Delivery roadmap

1. **Repeatable acceptance baseline** — lint is clean, CI is in place, and the
   unified test/acceptance commands are added. The 10-run guide soak exposed a
   real bug: the **global costmap re-injected live scan obstacles**, so NavFn
   could not plan from otherwise-open poses and ended the mission with
   `status=6`. Planning on the static map only (real obstacles stay in the
   local costmap for DWB) removed every real route failure: the guide route now
   completes 64/64. Faster-than-real-time runs (`--rtf`) can add a timing
   artifact (action-server ack / TF lapse), which is why reliability is
   measured at or near real time.
2. **Coffee delivery and dual-robot acceptance** — coffee deliveries complete
   end to end and return to standby. The task manager now gives the guide
   right of way: the coffee robot holds while the two robots are within 2 m and
   resumes once the guide clears 2.6 m (guide-priority yield).
3. **Safety-stop strategy** — done: a two-layer forward safety strip
   (slowdown + stop) is on by default, and the guide and coffee routes run
   through it without false stops.
4. **Voice and Qwen acceptance** — validated for Mock, Qwen, and the
   Ollama-unavailable error path.
5. **Runtime environment management** — done: `start_showroom.sh` allocates an
   isolated ROS domain, records the session, and refuses a second instance;
   `stop_showroom.sh` ends only that session (`--all` keeps the old sweep).
6. **Visual fidelity / pedestrians** — later.
7. **Real-robot migration** — later.
