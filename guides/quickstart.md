# 安装并跑通 Agent Engineering Toolkit

本页对应 `2026.11.23-p2`。需要 macOS 或 Linux、Python 3.9+、Git、Node.js 24、npm，以及访问 GitHub 和 npm registry 的网络。

## 下载并验收

在终端运行以下命令。验收脚本在临时目录安装，使用独立的宿主配置和 npm 缓存，退出后清理临时目录。

```sh
mkdir toolkit-download
cd toolkit-download
base=https://raw.githubusercontent.com/HarryHe12/agent-engineering-toolkit/v2026.11.23-p2
curl -fsSLO "$base/releases/2026.11.23-p2/Codex-Agent-Toolkit.zip"
curl -fsSLO "$base/releases/2026.11.23-p2/delivery-manifest.json"
curl -fsSLO "$base/validation/public_install_smoke.py"
python3 public_install_smoke.py \
  --archive Codex-Agent-Toolkit.zip \
  --manifest delivery-manifest.json
```

成功时最后一行以 `PUBLIC_INSTALL_OK` 开头。脚本核对 ZIP 的 SHA-256，执行安装器的四个阶段，确认过时文档被拒绝，再运行库存示例、回归测试和重复扣减反证。它也会调用生成的 Codex Stop 命令，检查验证前拦截和验证后放行，并用两个 Git 提交验证 CI 入口。

## 安装到日常使用的 Agent

解压下载的 ZIP，从解压目录运行。Codex 使用以下命令。

```sh
python3 -m zipfile -e Codex-Agent-Toolkit.zip toolkit
cd toolkit
python3 install.py doctor --host codex
python3 install.py plan --host codex
python3 install.py install --host codex
python3 install.py verify --host codex
```

确认 `plan` 指向你要接入的宿主配置，再运行 `install`。其他宿主可将以上命令中的 `codex` 全部替换成 `claude`、`gemini` 或 `manual`。接入真实宿主时，在宿主中确认信任和触发，再使用安装输出的 `task_command` 登记和验证项目改动。自定义配置路径、回滚和 CI 接入见 [P1 安装与接入](../archive/2026.11.23-p2/guides/Codex-P1-安装与接入.md)。将库存示例改成你项目的规则时，参见 [P2 行为验收](../archive/2026.11.23-p2/guides/Codex-P2-行为验收.md)。
