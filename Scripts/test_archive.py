"""Checks the real .NET ZIP extraction path used by the viewer."""
from pathlib import Path
import subprocess
import tempfile
import zipfile

SCRIPT = Path(__file__).with_name("Expand-MmdArchive.ps1")


def main():
    # Invoke using a generated encoded command, matching the C++ launcher.
    import base64
    def run(root, name, members):
        archive = root / (name + ".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for filename, data in members:
                z.writestr(filename, data)
        quote = lambda p: "'" + str(p).replace("'", "''") + "'"
        cmd = "& ([ScriptBlock]::Create([IO.File]::ReadAllText(" + quote(SCRIPT) + "))) -ArchivePath " + quote(archive) + " -Destination " + quote(root / name)
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(cmd.encode("utf-16-le")).decode()], capture_output=True)
        return result, root / name
    with tempfile.TemporaryDirectory(prefix="honkai-zip-") as temp:
        root = Path(temp)
        result, output = run(root, "valid", [("模型/人物.pmx", b"fixture"), ("模型/贴图.png", b"texture")])
        assert result.returncode == 0, result.stderr
        assert (output / "模型/人物.pmx").read_bytes() == b"fixture"
        for i, path in enumerate(("../escape.txt", "C:/escape.txt", "a/../../escape.txt", "a.txt:stream")):
            result, _ = run(root, "bad" + str(i), [(path, b"no")])
            assert result.returncode != 0, path
        result, _ = run(root, "duplicate", [("file", b"a"), ("FILE", b"b")])
        assert result.returncode != 0
        assert not (root / "escape.txt").exists()
    print("ZIP checks passed: Unicode, Deflate, traversal, absolute paths, alternate streams, duplicate names")


if __name__ == "__main__":
    main()
