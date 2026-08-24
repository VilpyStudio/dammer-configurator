import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

OUT_DIR = Path("/Users/basdewildt/Documents/New project/boat3-configurator/images/360-hull")
WIDTH = 1280
HEIGHT = 900
FRAMES = 8
BASE_COLLECTIONS = {"main boat", "seats", "wood", "streaing", "Collection 4", "Collection 8"}
BODY_MATERIAL = "Body"

HULL_COLORS = {
    "ral9010": ("RAL 9010", (0.94, 0.91, 0.84, 1.0)),
    "ral1013": ("RAL 1013", (0.82, 0.76, 0.64, 1.0)),
    "ral6034": ("RAL 6034", (0.54, 0.75, 0.74, 1.0)),
    "ral7033": ("RAL 7033", (0.43, 0.47, 0.39, 1.0)),
    "ral7034": ("RAL 7034", (0.51, 0.48, 0.41, 1.0)),
    "ral7038": ("RAL 7038", (0.68, 0.69, 0.65, 1.0)),
    "ral7039": ("RAL 7039", (0.35, 0.34, 0.30, 1.0)),
}


def requested_values(argument, all_values):
    if not argument:
        return list(all_values)
    wanted = {item.strip().lower() for item in argument.split(",") if item.strip()}
    return [item for item in all_values if item.lower() in wanted]


def parse_cli():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    options = {"colors": "", "frames": ""}
    index = 0
    while index < len(args):
        key = args[index]
        if key in {"--colors", "--frames"} and index + 1 < len(args):
            options[key[2:]] = args[index + 1]
            index += 2
        else:
            index += 1

    env_colors = os.environ.get("DAMMER_RENDER_COLORS", "")
    env_frames = os.environ.get("DAMMER_RENDER_FRAMES", "")
    colors = requested_values(options["colors"] or env_colors, HULL_COLORS.keys())
    frames = requested_values(options["frames"] or env_frames, [str(frame) for frame in range(FRAMES)])
    return colors, [int(frame) for frame in frames]


def visible_mesh_like_objects():
    return [
        obj for obj in bpy.context.scene.objects
        if obj.type in {"MESH", "CURVE"} and obj.visible_get()
    ]


def object_collection_names(obj):
    return {collection.name for collection in obj.users_collection}


def set_visibility(collection_names):
    for obj in bpy.context.scene.objects:
        if obj.type not in {"MESH", "CURVE"}:
            obj.hide_render = True
            continue
        obj.hide_render = object_collection_names(obj).isdisjoint(collection_names)


def bounds_for(objects):
    points = []
    for obj in objects:
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    minimum = Vector((
        min(point.x for point in points),
        min(point.y for point in points),
        min(point.z for point in points),
    ))
    maximum = Vector((
        max(point.x for point in points),
        max(point.y for point in points),
        max(point.z for point in points),
    ))
    return minimum, maximum


def look_at(obj, target):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_scene():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = WIDTH
    scene.render.resolution_y = HEIGHT
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1

    for obj in list(scene.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)

    all_objects = visible_mesh_like_objects()
    minimum, maximum = bounds_for(all_objects)
    center = (minimum + maximum) / 2
    span = maximum - minimum
    radius = max(span.x, span.y, span.z)

    camera_data = bpy.data.cameras.new("Configurator 360 Camera")
    camera = bpy.data.objects.new("Configurator 360 Camera", camera_data)
    scene.collection.objects.link(camera)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(span.x, span.y) * 1.16
    scene.camera = camera

    key_data = bpy.data.lights.new("Configurator Key", "AREA")
    key = bpy.data.objects.new("Configurator Key", key_data)
    scene.collection.objects.link(key)
    key_data.energy = 850
    key_data.size = radius * 0.75

    fill_data = bpy.data.lights.new("Configurator Fill", "AREA")
    fill = bpy.data.objects.new("Configurator Fill", fill_data)
    scene.collection.objects.link(fill)
    fill_data.energy = 180
    fill_data.size = radius

    return {
        "center": center,
        "radius": radius,
        "camera": camera,
        "key": key,
        "fill": fill,
    }


def set_orbit(context, frame):
    center = context["center"]
    radius = context["radius"]
    angle = math.radians(-128 + frame * (360 / FRAMES))
    base_distance = radius * 1.10
    camera = context["camera"]
    camera.location = center + Vector((
        math.cos(angle) * base_distance,
        math.sin(angle) * base_distance,
        0.58 * radius,
    ))
    look_at(camera, center + Vector((0, 0, 0.05 * radius)))

    key = context["key"]
    key.location = center + Vector((math.cos(angle - 0.55) * radius, math.sin(angle - 0.55) * radius, 1.35 * radius))
    look_at(key, center)

    fill = context["fill"]
    fill.location = center + Vector((math.cos(angle + 1.8) * radius, math.sin(angle + 1.8) * radius, 0.9 * radius))
    look_at(fill, center)


def set_body_color(color):
    material = bpy.data.materials.get(BODY_MATERIAL)
    if not material:
        raise RuntimeError(f"Missing material: {BODY_MATERIAL}")

    material.diffuse_color = color
    material.use_nodes = True
    nodes = material.node_tree.nodes
    principled = next((node for node in nodes if node.type == "BSDF_PRINCIPLED"), None)
    if not principled:
        raise RuntimeError(f"Missing Principled BSDF in material: {BODY_MATERIAL}")

    base_color = principled.inputs.get("Base Color")
    if base_color:
        for link in list(base_color.links):
            material.node_tree.links.remove(link)
        base_color.default_value = color

    paint_inputs = {
        "Metallic": 0.0,
        "Roughness": 0.34,
        "Alpha": 1.0,
        "Coat Weight": 0.24,
        "Coat Roughness": 0.22,
    }
    for input_name, value in paint_inputs.items():
        socket = principled.inputs.get(input_name)
        if not socket:
            continue
        for link in list(socket.links):
            material.node_tree.links.remove(link)
        socket.default_value = value


def render_variant(color_key, frame):
    bpy.context.scene.render.filepath = str(OUT_DIR / f"hull-{color_key}-{frame:02d}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered hull-{color_key}-{frame:02d}.png")


def main():
    colors, frames = parse_cli()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    context = setup_scene()
    set_visibility(BASE_COLLECTIONS)

    for color_key in colors:
        label, rgba = HULL_COLORS[color_key]
        print(f"Rendering {label}")
        set_body_color(rgba)
        for frame in frames:
            set_orbit(context, frame)
            render_variant(color_key, frame)


main()
