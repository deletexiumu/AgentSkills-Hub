# ai-news-digest Implementation Plan

> **For Claude/Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Build a skill that fetches AI news from a curated source list (RSS-first, HTML fallback), deduplicates items, and outputs a daily/weekly digest in Markdown (and optional JSON) with source attribution.

**Architecture:** Source registry → fetch (cache/limit) → parse/normalize → dedupe/merge → classify/rank → (optional) LLM summarize → render template.

**Tech Stack:** Python 3.10+. Prefer minimal deps; optionally add `requests` + `feedparser` + `beautifulsoup4` + `python-dateutil` for robustness.

---

## Scope / Non-goals

- In scope: public metadata ingestion (title/url/date/summary), dedupe, digest rendering, source-level failure reporting.
- In scope: flexible time window parsing with default “same-day” behavior (today/yesterday/day before, or `YYYY-MM-DD`).
- In scope: default timezone `UTC+8` and default Chinese output (translate EN items to ZH before rendering).
- Non-goals: bypass paywalls/login, heavy browser automation by default, full-text extraction for all sources.

---

## Task 0: Time window parsing (natural language + YYYY-MM-DD)

**Files:**
- Create: `skills/public/ai-news-digest/scripts/time_window.py`
- Create: `skills/public/ai-news-digest/references/time-window.md`

**Steps (TDD):**
1. Write tests for inputs → `(since, until)` (timezone-aware):
   - `"今天"` / `"today"` → local-day window
   - `"昨天"` / `"yesterday"` → previous local-day window
   - `"前天"` → two-days-ago local-day window
   - `"2026-01-16"` → that local-day window
2. Implement `parse_time_window(text, tz)`:
   - Default `text=None` → treat as `"今天"`
   - Default `tz=None` → treat as `UTC+8` (recommend `Asia/Shanghai`)
   - Output ISO 8601 `since/until` with explicit timezone
3. Document supported phrases, default timezone, and examples in `references/time-window.md`.

---

## Task 1: Define data model + output contract

**Files:**
- Create: `skills/public/ai-news-digest/references/output-spec.md`

**Steps:**
1. Define `ArticleItem` JSON schema (minimum required fields for “可验收”输出).
2. Define `Digest` schema: sections (research/product/opensource/funding/policy), plus failures list.
3. Define acceptance checklist: time window, no duplicates, every item has url+source+date (or marked unknown).

---

## Task 2: Source registry (configurable, RSS-first)

**Files:**
- Create: `skills/public/ai-news-digest/references/sources.yaml`
- Modify: `skills/public/ai-news-digest/references/sources.md`

**Steps:**
1. Create `sources.yaml` with fields: `id,name,homepage,feeds[],lang,topics[],weight,flags[]`.
2. For each source, add at least one feed URL if discoverable; otherwise mark `flags: [needs_manual_feed]`.
3. Keep `sources.md` as human notes + caveats (paywall/login/anti-bot) and link to canonical URL.

---

## Task 3: Fetcher (cache + retries + rate limit)

**Files:**
- Create: `skills/public/ai-news-digest/scripts/fetch_feeds.py`

**Steps (TDD):**
1. Write unit test for cache keying and retry backoff (create `skills/public/ai-news-digest/scripts/tests/test_fetch_feeds.py` if you introduce a test runner; otherwise keep minimal self-check in script).
2. Implement:
   - per-domain rate limit
   - timeout + retries (with jitter)
   - optional ETag/Last-Modified caching
3. Emit fetched payloads to a local cache dir (configurable output path).

---

## Task 4: RSS/Atom parsing + normalization

**Files:**
- Create: `skills/public/ai-news-digest/scripts/parse_feeds.py`

**Steps:**
1. Parse feed entries into `ArticleItem` (title, url, published_at, summary_raw, source).
2. Normalize URLs (strip tracking params; resolve relative URLs when possible).
3. Normalize time to ISO 8601 with timezone; if missing, set `published_at=null` and flag.

---

## Task 5: Dedup + merge mentions

**Files:**
- Create: `skills/public/ai-news-digest/scripts/dedupe.py`

**Steps:**
1. Dedup by canonical URL (primary).
2. Add optional “title similarity + time proximity” secondary rule (off by default).
3. Merge duplicates into one item with `mentions[]`.

---

## Task 6: Topic classification + ranking

**Files:**
- Create: `skills/public/ai-news-digest/scripts/classify_rank.py`
- Create: `skills/public/ai-news-digest/references/topic-keywords.md`

**Steps:**
1. Implement keyword-based topic tagging as baseline (deterministic).
2. Ranking: recency first, then `source.weight`, then keyword boosts.
3. Allow user overrides: include/exclude keywords, max per topic.

---

## Task 7: Digest renderer (Markdown + optional JSON)

**Files:**
- Create: `skills/public/ai-news-digest/scripts/render_digest.py`
- Use: `skills/public/ai-news-digest/assets/digest-template.md`

**Steps:**
1. Render Markdown using the template (a simple Mustache-like replacement is enough).
2. Ensure output includes: date/window/lang/sources + per-topic lists + failures list.
3. Optional: write `digest.json` with full structured data for downstream use.

---

## Task 8: Optional LLM summarization layer (pluggable)

**Files:**
- Create: `skills/public/ai-news-digest/assets/summarize-prompt.md`
- Create: `skills/public/ai-news-digest/references/translation.md`
- Create: `skills/public/ai-news-digest/scripts/summarize_llm.py`

**Steps:**
1. Define a provider-agnostic interface: input = (title_raw, summary_raw, excerpt/fulltext?, target_lang), output = (title_zh, summary_zh, tags).
2. Default behavior requirement: output is Chinese; if provider not configured, degrade gracefully:
   - Markdown: keep raw text but mark as `（未翻译）`
   - JSON: always keep `title_raw/summary_raw` and optional `title_zh/summary_zh`
3. Hard rule: include original URL and never summarize/translate paywalled full text (use only public snippet/metadata).
4. Document translation rules and terminology handling in `references/translation.md`.

---

## Task 9: CLI entrypoint + end-to-end smoke check

**Files:**
- Create: `skills/public/ai-news-digest/scripts/run.py`
- Modify: `skills/public/ai-news-digest/SKILL.md`

**Steps:**
1. Provide CLI flags:
   - time: `--day` (accepts `今天/昨天/前天/today/yesterday/YYYY-MM-DD`), plus explicit `--since`, `--until`
   - tz: `--tz` default `UTC+8` (recommend accept `Asia/Shanghai`, `UTC+8`, `+08:00`)
   - output lang: `--lang` default `zh`
   - others: `--topics`, `--sources`, `--out`, `--format`
2. Smoke run with 2-3 RSS sources; verify Markdown output matches acceptance checklist.
3. Update `SKILL.md` with “how to run” commands once scripts exist.

---

## Validation / Packaging

Run:
- `python3 scripts/validate_skill.py skills/public/ai-news-digest`
- `python3 scripts/package_skill.py skills/public/ai-news-digest dist`
