# HonkaiRendering / 崩坏渲染

基于 UE 5.8 的静态 MMD 角色查看器，研究米哈游角色渲染风格。MMD 读取由 VRM4U 完成；项目开发集中于卡通明暗、色彩、脸部受光、描边和角色展示。

An open-source UE 5.8 MMD character viewer and Honkai-inspired toon-rendering study. This is an independent project and is not affiliated with miHoYo/HoYoverse or Epic Games.

## 使用

默认画面仅显示角色与背景。将包含 PMX 和贴图的 ZIP 拖入窗口，在画面内选择 PMX。按 Esc 打开或关闭视口内菜单，遮罩与菜单用 0.18 秒淡入淡出，不创建独立窗口；“模型”子菜单提供 ZIP 导入，“视角”子菜单提供聚焦、投影切换和操作说明。菜单打开及淡出期间阻止镜头操作。文件导入失败会给出可关闭的提示，已加载模型会保留。

- 中键拖动：旋转；Shift + 中键：平移；Ctrl + 中键或滚轮：缩放。
- 小键盘 1 / 3 / 7：正面 / 右侧 / 顶部；Ctrl 配合为反向视图。
- 小键盘 5：正交 / 透视；小键盘小数点或 Home：聚焦。

ZIP 中应保留 PMX 与贴图的相对目录结构。首版支持 Windows 上的普通 ZIP，解包使用系统自带 PowerShell/.NET；导入缓存位于 `Saved/MmdImports`，源文件不被修改。

## 构建

需要已安装的 UE 5.8、兼容的 Visual Studio C++ 工具链和 Windows SDK。基础脚本检查仅使用 Python 标准库；Python 不是应用运行时依赖。

```powershell
git clone --recurse-submodules https://github.com/furinasdog/HonkaiRendering.git
cd HonkaiRendering
```

生成 `HonkaiRendering.uproject` 的工程文件并编译 `HonkaiRenderingEditor`，打开 `/Game/MmdViewer/L_Viewer`。VRM4U 以 submodule 固定到本项目 fork 的已提交版本；更新源码后使用 `git submodule update --init --recursive`。

`Content/MmdViewer` 包含本项目的关卡与材质。修改 `Scripts/HonkaiToon.hlsl` 后，在 UE Python 环境运行 `Scripts/setup_viewer.py` 更新材质；无界面命令模式必须加 `-AllowCommandletRendering` 才会编译 GPU 材质。

## 渲染范围

渲染对所有模型使用同一套灯光与参数，不按角色名称或模型高度调色。身体材质使用 UE Default Lit 取得方向光和投影，再在时间上采样前仅对角色光照做两段量化，保留原始贴图变化。通过 Custom Stencil 和深度限定角色范围；细窄亮边来自深度轮廓和光向。固定曝光，关闭电影色调曲线、局部曝光对比调整及屏幕空间 AO，避免眼窝和嘴角产生写实灰暗。背景球不参与投影。

共享材质以非金属、无物理镜面反射作为光照估算前提。PMX 作者配置的球面贴图按视空间法线采样，保留乘法/加法模式，为相应材质补充随视角变化的反射；不靠名字或颜色猜测材质类型。半透明 PMX 覆盖层保留原色和透明度；它们没有完整 GBuffer，不参与此光照分段。描边沿用模型作者提供的开关、颜色和宽度，统一缩放。

fork 中的 PMX 适配禁止 LOD0 自动减面，保留原始 Diffuse、Opacity、双面标记和材质描边属性，使隐藏表情、服装覆盖层和半透明材质维持其原始状态。Assimp 源码另以嵌套 submodule 关联，按需初始化，重建步骤见插件的 `HONKAI_RENDERING.md`。球面贴图目前支持 PMX 的乘法/加法模式，不支持使用额外 UV 的模式 3；找不到文件时保留基础材质。

面部可使用独立的线性空间阴影阈值贴图，绕开几何法线与投影，保留平滑、清楚的卡通色块。光向转换到模型局部坐标，左右各有一个通道，支持不对称 UV。面部材质角色由外部数据明确指定，运行时不猜名字或硬编码角色槽位。

通用 MMD 模型没有统一的 LightMap/FaceMap 标准。没有面部数据时使用共用身体材质回退。自动生成的数据是可编辑的风格化起点，不是恢复出的原游戏贴图；完整原游戏材质、动画、表情编辑与物理模拟不在首版范围内。

## 抗锯齿

抗锯齿使用 TSR，默认以 150% 内部分辨率渲染再输出，历史缓存为 200%。细发丝和描边在时间积累前参与处理。该质量设置增加 GPU 开销；需要降低负载时，可将 `Config/DefaultEngine.ini` 中的 `r.ScreenPercentage` 改为 100，仍保留 TSR。截图对比工具不额外模糊图像。

`r.EarlyZPassOnlyMaterialMasking=0` 保证颜色绘制阶段也检查透明度。PMX 的隐藏覆盖层与主体可能重合；只在深度预处理阶段裁剪透明度，会让部分零透明度描边在颜色阶段显示为黑块。

