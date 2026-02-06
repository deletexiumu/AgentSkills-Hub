---
name: sql-standards
description: SQL output standards and Hive dialect compatibility rules for data warehouse queries. This skill should be used when generating SQL for Hive/SparkSQL/GaussDB, or when reviewing SQL for compatibility issues.
---

# SQL 标准规范

生成数仓 SQL 时必须遵守的输出规范、方言规则和验收要求。

## 输出规范

- **可直接执行**：完整 SQL（允许 CTE），不输出伪代码
- **参数清晰**：可变参数用 `{{start_date}}` 占位符，注释说明格式
- **字段命名一致**：输出字段与需求字段一一对应
- **分区可下推**：用分区字段（`dt/ds/biz_date`）过滤，避免全表扫描
- **中文别名**：最终 SELECT 用中文别名，Hive 用 `` `中文` ``，GaussDB 用 `"中文"`

### CTE 推荐结构

1. `base`：事实表取数（必要列 + 分区过滤 + 业务过滤）
2. `agg`：按需求粒度聚合
3. `dim_*`：维度补充（先去重/取最新再 join）
4. `final`：整理输出字段、排序

## Hive 低版本兼容性

### 禁止的语法

| 禁止项 | 替代方案 |
|--------|----------|
| TRANSFORM 函数 | `LATERAL VIEW EXPLODE`、`regexp_extract`、`get_json_object` |
| SELECT/JOIN ON 中的子查询 `(select ...)` | 派生表 / CTE 先算好再 JOIN |
| `ORDER BY 1, 2, 3` 序号排序 | 用输出列名排序 |

### ORDER BY 规则

`ORDER BY` 必须只引用当前 SELECT 的输出列名。如果用了中文别名，必须用中文别名排序：

```sql
-- 正确
SELECT province_name AS `省份`, COUNT(*) AS `数量`
FROM t GROUP BY province_name
ORDER BY `省份`

-- 错误：用底层字段名
ORDER BY province_name
```

## 验收要点

- 禁用 `select *`，显式列出输出字段
- `group by` 与选择列一致，聚合指标不重复计算
- join 时写清类型与 key，维表多版本先去重再 join
- 默认 Hive/SparkSQL 方言，GaussDB 仅按需输出
- 口径不确定时给多分支 SQL 或注释说明假设

## 详细文档

| 主题 | 路径 |
|------|------|
| SQL 输出规范 | [`references/SQL-输出规范.md`](references/SQL-输出规范.md) |
| 方言兼容 | [`references/方言与兼容性.md`](references/方言与兼容性.md) |
| 静态验收清单 | [`references/静态验收清单.md`](references/静态验收清单.md) |
| 日志迭代 | [`references/日志与迭代机制.md`](references/日志与迭代机制.md) |
| 需求问卷 | [`references/问数需求问卷模板.md`](references/问数需求问卷模板.md) |
