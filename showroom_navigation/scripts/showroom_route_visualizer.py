#!/usr/bin/env python3
"""Visualize semantic routes in Gazebo and RViz from one route catalog."""

import json
import math
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from ament_index_python.packages import (
    get_package_prefix,
    get_package_share_directory,
)
from geometry_msgs.msg import Point
from gz.msgs10.empty_pb2 import Empty as GzEmpty
from gz.msgs10.marker_pb2 import Marker as GzMarker
from gz.transport13 import Node as GzNode
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from ros_gz_interfaces.msg import Entity
from ros_gz_interfaces.srv import SetEntityPose
from std_msgs.msg import ColorRGBA, String
from visualization_msgs.msg import Marker, MarkerArray
import yaml


GUIDE_ROUTE = 'guide_full_route'
COFFEE_ROUTE = 'coffee_delivery_route'
ROBOT_ROUTES = {'robot_0': GUIDE_ROUTE, 'robot_1': COFFEE_ROUTE}
BEACON_NAMES = {
    'robot_0': 'guide_target_beacon',
    'robot_1': 'coffee_target_beacon',
}
ROUTE_COLORS = {
    GUIDE_ROUTE: (0.10, 0.58, 1.00, 1.0),
    COFFEE_ROUTE: (0.10, 0.90, 0.34, 1.0),
}
ROBOT_TITLES = {'robot_0': 'GUIDE', 'robot_1': 'COFFEE'}
TASK_COLORS = (
    (0.18, 0.62, 1.00, 1.0),
    (1.00, 0.66, 0.12, 1.0),
    (0.15, 0.85, 0.95, 1.0),
    (0.25, 0.86, 0.38, 1.0),
    (0.95, 0.20, 0.24, 1.0),
    (0.84, 0.25, 0.92, 1.0),
    (1.00, 0.48, 0.16, 1.0),
)


def load_route_catalog(routes_file, task_units_file):
    """Load the authoritative route points and task color assignments."""
    route_document = yaml.safe_load(
        Path(routes_file).read_text(encoding='utf-8')) or {}
    task_document = yaml.safe_load(
        Path(task_units_file).read_text(encoding='utf-8')) or {}
    configured = route_document.get('routes') or {}
    routes = {}
    for route_name in (GUIDE_ROUTE, COFFEE_ROUTE):
        waypoints = configured.get(route_name, {}).get('waypoints') or []
        routes[route_name] = [
            {
                'x': float(item['x']),
                'y': float(item['y']),
                'label': str(item['label']),
            }
            for item in waypoints
        ]
    if len(routes[GUIDE_ROUTE]) != 65:
        raise ValueError('guide_full_route must contain 65 waypoints')
    if len(routes[COFFEE_ROUTE]) != 19:
        raise ValueError('coffee_delivery_route must contain 19 waypoints')

    guide_labels = [item['label'] for item in routes[GUIDE_ROUTE]]
    label_colors = {}
    for index, unit in enumerate(task_document.get('task_units') or []):
        start = guide_labels.index(str(unit['start_waypoint']))
        end = guide_labels.index(str(unit['end_waypoint']))
        for label in guide_labels[start:end + 1]:
            label_colors[label] = TASK_COLORS[index % len(TASK_COLORS)]
    return routes, label_colors


def build_waypoint_codes(routes):
    """Give every configured point a short stable operator-facing code."""
    codes = {}
    for route_name, prefix in ((GUIDE_ROUTE, 'G'), (COFFEE_ROUTE, 'C')):
        for index, point in enumerate(routes[route_name], start=1):
            codes[(route_name, index - 1)] = f'{prefix}{index:02d}'
            codes[(route_name, point['label'])] = f'{prefix}{index:02d}'
    return codes


