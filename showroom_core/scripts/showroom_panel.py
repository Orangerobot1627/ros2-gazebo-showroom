#!/usr/bin/env python3
"""
Human-readable operator panel for the showroom monitor stream.

The panel is a thin renderer over the durable `/showroom/monitor` JSON
document published by `showroom_monitor`; it owns no business state. Use
`--detail` to dump the raw JSON or `--once` to print a single frame.
"""

import argparse
import json

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String


STATE_LABELS = {
    'WAITING': '等待', 'NAVIGATING': '导航中', 'BLOCKED': '受阻',
    'PAUSED': '暂停', 'AVOIDING': '绕行', 'COMPLETED': '完成',
    'CANCELLED': '取消', 'READY': '就绪', 'RESUMED_AFTER_CLEARANCE': '已恢复',
    'WAITING_FOR_CLEARANCE': '等待清障', 'LOCAL_BYPASS': '本地绕障',
    'REJOINED_ROUTE': '已回路线',
}

BUSINESS_LABELS = {
    'IDLE': '空闲', 'RECEPTION': '接待', 'TOURING': '导览中',
    'GOING_TO_LOUNGE': '前往休息区', 'PAUSED': '暂停', 'BLOCKED': '受阻',
    'CANCELLED': '取消', 'FAILED': '失败',
    'STANDBY': '待命', 'TO_PICKUP': '前往取货', 'PICKUP': '取货',
    'DELIVERING': '配送中', 'DELIVERED': '已送达', 'RETURNING': '返回中',
    'TEMPORARY_NAVIGATION': '临时导航',
}

TITLE = {'robot_0': '蓝色导览', 'robot_1': '绿色配送'}

PRIORITY_LABELS = {
    'IDLE': '空闲', 'DEFAULT_ITINERARY': '默认导览',
    'TEMPORARY_VISIT': '临时参观', 'HUMAN_OVERRIDE': '人为接管',
}


def label(table, value):
    """Translate a state value for display, falling back to the raw value."""
    if value is None or value == '':
        return '-'
    return table.get(value, str(value))


def format_robot(robot_id, snapshot):
    """Render one robot's operational line block."""
    lines = []
    lines.append(
        f'[{TITLE.get(robot_id, robot_id)}] {robot_id}  '
        f'{label(STATE_LABELS, snapshot.get("navigation_state"))}')
    route = snapshot.get('route') or '-'
    index = snapshot.get('waypoint_index') or 0
    total = snapshot.get('waypoint_total') or 0
    waypoint = snapshot.get('current_waypoint') or '-'
    lines.append(f'    路线: {route}  航点: {index}/{total}  {waypoint}')
    pose = snapshot.get('pose')
    if pose:
        lines.append(
            f'    位姿: ({pose.get("x")}, {pose.get("y")}) '
            f'{pose.get("yaw_deg")}°')
    velocity = snapshot.get('command_velocity') or {}
    clearance = snapshot.get('front_clearance_m')
    clearance_text = '-' if clearance is None else f'{clearance} m'
    lines.append(
        f'    速度: 线 {velocity.get("linear_x", 0.0)} m/s  '
        f'角 {velocity.get("angular_z", 0.0)} rad/s  '
        f'前净空: {clearance_text}')
    lines.append(
        f'    受阻: {snapshot.get("blocked_duration_sec", 0.0)}s '
        f'(累计 {snapshot.get("block_count", 0)} 次)  '
        f'恢复: {label(STATE_LABELS, snapshot.get("recovery_state"))}')
    feedback = snapshot.get('nav2_feedback') or {}
    remaining = feedback.get('distance_remaining_m')
    eta = feedback.get('estimated_time_remaining_sec')
    if remaining is not None or eta is not None:
        lines.append(
            f'    Nav2: 剩余 {remaining} m  预计 {eta} s  '
            f'恢复 {feedback.get("number_of_recoveries", 0)} 次')
    return lines


def render_panel(document):
    """Render the monitor document into a compact multi-line panel."""
    lines = []
    published = document.get('published_at') or ''
    lines.append(f'==== 展馆运行面板  {published} ====')
    business = document.get('business') or {}
    lines.append(
        f'业务  导览: {label(BUSINESS_LABELS, business.get("guide_state"))}'
        f'   配送: {label(BUSINESS_LABELS, business.get("coffee_state"))}')

    priority = business.get('control_priority') or {}
    if priority:
        lines.append(
            f'控制优先级  {label(PRIORITY_LABELS, priority.get("level"))}'
            f' (rank {priority.get("rank", "-")})  '
            f'{priority.get("detail", "")}')

    current = business.get('current_task') or {}
    if isinstance(current, dict) and current:
        lines.append(
            f'当前任务  {current.get("ordinal", "-")}/'
            f'{current.get("total", "-")} {current.get("display_name", "")}')

    plan = business.get('active_plan') or {}
    if isinstance(plan, dict) and plan.get('state') not in (None, 'IDLE'):
        step = plan.get('current_step')
        total = plan.get('step_total') or 0
        done = '-' if step is None else step
        lines.append(
            f'多步计划  {plan.get("plan_id", "-")}  '
            f'状态 {plan.get("state")}  步骤 {done}/{total}')

    temporary = business.get('temporary_navigation')
    if isinstance(temporary, dict) and temporary:
        lines.append(
            f'临时导航  目标 {temporary.get("target_task_id", "-")}  '
            f'剩余 {temporary.get("remaining_sec", "-")}s')

    for robot_id in ('robot_0', 'robot_1'):
        snapshot = (document.get('robots') or {}).get(robot_id)
        if snapshot:
            lines.extend(format_robot(robot_id, snapshot))
    return '\n'.join(lines)


def render_detail(document):
    """Return the raw monitor document as indented JSON."""
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)


class ShowroomPanel(Node):
    """Subscribe to the durable monitor stream and print it for operators."""

    def __init__(self, once=False, detail=False, monitor_topic='/showroom/monitor'):
        super().__init__('showroom_panel')
        self.once = once
        self.detail = detail
        self.printed = False
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(String, monitor_topic, self.monitor_callback, qos)

    def monitor_callback(self, message):
        try:
            document = json.loads(message.data)
        except json.JSONDecodeError:
            return
        if not isinstance(document, dict):
            return
        text = (render_detail(document) if self.detail
                else render_panel(document))
        if self.once:
            print(text, flush=True)
            self.printed = True
        else:
            print('\033[2J\033[H' + text, flush=True)


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true',
                        help='print a single frame and exit')
    parser.add_argument('--detail', action='store_true',
                        help='print the raw monitor JSON instead of the panel')
    parser.add_argument('--topic', default='/showroom/monitor',
                        help='monitor topic to render')
    known, remaining = parser.parse_known_args(args=args)

    rclpy.init(args=remaining)
    node = ShowroomPanel(once=known.once, detail=known.detail,
                         monitor_topic=known.topic)
    try:
        if known.once:
            for _ in range(200):
                rclpy.spin_once(node, timeout_sec=0.1)
                if node.printed:
                    break
        else:
            rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
