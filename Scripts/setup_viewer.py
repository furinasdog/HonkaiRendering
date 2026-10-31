"""Run in UE's Python console using: py followed by this script's quoted absolute path."""
import unreal as u
from pathlib import Path

ROOT = "/Game/MmdViewer"
tools = u.AssetToolsHelpers.get_asset_tools()
lib = u.MaterialEditingLibrary

def connect(source, output, target, input_name):
    assert lib.connect_material_expressions(source, output, target, input_name), (source, output, target, input_name)

def output(source, output_name, prop):
    assert lib.connect_material_property(source, output_name, prop), (source, output_name, prop)


def material(name, translucent=False, outline=False, backdrop=False, two_sided=False):
    path = ROOT + "/" + name
    if u.EditorAssetLibrary.does_asset_exist(path):
        m = u.load_asset(path)
        lib.delete_all_material_expressions(m)
    else:
        m = tools.create_asset(name, ROOT, u.Material, u.MaterialFactoryNew())
    m.set_editor_property("shading_model", u.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("two_sided", two_sided or outline or backdrop)
    m.set_editor_property("blend_mode", u.BlendMode.BLEND_OPAQUE if backdrop else (u.BlendMode.BLEND_TRANSLUCENT if translucent else u.BlendMode.BLEND_MASKED))
    m.set_editor_property("opacity_mask_clip_value", 0.1)
    if not backdrop:
        lib.set_base_material_usage(m, u.MaterialUsage.MATUSAGE_SKELETAL_MESH)

    def node(cls, **props):
        n = lib.create_material_expression(m, cls)
        for k, v in props.items():
            n.set_editor_property(k, v)
        return n

    tint = node(u.MaterialExpressionVectorParameter, parameter_name="Tint", default_value=u.LinearColor(0.12, 0.16, 0.21, 1) if backdrop else u.LinearColor(1, 1, 1, 1))
    if backdrop:
        output(tint, "RGB", u.MaterialProperty.MP_EMISSIVE_COLOR)
    else:
        texture = node(u.MaterialExpressionTextureSampleParameter2D, parameter_name="BaseTexture", texture=u.load_asset("/Engine/EngineResources/WhiteSquareTexture"))
        opacity = node(u.MaterialExpressionScalarParameter, parameter_name="Opacity", default_value=1.0)
        alpha = node(u.MaterialExpressionMultiply)
        connect(texture, "A", alpha, "A")
        connect(opacity, "", alpha, "B")
        output(alpha, "", u.MaterialProperty.MP_OPACITY if translucent else u.MaterialProperty.MP_OPACITY_MASK)
        if outline:
            ink = node(u.MaterialExpressionCustom, output_type=u.CustomMaterialOutputType.CMOT_FLOAT3,
                       code="return max(Ink, Base * float3(0.16, 0.09, 0.12));")
            ink_inputs = []
            for input_name in ("Ink", "Base"):
                i = u.CustomInput()
                i.set_editor_property("input_name", input_name)
                ink_inputs.append(i)
            ink.set_editor_property("inputs", ink_inputs)
            connect(tint, "RGB", ink, "Ink")
            connect(texture, "RGB", ink, "Base")
            output(ink, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
            normal = node(u.MaterialExpressionVertexNormalWS)
            width = node(u.MaterialExpressionScalarParameter, parameter_name="OutlineWidth", default_value=0.12)
            offset = node(u.MaterialExpressionMultiply)
            connect(normal, "", offset, "A")
            connect(width, "", offset, "B")
            output(offset, "", u.MaterialProperty.MP_WORLD_POSITION_OFFSET)
            facing = node(u.MaterialExpressionTwoSidedSign)
            mask = node(u.MaterialExpressionCustom, output_type=u.CustomMaterialOutputType.CMOT_FLOAT1, code="return A * step(S, 0.0);")
            inputs = []
            for input_name in ("A", "S"):
                i = u.CustomInput()
                i.set_editor_property("input_name", input_name)
                inputs.append(i)
            mask.set_editor_property("inputs", inputs)
            connect(alpha, "", mask, "A")
            connect(facing, "", mask, "S")
            output(mask, "", u.MaterialProperty.MP_OPACITY_MASK)
        else:
            normal = node(u.MaterialExpressionVertexNormalWS)
            view = node(u.MaterialExpressionCameraVectorWS)
            shader = node(u.MaterialExpressionCustom, output_type=u.CustomMaterialOutputType.CMOT_FLOAT3)
            shader.set_editor_property("code", Path(__file__).with_name("HonkaiToon.hlsl").read_text(encoding="utf-8"))
            inputs = []
            for input_name in ("N", "V", "Base", "Tint", "Region", "LightDirection", "ToonStrength", "W", "Center", "Extent"):
                i = u.CustomInput()
                i.set_editor_property("input_name", input_name)
                inputs.append(i)
            shader.set_editor_property("inputs", inputs)
            for source, pin, target in ((normal, "", "N"), (view, "", "V"), (texture, "RGB", "Base"), (tint, "RGB", "Tint")):
                connect(source, pin, shader, target)
            region = node(u.MaterialExpressionScalarParameter, parameter_name="Region", default_value=0)
            light = node(u.MaterialExpressionVectorParameter, parameter_name="LightDirection", default_value=u.LinearColor(0.45, -0.6, 0.66, 0))
            connect(region, "", shader, "Region")
            connect(light, "RGB", shader, "LightDirection")
            strength = node(u.MaterialExpressionScalarParameter, parameter_name="ToonStrength", default_value=1)
            connect(strength, "", shader, "ToonStrength")
            connect(node(u.MaterialExpressionWorldPosition), "XYZ", shader, "W")
            connect(node(u.MaterialExpressionObjectPositionWS), "", shader, "Center")
            connect(node(u.MaterialExpressionObjectBounds), "", shader, "Extent")
            output(shader, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.layout_material_expressions(m)
    errors = lib.recompile_material(m)
    assert not errors, errors
    u.log("MMD_MATERIAL_CHECK " + name + " shading=" + str(m.get_editor_property("shading_model")))
    assert u.EditorAssetLibrary.save_loaded_asset(m), path
    return m


material("M_Toon")
material("M_ToonTwoSided", two_sided=True)
material("M_ToonTranslucent", translucent=True)
material("M_ToonTranslucentTwoSided", translucent=True, two_sided=True)
material("M_Outline", outline=True)
background = u.load_asset(ROOT + "/M_Backdrop") if u.EditorAssetLibrary.does_asset_exist(ROOT + "/M_Backdrop") else material("M_Backdrop", backdrop=True)

level_path = ROOT + "/L_Viewer"
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
if not u.EditorAssetLibrary.does_asset_exist(level_path):
    assert levels.new_level(level_path)
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    sphere = actors.spawn_actor_from_class(u.StaticMeshActor, u.Vector(0, 0, 0))
    sphere.set_actor_label("Studio backdrop")
    comp = sphere.static_mesh_component
    comp.set_static_mesh(u.load_asset("/Engine/BasicShapes/Sphere"))
    comp.set_material(0, background)
    comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    sphere.set_actor_scale3d(u.Vector(500, 500, 500))
    levels.save_current_level()
u.log("MMD_VIEWER_SETUP_COMPLETE")
