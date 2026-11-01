"""Isolated Blender worker: generate validated face data in a caller-owned staging directory."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

import numpy as np

ALGORITHM = "face-v2"
FACE_NAMES = {"face", "顔", "顏", "颜", "脸", "臉"}


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    text = json.dumps(value, ensure_ascii=False, indent=2)
    for attempt in range(10):
        try:
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(path)
            return
        except PermissionError:
            # Windows readers and scanners may briefly hold a handle without delete sharing.
            if attempt == 9:
                raise
            time.sleep(0.05)


def face_channels(coordinates, nose):
    if coordinates.ndim != 3 or coordinates.shape[2] < 3 or not np.isfinite(coordinates).all():
        raise ValueError("Invalid baked coordinates")
    if len(nose) != 2 or not np.isfinite(nose).all() or min(nose) < 0 or max(nose) > 1:
        raise ValueError("Invalid nose position")
    x = coordinates[:, :, 0] * 2 - 1
    height = coordinates[:, :, 1]
    x /= np.sqrt(np.maximum(0.25, 1 - (height * 2 - 1) ** 2))
    curve = 0.025 * np.cos(height * np.pi * 2)
    a, b = [np.clip(0.5 + sign * 0.32 * x + curve, 0, 1) for sign in (1, -1)]
    radius = np.sqrt(((coordinates[:, :, 0] - nose[0]) / 0.12) ** 2
                     + ((height - nose[1]) / 0.075) ** 2)
    outline = np.clip((radius - 0.7) / 0.5, 0, 1)
    nose_region = ((np.abs(coordinates[:, :, 0] - nose[0]) / 0.016
                    + np.abs(height - nose[1] - 0.015) / 0.045) < 1)
    covered = coordinates[:, :, 2] > 0.5
    # Uncovered UV space must never produce a nose shadow or suppress an outline.
    return np.stack((a, b, np.where(covered, outline, 1),
                     np.where(covered & nose_region, 0, 1)), axis=2).astype(np.float32)


def choose_material(model, index=None, name=None):
    candidates = [{"index": i, "name": m.name} for i, m in enumerate(model.materials)
                  if m.vertex_count > 0 and m.diffuse[3] > 0.5]
    if index is not None:
        if index not in {x["index"] for x in candidates}:
            raise ValueError("Selected material has no visible opaque geometry")
        return index, candidates
    if name is not None:
        matches = [x["index"] for x in candidates if x["name"] == name]
        if len(matches) != 1:
            raise ValueError("Material name is missing or ambiguous; select its index")
        return matches[0], candidates
    # Generic face labels only; no character names or per-model slot presets.
    matches = [x["index"] for x in candidates if x["name"].strip().casefold() in FACE_NAMES]
    return (matches[0] if len(matches) == 1 else None), candidates


def parameters(path):
    if path is not None and (not path.is_file() or path.stat().st_size > 65536):
        raise ValueError("Parameter file is missing or too large")
    value = {} if path is None else json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or set(value) - {"resolution"}:
        raise ValueError("Unknown generation parameter")
    resolution = value.get("resolution", 512)
    if type(resolution) is not int or resolution not in (256, 512, 1024):
        raise ValueError("Resolution must be 256, 512 or 1024")
    return {"resolution": resolution}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pmx", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mmd-tools", type=Path, required=True)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--material-index", type=int)
    selection.add_argument("--material")
    parser.add_argument("--parameters-json", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    output = args.output.resolve()
    source = args.pmx.resolve()
    if output == source or output in source.parents:
        raise ValueError("Staging directory must not contain the original model")
    if output.exists() and any(p.name != "status.json" for p in output.iterdir()):
        raise ValueError("Use a new empty staging directory; existing data is preserved")
    output.mkdir(parents=True, exist_ok=True)

    def status(stage, progress, message, state="running", **extra):
        atomic_json(output / "status.json", {"version": 1, "algorithm": ALGORITHM,
                    "stage": stage, "progress": progress, "state": state, "message": message, **extra})

    try:
        status("prepare", 0.05, "检查模型与生成依赖")
        if not source.is_file() or source.suffix.lower() != ".pmx" or not 0 < source.stat().st_size <= 256 * 1024 * 1024:
            raise ValueError("PMX must be a non-empty file no larger than 256 MiB")
        if not (args.mmd_tools / "mmd_tools/core/pmx/__init__.py").is_file():
            raise ValueError("Compatible MMD Tools PMX loader was not found")
        options = parameters(args.parameters_json)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        sys.path.insert(0, str(args.mmd_tools.resolve()))
        import bpy
        from mmd_tools.core import pmx
        from bake_face_coordinates import bake
        if bpy.app.version[:2] != (5, 0):
            raise ValueError("This worker is validated for Blender 5.0 only")
        source_hash = hashlib.sha1(source.read_bytes()).hexdigest()
        model = pmx.load(str(source))
        status("identify", 0.15, "识别面部材质")
        slot, candidates = choose_material(model, args.material_index, args.material)
        if slot is None:
            status("identify", 0.15, "请选择预览中的面部材质", state="needs_material", candidates=candidates)
            return
        status("generate", 0.25, "烘焙面部坐标")
        try:
            coordinates, entry = bake(model, slot, output, options["resolution"])
        except ValueError:
            if args.material_index is not None or args.material is not None:
                raise
            status("identify", 0.15, "自动识别的几何不适合生成，请选择面部材质", state="needs_material", candidates=candidates)
            return
        status("generate", 0.7, "生成卡通阴影与鼻部控制")
        nose = entry.pop("nose")
        if not (0.35 < nose[0] < 0.65 and 0.15 < nose[1] < 0.65):
            raise ValueError("Detected nose is outside the central face region")
        face = face_channels(coordinates, nose)
        if not (face[:, :, 3] == 0).any():
            raise ValueError("Nose control has no covered texels; review the selected face UVs")
        image = bpy.data.images.new("FaceControl", width=options["resolution"], height=options["resolution"],
                                     alpha=True, float_buffer=False)
        image.colorspace_settings.name = "Non-Color"
        image.alpha_mode = "CHANNEL_PACKED"
        image.pixels.foreach_set(face.ravel())
        image.filepath_raw = str(output / "face.png")
        image.file_format = "PNG"
        image.save()
        status("validate", 0.9, "检查生成数据")
        check = bpy.data.images.load(str(output / "face.png"), check_existing=False)
        check.colorspace_settings.name = "Non-Color"
        check.alpha_mode = "CHANNEL_PACKED"
        decoded = np.empty(face.size, dtype=np.float32)
        check.pixels.foreach_get(decoded)
        if tuple(check.size) != (options["resolution"],) * 2 or not np.isfinite(decoded).all():
            raise ValueError("Generated PNG failed validation")
        if np.max(np.abs(decoded.reshape(face.shape) - face)) > 1.1 / 255:
            raise ValueError("PNG color space or packed channels changed during encoding")
        if hashlib.sha1(source.read_bytes()).hexdigest() != source_hash:
            raise ValueError("Source model changed during generation; retry")
        entry["texture"] = "face.png"
        profile = {"version": 1, "algorithm": ALGORITHM, "source_sha1": source_hash,
                   "parameters": options, "materials": [entry]}
        atomic_json(output / "profile.json", profile)
        atomic_json(output / "result.json", {"version": 1, "algorithm": ALGORITHM,
                    "source_sha1": source_hash, "material_index": slot, "parameters": options,
                    "files": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                              for name in ("profile.json", "face.png", "coordinates.png")}})
        status("complete", 1, "增强数据已生成并通过检查", state="succeeded")
    except Exception as error:
        status("failed", 0, str(error), state="failed")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
