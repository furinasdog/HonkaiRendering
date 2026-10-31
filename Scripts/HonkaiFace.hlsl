// R/G hold the light-angle thresholds for opposite sides, in linear space.
// shortcut: the static PMX bind pose uses mesh-local axes; animated heads need bone axes.
float2 horizontal = normalize(Light.xy + float2(0, 0.00001));
float angle = acos(clamp(horizontal.y, -1.0, 1.0)) / 3.14159265;
float threshold = horizontal.x >= 0 ? Map.r : Map.g;
float width = max(fwidth(threshold), 0.008);
float lit = smoothstep(angle - width, angle + width, threshold);
return Base * lerp(float3(0.78, 0.61, 0.64), float3(1, 1, 1), lit);
