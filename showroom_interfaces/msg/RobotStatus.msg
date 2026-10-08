# One strongly typed operational snapshot for a showroom robot.
builtin_interfaces/Time stamp
string robot_id
string navigation_state
string route
string current_waypoint
uint32 waypoint_index
uint32 waypoint_total

bool pose_available
geometry_msgs/Pose2D pose
geometry_msgs/Twist command_velocity

bool front_clearance_available
float32 front_clearance_m
bool obstacle_detected
float32 blocked_duration_sec
float32 last_blocked_duration_sec
uint32 block_count

string recovery_policy
string recovery_state
bool action_active
# A negative value means that Nav2 has not supplied this feedback yet.
float32 navigation_time_sec
float32 estimated_time_remaining_sec
float32 distance_remaining_m
uint32 number_of_recoveries
string last_event
