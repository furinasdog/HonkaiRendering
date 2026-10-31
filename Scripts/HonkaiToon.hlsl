// MMD diffuse atlases already contain painted lighting. Preserve those values.
float3 n = normalize(N);
float3 v = normalize(V);
float3 l = normalize(LightDirection);
float isFace = step(0.5, Region) * (1.0 - step(1.5, Region));
float isHair = step(1.5, Region) * (1.0 - step(2.5, Region));
float isSkin = step(2.5, Region);

float halfLambert = dot(n, l) * 0.5 + 0.5;
float band = smoothstep(0.48, 0.52, halfLambert);
// shortcut: without an authored facial SDF use flattened facial lighting;
// replace this approximation when a matching FaceMap is supplied.
float faceBand = smoothstep(-0.3, 0.05, dot(normalize(lerp(n, float3(1,0,0), 0.82)), l));
band = lerp(band, faceBand, isFace);

float3 shadow = lerp(float3(0.65, 0.62, 0.74), float3(0.79, 0.64, 0.66), max(isFace, isSkin));
shadow = lerp(shadow, float3(0.71, 0.65, 0.73), isHair);
float3 ramp = lerp(shadow, float3(1.0, 0.985, 0.98), band);
float3 color = Base * Tint * ramp;
// Keep the painted hair highlights; add only a narrow, low-energy rim.
float rim = smoothstep(0.82, 0.94, 1.0 - abs(dot(n, v)));
rim *= smoothstep(-0.15, 0.5, dot(n, l)) * (1.0 - isFace);
color += Base * float3(0.09, 0.1, 0.14) * rim;
return lerp(Base * Tint, color, ToonStrength);
