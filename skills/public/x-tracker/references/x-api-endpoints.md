# X API v2 Endpoints Reference

## Authentication

All requests require OAuth 2.0 User Token (Authorization Code with PKCE).

**Base URL**: `https://api.x.com/2`

**Common Headers**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

---

## GET /2/users/:id/following

Retrieve accounts the specified user follows.

**Rate Limit**: 15 requests / 15 minutes (per user)

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | path | yes | User ID (numeric, 1-19 digits) |
| `max_results` | query | no | 1-1000 (default 100) |
| `pagination_token` | query | no | Token for next page |
| `user.fields` | query | no | Fields to include |
| `tweet.fields` | query | no | Tweet fields for pinned tweet |
| `expansions` | query | no | Expand related objects |

### Recommended user.fields

```
id,name,username,description,profile_image_url,public_metrics,created_at,verified,location,url
```

### Response

```json
{
  "data": [
    {
      "id": "12345",
      "name": "Display Name",
      "username": "handle",
      "description": "Bio text",
      "public_metrics": {
        "followers_count": 1234,
        "following_count": 567,
        "tweet_count": 8901
      },
      "created_at": "2020-01-01T00:00:00.000Z"
    }
  ],
  "meta": {
    "result_count": 100,
    "next_token": "abc123"
  }
}
```

### Pagination

Loop with `pagination_token = meta.next_token` until `next_token` is absent.

---

## GET /2/users/:id/bookmarks

Retrieve bookmarked tweets for the authenticated user.

**Rate Limit**: 180 requests / 15 minutes (per user)

**Important**: `:id` must match the authenticated user's ID.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | path | yes | Authenticated user's ID |
| `max_results` | query | no | 1-100 (default 100) |
| `pagination_token` | query | no | Token for next page |
| `tweet.fields` | query | no | Tweet fields to include |
| `expansions` | query | no | Expand related objects |
| `media.fields` | query | no | Media object fields |
| `user.fields` | query | no | User object fields |

### Recommended Fields

```
tweet.fields=id,text,author_id,created_at,public_metrics,entities,referenced_tweets,attachments
expansions=author_id,attachments.media_keys
user.fields=id,name,username,profile_image_url
media.fields=url,preview_image_url,type
```

### Response

```json
{
  "data": [
    {
      "id": "tweet_id",
      "text": "Tweet content",
      "author_id": "user_id",
      "created_at": "2026-02-14T10:00:00.000Z",
      "public_metrics": {
        "retweet_count": 10,
        "reply_count": 5,
        "like_count": 100,
        "quote_count": 2
      }
    }
  ],
  "includes": {
    "users": [{ "id": "user_id", "name": "Author", "username": "author_handle" }]
  },
  "meta": {
    "result_count": 100,
    "next_token": "abc123"
  }
}
```

---

## GET /2/users/:id/bookmarks/folders

Retrieve bookmark folders for the authenticated user.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | path | yes | Authenticated user's ID |

### Response

```json
{
  "data": [
    {
      "id": "folder_id",
      "name": "Folder Name"
    }
  ]
}
```

---

## GET /2/users/:id/bookmarks/folders/:folder_id

Retrieve bookmarks within a specific folder.

Same parameters and response as GET bookmarks, plus `folder_id` path parameter.

---

## GET /2/users/:id/tweets

Retrieve tweets authored by the specified user.

**Rate Limit**: 900 requests / 15 minutes (per user), 10000 / 15 min (per app)

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | path | yes | User ID |
| `max_results` | query | no | 5-100 (default 10) |
| `pagination_token` | query | no | Token for next page |
| `start_time` | query | no | ISO 8601 datetime (oldest) |
| `end_time` | query | no | ISO 8601 datetime (newest) |
| `since_id` | query | no | Tweet ID lower bound |
| `until_id` | query | no | Tweet ID upper bound |
| `exclude` | query | no | `retweets`, `replies` |
| `tweet.fields` | query | no | Tweet fields |
| `expansions` | query | no | Expand related objects |
| `media.fields` | query | no | Media fields |
| `user.fields` | query | no | User fields |

### Recommended Fields

```
tweet.fields=id,text,created_at,public_metrics,entities,referenced_tweets,attachments,note_tweet
expansions=attachments.media_keys,referenced_tweets.id
media.fields=url,preview_image_url,type,alt_text
```

### Note on Articles

X Articles appear as tweets with a `card` entity. Filter by checking:
- `entities.urls` containing `x.com/*/articles/`
- `referenced_tweets` type for article detection

---

## GET /2/users/me

Retrieve the authenticated user's profile.

**Rate Limit**: 75 requests / 15 minutes (per user)

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `user.fields` | query | no | Fields to include |
| `expansions` | query | no | Expand related objects |

### Response

```json
{
  "data": {
    "id": "12345",
    "name": "Display Name",
    "username": "handle"
  }
}
```

---

## Error Handling

### Rate Limit Response (429)

```json
{
  "title": "Too Many Requests",
  "detail": "Too Many Requests",
  "type": "about:blank",
  "status": 429
}
```

Headers include:
- `x-rate-limit-limit`: Max requests per window
- `x-rate-limit-remaining`: Remaining requests
- `x-rate-limit-reset`: Unix timestamp when window resets

### Token Expired (401)

Refresh using the refresh token. See `oauth-setup.md` for refresh flow.

---

## Pagination Pattern

```typescript
async function fetchAll<T>(url: string, token: string, maxResults = 100): Promise<T[]> {
  const allData: T[] = [];
  let paginationToken: string | undefined;

  do {
    const params = new URLSearchParams({ max_results: String(maxResults) });
    if (paginationToken) params.set('pagination_token', paginationToken);

    const response = await fetch(`${url}?${params}`, {
      headers: { Authorization: `Bearer ${token}` }
    });

    if (response.status === 429) {
      const resetAt = Number(response.headers.get('x-rate-limit-reset')) * 1000;
      const waitMs = Math.max(resetAt - Date.now(), 1000);
      console.log(`Rate limited. Waiting ${Math.ceil(waitMs / 1000)}s...`);
      await new Promise(r => setTimeout(r, waitMs));
      continue;
    }

    const json = await response.json();
    if (json.data) allData.push(...json.data);
    paginationToken = json.meta?.next_token;
  } while (paginationToken);

  return allData;
}
```