## 生成面部辅助数据

使用已安装的 Blender 5.0、MMD Tools 4.5、Python、NumPy 和 OpenCV。`Tools/sdf-shadow-threshold-map` 固定到 MIT 许可工具的提交，未修改其源码。PMX 仍由 MMD Tools 读取，不自写解析器，不修改源模型。

```powershell
python Scripts/generate_face_map.py '模型完整路径.pmx' --material '源模型中面部材质的准确名称' --blender 'Blender安装目录/blender.exe' --mmd-tools '包含mmd_tools目录的路径'
```

Blender 将面部平滑坐标烘焙到原 UV，随后生成左右各 9 张明暗遮罩，由现有 SDF 工具插值为阈值贴图。同一公式用于所有模型；不会把鼻孔、嘴角的物理阴影烘焙进去。输出位于 `Saved/MmdShading/<PMX SHA1>/`，重新导入相同 PMX 时自动使用。`masks_0` / `masks_1` 保留中间遮罩供检查；美术可以据此另行制作更精确的阈值图。

可将 `profile.json` 改名为 `<完整PMX文件名>.toon.json`，与 `face.png` 放到 PMX 同目录一起打包。配置核对版本、源文件哈希、材质索引和准确名称；贴图仅允许同目录 PNG，限制文件和解码前图像尺寸。无匹配数据则回退到共用材质。阈值图 R/G 是两侧光向的亮部截止角度，0 表示正面、1 表示背面，按线性数据采样。B 为面部描边控制：按标准 PMX 朝向，从中央最前方几何定位鼻尖，以同一比例减小局部线宽与对比度，保留鼻线和面部外轮廓。非标准朝向或非常规面部拓扑需要人工检查此数据。

当前只支持静态 PMX 默认姿态。动画头部需要以骨骼坐标更新光向。面部自动生成不等于原游戏的美术 SDF；发丝高光、衣料与金属分区仍需要相应的材质数据。

## 验证

```powershell
python Scripts/test_archive.py
python -m py_compile Scripts/setup_viewer.py Scripts/test_archive.py Scripts/compare_renders.py Scripts/bake_face_coordinates.py Scripts/generate_face_map.py
```

基础 CI 执行上述脚本，不包含 UE 构建或 GPU 画面验证。插件中包含 UE 自动化测试 `VRM4U.PMX.MaterialColorAndOpacity`。本地画面检查可使用以下参数自动加载和截图：

```text
-MmdArchive="完整 ZIP 路径" -MmdModel="包内 PMX 相对路径" -MmdCapture="截图完整路径.png" -MmdTestExit
```

可追加 `-MmdLightYaw=65` 改变光向、`-MmdViewYaw=135` 改变拍摄方向；两者作用于整个场景，不使用模型预设。PowerShell 中使用带引号的 `'-MmdFrameScale=0.22' '-MmdTargetHeight=1.72'` 生成近景，避免小数参数被拆开；默认值均为 1，分别相对聚焦距离和模型中心高度。

首次着色器编译结束前的画面不适合作为效果判断。更多检查与提交规范见 [CONTRIBUTING.md](CONTRIBUTING.md)。

增加 `-MmdBaseColor` 可临时关闭卡通明暗与描边，用基础贴图检查导入；这仍经过 UE 色调映射。已记录的本地验收及限制见 [VALIDATION.md](VALIDATION.md)。

## 对比图

`Scripts/compare_renders.py` 只裁切和等比排版原始截图，不重绘、不改色。它是离线验证工具，需要已有的 Matplotlib 和 Pillow；不属于查看器运行依赖。输入 JSON 的路径相对清单文件，`crop` 为原图像素坐标，可省略。不同姿态、镜头和环境的对比不能作为像素一致性评分。

```json
{"title":"Reference comparison","columns":["Reference","UE"],
 "note":"Different poses and cameras; no retouching.",
 "rows":[{"name":"Model A","images":[{"path":"reference.png"},{"path":"render.png"}]}]}
```

```powershell
python Scripts/compare_renders.py local-manifest.json Saved/Comparisons/comparison.png --font C:/Windows/Fonts/msyh.ttc
```

截图与清单应存于本地 `Saved` 目录；不把未授权素材推送到仓库。

## 许可与第三方

本项目原创代码与原创材质采用 [MIT](LICENSE)。原有 Epic 模板代码保留其版权声明并受相应 Unreal Engine 许可约束；本仓库不重新许可第三方代码。VRM4U、Assimp 等保持各自许可证，详情见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 submodule 内的声明。

模型、贴图、游戏截图及立绘不随仓库或构建分发，请自行准备有权使用的素材。

渲染研究参考：

- [崩铁角色渲染学习笔记](https://zhuanlan.zhihu.com/p/711037262)
- [崩坏3卡通渲染实现方式拆解](https://zhuanlan.zhihu.com/p/120908528)
- [原神三渲二学习笔记](https://zhuanlan.zhihu.com/p/699682089)
