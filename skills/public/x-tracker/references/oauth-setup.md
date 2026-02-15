# OAuth 2.0 PKCE Setup Guide

## Overview

X API v2 bookmarks endpoint requires OAuth 2.0 Authorization Code Flow with PKCE.
This provides user-context access tokens with specific scopes.

## Step 1: Create an X Developer App

1. Go to https://developer.x.com/en/portal/dashboard
2. Create a new Project and App (or use existing)
3. Note the **Client ID** (under OAuth 2.0 settings)

## Step 2: Configure OAuth 2.0

In the App settings → User authentication settings:

| Setting | Value |
|---------|-------|
| App permissions | Read |
| Type of App | Native App (for PKCE, no client secret needed) |
| Callback URL | `http://127.0.0.1:3000/callback` |
| Website URL | Any valid URL |

**Required Scopes** (select all):
- `tweet.read` — Read tweets
- `users.read` — Read user profiles
- `follows.read` — Read following/followers
- `bookmark.read` — Read bookmarks
- `offline.access` — Get refresh token for long-lived access

## Step 3: PKCE Authorization Flow

### 3.1 Generate PKCE Challenge

```typescript
import { createHash, randomBytes } from 'crypto';

// Generate code verifier (43-128 chars, URL-safe)
const codeVerifier = randomBytes(32).toString('base64url');

// Generate code challenge (SHA256 hash of verifier)
const codeChallenge = createHash('sha256')
  .update(codeVerifier)
  .digest('base64url');
```

### 3.2 Build Authorization URL

```
https://x.com/i/oauth2/authorize?
  response_type=code&
  client_id={CLIENT_ID}&
  redirect_uri=http://127.0.0.1:3000/callback&
  scope=tweet.read users.read follows.read bookmark.read offline.access&
  state={RANDOM_STATE}&
  code_challenge={CODE_CHALLENGE}&
  code_challenge_method=S256
```

### 3.3 Handle Callback

Start a local HTTP server on port 3000 to receive the callback:

```
GET /callback?code={AUTH_CODE}&state={STATE}
```

Verify `state` matches, extract `code`.

### 3.4 Exchange Code for Token

```
POST https://api.x.com/2/oauth2/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code={AUTH_CODE}&
redirect_uri=http://127.0.0.1:3000/callback&
client_id={CLIENT_ID}&
code_verifier={CODE_VERIFIER}
```

**Response**:
```json
{
  "token_type": "bearer",
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 7200,
  "scope": "tweet.read users.read follows.read bookmark.read offline.access"
}
```

## Step 4: Token Refresh

Access tokens expire in 2 hours. Use refresh token for renewal:

```
POST https://api.x.com/2/oauth2/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&
refresh_token={REFRESH_TOKEN}&
client_id={CLIENT_ID}
```

**Response** includes new `access_token` and `refresh_token`. The old refresh token is
invalidated — always store the new one.

## Token Storage

Tokens are stored in `config.json` at the skill installation directory:

```json
{
  "client_id": "abc123",
  "access_token": "...",
  "refresh_token": "...",
  "token_expires_at": 1739500000,
  "user_id": "12345",
  "username": "myhandle"
}
```

The `auth.ts` script handles automatic refresh when `token_expires_at` is approaching.

## Security Notes

- `config.json` contains sensitive tokens — add to `.gitignore`
- PKCE (Native App) does not require a client secret
- Refresh tokens are single-use — always persist the latest one
- If refresh fails, re-run `bun scripts/auth.ts login`
