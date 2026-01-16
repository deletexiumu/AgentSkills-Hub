# ai-news-digest 架构建议（RSS-first）

目标：用尽量确定性的方式，把“多信源 AI 资讯”变成可复用的数据与简报输出。推荐 **RSS/Atom 优先**，HTML 抽取作为兜底（且不对付费墙内容做绕过）。

## 总体数据流

1. **Source Registry**：维护信源元数据（名称、主页、RSS/Atom、语言、分类、权重、限制）。
2. **Fetcher**：按信源拉取 feed（带缓存、重试、限速、ETag/Last-Modified）。
3. **Parser/Normalizer**：统一成 `ArticleItem`（见下方字段）。
4. **Deduper/Merger**：同链接去重 + 相似标题合并（跨源重复聚合为 `mentions`）。
5. **Classifier/Ranker**：主题打标 + 排序（时间优先，兼顾权重/关键词）。
6. **Summarizer (LLM)**：基于标题/摘要/可用正文生成 1-3 句摘要与“为什么重要”（可选）。
7. **Renderer**：渲染 Markdown（套用 `assets/digest-template.md`），可选导出 JSON。

## 建议的数据结构（ArticleItem）

最小字段（用于“可验收”输出）：

- `id`：稳定 id（建议 `sha256(canonical_url)` 或 `source_id + entry_id`）
- `title`
- `url`（canonical 后）
- `published_at`（ISO 8601，带时区）
- `source`：`{ id, name, url }`
- `lang`：`zh/en/unknown`
- `summary_raw`：feed 自带摘要（如有）
- `summary_llm`：生成摘要（如启用）
- `topics`：数组（research/product/opensource/funding/policy/other）
- `mentions`：数组（跨源重复时记录：来源 + 链接）

## 去重策略（按可靠度降序）

1. **canonical URL 完全相同**：直接判重。
2. **entry_id/guid 相同**（同一 feed 内）：判重。
3. **标题相似 + 时间接近**：判重并合并 mentions（需阈值，避免误杀）。

## 可靠性与合规护栏

- **缓存**：避免频繁拉取与重复摘要；缓存 key 建议为 `source_id + day` 或 `etag/last_modified`。
- **限速**：默认每域名最少间隔（例如 1-2 秒），并支持并发上限。
- **付费/登录**：标记为 `paywalled/login_required` 的信源不做正文抽取，只保留标题/摘要/元信息。
- **可追溯**：输出中每条必须带原始链接与来源；摘要必须可回溯到输入内容。

