---
name: x-tracker
description: >-
  Track and archive X (Twitter) following list, bookmarks, and personal tweets.
  This skill should be used when the user asks to "sync X following", "archive bookmarks",
  "track X bookmarks", "分析我的推文", "X 关注同步", "书签存档", "推文风格分析",
  "生成 X 摘要", "sync my tweets", "analyze my posting style", "同步到 Notion",
  "X 数据导入 Notion", "我的推特分析", "每日精选", "今日精选", "X digest",
  "daily digest", "推文改写", "内容改写", "rewrite", "改写候选",
  or wants to aggregate content from followed accounts.
  Supports periodic archiving to local JSON + Notion sync, content digest with ranking,
  rewrite candidate selection, and personal writing style profiling.
version: 0.1.0
---

# X Tracker

同步并归档 X 数据（关注列表、书签、个人推文），支持内容聚合、改写和 Notion 同步。

**路径约定**：
- `{SKILL_DIR}` — skill 目录（含 scripts/、references/）
- `{PROJECT_ROOT}` — skill 父目录（含 config.json、data/、digests/）

## 首次设置

1. 配置 OAuth 2.0：参考 `references/oauth-setup.md`
2. 初始化：`cd {SKILL_DIR} && bun scripts/auth.ts init`
3. 登录：`cd {SKILL_DIR} && bun scripts/auth.ts login`

所需 scope：`tweet.read`, `users.read`, `follows.read`, `bookmark.read`, `offline.access`

## 数据同步

**重要**：不要主动运行 `sync-following.ts`。关注列表由定时任务或用户手动同步，新增关注需用户确认后才纳入跟踪。

```bash
cd {SKILL_DIR}
# bun scripts/sync-following.ts        # ⚠️ 仅限用户明确要求时运行
bun scripts/sync-bookmarks.ts          # 书签 → data/bookmarks/
bun scripts/fetch-my-tweets.ts         # 个人推文 → data/my-tweets/
bun scripts/fetch-following-tweets.ts  # 关注者推文 → data/following-tweets/
```

日常同步（不含关注列表）：`bun scripts/sync-bookmarks.ts && bun scripts/fetch-my-tweets.ts && bun scripts/fetch-following-tweets.ts`

## 每日精选（Digest）

```bash
cd {SKILL_DIR} && bun scripts/analyze.ts digest [--date YYYY-MM-DD]
```

零 API 调用，基于本地 `following-tweets` + `bookmarks`。按 `score = like + retweet×3 + bookmark×2` 排序取 Top 20。输出 `digests/{date}/digest.json`。

**触发流程**（"每日精选"/"今日精选"）：
1. 运行 digest 命令，生成 `digests/{date}/digest.json`
2. 读取 JSON，确认 `date_distribution` 日期分布
3. 按分类生成中文精选，每条格式：
   - `作者 | 类型 | 来源标签 | 互动数据`
   - 英文原文（保留原始内容）
   - 中文翻译/摘要（不超过 2 句话概括核心）
4. 来源标签：🔖 书签 / 📌 双来源 / 无标签=关注
5. 根据 `tweet_date` 标注发布日期，非当日内容标注 `[MM-DD]`
6. 写入 `{PROJECT_ROOT}/digests/{date}/digest.md`

## 内容改写（Rewrite）

```bash
cd {SKILL_DIR} && bun scripts/analyze.ts rewrite [--date YYYY-MM-DD] [--top 10]
```

按分数取 Top N，输出 `digests/{date}/rewrite.json`（含 `is_link_only`、`expanded_url`）。

**触发流程**（"推文改写"/"内容改写"/"rewrite"）：
1. 运行 rewrite 命令
2. 读取 JSON，**确认日期**：查看 `date_distribution` 中各日期占比，若当日（`tweet_date` = 今天）不足半数则展示分布并让用户确认是否继续
3. **纯链接处理**（`is_link_only: true`）：列出这些推文的 `expanded_url`，提示用户手动转存网页内容后再改写，跳过这些条目先处理其余内容
4. 并行 sub-agent（Task, general-purpose, model=sonnet），每条一个（跳过纯链接）
5. 改写风格见下方「改写风格指南」
6. 合并写入 `digests/{date}/rewrite.md`

**改写风格指南**（sub-agent prompt 必须包含）：
- **人称**：第一人称，站在用户视角写，像发推/写公众号，不是写新闻稿
- **语气**：口语化、短句为主，可以自嘲、可以直接，不端着、不用"值得关注的是"之类的套话
- **结构**：标题（一句话抓眼球）+ 正文（200-400字），不要小标题堆叠
- **内容**：先说事实（一两句话讲清楚发生了什么），再说自己的看法/体感，可以联系自身使用经验
- **禁止**：AI 腔（"值得注意的是"、"本质上"、"标志着"反复出现）、过度总结、三段式排比、空泛的"未来可期"
- **参考调性**：`data/my-tweets/all.json` 中的原创推文风格——中英混用、网络用语自然、技术人视角

## 风格分析（Style）

```bash
cd {SKILL_DIR} && bun scripts/analyze.ts style
```

分析个人推文风格，输出 `data/my-style/style-profile.json`。

## 单条推文获取

```bash
cd {SKILL_DIR} && bun scripts/fetch-tweet.ts <tweet_id>
```

通过 X API v2 获取单条推文全文（含 note_tweet），JSON 输出到 stdout。

## Notion 同步

```bash
cd {SKILL_DIR} && bun scripts/notion-sync.ts <following|bookmarks|all>
```

增量推送到 Notion 数据库。详见 `references/notion-schema.md`。

## 配置

`{PROJECT_ROOT}/config.json`（gitignored）：

```json
{
  "client_id": "...",
  "client_secret": "...",
  "access_token": "...",
  "refresh_token": "...",
  "user_id": "...",
  "data_dir": "./data",
  "notion": { "following_db_id": "...", "bookmarks_db_id": "..." }
}
```

## 参考文档

- `references/x-api-endpoints.md` — API 端点参考
- `references/oauth-setup.md` — OAuth 2.0 配置指南
- `references/notion-schema.md` — Notion 数据库 schema
