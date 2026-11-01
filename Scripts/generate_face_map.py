"""Launch the isolated Blender worker; no external NumPy/OpenCV installation is required."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pmx", type=Path)
    parser.add_argument("--material", required=True)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--mmd-tools", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="New staging directory; existing profiles are never overwritten")
    args = parser.parse_args()
    if not args.pmx.is_file() or not args.blender.is_file():
        parser.error("PMX and Blender must exist")
    if args.output:
        output = args.output.resolve()
    else:
        staging = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "HonkaiRendering/Staging"
        staging.mkdir(parents=True, exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="face-", dir=staging))
    subprocess.run([str(args.blender.resolve()), "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python", str(Path(__file__).with_name("generate_enhancement.py").resolve()), "--",
                    "--pmx", str(args.pmx.resolve()), "--output", str(output),
                    "--material", args.material, "--mmd-tools", str(args.mmd_tools.resolve())], check=True)
    print("FACE_PROFILE", output)


if __name__ == "__main__":
    main()
