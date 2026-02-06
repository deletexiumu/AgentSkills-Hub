# Smart Data Query

数仓问数插件 — 根据业务需求 + 数仓目录生成可执行 SQL。

## 架构

采用 **Plugin（Agent + Skill）** 架构，职责分离：

| 组件 | 职责 | 入口文件 |
|------|------|----------|
| **data-query Agent** | 自主执行工作流：搜索 → 选表 → 生成 SQL → 自检 → 交付 | `agents/data-query.md` |
| **sql-standards Skill** | SQL 知识规范：输出标准、方言兼容、验收清单 | `skills/sql-standards/SKILL.md` |

Agent 负责"做事"，Skill 负责"知识"。Agent 在生成 SQL 时引用 Skill 的规范文档。

## 目录结构

```
smart-data-query/
├── .claude-plugin/
│   └── plugin.json                     # 插件清单
├── agents/
│   └── data-query.md                   # 查询 Agent（工作流）
├── skills/
│   └── sql-standards/
│       ├── SKILL.md                    # SQL 规范（精简整合）
│       └── references/                 # 详细文档（按需加载）
│           ├── SQL-输出规范.md
│           ├── 方言与兼容性.md
│           ├── 静态验收清单.md
│           ├── 日志与迭代机制.md
│           └── 问数需求问卷模板.md
├── scripts/                            # 工具脚本
│   ├── build_catalog.py                # 构建目录索引
│   ├── search_catalog.py               # 搜索候选表
│   ├── check_query.py                  # SQL 静态检查
│   ├── log_qa.py                       # 问答日志记录
│   └── optimize_questionnaire.py       # 问卷自动优化
├── catalog.search.json                 # 轻量检索索引（生成产物）
├── catalog/full/                       # 按表详情（生成产物）
└── assets/logs/qa.jsonl                # 问答日志（运行产物）
```

## 使用方式

### 自然语言触发

在 Claude Code 对话中直接描述数据需求，Agent 会自动触发：

```
帮我查一下最近7天各产业链的企业数量
统计各城市高校数量，按985/211分类
写个SQL查各渠道新增用户数
```

触发关键词：`问数`、`写SQL`、`查数仓`、`取数`、`导数`、`生成查询`、`generate SQL`、`data query`

### Agent 工作流

1. **搜索候选表** — `search_catalog.py` 检索匹配表（支持中英文混合）
2. **读取表详情** — 打开 `catalog/full/<LAYER>/<table>.json` 确认粒度和口径
3. **生成 SQL** — CTE 结构（base → agg → dim → final），中文别名
4. **静态自检** — `check_query.py` 检查字段、join key、分区下推
5. **交付 + 日志** — 输出可执行 SQL，记录到 `qa.jsonl`

## 前提条件

### 构建目录索引（首次使用）

```bash
python3 scripts/build_catalog.py --root <数仓DDL目录> --out-dir .
```

生成 `catalog.search.json`（轻量索引，~4MB）和 `catalog/full/` 目录（按表 JSON 详情）。

数仓目录变更后需重新构建。

### Python 环境

Python 3.10+，无额外依赖。

## 默认策略

Agent 遵循"先出结果、后调整"原则，减少不必要的询问：

| 项目 | 默认行为 |
|------|----------|
| 时间范围 | 最新分区 `MAX(dt)` |
| 分层优先 | ADS → DWS → DWT |
| 输出字段 | 自行决定 |
| 方言 | Hive/SparkSQL |
| 中文别名 | 最终 SELECT 使用 |

## 护栏

- 禁止破坏性语句（`DROP`/`TRUNCATE`/`DELETE`/`INSERT OVERWRITE`）
- Hive 低版本兼容（禁 TRANSFORM、禁子查询表达式、禁 ORDER BY 序号）
- 口径不确定时给多分支 SQL 或注释说明假设

## License

MIT
