import io
import json
import struct
import sys
from pathlib import Path

from PIL import Image


ROOT = Path("/Users/basdewildt/Documents/New project/boat3-configurator")
SOURCE_GLB = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "images" / "dammer-boat-blender-v3.glb"
OUT_GLB = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "images" / "dammer-boat-blender-v3-web.glb"
OUT_REPORT = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "web-glb-optimization-report.json"

MAX_TEXTURE_SIZE = int(sys.argv[4]) if len(sys.argv) > 4 else 2048
JPEG_QUALITY = int(sys.argv[5]) if len(sys.argv) > 5 else 82


def read_glb(path):
    data = path.read_bytes()
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2 or length != len(data):
        raise ValueError("Not a GLB v2 file")

    chunks = {}
    offset = 12
    while offset < len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunks[chunk_type] = data[offset:offset + chunk_length]
        offset += chunk_length
    return json.loads(chunks[0x4E4F534A].decode("utf-8")), chunks[0x004E4942]


def padded_json_chunk(payload):
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return data + b" " * ((4 - len(data) % 4) % 4)


def pad4(data):
    return data + b"\x00" * ((4 - len(data) % 4) % 4)


def write_glb(path, gltf, bin_chunk):
    json_chunk = padded_json_chunk(gltf)
    chunks = [
        struct.pack("<II", len(json_chunk), 0x4E4F534A) + json_chunk,
        struct.pack("<II", len(bin_chunk), 0x004E4942) + bin_chunk,
    ]
    total_length = 12 + sum(len(chunk) for chunk in chunks)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, total_length) + b"".join(chunks))


def make_placeholder():
    image = Image.new("RGB", (1, 1), (255, 255, 255))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=60, optimize=True)
    return out.getvalue()


def optimized_image_bytes(raw):
    image = Image.open(io.BytesIO(raw))
    original_size = image.size
    image = image.convert("RGB")

    largest = max(image.size)
    if largest > MAX_TEXTURE_SIZE:
        scale = MAX_TEXTURE_SIZE / largest
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            Image.Resampling.LANCZOS,
        )

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return out.getvalue(), original_size, image.size


def texture_refs_from_texture_info(texture_info):
    if isinstance(texture_info, dict) and isinstance(texture_info.get("index"), int):
        return texture_info["index"]
    return None


def main():
    gltf, bin_chunk = read_glb(SOURCE_GLB)

    # The configurator renders cushions as one chosen color. Keep stitch/quilting
    # normal and roughness maps, but remove the source color maps so no blue or
    # multicolor fabric texture can leak through.
    for material in gltf.get("materials", []):
        if material.get("name") == "config_cushions":
            pbr = material.setdefault("pbrMetallicRoughness", {})
            pbr.pop("baseColorTexture", None)

    referenced_textures = set()
    for material in gltf.get("materials", []):
        pbr = material.get("pbrMetallicRoughness", {})
        for key in ("baseColorTexture", "metallicRoughnessTexture"):
            ref = texture_refs_from_texture_info(pbr.get(key))
            if ref is not None:
                referenced_textures.add(ref)
        ref = texture_refs_from_texture_info(material.get("normalTexture"))
        if ref is not None:
            referenced_textures.add(ref)
        ref = texture_refs_from_texture_info(material.get("occlusionTexture"))
        if ref is not None:
            referenced_textures.add(ref)
        ref = texture_refs_from_texture_info(material.get("emissiveTexture"))
        if ref is not None:
            referenced_textures.add(ref)

    referenced_images = {
        texture.get("source")
        for index, texture in enumerate(gltf.get("textures", []))
        if index in referenced_textures and isinstance(texture.get("source"), int)
    }

    image_by_buffer_view = {}
    for image_index, image in enumerate(gltf.get("images", [])):
        if isinstance(image.get("bufferView"), int):
            image_by_buffer_view[image["bufferView"]] = image_index

    placeholder = make_placeholder()
    report = []
    new_bin = bytearray()
    for buffer_index, buffer_view in enumerate(gltf.get("bufferViews", [])):
        start = buffer_view.get("byteOffset", 0)
        end = start + buffer_view["byteLength"]
        raw = bin_chunk[start:end]
        image_index = image_by_buffer_view.get(buffer_index)

        if image_index is not None:
            image = gltf["images"][image_index]
            original_len = len(raw)
            if image_index not in referenced_images:
                raw = placeholder
                image["mimeType"] = "image/jpeg"
                report.append({
                    "image": image.get("name"),
                    "action": "placeholder-unused",
                    "before_bytes": original_len,
                    "after_bytes": len(raw),
                })
            else:
                try:
                    raw, original_size, new_size = optimized_image_bytes(raw)
                    image["mimeType"] = "image/jpeg"
                    report.append({
                        "image": image.get("name"),
                        "action": "jpeg-optimized",
                        "before_bytes": original_len,
                        "after_bytes": len(raw),
                        "before_size": original_size,
                        "after_size": new_size,
                    })
                except Exception as error:
                    report.append({
                        "image": image.get("name"),
                        "action": "kept-original",
                        "error": repr(error),
                        "bytes": original_len,
                    })

        buffer_view["byteOffset"] = len(new_bin)
        buffer_view["byteLength"] = len(raw)
        new_bin.extend(pad4(raw))

    gltf["buffers"][0]["byteLength"] = len(new_bin)
    write_glb(OUT_GLB, gltf, bytes(new_bin))

    OUT_REPORT.write_text(json.dumps({
        "source": str(SOURCE_GLB),
        "output": str(OUT_GLB),
        "source_bytes": SOURCE_GLB.stat().st_size,
        "output_bytes": OUT_GLB.stat().st_size,
        "saved_bytes": SOURCE_GLB.stat().st_size - OUT_GLB.stat().st_size,
        "max_texture_size": MAX_TEXTURE_SIZE,
        "jpeg_quality": JPEG_QUALITY,
        "images": report,
    }, indent=2), encoding="utf-8")

    print(f"Wrote {OUT_GLB}")
    print(f"Size: {SOURCE_GLB.stat().st_size} -> {OUT_GLB.stat().st_size} bytes")
    print(f"Wrote {OUT_REPORT}")


if __name__ == "__main__":
    main()
