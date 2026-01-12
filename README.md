# AgentSkills

通用的 agent skill 开发与管理仓库：提供规范、模板与脚本工具，用于快速创建、校验并打包可分发的 skill。

## 快速开始

创建一个新 skill（示例：放到 `skills/public`）：

```bash
python3 scripts/init_skill.py my-skill --path skills/public --resources scripts,references,assets
```

校验与打包：

```bash
python3 scripts/validate_skill.py skills/public/my-skill
python3 scripts/package_skill.py skills/public/my-skill dist
```

更多流程与规范见：`docs/skill-workflow.md`。

安装与加载（Claude / Codex）见：`docs/skill-installation.md`。
