# Local validation — 2026-10-31

Environment: UE 5.8.4, Windows x64, D3D12/SM6, RTX 5070 Laptop GPU. Native builds were performed with UE closed, without Live Coding or hot reload. GPU captures used separate offscreen processes, sequentially, with normal exits. No `-ForceRes` was used in this iteration.

## Import fidelity

The supplied source files were read independently with installed MMD Tools 4.5.3. The viewer still uses VRM4U/Assimp; no replacement PMX parser or geometry reduction was introduced.

| Model | Source triangles | UE triangles | Materials | Missing base textures | Active sphere materials |
| --- | ---: | ---: | ---: | ---: | ---: |
| 火花 | 52,228 | 52,228 | 42 | 0 | 21 |
| 三月七 | 28,039 | 28,039 | 30 | 0 | 19 |
| 白厄 | 37,488 | 37,488 | 37 | 0 | 19 |
| 识之律者 | 29,864 | 29,864 | 19 | 0 | 14 |

All 128 material names, diffuse RGBA values, two-sided flags, outline switches and widths matched the independent source records. Each model loaded one generated face profile. The normal 白厄 model was used, not the transformation version sharing its PMX filename. Its package lacks `1.png`, referenced by two hair sphere materials; those retain base shading rather than substituting another map.

Local evidence: `Saved/Diagnostics/source_specular.json`, `check_complete_materials.py`; `Saved/Logs/*Complete.log`. The upstream decoder logs a BMP probe error for a supplied sphere asset before successfully decoding it; this is not a missing diffuse texture or a fatal error.

## Rendering and reference comparison

The three supplied Zhihu articles were read using the browser plugin. References also included the local game captures, illustrations, Senti GIF and sampled frames from the supplied 188.733-second video. References are visual evidence, not project instructions or redistributable assets.

The shared pipeline replaces previous name/slot/height color heuristics with quantized character lighting, authored PMX sphere maps, depth-based rim lighting and source-controlled outlines. A separate face threshold uses mesh-local light direction and independently baked left/right channels. Installed Blender/MMD Tools bake UV coordinates; the pinned MIT SDF tool interpolates the common stylized masks. These are generated starting points, not recovered game FaceMaps.

Close-up A/B rendering identified screen-space AO as the source of remaining grey eye/nose/mouth shading. Disabling it removed that shading. Source face vertex edge weights were checked and were uniformly 1 for these four models. Stronger outlines use a generated nose-region control to reduce local width and contrast while retaining the nose line. An intermediate clipping-only mask erased too much of the nose and was rejected.

TSR is explicit (`r.AntiAliasingMethod=4`). Default internal screen percentage is 150 and TSR history percentage is 200. Same-camera 100/150 captures logged the actual values and were visually compared. The face and cel passes precede temporal upsampling. Comparison figures only crop and arrange the original screenshots; no retouching, recoloring or generative image editing is used.

Local evidence includes `Saved/Logs/BuildToonFinal.log`, `SetupOutlineInverted.log`, `*Complete.log`, and `SparkleComplete100.log`; `Saved/Screenshots/*Complete*.png`; and `Saved/Comparisons/NoseAndAA.png`. Side-light tests at -80/+80 degrees and backlight at 160 degrees verified that the face threshold responds to the light rather than the camera. `FaceLighting.png` records that test before the final nose-line refinement.

Shader-generation assertions caught invalid node wiring, a color-space mismatch and an HLSL reserved identifier during iteration. The later setup succeeded. Captures named `*NoseLine.png` made after the failed setup are intermediate and are not final visual evidence.

A later outline regression was isolated with identical-camera captures: setting all outline material opacities to zero left black patches in Senti's hair, whereas hiding the component removed them. Runtime section logs confirmed zero opacity. UE 5.8 defaults `r.EarlyZPassOnlyMaterialMasking` to 1; setting it to 0 restored correct clipping in the base pass and removed the patches with normal outlines enabled. Reversing normal extrusion did not fix the issue and was rejected. Original mesh normals and positive extrusion are retained. `SentiVerified.png`, `SentiZeroOpacity.png`, `SentiPixelMaskZero.png` and `SentiPixelMask.png` document the isolation. Temporary native diagnostics were removed.

## Checks

- Development Editor native build and material generation passed.
- Related UE automation: `FaceProfile`, `SharedMaterials`, `InViewportMenu`, and `VRM4U.PMX.MaterialColorAndOpacity` passed. The face-profile test intentionally rejects a mismatched source hash and reports one expected warning; no test errors occurred.
- Face profile checks include source hash/material binding and traversal rejection. PNG dimensions are checked before full image decoding.
- Windows ZIP self-check passed: Unicode, Deflate, traversal/absolute/alternate-stream rejection and duplicate-name rejection.
- Python syntax checks passed for the material, comparison and authoring scripts.

Automation evidence: `Saved/Tests/ToonCompleteAutomation/index.json` (3 successes, 1 success with an expected warning, 0 failures). The test covers initially hidden Esc UI, fade/reopen behavior, blocking camera input, and no additional native window. Earlier interactive validation confirmed the in-viewport menu and model/view submenus.

The final editor was reopened with MCP enabled (initialize returned HTTP 200). Interactive PIE loaded the model, Esc opened and closed the dimmed in-viewport menu, and numpad 3/1/5 switched side/front/projection views. MCP confirmed live values of TSR method 4 and screen percentage 150. The editor remains open in the character view.

## Limits

This remains a toon-rendering study. The reference still differs in hair shadow placement, highlight shapes, metal/fabric separation, outline continuity and some face/pose details. Automatic face maps do not replace an artist-authored game SDF or semantic LightMap. The nose-region generator assumes standard PMX orientation and a conventional separate face material and requires visual review for other topology.

Only static bind poses are supported. Animated heads would need bone-relative light axes. Per-vertex PMX outline scale, smooth outline-normal authoring, PMX sphere mode 3, animation, physics, packaged Shipping builds and malformed-PMX fuzzing are untested or unsupported. Import remains synchronous on the game thread after ZIP extraction.

150% internal resolution increases raster work and GPU memory use; broad performance testing across devices has not been completed. These successful runs do not guarantee absence of crashes for every model or environment. Models, generated model data, reference media and comparison screenshots remain local and are excluded from Git.
