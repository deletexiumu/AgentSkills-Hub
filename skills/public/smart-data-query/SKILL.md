---
name: smart-data-query
description: 智能问数/数仓问答技能：输入一段业务需求 + 一个数仓目录（含 ADS/DWS/DWT 表目录、表设计文档、每表 SQL(DDL+ETL)），逐步检索并加载相关表，最终产出可直接在数据库执行的查询 SQL（人工执行导出）。适用于“给我一条能按需求导出的 SQL”“根据需求在数仓里找表/字段/口径并写查询”“已给 ADS/DWS/DWT 表定义与 ETL SQL，要求拼出最终取数 SQL”等场景。
---

# 目标

根据“需求文本 + 数仓目录”生成一条（或一组 CTE 组成的）最终查询 SQL，满足可读、可执行、可验收，且能说明关键口径/过滤条件/粒度假设。

# 输入（先问清）

建议优先使用标准化问卷收集需求，避免遗漏：[`references/问数需求问卷模板.md`](references/问数需求问卷模板.md)。

## 业务侧（给业务方填写）

1. 需求内容：指标/维度/口径/时间范围/过滤条件/输出字段清单/排序与 TopN 规则（尽量用业务语言）。
2. 业务对象定义：例如“订单/用户/门店/商家”的定义与边界（含口径差异）。
3. 验收方式与样例：对账来源、旧报表/看板链接、期望结果样例（3-5 行）。

## 数仓侧补充（由数据同学补齐）

1. 数仓目录路径：包含 `ADS/`、`DWS/`、`DWT/`（大小写不敏感）及其下的表目录/设计文档/SQL 文件。
2. SQL 方言与执行引擎：默认 Hive/SparkSQL；仅当用户明确要求时再输出 GaussDB 版本（影响日期函数、分区写法、引用符号）。
   - 若 Hive 版本偏低/不确定：避免在 `SELECT` 列表或 `JOIN ... ON` 中使用子查询表达式（低版本 Hive 常报 `Unsupported SubQuery Expression`），优先改写为 `JOIN`/派生表/CTE。
   - Hive（尤其低版本）兼容性规则：
     - `ORDER BY` 必须只引用“当前 `SELECT` 的输出列名”（如果输出用了中文别名，就必须用中文别名；不要写底层字段名）。
     - 不要使用 `ORDER BY 1/2/3` 这类序号排序（你们环境明确不允许，且兼容性差）。
3. 表名命名/库名规则：是否需要加库前缀（如 `dw.ads_xxx`），以及环境（prod/test）。
4. 时间字段与分区策略：常用分区字段名（如 `dt`/`ds`/`biz_date`），是字符串还是日期类型。
5. 交付形式：只要最终 SQL，还是需要同时输出口径说明/字段释义/可选参数模板。
6. schema 关系文档（如果有）：描述表与表之间关系/主外键/维度映射的文档路径或命名规则。
7. 输出字段命名偏好：业务验收优先用中文字段名（默认是）；若担心引擎兼容，可用“英文 alias + 中文注释”的双轨输出。

# 流程（逐步加载，尽量少读文件）

0. 先读 schema 关系（如果提供）
   - 目标：明确“事实表候选 + 关键维度表/映射表 + join key + 可能的多版本维表去重规则”。
   - schema 文档通常比单表文档更能快速判断 join 路径与多对多风险。
1. 建立“轻量目录索引”（避免一次性把所有文档塞进上下文）
   - 运行 `scripts/build_catalog.py` 生成 catalog：表名、层级（ADS/DWS/DWT）、相关文件路径、DDL 字段（尽力解析）。
   - catalog 会尽力抽取：分区列（`partitioned by`）与 ETL 信号（insert 目标表、group by 键、row_number 去重线索、来源表 from/join）。
   - 仅当需要时再打开某个表的设计文档/SQL 文件（按候选优先级逐个加载）。
2. 优先从 ADS 找“可直接出数”的结果表
   - ADS 常是面向报表/应用的结果层，若已存在目标指标/维度组合，优先直接查询 ADS。
   - 找不到或口径不匹配，再回到 DWS（公共汇总/服务层）或 DWT（主题宽表/明细宽表）。
3. 候选表检索与缩小范围
   - 用 `scripts/search_catalog.py` 基于需求关键词检索表名/字段/路径。
   - 对 Top 候选表：先看 catalog 输出的 `PART`/`SIGNAL` 摘要，优先挑“粒度更接近 + 分区明确 + 已有指标字段/聚合逻辑清晰”的表。
   - 再读取该表的 SQL（DDL+ETL）与设计文档，确认粒度、主键/维度键、分区字段、指标口径与去重规则。
4. 组装查询 SQL（先定粒度再写 SQL）
   - 明确事实粒度（例如：按天-用户、按天-门店、按订单、按事件等）。
   - 明确维度表/映射表是否需要（地区、渠道、类目、组织等）。
   - 明确去重规则（订单行/订单/用户、拉链表取最新等）。
   - 写 CTE：`base`（过滤+选列）→ `agg`（聚合口径）→ `dim`（维度补充）→ `final`（输出）。
5. 自检（无数据库也要做的静态检查）
   - 所有引用字段在 DDL 中存在（或在 ETL 中可推导出别名）。
   - join key 类型一致、不会引入多对多放大（必要时先对维表去重/取最新）。
   - `group by` 与选择列一致；聚合指标不重复计算。
   - 时间过滤命中分区字段（能下推则下推），避免全表扫描。
   - 可选：运行 `scripts/check_query.py --catalog <catalog.json> --dialect hive --sql <your.sql>` 输出启发式风险提示。
   - 若 Hive 版本偏低：运行 `scripts/check_query.py --dialect hive-legacy --sql <your.sql>` 额外检查“SELECT/ON 中的子查询表达式”等兼容性雷点。
