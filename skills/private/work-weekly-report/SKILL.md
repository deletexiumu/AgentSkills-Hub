---
name: work-weekly-report
description: Generates weekly work reports by integrating data from report JSON, Notion meetings, and WeChat messages. Supports parse mode (extract from JSON) and generate mode (create new report from multiple sources). Output in Chinese Markdown format.
---

<!-- i18n-examples:start -->
## 调用 / Invoke / 呼び出し

### 中文
- "用 work-weekly-report 解析最新周报"
- "用 work-weekly-report 生成本周周报 01.26~02.01"
- "用 work-weekly-report 生成工作周报"
- "解析周报原始内容"
- "生成这周的工作周报"

### English
- "Use work-weekly-report to parse latest report"
- "Use work-weekly-report to create this week's report"
- "Parse weekly report JSON"
- "Generate weekly work report"

### 日本語
- "work-weekly-report で週報を解析して"
- "work-weekly-report で今週の週報を生成して"
- "週報を作成して"
<!-- i18n-examples:end -->

# 目标

从多个数据源整合信息，生成标准格式的 Markdown 工作周报：
- **parse 模式**：解析周报原始 JSON，清理 HTML 标签，输出干净的 Markdown
- **generate 模式**：整合上期下周计划、Notion 会议记录、微信工作消息，生成周报草稿

# 数据源

| 数据源 | 路径 | 说明 |
|--------|------|------|
| 周报 JSON | `/Users/cookie/Documents/个人周报/周报原始内容.json` | 周报系统导出的原始数据 |
| Notion 会议 | 数据库 ID: `27056ff3-93f2-80b3-9ae9-000b19738aa0` | 会议记录数据库 |
| 微信数据库 | `/Users/cookie/Documents/wechat/wechat.duckdb` | 微信聊天记录 |

# 流程

## 模式一：parse（解析已有周报）

解析周报系统导出的 JSON 文件，生成干净的 Markdown 文件。

```bash
# 解析最新一期
python3 scripts/parse_json_report.py

# 解析最新 N 期
python3 scripts/parse_json_report.py -n 5

# 解析所有
python3 scripts/parse_json_report.py --all
```

输出位置：`/Users/cookie/Documents/个人周报/`

## 模式二：generate（生成新周报）

整合多个数据源，生成周报草稿。

### 第一步：收集上期下周计划

读取最新一期已解析的周报 Markdown，提取"下周计划"部分作为本周工作参考。

### 第二步：获取 Notion 会议记录

```bash
python3 scripts/fetch_notion_meetings.py --start 2026-01-19 --end 2026-01-25
```

提取本周所有会议的关键信息：
- 会议时间、主题
- 参会人员
- 会议要点/决议

### 第三步：查询微信工作消息

```bash
python3 scripts/query_wechat_messages.py --start 2026-01-19 --end 2026-01-25
```

根据 `assets/keywords.yaml` 中的关键词过滤工作相关消息：
- @淇奥 的消息
- 包含工作关键词的对话
- 问题/任务/需求相关讨论

### 第四步：整合生成周报

根据收集的信息，按照 `references/report_template.md` 模板生成周报草稿。

**AI 需要做的工作**：
1. 对照上期"下周计划"，总结本周实际完成情况
2. 从 Notion 会议记录提炼重要进展
3. 从微信消息中补充细节和问题跟进情况
4. 编写本周总结和下周计划

# 护栏

- **只读操作**：不修改原始数据源（JSON、Notion、DuckDB）
- **输出确认**：生成周报前先展示草稿，由用户确认后再保存
- **敏感信息**：不在周报中暴露个人隐私或敏感对话内容
- **默认输出**：周报保存到 `/Users/cookie/Documents/个人周报/` 目录

# 资源

- `scripts/parse_json_report.py`：解析周报 JSON
- `scripts/fetch_notion_meetings.py`：获取 Notion 会议记录
- `scripts/query_wechat_messages.py`：查询微信工作消息
- `scripts/generate_weekly_report.py`：主程序（协调各脚本）
- `references/report_template.md`：周报 Markdown 模板
- `assets/keywords.yaml`：工作相关关键词配置
