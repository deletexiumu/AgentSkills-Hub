# smart-data-query：基于 DDL+ETL 的“选表/口径”信号增强（方案2）

目标：在不直连数据库、仅拿到“需求 + 数仓目录（稳定提供 DDL+ETL SQL）+ schema 关系文档”的前提下，降低两类主要失败：
- 选错表（该用 ADS 结果表却绕到 DWS/DWT，或相反）
- 粒度/去重判断错误（导致指标放大、重复计算）

同时提升交付 SQL 的“可执行/可验收”：
- 明确分区/时间过滤下推
- 避免多对多 join 放大
- 输出字段/别名可对账
- 默认 Hive/SparkSQL；GaussDB 仅在用户明确要求时另给版本

## 关键思路

1) 把“读 ETL SQL”从纯人工动作变成“先抽信号、再精读少量文件”：
- 从 ETL 中抽取：写入目标表、分区字段线索、group by 键线索、去重窗口函数线索、上游来源表线索。
- 用信号做候选排序与风险预警，让 agent 更快定位到“最可能可直接出数”的 ADS 或最合适的 DWS。

2) 让每个候选表都能快速生成“表卡片”用于决策：
- 层级（ADS/DWS/DWT）
- 字段（DDL columns + partition columns）
- ETL 信号（是否聚合、group by 键、是否去重、上游来源表）
- 可直接出数判断（是否已有目标指标字段，是否需要再聚合/拼维）
- 风险提示（疑似多对多 join、粒度不明、无分区过滤线索等）

3) 输出 SQL 前增加“静态验收”：
- 明确粒度（事实粒度、维度补充策略）
- 分区/时间过滤写法与方言匹配（默认 Hive/SparkSQL）
- 防止 select *、group by 不一致、重复计算、维表未去重等常见坑

## 交付物（仓库内变更）

- `skills/public/smart-data-query/scripts/build_catalog.py`
  - 新增：从 SQL 中识别 `INSERT INTO/OVERWRITE` 目标表（用于 ETL 文件归档到正确表）
  - 新增：解析 `PARTITIONED BY (...)` 分区列
  - 新增：抽取 ETL 信号（group by 键、row_number 去重、distinct、来源表 from/join）
  - catalog 输出增加字段：`partition_columns`、`signals`（不要求强解析，启发式即可）

- `skills/public/smart-data-query/scripts/search_catalog.py`
  - 检索范围扩展到 `partition_columns`/`signals`（提高命中率与排序质量）
  - 输出增加“表卡片关键信息”摘要（分区列、group by 键样例、去重信号）

- `skills/public/smart-data-query/scripts/check_query.py`（新增）
  - 对生成的 SQL 做静态检查并输出警告（不阻断）：分区过滤缺失、select *、疑似多对多 join、group by 与 select 不一致（启发式）、Hive vs GaussDB 雷点提示等

- `skills/public/smart-data-query/SKILL.md` & `references/*`
  - 把“schema 关系文档”纳入流程：先读关系，再精读 Top 表 SQL
  - 强制闸口：必须先确定粒度/去重规则，再写 SQL
  - 增加静态验收 checklist 与默认方言策略（Hive/SparkSQL 默认，GaussDB 按需）

## 非目标

- 不做完整 SQL 语法树解析
- 不做自动方言互转（仅提供按需的 GaussDB 版本与注意点）
- 不尝试实际连库执行

