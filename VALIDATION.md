# Local validation — 2026-10-31

Environment: UE 5.8.4, Windows x64, D3D12/SM6. Development Editor build succeeded. The supplied source models were read separately with installed MMD Tools 4.5.3 and with the patched Assimp library before testing in UE.

| Model | Source triangles | Assimp triangles | UE before | UE after | Materials | Missing base textures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 星穹铁道—火花2 | 52,228 | 52,228 | 26,105 | 52,228 | 42 | 0 |
| 识之律者 | 29,864 | 29,864 | 14,930 | 29,864 | 19 | 0 |

All 61 material diffuse RGBA values, two-sided flags, outline switches, and outline widths were compared against MMD Tools output and matched the UE import logs. The unit test additionally checks outline RGBA and absent-property defaults. Counts alone do not prove visual fidelity; the two base-color screenshots were inspected for faces, clothing, silhouettes, and texture assignment.

Passed checks:

- `VRM4U.PMX.MaterialColorAndOpacity`: 1 success, 0 failures in the exported automation report.
- Windows ZIP self-check: Unicode names, Deflate, traversal/absolute/alternate-stream rejection, and duplicate-name rejection.
- Python syntax compilation and role-material generation with `-AllowCommandletRendering`.
- Separate offscreen base-color imports/screenshots for both models, each exiting normally with code 0. No automatic LOD0 reduction is reported.
- Separate toon-material imports/screenshots for both models also exited normally with code 0; authored outline switches remained in effect. This run did not reproduce the earlier crash.

Local evidence (ignored by Git): `Saved/Diagnostics/source_materials.json`, `assimp_fixed_52228.txt`, `assimp_fixed_29864.txt`; `Saved/Logs/BuildPmxFidelity.log`, `SetupPmxFidelity2.log`, `SparkleBaseFixed.log`, `SentiBaseFixed.log`, `SparkleToonFixed.log`, `SentiToonFixed.log`; `Saved/Tests/PmxFidelityAutomation/index.json`; `Saved/Screenshots/*BaseFixed.png` and `*ToonFixed.png`.

The initial material-generation pass encountered a locked, already loaded backdrop asset when the editor was reopened. The script now reuses the unchanged backdrop and checks every modified material's save result. The subsequent pass succeeded. Startup engine test diagnostics are not counted as the PMX automation test result; the exported test report is the result used above.

## Scope and limits

This verifies the two supplied static models; it is not a claim that every PMX loads correctly or that crashes are impossible. Full malformed-PMX fuzzing and packaged Shipping builds were not tested. The caller still imports synchronously on the game thread after ZIP extraction, so large models can pause interaction.

The toon material remains a rendering study. No matching authored facial SDF is available in these model packs. Material-level outline settings are preserved, but per-vertex edge scale, original sphere/toon-map shaders, dynamic cast shadows, animation, and physics are not reproduced. Base-color mode still passes through Unreal's color pipeline. Game-reference equivalence is not claimed.

Earlier interactive checks covered Esc, floating-window movement, Model submenu and file-dialog import. The full drag/drop and Blender mouse-control matrix has not been independently revalidated in this fix.

Copyrighted source models, textures, screenshots, and illustrations are deliberately excluded from this repository.
