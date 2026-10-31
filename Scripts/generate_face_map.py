"""Generate a shared stylized face-shadow profile with Blender/MMD Tools and the MIT SDF tool.

The smooth masks are an editable starting point, not recovered game LightMaps.
Run in ordinary Python with installed numpy and OpenCV. Outputs stay in Saved.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tools/sdf-shadow-threshold-map"))
import sdftool


def thresholds(coordinates):
    x = coordinates[:, :, 0] * 2 - 1
    height = coordinates[:, :, 1]
    # A broad curved terminator ignores geometric nose/lip cavities on every model.
    curve = 0.025 * np.cos(height * np.pi * 2)
    return [np.clip(0.5 + sign * 0.32 * x + curve, 0, 1) for sign in (1, -1)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pmx", type=Path)
    parser.add_argument("--material", required=True)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--mmd-tools", type=Path, required=True)
    args = parser.parse_args()
    assert args.pmx.is_file() and args.blender.is_file()
    source_hash = hashlib.sha1(args.pmx.read_bytes()).hexdigest()
    output = ROOT / "Saved/MmdShading" / source_hash
    output.mkdir(parents=True, exist_ok=True)
    # ASCII scratch paths also work with upstream OpenCV builds lacking Unicode paths.
    with tempfile.TemporaryDirectory(prefix="honkai_face_") as scratch:
        work = Path(scratch)
        subprocess.run([str(args.blender), "--background", "--factory-startup", "--python-exit-code", "1",
                        "--python", str(ROOT / "Scripts/bake_face_coordinates.py"), "--",
                        str(args.pmx.resolve()), str(work), "--material", args.material,
                        "--mmd-tools", str(args.mmd_tools)], check=True)
        raw = cv2.imread(str(work / "coordinates.png"), cv2.IMREAD_COLOR)
        assert raw is not None
        coordinates = raw[:, :, ::-1].astype(np.float32) / 255
        channels = []
        for side, threshold in enumerate(thresholds(coordinates)):
            mask_dir = work / str(side)
            mask_dir.mkdir()
            masks = []
            for frame, angle in enumerate(np.linspace(0, 1, 9)):
                mask = ((threshold > angle) & (coordinates[:, :, 2] > 0.5)).astype(np.uint8) * 255
                path = mask_dir / f"mask_{frame:02d}.png"
                assert cv2.imwrite(str(path), mask)
                masks.append(str(path))
            target = work / f"threshold_{side}.png"
            sdftool.generate_shadow_threshold_map(masks, str(target), bit_depth=8)
            result = cv2.imread(str(target), cv2.IMREAD_GRAYSCALE)
            assert result is not None and np.isfinite(result).all()
            channels.append(result)
            # Keep the authoring masks for review or paint-over, not in the public repo.
            for path in mask_dir.iterdir():
                dest = output / f"masks_{side}"
                dest.mkdir(exist_ok=True)
                (dest / path.name).write_bytes(path.read_bytes())
        entry = json.loads((work / "material.json").read_text(encoding="utf-8"))
        nose = entry.pop("nose")
        radius = np.sqrt(((coordinates[:, :, 0] - nose[0]) / 0.12) ** 2
                         + ((coordinates[:, :, 1] - nose[1]) / 0.075) ** 2)
        outline = np.clip((radius - 0.7) / 0.5, 0, 1)
        outline = (outline * 255).astype(np.uint8)
        encoded = cv2.imencode(".png", cv2.merge([outline, channels[1], channels[0]]))[1]
        (output / "face.png").write_bytes(encoded.tobytes())
        entry["texture"] = "face.png"
        (output / "profile.json").write_text(json.dumps({"version": 1, "source_sha1": source_hash,
                                                        "materials": [entry]}, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "coordinates.png").write_bytes((work / "coordinates.png").read_bytes())
    print("FACE_PROFILE", output)


if __name__ == "__main__":
    # Left/right masks mirror each other; front is lit and rear is dark.
    sample = np.array([[[0, .5, 1], [.5, .5, 1], [1, .5, 1]]])
    a, b = thresholds(sample)
    assert np.allclose(a, b[:, ::-1]) and np.all(a > 0) and np.all(a < 1)
    main()
