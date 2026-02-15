# Notion Database Schema

## X Following Database

Track all accounts the user follows on X with historical status.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| Name | Title | Display name of the account |
| Username | Rich Text | @handle (without @) |
| User ID | Rich Text | X numeric user ID |
| Bio | Rich Text | Account description/bio |
| Profile Image | URL | Profile picture URL |
| Followers | Number | Follower count at last sync |
| Following | Number | Following count at last sync |
| Tweets | Number | Tweet count at last sync |
| Location | Rich Text | User-set location |
| Website | URL | User website link |
| Status | Select | `active` / `unfollowed` |
| First Seen | Date | Date first appeared in following list |
| Last Seen | Date | Date last seen in following list |
| Created At | Date | Account creation date on X |

### Views

- **All Following** — Filter: Status = active, Sort: First Seen desc
- **Recently Unfollowed** — Filter: Status = unfollowed, Sort: Last Seen desc

---

## X Bookmarks Database

Archive all bookmarked tweets with AI-powered categorization.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| Content | Title | Tweet text (truncated to 100 chars for title) |
| Full Text | Rich Text | Complete tweet text |
| Tweet URL | URL | Link to original tweet |
| Tweet ID | Rich Text | X tweet ID |
| Author | Rich Text | @handle of tweet author |
| Author Name | Rich Text | Display name of author |
| Category | Multi-Select | AI-assigned topic tags |
| Metrics | Rich Text | likes/retweets/replies formatted |
| Has Media | Checkbox | Whether tweet has images/video |
| Media URLs | Rich Text | Comma-separated media URLs |
| Bookmarked Date | Date | Date added to bookmarks |
| Tweet Date | Date | Original tweet creation date |
| Synced At | Date | Last sync timestamp |

### Category Options

Pre-defined categories for AI classification:
- `AI/ML` — Artificial intelligence, machine learning
- `Programming` — Code, dev tools, languages
- `Product` — Product launches, tools, apps
- `Design` — UI/UX, visual design
- `Business` — Startups, entrepreneurship
- `Science` — Research, papers, discoveries
- `Life` — Personal development, lifestyle
- `News` — Current events, industry news
- `Thread` — Long-form thread worth archiving
- `Tutorial` — How-to, educational content
- `Other` — Uncategorized

### Views

- **All Bookmarks** — Sort: Bookmarked Date desc
- **By Category** — Group by Category
- **AI Related** — Filter: Category contains AI/ML

---

## Sync Strategy

### Initial Sync
1. Create databases via Notion MCP tool if not exist
2. Fetch all data from X API
3. Insert all records

### Incremental Sync
1. Fetch latest data from X API
2. Compare with Notion database records (by Tweet ID or User ID)
3. Insert new records only
4. Update changed fields (e.g., follower count, status)

### Deduplication
- Following: Deduplicate by `User ID`
- Bookmarks: Deduplicate by `Tweet ID`

### Using Notion MCP

Create pages using `mcp__plugin_Notion_notion__notion-create-pages`:
- `pages` parameter must be JSON array
- `parent` uses `data_source_id`
- Relation fields use string URL, not array

Refer to `~/.claude/rules/notion-integration.md` for MCP usage conventions.
