from pathlib import Path

import bpy

ROOT = Path("/Users/basdewildt/Documents/New project/boat3-configurator")
SOURCE_GLB = ROOT / "images" / "dammer-boat.glb"
OUT_GLB = ROOT / "images" / "dammer-boat-configurator-v2.glb"

CONFIG_HULL = {"Body"}
CONFIG_CUSHIONS = {"Leather", "Leather Used Red Diamon Quilted.002", "Leather Used Red Diamon Quilted.004"}
CONFIG_TEAK = {"Wood Plank", "Wood Plank.001", "Wood Plank_3"}

FIXED_MATERIALS = {
    "Wood.001": ("fixed_steering_wood", "#8c562f", 0.46, 0.0),
    "Very dark red wood": ("fixed_dark_trim", "#3f1713", 0.42, 0.0),
    "Very dark red wood_2": ("fixed_dark_trim", "#3f1713", 0.42, 0.0),
    "Very dark red wood3": ("fixed_dark_trim", "#3f1713", 0.42, 0.0),
    "White plastic": ("fixed_white_plastic", "#f1eee8", 0.48, 0.0),
    "Inner_body": ("fixed_inner_body", "#f1eee8", 0.5, 0.0),
    "Material_001": ("fixed_inner_body", "#f1eee8", 0.5, 0.0),
    "Material_003": ("fixed_inner_body", "#f1eee8", 0.5, 0.0),
    "Stainless steel": ("fixed_metal", "#c8cac4", 0.22, 0.88),
    "Steel with procedural imperfections": ("fixed_metal", "#aeb0aa", 0.28, 0.82),
    "metal": ("fixed_metal", "#c6c8c0", 0.2, 0.86),
    "Scratched black metal": ("fixed_black_metal", "#111410", 0.32, 0.65),
    "Black plastic": ("fixed_black_plastic", "#111410", 0.44, 0.0),
    "Black wood": ("fixed_black_wood", "#15100d", 0.5, 0.0),
    "Blur Translucent Glass (glass)": ("fixed_glass", "#dbe7e4", 0.08, 0.0),
}


def srgb_channel_to_linear(value):
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def hex_to_linear_rgba(hex_color):
    clean = hex_color.replace("#", "")
    channels = [int(clean[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    return tuple(srgb_channel_to_linear(channel) for channel in channels) + (1.0,)


def set_if_present(node, input_name, value):
    if input_name in node.inputs:
        node.inputs[input_name].default_value = value


def make_material(name, color, roughness, metallic, alpha=1.0):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = hex_to_linear_rgba(color)[:3] + (alpha,)
    material.blend_method = "BLEND" if alpha < 1 else "OPAQUE"
    material.use_screen_refraction = alpha < 1

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new(type="ShaderNodeOutputMaterial")
    shader = nodes.new(type="ShaderNodeBsdfPrincipled")
    shader.inputs["Base Color"].default_value = hex_to_linear_rgba(color)[:3] + (alpha,)
    set_if_present(shader, "Alpha", alpha)
    set_if_present(shader, "Metallic", metallic)
    set_if_present(shader, "Roughness", roughness)
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def build_material_library():
    library = {
        "config_hull": make_material("config_hull", "#080907", 0.28, 0.2),
        "config_cushions": make_material("config_cushions", "#dfb9a7", 0.82, 0.0),
        "config_teak": make_material("config_teak", "#9b9283", 0.74, 0.0),
    }

    for old_name, (new_name, color, roughness, metallic) in FIXED_MATERIALS.items():
        alpha = 0.36 if new_name == "fixed_glass" else 1.0
        library[old_name] = make_material(new_name, color, roughness, metallic, alpha)

    return library


def target_material(old_name, library):
    if old_name in CONFIG_HULL:
        return library["config_hull"]
    if old_name in CONFIG_CUSHIONS:
        return library["config_cushions"]
    if old_name in CONFIG_TEAK:
        return library["config_teak"]
    if old_name in library:
        return library[old_name]
    return make_material(f"fixed_{old_name.lower().replace(' ', '_')}", "#d2d1c9", 0.55, 0.0)


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_source():
    if not SOURCE_GLB.exists():
        raise FileNotFoundError(SOURCE_GLB)
    bpy.ops.import_scene.gltf(filepath=str(SOURCE_GLB))


def remap_materials():
    library = build_material_library()
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        obj.name = obj.name.replace(" ", "_")
        for slot in obj.material_slots:
            if slot.material:
                slot.material = target_material(slot.material.name, library)


def export_glb():
    OUT_GLB.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT_GLB),
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
        export_animations=False,
    )
    print(f"Exported {OUT_GLB}")


clean_scene()
import_source()
remap_materials()
export_glb()