def progress_text(robot_id, state, target, reached, total, codes):
    """Build the compact status shown beside the current Gazebo target."""
    title = ROBOT_TITLES[robot_id]
    if target:
        route_name = ROBOT_ROUTES[robot_id]
        code = codes.get((route_name, target), '--')
        index = min(max(1, int(reached) + 1), max(1, int(total)))
        return f'{title} {index}/{int(total)}  {code}  {target}'
    if state == 'COMPLETED':
        return f'{title} COMPLETED  {int(total)}/{int(total)}'
    if state == 'CANCELLED':
        return f'{title} CANCELLED'
    if state == 'PAUSED':
        return f'{title} PAUSED  {int(reached)}/{int(total)}'
    return f'{title} WAITING'


def gazebo_progress_code(robot_id, state, target, reached, total, codes):
    """Build the short code rendered by Gazebo's line-marker backend."""
    route_name = ROBOT_ROUTES[robot_id]
    if target:
        code = codes.get((route_name, target), '--')
        index = min(max(1, int(reached) + 1), max(1, int(total)))
    elif state == 'COMPLETED':
        code = codes[(route_name, len(
            [key for key in codes if key[0] == route_name
             and isinstance(key[1], int)]) - 1)]
        index = int(total)
    else:
        code = codes[(route_name, 0)]
        index = int(reached)
    return f'{code} {index}/{int(total)}'


STROKE_SEGMENTS = {
    'a': ((0.0, 1.0), (1.0, 1.0)),
    'b': ((1.0, 1.0), (1.0, 0.5)),
    'c': ((1.0, 0.5), (1.0, 0.0)),
    'd': ((1.0, 0.0), (0.0, 0.0)),
    'e': ((0.0, 0.0), (0.0, 0.5)),
    'f': ((0.0, 0.5), (0.0, 1.0)),
    'g': ((0.0, 0.5), (1.0, 0.5)),
    '/': ((0.0, 0.0), (1.0, 1.0)),
}
STROKE_GLYPHS = {
    '0': 'abcdef', '1': 'bc', '2': 'abdeg', '3': 'abcdg',
    '4': 'bcfg', '5': 'acdfg', '6': 'acdefg', '7': 'abc',
    '8': 'abcdefg', '9': 'abcdfg', 'G': 'acdefg', 'C': 'adef',
    '-': 'g', '/': '/', ' ': '',
}


def build_gazebo_progress_marker(marker_id, point, text, color):
    """Build a floor-level vector label supported by Gazebo Ogre2."""
    marker = GzMarker()
    marker.action = GzMarker.ADD_MODIFY
    marker.ns = 'showroom_route_progress'
    marker.id = int(marker_id)
    marker.type = GzMarker.LINE_LIST
    marker.layer = 20
    marker.visibility = GzMarker.GUI
    marker.pose.position.x = float(point['x'])
    marker.pose.position.y = float(point['y']) - 0.12
    marker.pose.position.z = 1.42
    marker.pose.orientation.w = 1.0
    # Marker scale transforms all line coordinates; keep it at one so the
    # operator code remains readable from the default showroom camera.
    marker.scale.x = marker.scale.y = marker.scale.z = 1.0
    glyph_width = 0.22
    glyph_height = 0.38
    advance = 0.29
    content = str(text)
    origin_x = -(max(0, len(content) - 1) * advance + glyph_width) / 2.0
    for character_index, character in enumerate(content):
        for segment_name in STROKE_GLYPHS.get(character, ''):
            start, end = STROKE_SEGMENTS[segment_name]
            for x_value, y_value in (start, end):
                output = marker.point.add()
                output.x = (
                    origin_x + character_index * advance
                    + x_value * glyph_width)
                output.y = 0.0
                output.z = y_value * glyph_height
    marker.material.lighting = False
    for output in (marker.material.ambient, marker.material.diffuse):
        output.r, output.g, output.b = map(float, color[:3])
        output.a = 1.0
    return marker


def sub(parent, tag, text=None, **attributes):
    """Append one XML element."""
    element = ET.SubElement(parent, tag, attributes)
    if text is not None:
        element.text = str(text)
    return element


