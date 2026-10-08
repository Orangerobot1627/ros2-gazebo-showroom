# Stage migration baseline

This file records the accepted Stage behavior before replacing its simulation
and navigation backends. The machine-readable contract is
`stage_baseline.json`.

The baseline points to commit
`fa25d97eb48e8d3d0a73c1a40c696801de96f572` of `demo_stage`. SHA-256 hashes
cover the route, semantic graph, task-unit, action-policy, and robot-description
sources. A changed hash means the migration comparison must be reviewed and the
baseline intentionally renewed.

## Preserved behavior

- The guide itinerary contains 65 ordered waypoints and seven semantic task
  units, from reception through the lounge.
- Human commands may temporarily override the default itinerary. Completion or
  lease expiry returns control to the saved default task.
- Coffee work is event-driven. Its accepted event sequence is recorded in the
  JSON contract and must not be replaced with fixed wall-clock delays.
- LLM, voice, task arbitration, task editing, and multi-step planning stay above
  the navigation backend boundary.

## Milestone 2 interface change

Gazebo keeps the robot namespace and command/odometry contract. The Stage topic
`/robot_0/base_scan` becomes the conventional Nav2 topic `/robot_0/scan`.
`/ground_truth` is deliberately excluded because later localization must use
TF and AMCL instead of simulator truth.

The first Gazebo milestone is accepted only when `/clock`, `/robot_0/odom`,
`/robot_0/scan`, `/robot_0/joint_states`, `/tf`, and `/tf_static` are active and
a bounded `/robot_0/cmd_vel` command produces matching translation and rotation.
