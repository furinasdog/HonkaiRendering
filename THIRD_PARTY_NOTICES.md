# Third-party notices

## VRM4U

MMD import uses [VRM4U](https://github.com/ruyo/VRM4U), copyright Haruyoshi Yamamoto, under its MIT license. The project uses [the HonkaiRendering fork](https://github.com/furinasdog/VRM4U) as the `Plugins/VRM4U` Git submodule. The main repository pins the precise fork commit rather than an unversioned download.

The fork starts from upstream tag `v1.2026.10.17` (`7395b50e9aa50245c8677132d805e8a8eff10093`) and adapts PMX LOD0 and material-property preservation. Its PMX parser is unchanged. Upstream license files and Assimp/other dependency notices remain in the submodule and must accompany redistribution. See the fork's `HONKAI_RENDERING.md` for the adaptation.

## Assimp

The VRM4U fork includes a rebuilt Assimp Windows library and pins [the adapted Assimp source](https://github.com/furinasdog/assimp) at `ThirdParty/assimp-source`. The source baseline is `ruyo/assimp` commit `06c4e29a3c873648a107de9c1ac50f687b4d50d8`. The change exports existing PMX culling and outline fields; it does not replace the parser. Assimp retains its BSD 3-clause license; see the source `LICENSE` and bundled `ThirdParty/assimp/LICENSE`. Source initialization and build instructions are documented in the VRM4U fork.

## Unreal Engine templates

Existing template files under `Source/HonkaiRendering` retain their Epic Games copyright notices. Unreal Engine and template-derived code are subject to their applicable Epic license, not a replacement MIT license from this repository. The engine installation and engine binaries are not included here.

## Reference media

User-provided MMD models, textures, game screenshots and illustrations are separate local reference assets. They are excluded from this repository, CI and cooked application; their original usage terms apply. The repository does not grant redistribution rights to miHoYo/HoYoverse content or third-party models.
