# X Tracker

Sync and archive your X (Twitter) data — following list, bookmarks, personal tweets — with content digest, rewrite, and Notion integration.

## Features

- **Data Sync** — Following list, bookmarks, personal tweets, following tweets → local JSON
- **Daily Digest** — Rank tweets by `like + retweet×3 + bookmark×2`, generate Top 20 digest
- **Content Rewrite** — AI-powered rewrite in your personal style (parallel sub-agents)
- **Style Analysis** — Profile your posting style from historical tweets
- **Post Tweets** — Post, quote, reply via X API v2 (no browser needed)
- **Notion Sync** — Incremental push to Notion databases
- **Manual Lists** — `manual_include.json` / `manual_exclude.json` for custom curation

## Prerequisites

- [Bun](https://bun.sh/) runtime
- X API OAuth 2.0 credentials (free tier works)

## Quick Start

```bash
# 1. Initialize config
bun scripts/auth.ts init

# 2. Authenticate (opens browser for OAuth)
bun scripts/auth.ts login

# 3. Sync your data
bun scripts/sync-following.ts
bun scripts/sync-bookmarks.ts
bun scripts/fetch-my-tweets.ts
```

## Directory Layout

```
{PROJECT_ROOT}/
├── config.json              # OAuth tokens & settings (gitignored)
├── data/
│   ├── following/           # Following list snapshots
│   ├── bookmarks/           # Bookmark archives
│   ├── my-tweets/           # Personal tweet history
│   └── following-tweets/    # Tweets from followed accounts
├── digests/
│   └── {YYYY-MM-DD}/       # Daily digest & rewrite output
└── x-tracker/               # Skill directory
    ├── SKILL.md
    ├── scripts/             # All executable scripts
    ├── references/          # API docs, OAuth guide, Notion schema
    └── assets/              # Templates
```

## Scripts

| Script | Description |
|--------|-------------|
| `auth.ts init` | Create config with client credentials |
| `auth.ts login` | OAuth 2.0 PKCE login flow |
| `auth.ts refresh` | Manually refresh access token |
| `auth.ts status` | Check token status |
| `sync-following.ts` | Sync following list |
| `sync-bookmarks.ts` | Sync bookmarks |
| `fetch-my-tweets.ts` | Fetch personal tweets |
| `fetch-following-tweets.ts` | Fetch tweets from followed accounts |
| `fetch-tweet.ts <id>` | Fetch a single tweet by ID |
| `post-tweet.ts <text>` | Post a tweet (`--quote` / `--reply` supported) |
| `analyze.ts digest` | Generate daily digest |
| `analyze.ts rewrite` | Generate rewrite candidates |
| `analyze.ts style` | Analyze personal posting style |
| `notion-sync.ts <type>` | Push to Notion (`following` / `bookmarks` / `all`) |
| `manage-following.ts` | Manage manual include/exclude lists |
| `weekly-sync-following.ts` | Weekly following list diff report |

## Configuration

`config.json` (in project root, gitignored):

```json
{
  "client_id": "your_client_id",
  "access_token": "",
  "refresh_token": "",
  "token_expires_at": 0,
  "user_id": "",
  "username": "",
  "data_dir": "./data",
  "redirect_uri": "http://127.0.0.1:18923/callback",
  "notion": {
    "token": "notion_integration_token",
    "following_db_id": "...",
    "bookmarks_db_id": "..."
  }
}
```

### Custom OAuth Callback

By default, the OAuth callback listens on `http://127.0.0.1:18923/callback`. To use a public URL (e.g., for remote server auth), set `redirect_uri` in `config.json` and configure your reverse proxy to 302 redirect to `http://127.0.0.1:18923/callback`.

## Required OAuth Scopes

`tweet.read` `tweet.write` `users.read` `follows.read` `bookmark.read` `offline.access`

## License

MIT
