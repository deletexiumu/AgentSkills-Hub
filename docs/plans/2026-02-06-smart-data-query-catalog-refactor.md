# Smart Data Query — Catalog 重构设计

> 日期：2026-02-06
> 状态：待审批

## 背景与问题

当前 smart-data-query skill 的 catalog 机制存在三个严重缺陷：

1. **层级检测完全失效** — 2882 张表全部标记为 UNKNOWN。原因：`_detect_layer()` 只匹配路径中精确等于 "ADS" 的部分，但实际目录命名为 "05-应用专题库-ADS"
2. **COMMENT 未提取** — SQL 文件中有丰富的 `COMMENT '中文说明'`，但 `build_catalog.py` 完全没有抽取
3. **catalog.json 太大** — 39 万行、单文件，无法有效加载到上下文

这直接导致选表不准（层级优先级失效 + 无语义搜索能力）和 SQL 生成质量差。

## 设计目标

- 修复层级检测，正确识别 ADS/DWS/DWT/DWD/ODS
- 提取字段级 COMMENT 和表级 COMMENT/描述
- 拆分为轻量检索索引 + 按表详情文件，支持按需加载
- 增强搜索质量：COMMENT 纳入权重、stopwords 过滤

## 方案设计

### 1. Catalog 输出拆分为两层

#### catalog.search.json（轻量检索索引）

用于 `search_catalog.py` 快速检索候选表，只包含检索必需字段：

```json
{
  "schema_version": 2,
  "root": "relative/path/to/warehouse",
  "generated_at": "2026-02-06T00:00:00Z",
  "tables": [
    {
      "id": "ADS|ads_industry_map_mainland_university_wide_mf",
      "layer": "ADS",
      "name": "ads_industry_map_mainland_university_wide_mf",
      "description": "产业地图-国内高校信息",
      "table_comment": "国内高校与产业链关联宽表",
      "columns": [
        ["university_id", "主键-高校ID"],
        ["university_name", "高校名称"],
        ["chain_name", "产业链名称"]
      ],
      "partition_columns": ["dt"],
      "ddl_sql_file": "05-应用专题库-ADS/产业地图/生产/xxx.sql",
      "detail_ref": "catalog/full/ADS/ads_industry_map_mainland_university_wide_mf.json"
    }
  ]
}
```

设计要点：
- `columns` 用二维数组 `[name, comment]`，比对象列表省体积
- `ddl_sql_file` 只放 1 个代表路径（相对路径）
- `detail_ref` 指向单表详情文件
- 输出 compact JSON（无 indent），加 `--pretty` 参数可选美化
- 不包含 UNKNOWN 层级的表（过滤噪声）

#### catalog/full/{layer}/{table_id}.json（按表详情）

选表确认后按需加载单表完整信息：

```json
{
  "id": "ADS|ads_industry_map_mainland_university_wide_mf",
  "layer": "ADS",
  "name": "ads_industry_map_mainland_university_wide_mf",
  "description": "产业地图-国内高校信息",
  "table_comment": "国内高校与产业链关联宽表",
  "columns": [
    {"name": "university_id", "type": "STRING", "comment": "主键-高校ID"},
    {"name": "university_name", "type": "STRING", "comment": "高校名称"}
  ],
  "partition_columns": [
    {"name": "dt", "type": "STRING", "comment": ""}
  ],
  "sql_files": ["05-应用专题库-ADS/产业地图/生产/xxx.sql"],
  "doc_files": [],
  "signals": {
    "insert_targets": ["ads_industry_map_prod.ads_industry_map_mainland_university_wide_mf"],
    "source_tables": ["dws_xxx", "dim_xxx"],
    "group_by": ["university_id", "chain_code"]
  }
}
```

### 2. build_catalog.py 改动

#### 2.1 层级检测修复

```python
LAYER_PATTERN = re.compile(r'(?:^|[^a-zA-Z])(ADS|DWS|DWT|DWD|ODS)(?:$|[^a-zA-Z])', re.IGNORECASE)

def _detect_layer(path: Path) -> str:
    for part in path.parts:
        m = LAYER_PATTERN.search(part)
        if m:
            return m.group(1).upper()
    return "UNKNOWN"
```

使用 `[^a-zA-Z]` 边界而非 `\b`，避免 `_` 属于 `\w` 导致 `ads_xxx` 误匹配。

#### 2.2 COMMENT 提取

