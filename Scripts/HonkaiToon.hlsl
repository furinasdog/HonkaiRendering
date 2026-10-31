// Quantize illumination, not the painted texture; only visible character pixels participate.
float visible = step(abs(Stencil.r - 1.0), 0.1) * step(abs(Depth.r - CustomDepth.r), 0.1);
float3 base = Diffuse.rgb;
float baseLuma = dot(base, float3(0.2126, 0.7152, 0.0722));
if (visible < 0.5 || baseLuma < 0.0001) return Scene.rgb;
// shortcut: this diffuse estimate assumes the viewer's neutral light and nonmetallic material.
float3 linearScene = Scene.rgb * View.OneOverPreExposure;
float illumination = dot(linearScene, float3(0.2126, 0.7152, 0.0722)) / baseLuma;
float width = max(fwidth(illumination), 0.025);
float band = smoothstep(0.42 - width, 0.42 + width, illumination);
float3 lighting = lerp(float3(0.64, 0.52, 0.61), float3(1.0, 1.0, 1.0), band);
// A narrow depth edge follows the silhouette instead of brightening painted texture boundaries.
float2 uv = GetDefaultSceneTextureUV(Parameters, 1);
float2 pixel = View.ViewSizeAndInvSize.zw * 1.5;
float adjacentDepth = max(max(SceneTextureLookup(uv + float2(pixel.x, 0), 1, false).r,
                             SceneTextureLookup(uv - float2(pixel.x, 0), 1, false).r),
                         max(SceneTextureLookup(uv + float2(0, pixel.y), 1, false).r,
                             SceneTextureLookup(uv - float2(0, pixel.y), 1, false).r));
float rim = step(max(0.5, Depth.r * 0.003), adjacentDepth - Depth.r);
rim *= saturate(dot(normalize(Normal.xyz), normalize(LightDirection)));
return base * (lighting + rim * 0.12) * View.PreExposure;
