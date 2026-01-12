# AgentSkills 仓库工作约定

本仓库用于沉淀和分发可复用的 `agent skill`（以 `SKILL.md` 为核心的“可执行知识包”）。

## 目录结构

```
scripts/                 # 工具脚本：初始化/校验/打包 skill
skills/
  public/                # 可公开分发的 skill
  private/               # 内部使用的 skill（如含敏感引用/资产）
templates/               # 模板（用于生成/对齐规范）
docs/                    # 人类阅读的开发流程与规范
```

## Skill 目录约束（对 `skills/**` 生效）

- Skill 文件夹命名：仅允许小写字母、数字、连字符（kebab-case），长度 ≤ 64。
- Skill 根目录必须包含 `SKILL.md`（带 YAML frontmatter：仅 `name` 与 `description` 两个字段）。
- Skill 目录中仅放“让 agent 交付更稳更快”的文件：`scripts/`、`references/`、`assets/`；避免额外文档（如 `README.md`、`CHANGELOG.md`）。
- `SKILL.md` 尽量短（建议 < 500 行），把大段资料拆到 `references/`，并在 `SKILL.md` 中用相对路径直接链接（避免多层引用链）。

## 开发/发布流程（推荐）

- 初始化：`python3 scripts/init_skill.py <skill-name> --path skills/public --resources scripts,references,assets`
- 编辑：完善 `SKILL.md` 与资源文件（必要时补充可执行脚本，优先脚本化重复工作）
- 校验：`python3 scripts/validate_skill.py <path/to/skill>`
- 打包：`python3 scripts/package_skill.py <path/to/skill> dist`

## 变更要求

- 任何新增/修改 skill：必须通过 `scripts/validate_skill.py`。
- 仅做与目标相关的最小变更；避免无关重构。

