"""Blender background helper: bake a selected PMX face's smooth coordinates, not its lighting."""
import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("pmx", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("--material", required=True, help="Exact source face material name")
parser.add_argument("--mmd-tools", type=Path, required=True, help="Directory containing mmd_tools")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
sys.path.insert(0, str(args.mmd_tools))
from mmd_tools.core import pmx

model = pmx.load(str(args.pmx.resolve()))
slots = [i for i, mat in enumerate(model.materials) if mat.name == args.material]
assert len(slots) == 1, "Select one unambiguous face material"
slot = slots[0]
start = sum(mat.vertex_count for mat in model.materials[:slot]) // 3
faces = model.faces[start:start + model.materials[slot].vertex_count // 3]
indices = sorted({v for face in faces for v in face})
assert indices, "Face material has no geometry"
remap = {v: i for i, v in enumerate(indices)}
positions = np.array([model.vertices[i].co for i in indices])
span = np.ptp(positions, axis=0)
assert span[0] > 0 and span[1] > 0
coordinates = (positions - positions.min(axis=0)) / np.maximum(span, 1e-6)
central = (np.abs(coordinates[:, 0] - 0.5) < 0.15) & (coordinates[:, 1] > 0.15) & (coordinates[:, 1] < 0.65)
assert central.any(), "Face selection has no central geometry"
# Standard PMX faces -Z; the central foremost point locates the nose without a model preset.
nose_index = np.flatnonzero(central)[np.argmin(positions[central, 2])]
nose = coordinates[nose_index, :2].tolist()

# Emission baking only transfers the source UVs; it introduces no nose or lip shadows.
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
target = bpy.data.images.new("FaceCoordinates", width=512, height=512, alpha=False, float_buffer=True)
target.colorspace_settings.name = "Non-Color"
tex = nodes.new("ShaderNodeTexImage")
tex.image = target
nodes.active = tex
mesh.materials.append(mat)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 1
scene.cycles.device = "CPU"
bpy.ops.object.bake(type="EMIT", margin=12, use_clear=True)
args.output.mkdir(parents=True, exist_ok=True)
target.filepath_raw = str((args.output / "coordinates.png").resolve())
target.file_format = "PNG"
target.save()
(args.output / "material.json").write_text(json.dumps({"index": slot, "name": args.material, "nose": nose}, ensure_ascii=False), encoding="utf-8")
print("FACE_COORDINATES_BAKED", slot, len(faces), target.filepath_raw)
