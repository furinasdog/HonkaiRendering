# 参与开发

请先阅读 README 中的开发环境、渲染范围和已知限制。提交 issue 时说明 UE 版本、操作系统、复现步骤、预期结果与实际结果；附日志前删除个人路径、凭据等无关信息。模型和贴图只有在允许重新分发时才能公开上传。

## 本地开发

```powershell
git clone --recurse-submodules https://github.com/furinasdog/HonkaiRendering.git
cd HonkaiRendering
python Scripts/test_archive.py
```

使用 UE 5.8 生成工程文件、编译 `HonkaiRenderingEditor`，再在 `/Game/MmdViewer/L_Viewer` 运行。修改着色器后，在 UE Python 环境运行 `Scripts/setup_viewer.py` 更新材质；命令模式需要 `-AllowCommandletRendering`。

主项目负责界面、相机、ZIP 文件整理和展示材质。PMX 解码和模型构建由 VRM4U 负责。修改插件时在 fork 中提交，先推送插件提交，再在主项目更新 submodule 指针。不要将插件源码作为普通目录复制进主仓库，也不要让 submodule 跟随未固定的最新版本。

## 提交与验证

每个提交只处理一个明确问题，说明用户可见的变化与验证结果。保留第三方版权和许可证声明。不要提交引擎安装目录、构建产物、本机 MCP 配置、模型、截图或立绘。

界面改动检查默认无菜单、Esc 开关视口内菜单、淡出中重新打开、菜单期间阻止镜头操作、子菜单返回、拖入 ZIP 后选择 PMX、取消与错误提示。UE 自动化测试前缀为 `HonkaiRendering`。渲染改动检查正面、侧面、背面以及脸部、头发、衣服和透明覆盖层，并记录使用的模型及证据限制。基础 CI 不包含 UE 编译或 GPU 画面验证，PR 中应如实列出这些本地检查。