def sdf_material(parent, color, emissive_scale=0.18):
    """Add a bright route material to a Gazebo visual."""
    rgba = ' '.join(f'{value:.3f}' for value in color)
    emissive = ' '.join(
        f'{min(1.0, value * emissive_scale):.3f}'
        for value in color[:3]) + f' {color[3]:.3f}'
    material = sub(parent, 'material')
    sub(material, 'ambient', rgba)
    sub(material, 'diffuse', rgba)
    sub(material, 'emissive', emissive)


def add_box_visual(link, name, x, y, length, yaw, color):
    """Add one non-colliding route segment."""
    visual = sub(link, 'visual', name=name)
    sub(visual, 'pose', f'{x:.3f} {y:.3f} 0.018 0 0 {yaw:.6f}')
    geometry = sub(visual, 'geometry')
    box = sub(geometry, 'box')
    sub(box, 'size', f'{length:.3f} 0.055 0.025')
    sdf_material(visual, color)
    sub(visual, 'cast_shadows', 'false')


def add_point_visual(link, name, point, color, radius):
    """Add one non-colliding waypoint disc."""
    visual = sub(link, 'visual', name=name)
    sub(visual, 'pose', f'{point["x"]:.3f} {point["y"]:.3f} 0.045 0 0 0')
    geometry = sub(visual, 'geometry')
    cylinder = sub(geometry, 'cylinder')
    sub(cylinder, 'radius', f'{radius:.3f}')
    sub(cylinder, 'length', '0.070')
    sdf_material(visual, color, emissive_scale=0.30)
    sub(visual, 'cast_shadows', 'false')


def build_gazebo_route_sdf(routes, label_colors):
    """Build a static collision-free model containing both route networks."""
    sdf = ET.Element('sdf', {'version': '1.10'})
    model = sub(sdf, 'model', name='showroom_route_markers')
    sub(model, 'static', 'true')
    link = sub(model, 'link', name='routes')
    for route_name, waypoints in routes.items():
        prefix = 'guide' if route_name == GUIDE_ROUTE else 'coffee'
        default_color = ROUTE_COLORS[route_name]
        for index, (start, goal) in enumerate(
                zip(waypoints, waypoints[1:])):
            dx = goal['x'] - start['x']
            dy = goal['y'] - start['y']
            add_box_visual(
                link, f'{prefix}_segment_{index:02d}',
                (start['x'] + goal['x']) / 2.0,
                (start['y'] + goal['y']) / 2.0,
                math.hypot(dx, dy), math.atan2(dy, dx),
                label_colors.get(goal['label'], default_color),
            )
        for index, point in enumerate(waypoints):
            add_point_visual(
                link, f'{prefix}_waypoint_{index:02d}', point,
                label_colors.get(point['label'], default_color),
                0.14 if route_name == GUIDE_ROUTE else 0.11,
            )
    ET.indent(sdf, space='  ')
    return ET.tostring(sdf, encoding='unicode')


def build_beacon_sdf(name, color):
    """Build a tall target beacon that can be moved with SetEntityPose."""
    sdf = ET.Element('sdf', {'version': '1.10'})
    model = sub(sdf, 'model', name=name)
    sub(model, 'static', 'true')
    link = sub(model, 'link', name='beacon')
    # The guide robot's 2D lidar scans at z=0.50. Gazebo renders visual
    # geometry into sensors, so a solid pole standing on the target waypoint
    # would be reported as an obstacle there and trip the collision monitor
    # before the robot can reach the goal. Split the pole around that height so
    # the beacon stays tall and visible while leaving the scan plane clear.
    for visual_name, radius, length, z in (
            ('target_disc', 0.30, 0.055, 0.035),
            ('target_pole_lower', 0.035, 0.40, 0.20),
            ('target_pole_upper', 0.035, 0.62, 0.89)):
        visual = sub(link, 'visual', name=visual_name)
        sub(visual, 'pose', f'0 0 {z:.3f} 0 0 0')
        geometry = sub(visual, 'geometry')
        cylinder = sub(geometry, 'cylinder')
        sub(cylinder, 'radius', f'{radius:.3f}')
        sub(cylinder, 'length', f'{length:.3f}')
        sdf_material(visual, color, emissive_scale=0.55)
        sub(visual, 'cast_shadows', 'false')
    top = sub(link, 'visual', name='target_light')
    sub(top, 'pose', '0 0 1.24 0 0 0')
    geometry = sub(top, 'geometry')
    sphere = sub(geometry, 'sphere')
    sub(sphere, 'radius', '0.105')
    sdf_material(top, color, emissive_scale=0.70)
    sub(top, 'cast_shadows', 'false')
    ET.indent(sdf, space='  ')
    return ET.tostring(sdf, encoding='unicode')


