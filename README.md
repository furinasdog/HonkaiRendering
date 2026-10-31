# HonkaiRendering / 崩坏渲染

基于 UE 5.8 的静态 MMD 角色查看器，研究米哈游角色渲染风格。MMD 读取由 VRM4U 完成；项目开发集中于卡通明暗、色彩、脸部受光、描边和角色展示。

An open-source UE 5.8 MMD character viewer and Honkai-inspired toon-rendering study. This is an independent project and is not affiliated with miHoYo/HoYoverse or Epic Games.

## 使用

默认画面仅显示角色与背景。将包含 PMX 和贴图的 ZIP 拖入窗口，在浮动窗口中选择 PMX。按 Esc 打开或关闭浮动菜单；“模型”子菜单提供 ZIP 导入，“视角”子菜单提供聚焦、投影切换和操作说明。文件导入失败会给出可关闭的提示，已加载模型会保留。

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

当前使用带色阴影、窄明暗交界、脸部平整受光、低强度边缘光和背面外扩描边，保留基础贴图里已经画入的高光与阴影。按材质名识别脸部、头发和皮肤。fork 中的 PMX 适配禁止 LOD0 自动减面，保留原始 Diffuse、Opacity、双面标记和材质描边属性，使隐藏表情、服装覆盖层和半透明材质维持其原始状态。Assimp 源码另以嵌套 submodule 关联，按需初始化，重建步骤见插件的 `HONKAI_RENDERING.md`。

通用 MMD 模型没有统一的 LightMap/FaceMap 标准。没有配套 SDF 时，脸部使用近似受光；它还不等同于游戏内的完整角色渲染。动画、表情编辑、物理模拟和完整的原游戏多通道材质还原不在首版范围内。

## 验证

```powershell
python Scripts/test_archive.py
python -m py_compile Scripts/setup_viewer.py Scripts/test_archive.py
```

基础 CI 执行上述脚本，不包含 UE 构建或 GPU 画面验证。插件中包含 UE 自动化测试 `VRM4U.PMX.MaterialColorAndOpacity`。本地画面检查可使用以下参数自动加载和截图：

```text
-MmdArchive="完整 ZIP 路径" -MmdModel="包内 PMX 相对路径" -MmdCapture="截图完整路径.png" -MmdTestExit
```

首次着色器编译结束前的画面不适合作为效果判断。更多检查与提交规范见 [CONTRIBUTING.md](CONTRIBUTING.md)。

增加 `-MmdBaseColor` 可临时关闭卡通明暗与描边，用基础贴图检查导入；这仍经过 UE 色调映射。已记录的本地验收及限制见 [VALIDATION.md](VALIDATION.md)。

## 许可与第三方

本项目原创代码与原创材质采用 [MIT](LICENSE)。原有 Epic 模板代码保留其版权声明并受相应 Unreal Engine 许可约束；本仓库不重新许可第三方代码。VRM4U、Assimp 等保持各自许可证，详情见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 submodule 内的声明。

模型、贴图、游戏截图及立绘不随仓库或构建分发，请自行准备有权使用的素材。

渲染研究参考：

- [崩铁角色渲染学习笔记](https://zhuanlan.zhihu.com/p/711037262)
- [崩坏3卡通渲染实现方式拆解](https://zhuanlan.zhihu.com/p/120908528)
- [原神三渲二学习笔记](https://zhuanlan.zhihu.com/p/699682089)