字段级 COMMENT：
```python
COLUMN_COMMENT_RE = re.compile(r"comment\s+['\"]([^'\"]*)['\"]", re.IGNORECASE)

@dataclass(frozen=True)
class Column:
    name: str
    type: str
    comment: str = ""
```

在 `_parse_columns_from_create_table` 中，解析每个字段定义时额外提取 COMMENT。

表级 COMMENT：
```python
TABLE_COMMENT_RE = re.compile(
    r"comment\s*=?\s*['\"]([^'\"]*)['\"]",
    re.IGNORECASE,
)
```

在 `TBLPROPERTIES` 或 `CREATE TABLE ... COMMENT '...'` 中提取。

#### 2.3 表级描述提取

从文件名中文部分提取：

```python
def _extract_description_from_filename(file_path: Path) -> str:
    stem = file_path.stem
    # 去掉最后的英文表名部分：如 "产业地图-国内高校信息-ads_xxx" → "产业地图-国内高校信息"
    parts = re.split(r'-(?=[a-z])', stem, maxsplit=1)
    if len(parts) > 1:
        return parts[0]
    return ""
```

多源合并策略：优先用表级 COMMENT > 文件名中文部分 > 空。

#### 2.4 输出改动

- 默认输出 compact JSON（`separators=(",", ":")`)，加 `--pretty` 参数可选
- 文件路径改为相对于 root 的相对路径
- signals 中空列表/False 值不输出
- UNKNOWN 层级默认不输出到 search.json（加 `--include-unknown` 可选）
- 新增 `--out-dir` 参数指定输出目录

输出结构：
```
<out-dir>/
├── catalog.search.json        # 轻量检索索引
└── full/                      # 按表详情
    ├── ADS/
    │   ├── ads_industry_map_mainland_university_wide_mf.json
    │   └── ...
    ├── DWS/
    └── DWT/
```

### 3. search_catalog.py 改动

#### 3.1 适配新 schema

- 读取 `catalog.search.json` 而非 `catalog.json`
- 适配 `columns` 二维数组格式
- 新增 `--detail` 参数：命中后自动读取 `detail_ref` 显示完整信息

#### 3.2 搜索增强

改进 `_tokenize`：
- Unicode 归一化 (NFKC) + 小写
- 正则提取英文标识符和中文连续串
- 英文标识符拆 snake_case（`enterprise_id` → `enterprise_id` + `enterprise`）
- stopwords 过滤：SQL 关键字（select/from/where...）、中文空泛词（查询/统计/数据/信息...）
- 最小长度：英文 < 2 丢弃，中文 < 2 丢弃，纯数字 < 3 丢弃
- `LOW_INFO` 高频列名（id/dt/name/code）降权而非删除

改进 `_score_entry`：
- 新增 `comment` 搜索权重 4（仅次于表名 5）
- 新增 `description` + `table_comment` 搜索权重 4
- `LOW_INFO` token 权重减半

### 4. SKILL.md 调整

- 流程中 `build_catalog.py` 的调用命令更新（新增 `--out-dir` 参数）
- `search_catalog.py` 的 `--catalog` 参数指向 `catalog.search.json`
- 删掉 `references/分层与选表指南.md`（核心内容已体现在 SKILL.md 和 catalog 层级中）
- 删掉 `references/调用示例.md`（不必要）
- 保留：SQL-输出规范、方言与兼容性、静态验收清单、日志与迭代机制、问数需求问卷模板

## 实施步骤

1. **修改 `build_catalog.py`**：层级检测 + COMMENT 提取 + 表描述 + 两层输出
2. **修改 `search_catalog.py`**：适配新 schema + 搜索增强（tokenize / stopwords / 权重）
3. **重新生成 catalog**：运行新版 build_catalog.py
4. **验证**：检查层级分布、COMMENT 覆盖率、搜索准确度
5. **精简 references**：删除 2 个不必要的 reference 文件
6. **更新 SKILL.md**：同步命令调用方式

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 改 schema 后 check_query.py 可能受影响 | check_query.py 不依赖 catalog schema，只做 SQL 文本分析，无需改动 |
| 2882 个 full 文件可能太多 | 实际有效表（非 UNKNOWN）预计 < 1000，可接受 |
| stopwords 过滤太激进 | LOW_INFO 类降权而非删除，中文 stopwords 保守 |
| 旧 catalog.json 使用方迁移 | search_catalog.py 是唯一消费方，同步更新即可 |
