"""Windows stdlib checks for enhancement cache identity and tool archive boundaries."""
import base64
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def main():
    script = Path(__file__).with_name("Prepare-MmdEnhancement.ps1").resolve()
    with tempfile.TemporaryDirectory(prefix="honkai-enhancement-") as temp:
        root = Path(temp)
        resources = root / "resources"
        resources.mkdir()
        (resources / "model.pmx").write_bytes(b"model fixture")
        (resources / "texture.png").write_bytes(b"texture fixture")
        scripts = root / "scripts"
        scripts.mkdir()
        for name in ("generate_enhancement.py", "bake_face_coordinates.py", "enhancement-tools.json"):
            (scripts / name).write_text(name, encoding="utf-8")
        for name, member in (("valid", "mmd_tools/module.py"), ("escape", "../escape.py")):
            with zipfile.ZipFile(root / (name + ".zip"), "w") as archive:
                archive.writestr(member, b"fixture")
        command = f"""
. ([ScriptBlock]::Create([IO.File]::ReadAllText({quote(script)}))) -FunctionsOnly
$resources={quote(resources)}; $scripts={quote(scripts)}; $root={quote(root)}
function Key {{ Hash-Text ((Resource-Manifest $resources (Join-Path $resources 'model.pmx') $scripts -1 ([ordered]@{{resolution=512}})) | ConvertTo-Json -Depth 12 -Compress) }}
$first=Key
if((Key) -ne $first){{throw 'Cache identity is unstable.'}}
[IO.File]::WriteAllText((Join-Path $resources 'texture.png'),'changed')
$texture=Key
if($texture -eq $first){{throw 'Texture changes did not invalidate cache.'}}
[IO.File]::WriteAllText((Join-Path $resources 'new-texture.png'),'added')
$added=Key
if($added -eq $texture){{throw 'New dependencies did not invalidate cache.'}}
[IO.File]::WriteAllText((Join-Path $scripts 'generate_enhancement.py'),'new algorithm')
if((Key) -eq $added){{throw 'Algorithm changes did not invalidate cache.'}}
Write-Json (Join-Path $root 'state.json') @{{version=1;choice=0}}
Write-Json (Join-Path $root 'state.json') @{{version=1;choice=1}}
if((Read-Json (Join-Path $root 'state.json')).choice -ne 1){{throw 'Atomic JSON state replacement failed.'}}
Expand-VerifiedTool (Join-Path $root 'valid.zip') (Join-Path $root 'valid')
if(-not (Test-Path -LiteralPath (Join-Path $root 'valid/mmd_tools/module.py'))){{throw 'Valid tool archive did not expand.'}}
$rejected=$false
try{{Expand-VerifiedTool (Join-Path $root 'escape.zip') (Join-Path $root 'escape')}}catch{{$rejected=$true}}
if(-not $rejected -or (Test-Path -LiteralPath (Join-Path $root 'escape.py'))){{throw 'Tool archive traversal was not rejected.'}}
$rejected=$false
try{{Download-Verified 'http://example.invalid/tool.zip' ('0'*64) (Join-Path $root 'tool.zip')}}catch{{$rejected=$true}}
if(-not $rejected){{throw 'Untrusted download source was accepted.'}}
Write-Output 'PASS enhancement cache keys, JSON replacement, tool extraction and URL boundaries'
"""
        encoded = base64.b64encode(command.encode("utf-16-le")).decode()
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr.decode("utf-8", "replace"))
        print(result.stdout.decode("utf-8", "replace").strip())


if __name__ == "__main__":
    main()
