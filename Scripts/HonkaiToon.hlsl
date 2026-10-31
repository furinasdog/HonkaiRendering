// Work in linear light; source atlases already contain painted details.
float3 n = normalize(N);
float3 v = normalize(V);
float3 l = normalize(LightDirection);
float face = step(0.5, Region) * (1.0 - step(1.5, Region));
float hair = step(1.5, Region) * (1.0 - step(2.5, Region));
float skin = step(2.5, Region) * (1.0 - step(3.5, Region));
float eyes = step(3.5, Region) * (1.0 - step(4.5, Region));
float metal = step(4.5, Region);
float ndl = dot(n, l);
float threshold = lerp(0.12, 0.32, hair);
float band = smoothstep(threshold - 0.025, threshold + 0.025, ndl);
// shortcut: softened directional face response until a matching authored SDF is available.
float3 faceNormal = normalize(n * float3(0.45, 1.0, 0.35) + float3(0.65, 0, 0));
float faceBand = smoothstep(0.04, 0.28, dot(faceNormal, l));
band = lerp(band, lerp(0.70, 1.0, faceBand), face);
float flesh = max(face, skin);
float3 lit = Base * Tint * lerp(float3(1,1,1), float3(1.0,0.95,0.96), flesh);
float3 shadow = lerp(float3(0.48,0.43,0.60), float3(0.85,0.67,0.72), flesh);
shadow = lerp(shadow, float3(0.49,0.34,0.49), hair);
float3 color = lit * lerp(shadow, float3(1,1,1), band);
// Long pale hair in the supplied references darkens towards lavender/pink tips.
float height = saturate((W.z - Center.z) / max(2.0 * Extent.z, 0.001) + 0.5);
float tips = 1.0 - smoothstep(0.40, 0.88, height);
color *= lerp(float3(1,1,1), float3(0.53,0.37,0.53), hair * tips * 0.72);
// A narrow normal-based glint never replaces painted hair highlights.
float3 h = normalize(l + v);
float glint = smoothstep(0.965, 0.985, dot(n,h));
color += lit * glint * band * (hair * 0.10 + metal * 0.32);
float rim = smoothstep(0.76, 0.94, 1.0 - saturate(dot(n,v)));
rim *= smoothstep(-0.15,0.55,ndl) * (1.0-face) * (1.0-eyes);
color += lit * float3(0.13,0.15,0.21) * rim;
color = lerp(color, Base * Tint, eyes);
return lerp(Base * Tint, color, ToonStrength);
