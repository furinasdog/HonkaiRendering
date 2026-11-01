"""Bake face coordinates using Blender/MMD Tools; no texture import or saved preferences."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np


def bake(model, slot, output, resolution=512):
    if type(slot) is not int or not 0 <= slot < len(model.materials):
        raise ValueError("Invalid face material index")
    counts = [m.vertex_count for m in model.materials]
    if any(n < 0 or n % 3 for n in counts) or sum(counts) != len(model.faces) * 3:
        raise ValueError("Material triangle ranges are inconsistent")
    start = sum(mat.vertex_count for mat in model.materials[:slot]) // 3
    faces = model.faces[start:start + model.materials[slot].vertex_count // 3]
    indices = sorted({v for face in faces for v in face})
    if not indices:
        raise ValueError("Face material has no geometry")
    remap = {v: i for i, v in enumerate(indices)}
    if min(indices) < 0 or max(indices) >= len(model.vertices):
        raise ValueError("Invalid face vertex index")
    positions = np.array([model.vertices[i].co for i in indices])
    uvs = np.array([model.vertices[i].uv for i in indices])
    if not np.isfinite(positions).all() or not np.isfinite(uvs).all():
        raise ValueError("Non-finite positions or UVs")
    if (uvs < 0).any() or (uvs > 1).any():
        raise ValueError("Face UVs must lie in one 0..1 tile")
    span = np.ptp(positions, axis=0)
    if span[0] <= 1e-6 or span[1] <= 1e-6:
        raise ValueError("Face geometry has no width or height")
    coordinates = (positions - positions.min(axis=0)) / np.maximum(span, 1e-6)
    central = (np.abs(coordinates[:, 0] - 0.5) < 0.15) & (coordinates[:, 1] > 0.15) & (coordinates[:, 1] < 0.65)
    if not central.any():
        raise ValueError("Face selection has no central nose geometry")
    # shortcut: standard PMX faces -Z; other orientations need an authored profile.
    nose_index = np.flatnonzero(central)[np.argmin(positions[central, 2])]
    nose = coordinates[nose_index, :2].tolist()

    # Emission baking only transfers the source UVs; it introduces no nose or lip shadows.
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mesh = bpy.data.meshes.new("FaceBake")
    mesh.from_pydata(positions.tolist(), [], [[remap[v] for v in f] for f in faces])
    obj = bpy.data.objects.new("FaceBake", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    uv = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        source_uv = model.vertices[indices[loop.vertex_index]].uv
        uv.data[loop.index].uv = (source_uv[0], 1 - source_uv[1])
    attribute = mesh.color_attributes.new(name="FaceCoordinates", type="FLOAT_COLOR", domain="POINT")
    colors = np.column_stack((coordinates[:, 0], coordinates[:, 1], np.ones((len(indices), 2))))
    attribute.data.foreach_set("color", colors.ravel())
    mat = bpy.data.materials.new("CoordinateBake")
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    out = nodes.new("ShaderNodeOutputMaterial")
    emit = nodes.new("ShaderNodeEmission")
    color = nodes.new("ShaderNodeVertexColor")
    color.layer_name = attribute.name
    links.new(color.outputs["Color"], emit.inputs["Color"])
    links.new(emit.outputs[0], out.inputs["Surface"])
    target = bpy.data.images.new("FaceCoordinates", width=resolution, height=resolution, alpha=True, float_buffer=True)
    target.colorspace_settings.name = "Non-Color"
    target.alpha_mode = "CHANNEL_PACKED"
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = target
    nodes.active = tex
    mesh.materials.append(mat)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.device = "CPU"
    bpy.ops.object.bake(type="EMIT", margin=12, use_clear=True)
    output.mkdir(parents=True, exist_ok=True)
    target.filepath_raw = str((output / "coordinates.png").resolve())
    target.file_format = "PNG"
    target.save()
    pixels = np.empty(resolution * resolution * 4, dtype=np.float32)
    target.pixels.foreach_get(pixels)
    pixels = np.rint(np.clip(pixels.reshape(resolution, resolution, 4), 0, 1) * 255) / 255
    if not (pixels[:, :, 2] > 0.5).any():
        raise ValueError("UV baking produced no covered pixels")
    entry = {"index": slot, "name": model.materials[slot].name, "nose": nose}
    (output / "material.json").write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
    return pixels, entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pmx", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--material", required=True)
    parser.add_argument("--mmd-tools", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    sys.path.insert(0, str(args.mmd_tools))
    from mmd_tools.core import pmx
    model = pmx.load(str(args.pmx.resolve()))
    slots = [i for i, mat in enumerate(model.materials) if mat.name == args.material]
    if len(slots) != 1:
        raise ValueError("Select one unambiguous face material")
    bake(model, slots[0], args.output)
    print("FACE_COORDINATES_BAKED", slots[0], args.output.resolve())


if __name__ == "__main__":
    main()
