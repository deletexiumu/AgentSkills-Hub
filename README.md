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

## 当前包含的 Skills

Public（可分发）：
- `example-skill`：示例 skill，用于验证本仓库的 skill 工具链与约束（`skills/public/example-skill/SKILL.md`）
- `smart-data-query`：智能问数/数仓问答（基于需求 + 数仓目录 DDL+ETL 产出可执行 SQL；默认 Hive/SparkSQL，GaussDB 按需）（`skills/public/smart-data-query/SKILL.md`）

Private（内部使用）：
- `skills/private/`：当前无内置 skill（如新增请遵循同样的 `SKILL.md` 规范）