6. 输出最终 SQL
   - 输出一段可直接执行的 SQL（含必要注释与参数占位），不要输出伪代码。
   - 若存在不确定口径，输出“可选分支 SQL”或在注释中明确假设，并给出需要用户确认的问题。
   - 若用户明确要求 GaussDB：在给出 Hive/SparkSQL 版本的同时，额外提供一份 GaussDB 版本，并明确“需用户在目标引擎做一次试跑确认”。
   - 若需求方是业务用户：最终输出列尽量用中文别名（Hive/SparkSQL 推荐用反引号包裹中文列名）。

# 护栏（安全与风险控制）

- 未经用户明确确认，不生成包含破坏性语句的脚本（如 `DROP`/`TRUNCATE`/`DELETE`/`INSERT OVERWRITE`）。
- 默认只做“查询导出 SQL”，不尝试实际连库执行或推断结果正确性（除非用户提供样例数据/结果对账规则）。
- 发现需求与现有表口径不一致时，优先回问澄清，或同时给出多种口径的可执行 SQL 分支。

# 持续优化迭代（日志 + 问卷模板）

目标：把每次问数问答沉淀为可复盘/可训练的样本（good/bad case），并在样本累计到一定数量时自动更新“问数需求问卷模板”。

重要说明：
- 本 skill 的日志需要由“执行本 skill 的 agent”自动写入（本地运行 `scripts/log_qa.py`），而不是让用户手动执行命令。
- 日志默认写在 `assets/logs/` 下，该目录已被仓库 `.gitignore` 忽略，所以 `git status` 看不到它，但文件实际存在。

## 自动记录（每次执行都写一条）

规则：每次使用本 skill 完成一次交付（输出最终 SQL/说明）后，agent **必须**自动写入一条日志（默认先记为 `unknown`，待用户反馈后再更新为 `good`/`bad`）。

内部动作（agent 自己执行，不要求用户执行）：

1. 生成 `session-id`（UUID）并贯穿本轮问答。
2. 把“用户需求文本”和“最终交付内容”保存为临时文件（避免命令行过长）：`need.txt` / `final.sql`。
3. 追加写入日志（默认 `unknown`）：
   - `python3 scripts/log_qa.py --label unknown --session-id <uuid> --question-file need.txt --answer-file final.sql`

## 收集反馈并更新标签（good/bad）

在交付后向用户只问一个问题：  
“本次结果是否可用？请回复 `good` 或 `bad`，并用 1-3 句话说明原因（如是 bad，尽量说明哪里不对/缺了什么）。”

收到用户反馈后，agent **必须**更新同一个 `session-id` 的日志记录（不会新增一条，而是更新原记录）：

- good：`python3 scripts/log_qa.py --update --label good --session-id <uuid> --feedback "<原因>"`
- bad：`python3 scripts/log_qa.py --update --label bad --session-id <uuid> --feedback "<原因>" --issues <issue1,issue2,...>`

建议 bad case 用 `--issues` 记录结构化问题，便于后续模板与规则自动迭代。常用 issue 示例：

- `missing_metric` / `missing_dimension` / `missing_grain` / `missing_time_range` / `missing_filters`
- `missing_output_fields` / `missing_topn_sort` / `missing_dialect_engine` / `missing_dw_path` / `missing_partition_field`
- `mismatch_definition` / `performance_risk`

## 自动更新问卷模板（阈值触发）

当日志中“已标注（good/bad）的样本”累计到 20 条（每新增 20 条再触发一次），会自动运行一轮模板更新，写入：[`references/问数需求问卷模板.md`](references/问数需求问卷模板.md)，并同步更新本文件的“迭代摘要”。

也可手动触发：

- `python3 scripts/optimize_questionnaire.py`

## 每次问答结束的“强制收尾动作”（让日志真的被写入）

在输出最终 SQL/口径说明后：
1. 自动记录：先写入 `unknown` 日志（保存 session-id）。
2. 收集反馈：让用户回复 `good/bad + 原因`；收到后用 `--update` 更新同一条日志为 `good`/`bad`。
3. 达到阈值：由脚本自动触发模板与本 skill 的迭代摘要更新。

<!-- ITERATION:START -->

## 迭代摘要（自动生成）

说明：本段由日志自动汇总，用于沉淀“容易遗漏的澄清点/护栏”。业务问卷尽量保持非技术化；技术性补问沉淀在本 skill 规则中。

- 更新时间：2026-01-22T04:10:43+00:00
- 累计样本：1（good=0, bad=1）

### bad case 高频问题（Top）

- missing_time_range: 1

### 规则沉淀建议（偏技术，写进本 skill）

- 暂无（建议在 bad case 里补充 `--issues`，尤其是技术性遗漏项）。

<!-- ITERATION:END -->
# 资源（按需使用）

- 生成/更新索引：`scripts/build_catalog.py`
- 关键词检索候选表：`scripts/search_catalog.py`
- 输出 SQL 静态检查：`scripts/check_query.py`
- 记录问答样本（good/bad + 反馈 + issues）：`scripts/log_qa.py`
- 从日志更新“问数需求问卷模板”：`scripts/optimize_questionnaire.py`
- 分层选表与口径核对要点：`references/分层与选表指南.md`
- 最终 SQL 输出规范：`references/SQL-输出规范.md`
- 静态验收清单：`references/静态验收清单.md`
- 问数需求问卷模板：`references/问数需求问卷模板.md`
