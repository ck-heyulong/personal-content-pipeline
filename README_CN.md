# Personal Content V1

Personal Content 是一个基于 WSL 的轻量自动化工作流，可将本地原始文本与图片转换为忠于事实的小红书图文帖子。系统通过 DeepSeek Vision 生成结构化事实基准与文案草稿，经由 WSL 终端人工单键审核确认后，调用 Windows 宿主端的独立发布组件驱动浏览器完成最终发布。自动化测试完全离线，不产生实际外部调用。

## 核心特性

- **单命令日常发布**：日常仅需执行 `./scripts/post_xhs.sh`。
- **多模态内容生成**：采用 DeepSeek `deepseek-v4-flash-vision-exp` 模型。
- **事实基准约束**：基于 Canonical Record（事实源）严格限制模型生成未支持的虚构描述。
- **多文案风格支持**：内置 `personal`（个人日常）、`knowledge`（干货知识）与 `concise`（精炼）风格。
- **终端直观预览**：在 WSL 终端直接渲染展示标题、正文、标签及排序后的图片路径。
- **单键免回车审核**：支持 `y`、`e`、`r`、`q` 单键快速交互。
- **不可变包与哈希绑定**：使用 SHA-256 签名绑定审核内容，任何变动都会使批准失效并生成不可变发布包。
- **安全演练机制**：在正式发布前自动执行 Dry-run 空跑演练。
- **轻量无额外依赖**：基于 Python 标准库实现，搭配确定性离线测试集。

## 架构流程

```text
原始文本 + 本地图片
    → DeepSeek Vision 多模态处理
    → 生成 Canonical 事实基准
    → 生成小红书草稿
    → 终端人工审核
    → SHA-256 签名绑定
    → 生成不可变发布包
    → WSL 与 PowerShell 桥接
    → 外部 Windows SAU 后端
    → Microsoft Edge 浏览器
    → 小红书发布
```

事实 Canonical JSON 是唯一事实来源。审核确认涵盖标题、正文、标签序列、图片路径及图像哈希，后续任何变动都会使批准失效。

## 环境要求

- **WSL 环境**：Python 3.12+、Bash、Git、`wslpath` 及 `explorer.exe` 互操作支持。
- **DeepSeek API Key**：用于在线多模态生成。
- **Windows 端**：Windows PowerShell 及 Microsoft Edge 浏览器。
- **外部 SAU 工具**：独立安装的 [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload) (SAU)，并配置别名为 `main` 的小红书账号。
- *无需额外安装数据库、Web 服务、前端框架或 python-dotenv 包。*

## 快速开始

在仓库根目录下运行：

```bash
./scripts/post_xhs.sh
```

首次运行需在安全提示下输入 DeepSeek API Key。随后流程如下：

1. 粘贴原始素材文本并按 `Ctrl-D` 提交。
2. 脚本自动在 Windows 资源管理器中打开 `jobs/<job>/images/` 目录，将图片放入该目录后返回 WSL 终端按回车。
3. 在终端检查生成的标题、正文、标签及图片顺序。
4. 按 `y` 确认，系统将自动执行 Dry-run 演练并进入真实发布阶段。

日常标准化流程：输入文本 + 放入图片 + 终端核对 + 按 `y` 确认发布。

## 日常使用与操作

默认风格为 `personal`：

```bash
./scripts/post_xhs.sh
```

通过环境变量切换文案风格：

```bash
CONTENT_STYLE=knowledge ./scripts/post_xhs.sh
CONTENT_STYLE=concise ./scripts/post_xhs.sh
```

### 审核按键交互（无需按回车）

- `y` —— 审核通过，执行 Dry-run 演练后唤起真实发布。
- `e` —— 手动编辑生成的 `jobs/<job>/xiaohongshu.json`。
- `r` —— 修改原始文本/图片并重新生成。
- `q` —— 暂停任务，不进行审批和发布。

恢复未完成或已暂停的任务：

```bash
./scripts/post_xhs.sh '<job-name>'
```

底层 CLI 工具仍可用于调试与离线工作流，运行 `./content --help` 查看详情。

## 配置说明

### DeepSeek 配置

首次输入的 API Key 会保存在仓库外部的安全配置文件中：

```text
~/.config/personal-content/deepseek_api_key
```

目录权限为 `700`，文件权限为 `600`。后续运行将自动读取该文件。也可通过环境变量 `CONTENT_PROVIDER_API_KEY` 注入密钥。

生产环境默认配置：

```text
CONTENT_PROVIDER=live
CONTENT_PROVIDER_URL=https://api.deepseek.com/chat/completions
CONTENT_PROVIDER_MODEL=deepseek-v4-flash-vision-exp
CONTENT_PROVIDER_TIMEOUT=60
```

`.env.example` 仅作为配置参考文档，程序不会主动加载 `.env` 文件。切勿将真实密钥写入 Git、日志或脚本中。

系统支持标准代理变量（`HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY`）及 `CONTENT_PROXY_URL`。

离线测试模式配置：

```bash
export CONTENT_PROVIDER=fake
unset CONTENT_PROVIDER_API_KEY
```

离线模式下不会进行实际图像理解并在事实数据中明确标注。

### Windows SAU 与 Edge 配置

在 Windows 端独立安装 SAU（推荐路径 `%USERPROFILE%\tools\social-auto-upload`）。若安装在自定义路径，需配置环境变量：

```bash
export CONTENT_SAU_HOME='D:\tools\social-auto-upload'
export CONTENT_SAU_ACCOUNT=main
```

桥接脚本将通过 `sau xiaohongshu upload-note --account main ...` 调用外部程序。

- 请确保在 Edge 中完成小红书 `main` 账号的登录认证。
- 登录态 Cookie 与凭证均保留在外部 SAU 安装目录中。
- 扫码登录、人机验证码、短信验证及平台风控均需人工处理，本项目不提供绕过逻辑。

## 安全与隐私

- API Key、浏览器 Cookie、Session 绝不提交到 Git 仓库。
- 本地 `jobs/` 及 `publish-packages/` 目录默认已被 `.gitignore` 忽略。
- 调试输出严禁打印密钥、Token 或 Authorization 请求头。
- 真实发布必须经过人工显式确认，用户须自行遵守小红书平台规范及当地法律法规。
- 更多安全指引详见 [SECURITY.md](SECURITY.md)。

## 项目结构

```text
content                         底层 CLI 工具
scripts/post_xhs.sh             V1 日常运行入口脚本
scripts/publish_xiaohongshu.ps1 Windows 暂存与外部 SAU 调用桥接脚本
scripts/verify_v1.sh            离线验证测试脚本
personal_content/               Python 标准库核心实现
tests/                          确定性离线测试套件
jobs/                           本地素材与生成内容（已被 Git 忽略）
publish-packages/               不可变发布打包产物（已被 Git 忽略）
```

## 自动化测试与验证

运行完整的离线验证套件（不产生网络调用与发布操作）：

```bash
./scripts/verify_v1.sh
```

在支持 PowerShell 互操作的环境下可加入语法解析校验：

```bash
CONTENT_VERIFY_POWERSHELL=1 ./scripts/verify_v1.sh
```

## 限制说明

- V1 版本仅支持小红书图文帖子，不支持视频发布。
- 在线生成依赖外部网络及有效的 API Key。
- 自动化发布依赖 Windows、PowerShell、Edge 及外部 SAU 的适配情况。
- AI 生成内容仍需人工进行事实保真度核对。

## 开源协议与致谢

- 本项目原创代码遵循 [MIT License](LICENSE) 协议开源。
- 感谢 [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload) 开源项目。第三方软件遵循其各自的开源许可协议，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