def ros_color(values):
    """Convert a tuple into a ROS color."""
    return ColorRGBA(
        r=float(values[0]), g=float(values[1]),
        b=float(values[2]), a=float(values[3]))


class ShowroomRouteVisualizer(Node):
    """Publish RViz markers and create matching Gazebo route visuals."""

    def __init__(self):
        super().__init__('showroom_route_visualizer')
        share = Path(get_package_share_directory('showroom_navigation'))
        self.declare_parameter(
            'routes_file', str(share / 'config' / 'routes.yaml'))
        self.declare_parameter(
            'task_units_file', str(share / 'config' / 'task_units.yaml'))
        self.declare_parameter('world_name', 'showroom')
        self.declare_parameter('gazebo_visuals', True)
        self.declare_parameter('gazebo_progress_labels', True)
        self.declare_parameter('marker_topic', '/showroom/route_markers')
        self.routes, self.label_colors = load_route_catalog(
            self.get_parameter('routes_file').value,
            self.get_parameter('task_units_file').value,
        )
        self.points = {
            point['label']: point
            for waypoints in self.routes.values() for point in waypoints
        }
        self.waypoint_codes = build_waypoint_codes(self.routes)
        self.current_targets = {'robot_0': None, 'robot_1': None}
        self.completed = {'robot_0': set(), 'robot_1': set()}
        self.progress = {
            robot_id: {
                'state': 'WAITING', 'reached': 0,
                'total': len(self.routes[route_name]),
            }
            for robot_id, route_name in ROBOT_ROUTES.items()
        }
        self.beacon_dirty = set()
        self.gazebo_label_dirty = set(ROBOT_ROUTES)
        self.gazebo_label_attempts = {robot_id: 0 for robot_id in ROBOT_ROUTES}
        self.gazebo_label_errors = {robot_id: '' for robot_id in ROBOT_ROUTES}
        self.gazebo_labels_available = False
        self.gz_node = GzNode()
        self.spawned = set()
        self.spawn_attempts = 0

        transient = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.marker_publisher = self.create_publisher(
            MarkerArray, self.get_parameter('marker_topic').value, transient)
        self.create_subscription(
            String, '/showroom/navigation_status',
            self.navigation_status_callback, transient)
        self.create_subscription(
            String, '/showroom/robot_events',
            self.navigation_event_callback, transient)
        self.pose_client = self.create_client(
            SetEntityPose, '/world/showroom/set_pose')
        self.create_timer(1.0, self.publish_markers)
        self.spawn_timer = self.create_timer(1.0, self.spawn_gazebo_visuals)
        self.create_timer(0.5, self.update_beacons)
        self.create_timer(0.5, self.update_gazebo_progress_labels)
        self.publish_markers()
        self.get_logger().info(
            'Route visualizer ready: 65 guide and 19 coffee waypoints')

    def spawn_entity(self, name, sdf, point):
        """Create one visual-only Gazebo model."""
        executable = os.path.join(
            get_package_prefix('ros_gz_sim'), 'lib', 'ros_gz_sim', 'create')
        command = [
            executable,
            '-world', str(self.get_parameter('world_name').value),
            '-name', name,
            '-allow_renaming', 'false',
            '-string', sdf,
            '-x', str(point['x']), '-y', str(point['y']), '-z', '0.0',
        ]
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=12.0,
            check=False)
        if result.returncode == 0:
            self.spawned.add(name)
            return True
        detail = (result.stderr or result.stdout).strip().splitlines()
        if detail:
            self.get_logger().warning(
                f'Could not create {name}: {detail[-1]}')
        return False

    def spawn_gazebo_visuals(self):
        """Spawn route and target models once the Gazebo world is ready."""
        if not self.get_parameter('gazebo_visuals').value:
            self.spawn_timer.cancel()
            return
        required = {'showroom_route_markers', *BEACON_NAMES.values()}
        if required <= self.spawned:
            self.spawn_timer.cancel()
            self.beacon_dirty.update(BEACON_NAMES)
            self.get_logger().info('Gazebo route and target visuals created')
            return
        self.spawn_attempts += 1
        try:
            if 'showroom_route_markers' not in self.spawned:
                self.spawn_entity(
                    'showroom_route_markers',
                    build_gazebo_route_sdf(self.routes, self.label_colors),
                    {'x': 0.0, 'y': 0.0},
                )
            beacon_colors = {
                'robot_0': (1.0, 0.92, 0.05, 1.0),
                'robot_1': (1.0, 0.25, 0.75, 1.0),
            }
            starts = {
                'robot_0': self.routes[GUIDE_ROUTE][0],
                'robot_1': self.routes[COFFEE_ROUTE][0],
            }
            for robot_id, name in BEACON_NAMES.items():
                if name not in self.spawned:
                    self.spawn_entity(
                        name, build_beacon_sdf(name, beacon_colors[robot_id]),
                        starts[robot_id])
        except (OSError, subprocess.SubprocessError) as exception:
            self.get_logger().warning(
                f'Gazebo route visual creation failed: {exception}')
        if self.spawn_attempts >= 10 and not required <= self.spawned:
            self.spawn_timer.cancel()
            self.get_logger().error('Gazebo route visuals could not be created')

    def navigation_status_callback(self, message):
        """Track the current semantic target for each robot."""
        try:
            document = json.loads(message.data)
        except json.JSONDecodeError:
            return
        robot_id = document.get('robot_id')
        target = document.get('target_waypoint')
        if robot_id not in ROBOT_ROUTES or target not in self.points:
            return
        if self.current_targets[robot_id] != target:
            self.current_targets[robot_id] = target
            self.beacon_dirty.add(robot_id)
            self.gazebo_label_dirty.add(robot_id)
            self.publish_markers()

    def navigation_event_callback(self, message):
        """Color completed route points from durable navigation events."""
        try:
            document = json.loads(message.data)
        except json.JSONDecodeError:
            return
        robot_id = document.get('robot_id')
        if robot_id not in ROBOT_ROUTES:
            return
        event_type = document.get('type')
        if event_type == 'route_started':
            self.completed[robot_id].clear()
            self.progress[robot_id].update({
                'state': 'NAVIGATING',
                'reached': 0,
                'total': int(document.get('total', 0)),
            })
        elif event_type == 'waypoint_reached':
            label = document.get('label')
            if label in self.points:
                self.completed[robot_id].add(label)
            self.progress[robot_id].update({
                'state': 'NAVIGATING',
                'reached': int(document.get(
                    'index', self.progress[robot_id]['reached'])),
                'total': int(document.get(
                    'total', self.progress[robot_id]['total'])),
            })
        elif event_type == 'route_paused':
            self.progress[robot_id]['state'] = 'PAUSED'
        elif event_type == 'route_resumed':
            self.progress[robot_id]['state'] = 'NAVIGATING'
        elif event_type in ('route_completed', 'route_cancelled'):
            self.progress[robot_id]['state'] = (
                'COMPLETED' if event_type == 'route_completed'
                else 'CANCELLED')
            if event_type == 'route_completed':
                self.progress[robot_id]['reached'] = self.progress[
                    robot_id]['total']
            self.current_targets[robot_id] = None
            self.beacon_dirty.add(robot_id)
        else:
            return
        self.gazebo_label_attempts[robot_id] = 0
        self.gazebo_label_dirty.add(robot_id)
        self.publish_markers()

    def update_beacons(self):
        """Move Gazebo target beacons when active semantic targets change."""
        if not self.pose_client.service_is_ready():
            return
        for robot_id in tuple(self.beacon_dirty):
            if BEACON_NAMES[robot_id] not in self.spawned:
                continue
            target = self.current_targets[robot_id]
            request = SetEntityPose.Request()
            request.entity.name = BEACON_NAMES[robot_id]
            request.entity.type = Entity.MODEL
            request.pose.orientation.w = 1.0
            if target in self.points:
                request.pose.position.x = self.points[target]['x']
                request.pose.position.y = self.points[target]['y']
                request.pose.position.z = 0.0
            else:
                request.pose.position.z = -2.0
            self.pose_client.call_async(request)
            self.beacon_dirty.discard(robot_id)

    def update_gazebo_progress_labels(self):
        """Show the current semantic label and progress in the Gazebo GUI."""
        if (not self.get_parameter('gazebo_visuals').value
                or not self.get_parameter('gazebo_progress_labels').value):
            self.gazebo_label_dirty.clear()
            return
        colors = {
            'robot_0': (1.0, 0.92, 0.05),
            'robot_1': (1.0, 0.25, 0.75),
        }
        starts = {
            robot_id: self.routes[route_name][0]
            for robot_id, route_name in ROBOT_ROUTES.items()
        }
        for robot_id in tuple(self.gazebo_label_dirty):
            if self.gazebo_label_attempts[robot_id] >= 12:
                self.gazebo_label_dirty.discard(robot_id)
                detail = self.gazebo_label_errors[robot_id]
                if detail:
                    self.get_logger().warning(
                        'Gazebo waypoint label service unavailable: '
                        f'{detail}')
                continue
            target = self.current_targets[robot_id]
            point = self.points.get(target, starts[robot_id])
            status = self.progress[robot_id]
            label = gazebo_progress_code(
                robot_id, status['state'], target,
                status['reached'], status['total'], self.waypoint_codes)
            marker = build_gazebo_progress_marker(
                1 if robot_id == 'robot_0' else 2,
                point, label, colors[robot_id])
            self.gazebo_label_attempts[robot_id] += 1
            try:
                if '/marker' not in self.gz_node.service_list():
                    self.gazebo_label_errors[robot_id] = (
                        '/marker is not advertised (headless runs omit it)')
                    continue
                self.gz_node.request(
                    '/marker', marker, GzMarker, GzEmpty, 250)
            except RuntimeError as exception:
                self.gazebo_label_errors[robot_id] = str(exception)
                continue
            self.gazebo_label_dirty.discard(robot_id)
            if not self.gazebo_labels_available:
                self.gazebo_labels_available = True
                self.get_logger().info(
                    'Gazebo live waypoint progress labels active')

    def base_marker(self, marker_id, marker_type, namespace):
        """Create one persistent map-frame RViz marker."""
        marker = Marker()
        marker.header.frame_id = 'map'
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = namespace
        marker.id = marker_id
        marker.type = marker_type
        marker.action = Marker.ADD
        marker.pose.orientation.w = 1.0
        return marker

    def route_markers(self, route_name, marker_id):
        """Build line and state-colored point markers for one route."""
        robot_id = (
            'robot_0' if route_name == GUIDE_ROUTE else 'robot_1')
        waypoints = self.routes[route_name]
        line = self.base_marker(marker_id, Marker.LINE_STRIP, route_name)
        line.scale.x = 0.055
        line.color = ros_color(ROUTE_COLORS[route_name])
        line.points = [
            Point(x=point['x'], y=point['y'], z=0.04)
            for point in waypoints
        ]
        points = self.base_marker(
            marker_id + 1, Marker.SPHERE_LIST, route_name)
        diameter = 0.28 if route_name == GUIDE_ROUTE else 0.22
        points.scale.x = diameter
        points.scale.y = diameter
        points.scale.z = 0.10
        points.points = [
            Point(x=point['x'], y=point['y'], z=0.09)
            for point in waypoints
        ]
        for point in waypoints:
            label = point['label']
            if label == self.current_targets[robot_id]:
                color = (1.0, 0.92, 0.05, 1.0)
            elif label in self.completed[robot_id]:
                color = (0.15, 1.0, 0.30, 1.0)
            else:
                color = self.label_colors.get(
                    label, ROUTE_COLORS[route_name])
            points.colors.append(ros_color(color))
        return [line, points]

    def waypoint_label_markers(self, route_name, marker_id):
        """Build short waypoint-number labels for RViz route inspection."""
        markers = []
        for offset, point in enumerate(self.routes[route_name]):
            marker = self.base_marker(
                marker_id + offset, Marker.TEXT_VIEW_FACING,
                f'{route_name}_labels')
            marker.pose.position.x = point['x']
            marker.pose.position.y = point['y']
            marker.pose.position.z = 0.34
            marker.scale.z = 0.22 if route_name == GUIDE_ROUTE else 0.18
            marker.color = ros_color((1.0, 1.0, 1.0, 0.95))
            marker.text = self.waypoint_codes[(route_name, offset)]
            markers.append(marker)
        return markers

    def current_target_markers(self):
        """Build labeled RViz beacons for the active targets."""
        markers = []
        for index, robot_id in enumerate(('robot_0', 'robot_1')):
            label = self.current_targets[robot_id]
            if label not in self.points:
                for marker_id in (100 + index * 2, 101 + index * 2):
                    marker = self.base_marker(
                        marker_id, Marker.SPHERE, 'current_targets')
                    marker.action = Marker.DELETE
                    markers.append(marker)
                continue
            point = self.points[label]
            sphere = self.base_marker(
                100 + index * 2, Marker.SPHERE, 'current_targets')
            sphere.pose.position.x = point['x']
            sphere.pose.position.y = point['y']
            sphere.pose.position.z = 0.32
            sphere.scale.x = sphere.scale.y = sphere.scale.z = 0.42
            sphere.color = ros_color(
                (1.0, 0.92, 0.05, 1.0) if robot_id == 'robot_0'
                else (1.0, 0.25, 0.75, 1.0))
            text = self.base_marker(
                101 + index * 2, Marker.TEXT_VIEW_FACING,
                'current_targets')
            text.pose.position.x = point['x']
            text.pose.position.y = point['y']
            text.pose.position.z = 0.85
            text.scale.z = 0.32
            text.color = ros_color((1.0, 1.0, 1.0, 1.0))
            status = self.progress[robot_id]
            text.text = progress_text(
                robot_id, status['state'], label,
                status['reached'], status['total'], self.waypoint_codes)
            markers.extend((sphere, text))
        return markers

    def publish_markers(self):
        """Publish the complete route state for RViz consumers."""
        markers = []
        markers.extend(self.route_markers(GUIDE_ROUTE, 0))
        markers.extend(self.route_markers(COFFEE_ROUTE, 10))
        markers.extend(self.waypoint_label_markers(GUIDE_ROUTE, 1000))
        markers.extend(self.waypoint_label_markers(COFFEE_ROUTE, 2000))
        markers.extend(self.current_target_markers())
        self.marker_publisher.publish(MarkerArray(markers=markers))


def main(args=None):
    """Run the route visualizer node."""
    rclpy.init(args=args)
    node = ShowroomRouteVisualizer()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
