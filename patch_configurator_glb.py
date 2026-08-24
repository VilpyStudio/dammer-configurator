import json
import struct
import sys
from pathlib import Path

ROOT = Path("/Users/basdewildt/Documents/New project/boat3-configurator")
SOURCE_GLB = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "images" / "dammer-boat.glb"
OUT_GLB = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "images" / "dammer-boat-configurator-v2.glb"
OUT_REPORT = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "configurator-glb-v2-report.json"

CONFIG_NAMES = {
    "Body": ("config_hull", [0.002, 0.002, 0.001, 1.0], 0.22, 0.3),
    "Leather": ("config_cushions", [0.74, 0.55, 0.47, 1.0], 0.0, 0.82),
    "Leather Used Red Diamon Quilted.002": ("config_cushions", [0.74, 0.55, 0.47, 1.0], 0.0, 0.82),
    "Leather Used Red Diamon Quilted.004": ("config_cushions", [0.74, 0.55, 0.47, 1.0], 0.0, 0.82),
    "Wood Plank": ("config_teak", [0.48, 0.42, 0.34, 1.0], 0.0, 0.72),
    "Wood Plank.001": ("config_teak", [0.48, 0.42, 0.34, 1.0], 0.0, 0.72),
    "Wood Plank_3": ("config_teak", [0.48, 0.42, 0.34, 1.0], 0.0, 0.72),
}

FIXED_NAMES = {
    "Wood.001": ("fixed_steering_wood", [0.42, 0.22, 0.10, 1.0], 0.0, 0.46),
    "Very dark red wood": ("fixed_dark_trim", [0.18, 0.035, 0.025, 1.0], 0.0, 0.42),
    "Very dark red wood_2": ("fixed_dark_trim", [0.18, 0.035, 0.025, 1.0], 0.0, 0.42),
    "Very dark red wood3": ("fixed_dark_trim", [0.18, 0.035, 0.025, 1.0], 0.0, 0.42),
    "White plastic": ("fixed_white_plastic", [0.88, 0.86, 0.82, 1.0], 0.0, 0.48),
    "Inner_body": ("fixed_inner_body", [0.88, 0.86, 0.82, 1.0], 0.0, 0.5),
    "fixed_inner_body_export": ("fixed_inner_body", [0.88, 0.86, 0.82, 1.0], 0.0, 0.5),
    "Material_001": ("fixed_inner_body", [0.88, 0.86, 0.82, 1.0], 0.0, 0.5),
    "Material_003": ("fixed_inner_body", [0.88, 0.86, 0.82, 1.0], 0.0, 0.5),
    "Stainless steel": ("fixed_metal", [0.58, 0.59, 0.56, 1.0], 0.9, 0.22),
    "Steel with procedural imperfections": ("fixed_metal", [0.43, 0.44, 0.41, 1.0], 0.82, 0.28),
    "metal": ("fixed_metal", [0.58, 0.59, 0.56, 1.0], 0.86, 0.2),
    "Scratched black metal": ("fixed_black_metal", [0.006, 0.007, 0.005, 1.0], 0.65, 0.32),
    "Black plastic": ("fixed_black_plastic", [0.006, 0.007, 0.005, 1.0], 0.0, 0.44),
    "Black wood": ("fixed_black_wood", [0.007, 0.004, 0.003, 1.0], 0.0, 0.5),
    "Blur Translucent Glass (glass)": ("fixed_glass", [0.70, 0.80, 0.76, 0.36], 0.0, 0.08),
}


def read_glb(path):
    data = path.read_bytes()
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2 or length != len(data):
        raise ValueError("Not a GLB v2 file")

    offset = 12
    chunks = []
    while offset < len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunks.append((chunk_type, data[offset:offset + chunk_length]))
        offset += chunk_length
    return chunks


def padded_json_chunk(payload):
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    padding = (4 - len(data) % 4) % 4
    return data + b" " * padding


def write_glb(path, json_payload, bin_chunk):
    json_chunk = padded_json_chunk(json_payload)
    chunks = [
        struct.pack("<II", len(json_chunk), 0x4E4F534A) + json_chunk,
        struct.pack("<II", len(bin_chunk), 0x004E4942) + bin_chunk,
    ]
    total_length = 12 + sum(len(chunk) for chunk in chunks)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, total_length) + b"".join(chunks))


def patch_material(material):
    old_name = material.get("name", "")
    target = CONFIG_NAMES.get(old_name) or FIXED_NAMES.get(old_name)
    if not target:
        return {"old": old_name, "new": old_name, "role": "unknown"}

    new_name, color, metallic, roughness = target
    material["name"] = new_name
    pbr = material.setdefault("pbrMetallicRoughness", {})
    pbr["baseColorFactor"] = color
    pbr["metallicFactor"] = metallic
    pbr["roughnessFactor"] = roughness
    if new_name == "fixed_glass":
        material["alphaMode"] = "BLEND"
        material["doubleSided"] = True
    role = new_name.replace("config_", "") if new_name.startswith("config_") else "fixed"
    return {"old": old_name, "new": new_name, "role": role}


def main():
    chunks = read_glb(SOURCE_GLB)
    json_chunk = next(chunk for kind, chunk in chunks if kind == 0x4E4F534A)
    bin_chunk = next(chunk for kind, chunk in chunks if kind == 0x004E4942)
    gltf = json.loads(json_chunk.decode("utf-8"))

    material_report = [patch_material(material) for material in gltf.get("materials", [])]
    write_glb(OUT_GLB, gltf, bin_chunk)

    OUT_REPORT.write_text(json.dumps({
        "source": str(SOURCE_GLB),
        "output": str(OUT_GLB),
        "materials": material_report,
    }, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_GLB}")
    print(f"Wrote {OUT_REPORT}")


if __name__ == "__main__":
    main()
