#!/usr/bin/env python3
"""Render the current Gazebo showroom world and semantic routes in 3D."""

from pathlib import Path
import math
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
from mpl_toolkits.mplot3d import proj3d
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import yaml


ROOT = Path(__file__).resolve().parents[1]
FONT = font_manager.FontProperties(
    fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc')


def numbers(text, default):
    """Parse a space-separated SDF vector."""
    return [float(value) for value in (text or default).split()]


def box_faces(pose, size):
    """Return the six rotated faces of an SDF box."""
    x, y, z, _, _, yaw = pose
    sx, sy, sz = size
    vertices = []
    for dx, dy, dz in (
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)):
        local_x = dx * sx / 2
        local_y = dy * sy / 2
        vertices.append((
            x + local_x * math.cos(yaw) - local_y * math.sin(yaw),
            y + local_x * math.sin(yaw) + local_y * math.cos(yaw),
            z + dz * sz / 2))
    return [[vertices[index] for index in face] for face in (
        (0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
        (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))]


def cylinder_faces(pose, size, sides=32):
    """Return polygon faces for a vertical cylinder."""
    x, y, z, _, _, _ = pose
    radius, length = size
    bottom_z = z - length / 2
    top_z = z + length / 2
    ring = [2 * math.pi * index / sides for index in range(sides)]
    bottom = [(x + radius * math.cos(angle),
               y + radius * math.sin(angle), bottom_z) for angle in ring]
    top = [(x + radius * math.cos(angle),
            y + radius * math.sin(angle), top_z) for angle in ring]
    faces = [bottom, top]
    for index in range(sides):
        following = (index + 1) % sides
        faces.append([
            bottom[index], bottom[following], top[following], top[index]])
    return faces


def draw_box(axis, pose, size, color):
    """Draw a shaded box."""
    collection = Poly3DCollection(
        box_faces(pose, size), facecolors=[color], edgecolors='#273444',
        linewidths=0.25, zsort='average')
    axis.add_collection3d(collection)


def draw_zone(axis, pose, size, color):
    """Draw only the top face of a functional zone."""
    top = box_faces(
        [pose[0], pose[1], 0.025, 0, 0, pose[5]],
        [size[0], size[1], 0.01])[1]
    axis.add_collection3d(Poly3DCollection(
        [top], facecolors=[color], edgecolors=color[:3], linewidths=0.6,
        zsort='min'))


def draw_cylinder(axis, pose, size, color):
    """Draw a vertical cylinder."""
    x, y, z, _, _, _ = pose
    radius, length = size
    theta = np.linspace(0, 2 * np.pi, 48)
    theta_grid, z_grid = np.meshgrid(
        theta, np.array([z - length / 2, z + length / 2]))
    axis.plot_surface(
        x + radius * np.cos(theta_grid),
        y + radius * np.sin(theta_grid), z_grid,
        color=color[:3], alpha=color[3], shade=True, linewidth=0)
    for cap_z in (z - length / 2, z + length / 2):
        face = [(x, y, cap_z)] + [
            (x + radius * math.cos(angle),
             y + radius * math.sin(angle), cap_z)
            for angle in theta]
        axis.add_collection3d(Poly3DCollection(
            [face], facecolors=[color], edgecolors='none'))


def visual_data(visual):
    """Extract supported geometry and material from one SDF visual."""
    pose = numbers(visual.findtext('pose'), '0 0 0 0 0 0')
    diffuse = (
        visual.findtext('material/diffuse') or
        visual.findtext('material/ambient') or '0.55 0.58 0.62 1')
    color = numbers(diffuse, '0.55 0.58 0.62 1')
    color[3] = max(0.38, min(1.0, color[3]))
    box = visual.find('geometry/box/size')
    cylinder = visual.find('geometry/cylinder')
    if box is not None:
        return pose, color, 'box', numbers(box.text, '1 1 1')
    if cylinder is not None:
        return pose, color, 'cylinder', [
            float(cylinder.findtext('radius')),
            float(cylinder.findtext('length'))]
    return None


def draw_robot(axis, x, y, color):
    """Draw a simple robot at an initial position."""
    draw_cylinder(axis, [x, y, 0.35, 0, 0, 0], [0.32, 0.70], color)
    draw_cylinder(axis, [x + 0.13, y, 0.78, 0, 0, 0],
                  [0.18, 0.28], color)


def add_overlay_label(axis, xyz, text, color):
    """Place a readable two-dimensional label at a projected 3D point."""
    projected_x, projected_y, _ = proj3d.proj_transform(
        *xyz, axis.get_proj())
    axis.annotate(
        text, xy=(projected_x, projected_y), xytext=(0, 8),
        textcoords='offset points', ha='center', va='bottom',
        color='white', fontproperties=FONT, fontsize=8.5,
        bbox={
            'boxstyle': 'round,pad=.32', 'fc': '#111b28',
            'ec': color, 'lw': 1.15, 'alpha': .96},
        arrowprops={'arrowstyle': '-', 'color': color, 'lw': .75})


def main():
    """Render the world, routes, robots, and exact semantic area names."""
    world = ET.parse(
        ROOT / 'showroom_gz_sim/worlds/showroom.sdf').getroot()
    link = world.find(
        ".//model[@name='showroom_structure']/link[@name='structure']")

    figure = plt.figure(figsize=(18, 12), dpi=170, facecolor='#0b1119')
    axis = figure.add_subplot(111, projection='3d', facecolor='#0b1119')
    scene_faces = [[
        (-25, -17.5, -0.12), (25, -17.5, -0.12),
        (25, 17.5, -0.12), (-25, 17.5, -0.12)]]
    scene_colors = [(0.18, 0.21, 0.25, 1)]

    for visual in link.findall('visual'):
        name = visual.attrib.get('name', '')
        if name == 'floor_visual':
            continue
        data = visual_data(visual)
        if not data:
            continue
        pose, color, shape, size = data
        if name.startswith('zone_'):
            color[3] = 0.88
            scene_faces.append(box_faces(
                [pose[0], pose[1], 0.025, 0, 0, pose[5]],
                [size[0], size[1], 0.01])[1])
            scene_colors.append(color)
        elif shape == 'box':
            faces = box_faces(pose, size)
            scene_faces.extend(faces)
            scene_colors.extend([color] * len(faces))
        else:
            faces = cylinder_faces(pose, size)
            scene_faces.extend(faces)
            scene_colors.extend([color] * len(faces))

    routes = yaml.safe_load((
        ROOT / 'showroom_navigation/config/routes.yaml').read_text())['routes']
    for x, y, color in (
            (0, -14.5, (0.12, 0.55, 0.98, 1)),
            (2.3, -14.5, (0.15, 0.82, 0.42, 1))):
        for pose, size in (
                ([x, y, .35, 0, 0, 0], [.32, .70]),
                ([x + .13, y, .78, 0, 0, 0], [.18, .28])):
            faces = cylinder_faces(pose, size)
            scene_faces.extend(faces)
            scene_colors.extend([color] * len(faces))

    axis.add_collection3d(Poly3DCollection(
        scene_faces, facecolors=scene_colors, edgecolors='#273444',
        linewidths=.22, zsort='average'))

    axis.set_xlim(-27, 27)
    axis.set_ylim(-19, 19)
    axis.set_zlim(0, 7)
    axis.set_box_aspect((54, 38, 10))
    axis.view_init(elev=53, azim=-58)
    axis.grid(False)
    axis.set_axis_off()
    axis.set_title(
        'ROS 2 GAZEBO 智慧展厅 · 当前地图 3D 总览',
        fontproperties=FONT, fontsize=23, color='white', pad=20)
    figure.canvas.draw()

    # Routes are projected to a top overlay so the floor cannot obscure them.
    for key, color, height, width in (
            ('guide_full_route', '#4fe4ff', 0.36, 2.5),
            ('coffee_delivery_route', '#ff5ad6', 0.42, 2.3)):
        points = routes[key]['waypoints']
        projected = [proj3d.proj_transform(
            float(point['x']), float(point['y']), height,
            axis.get_proj()) for point in points]
        xs = [point[0] for point in projected]
        ys = [point[1] for point in projected]
        axis.add_artist(Line2D(
            xs, ys, transform=axis.transData, color=color, lw=width,
            marker='o', markersize=2.2, zorder=500))

    labels = (
        ((0, -15.3, 1.2), '入口 / Entrance', '#77b8ff'),
        ((-16.4, -8.5, 2.8), '视觉展厅 / Vision Hall', '#55c8ff'),
        ((-16.4, 10.1, 2.8), '机器人展厅 / Robotics Hall', '#d4d8de'),
        ((4.8, 3.0, 2.8), '科技历史展区 / Technology History', '#ffc35c'),
        ((0, 13.0, 3.0), '时光隧道 / Time Tunnel', '#7c94ff'),
        ((16.4, 10.1, 2.8), '舞蹈展厅 / Dance Hall', '#ef84ff'),
        ((17.2, -5.5, 2.8), '休息区 / Lounge', '#68e7ad'),
        ((0, 0, 1.6), '咖啡吧 / Coffee Bar', '#ff9a5a'))
    for xyz, text, color in labels:
        add_overlay_label(axis, xyz, text, color)

    figure.text(
        .5, .925,
        '50 m × 35 m  |  世界模型：showroom.sdf  |  航线：routes.yaml',
        ha='center', color='#a9b8c9', fontsize=10, fontproperties=FONT)
    legend = (
        Line2D([0], [0], color='#4fe4ff', lw=3,
               label='导览机器人完整路线 / Guide Route'),
        Line2D([0], [0], color='#ff5ad6', lw=3,
               label='咖啡配送路线 / Coffee Route'),
        Patch(facecolor='#2877ad', edgecolor='#55c8ff',
              label='功能区地面 / Zone'),
        Patch(facecolor='#87919e', edgecolor='#28323d',
              label='墙体与展项 / Structure'))
    rendered_legend = axis.legend(
        handles=legend, loc='lower left', bbox_to_anchor=(.04, .035),
        frameon=True, facecolor='#111b28', edgecolor='#33475c',
        labelcolor='white', prop=FONT, fontsize=9)
    rendered_legend.get_frame().set_alpha(.95)
    figure.text(
        .955, .045, '坐标与名称均来自当前项目配置', ha='right',
        color='#7f91a5', fontsize=9, fontproperties=FONT)
    plt.subplots_adjust(left=.015, right=.985, bottom=.015, top=.92)
    figure.savefig(
        ROOT / 'docs/showroom_3d_overview.png', facecolor='#0b1119',
        bbox_inches='tight', pad_inches=.12)


if __name__ == '__main__':
    main()
