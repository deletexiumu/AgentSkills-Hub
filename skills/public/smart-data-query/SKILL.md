---
name: smart-data-query
description: Smart data warehouse Q&A skill - input business requirements + DWH catalog, output executable SQL queries. Features catalog-aware search, multi-dialect support (Hive/SparkSQL/GaussDB), auto-iteration from feedback.
---

# 目标

根据"需求文本 + 数仓目录"生成可执行的最终 SQL，满足可读、可执行、可验收。

# 默认策略（减少询问，先出结果）

**核心原则：不要过多询问，先出 SQL，用户看完有问题再反馈调整。**

| 项目 | 默认行为 |
|------|----------|
| 数仓目录 | 当前目录（搜不到再问） |
| 输出字段 | 自行决定（不要问用户） |
| 时间范围 | 最新分区 `MAX(dt)`（不要问） |
| 分层选表 | ADS → DWS → DWT（不要问） |
| 表名格式 | 带库名前缀，prod 环境 |

# 流程

1. **建立目录索引**：运行 `scripts/build_catalog.py` 生成 catalog
2. **选表**：按 ADS → DWS → DWT 优先级，用 `scripts/search_catalog.py` 检索
3. **读表文档**：确认粒度、分区字段、指标口径
4. **组装 SQL**：
   - 数组字段默认用 `LATERAL VIEW EXPLODE` 全部展开
   - 多条件筛选明确交集/并集逻辑
   - 分区过滤用 `SELECT MAX(dt)` 动态获取
   - CTE 结构：`base` → `agg` → `dim` → `final`
5. **自检**：字段存在、join key 类型一致、group by 与 select 一致、分区下推
6. **输出**：带库名的可执行 SQL + 中文别名

# 护栏

- 禁止生成破坏性语句（`DROP`/`TRUNCATE`/`DELETE`/`INSERT OVERWRITE`）
- 禁止 TRANSFORM 函数、SELECT/ON 中的子查询表达式（Hive 兼容）
- 口径不确定时给出多分支 SQL 或在注释中说明假设

# 收尾

每次交付后：
1. 写入日志（`scripts/log_qa.py`）
2. 问用户："本次结果是否可用？回复 `good` 或 `bad` + 原因"
3. 更新日志标签

详见 [`references/日志与迭代机制.md`](references/日志与迭代机制.md)

# 资源

| 用途 | 路径 |
|------|------|
| 生成索引 | `scripts/build_catalog.py` |
| 检索候选表 | `scripts/search_catalog.py` |
| SQL 静态检查 | `scripts/check_query.py` |
| 记录日志 | `scripts/log_qa.py` |
| 需求问卷 | [`references/问数需求问卷模板.md`](references/问数需求问卷模板.md) |
| 方言兼容 | [`references/方言与兼容性.md`](references/方言与兼容性.md) |
| 调用示例 | [`references/调用示例.md`](references/调用示例.md) |
