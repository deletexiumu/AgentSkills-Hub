ti# Agent Skill 开发流程与规范

本文件面向“在本仓库内开发/维护 skill”的贡献者，目标是：可复用、可校验、可分发、可维护。

## 1. Skill 的目标与边界

- Skill 是给另一个 agent 用的“工作手册 + 资源包”，核心在于：把不稳定/重复/易错的部分变成确定性的流程或脚本。
- Skill 不承担用户文档职责；避免把 README、安装指南、长篇背景塞进 skill 目录。
- Skill 的触发依赖 frontmatter 的 `description`（被加载前的唯一线索），因此必须把“何时使用/典型触发语境”写进 `description`。

## 2. 标准目录结构

每个 skill（以 `<skill-name>/` 表示）：

```
<skill-name>/
  SKILL.md
  scripts/        # 可执行脚本（可选）
  references/     # 仅在需要时加载的资料（可选）
  assets/         # 输出/模板等资源（可选）
```

约束：
- `<skill-name>` 使用 kebab-case（小写+数字+连字符），≤ 64 字符。
- `SKILL.md` 必须存在，且 frontmatter 仅包含 `name` 与 `description`。
- `SKILL.md` 中引用其他文件时，使用相对路径，且尽量“一跳可达”（避免 references 继续引用 references）。

## 3. 开发流程（从需求到发布）

### 3.1 需求澄清（最少但足够）

在动手前，确认：
- Skill 解决的具体任务/痛点是什么（可列 3–5 个典型用户请求）。
- 预期输出是什么（格式、质量标准、成功/失败判定）。
- 约束条件：是否允许联网、是否接触敏感信息、是否允许破坏性操作、是否需要审批等。

### 3.2 资源规划（可复用优先）

把每个典型请求拆解为步骤，并判断哪些应该沉淀为资源：
- 需要稳定可重复执行：优先写进 `scripts/`。
- 需要查阅但不应常驻上下文：放到 `references/`。
- 需要复用模板/素材：放到 `assets/`。

### 3.3 初始化

用脚本创建骨架并统一模板：

```bash
python3 scripts/init_skill.py <skill-name> --path skills/public --resources scripts,references,assets
```

### 3.4 编写 SKILL.md（写作规范）

- 使用祈使句/动词开头（例如“解析…/校验…/生成…”）。
- 用清晰的步骤列表表达流程（必要时增加分支条件）。
- 明确失败/回退策略（遇到缺参、权限不足、风险操作时如何处理）。
- 把“何时使用”写进 frontmatter 的 `description`，不要在正文里再写“when to use”章节。

### 3.5 校验与打包

```bash
python3 scripts/validate_skill.py <path/to/skill>
python3 scripts/package_skill.py <path/to/skill> dist
```

## 4. 评审清单（PR checklist）

- `description` 覆盖触发语境（包含典型关键词/任务类型），且不是空泛描述。
- `SKILL.md` 足够短，长资料已移入 `references/`。
- 所有相对链接可达且不越界（不允许 `..` 指向 skill 外）。
- 脚本可运行（至少跑一条代表性命令）。
- 不包含多余文档文件（如 `README.md`）进入 skill 目录。

