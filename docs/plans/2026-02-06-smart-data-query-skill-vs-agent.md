# Smart Data Query — Skill vs Agent 架构决策备忘

> 日期：2026-02-06
> 状态：已实施方案 B（2026-02-06）

## 背景

用户认为当前 smart-data-query 作为纯 Skill 形态不合适，更倾向 **Skill + Agent 组合**。在与 Codex 讨论后，发现此决策涉及多个技术和架构层面的权衡。

## 当前形态

纯 Skill：
```
smart-data-query/
├── SKILL.md              # 混合了知识规范 + 执行工作流
├── references/           # 7 个详细文档
├── scripts/              # 5 个工具脚本
├── assets/logs/          # 日志
└── catalog.json          # 数仓索引
```

**问题**：SKILL.md 同时承载了两种角色：
- **知识**：SQL 规范、方言兼容性、验收清单、护栏规则
- **工作流**：搜索 → 选表 → 读文档 → 生成 SQL → 自检 → 日志

这导致职责不清，且工作流指令（"先运行 search_catalog.py，再读表文档..."）与知识规范（"禁止 TRANSFORM 函数"）混在一起。

## 用户期望的形态

Skill + Agent 组合：
- **Skill**：放知识/规范（SQL 输出规范、方言规则、验收清单）
- **Agent**：放自主执行工作流（接收需求 → 搜索 → 选表 → 生成 → 自检 → 交付）

## Codex 的顾虑

### 1. 运行时加载问题

> "你们的 Claude Code 插件运行时是否真的支持加载一个独立的 Agent（单独 system prompt 文件）？如果不支持，别做文件形态拆分。"

**关键点**：smart-data-query 当前是 AgentSkills 仓库中的独立 skill，不是某个 `.claude-plugin` 下的组件。如果要支持 Agent，需要：
- 要么将其封装为一个完整的 Claude Code plugin（含 `plugin.json`、`agents/`、`skills/` 目录）
- 要么确认 AgentSkills 仓库的加载机制支持 Agent 文件

### 2. 替代方案：SKILL.md 内闭环

Codex 建议：如果运行时不支持独立 Agent，可以在 **SKILL.md 内完成工作流闭环**：

```
smart-data-query/
├── SKILL.md              # 工作流（精简）+ 护栏 + 脚本调用指南
├── references/
│   ├── SQL-输出规范.md    # 知识：SQL 格式标准
│   ├── 方言与兼容性.md    # 知识：Hive/SparkSQL/GaussDB 差异
│   └── 静态验收清单.md    # 知识：自检规则
├── assets/
│   └── agent-system-prompt.md  # （可选）未来 Agent 的 system prompt 预留
└── scripts/
```

SKILL.md 保留工作流（精简版），知识规范全部下沉到 references/。这样符合现有目录约束，且不依赖 Agent 运行时支持。

### 3. 如果要做 Plugin 封装

若决定做完整 plugin，结构大致为：

```
smart-data-query-plugin/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── smart-data-query/
│       ├── SKILL.md          # 知识规范
│       └── references/
├── agents/
│   └── data-query/
│       └── AGENT.md          # 自主执行工作流
└── scripts/                  # 共享脚本
```

**代价**：
- 需要从 AgentSkills 仓库迁出，成为独立 plugin
- 需要编写 plugin.json manifest
- 维护复杂度增加（两个入口文件）

## 决策矩阵

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **A. SKILL.md 内闭环** | 简单、兼容现有架构、无运行时依赖 | 职责混合（虽可通过 references 缓解） | 想快速改善，不想动架构 |
| **B. 封装为 Plugin（Skill + Agent）** | 职责清晰分离、Agent 有独立 system prompt | 需迁移仓库、维护成本高 | 长期投入，想做成产品级工具 |
| **C. SKILL.md + assets/agent-prompt.md** | 折中方案：skill 内预留 Agent prompt，未来可迁移 | Agent prompt 不会被自动加载，需手动引用 | 先过渡，未来再决定是否升级为 Plugin |

## 待确认事项

1. **AgentSkills 仓库的加载机制**：是否只支持 skill（SKILL.md），还是也支持 agent（AGENT.md）？
2. **使用频率**：smart-data-query 是高频使用（值得做 plugin）还是偶尔使用（skill 够了）？
3. **其他 skill 是否有类似需求**：如果多个 skill 都需要 Agent，可能值得统一升级仓库架构

## 实施记录

**2026-02-06：已实施方案 B**

Catalog 重构完成后，决定升级为 Plugin（Skill + Agent 架构）：

- 新增 `.claude-plugin/plugin.json` 插件清单
- 新增 `agents/data-query.md` 承载自主查询工作流
- 新增 `skills/sql-standards/SKILL.md` 承载 SQL 知识规范
- 移动 `references/` → `skills/sql-standards/references/`
- 删除根目录旧 `SKILL.md`

职责分离：Agent 负责执行工作流（搜索 → 选表 → 生成 → 自检 → 交付），Skill 负责知识规范（SQL 输出标准、方言兼容、验收清单）。
