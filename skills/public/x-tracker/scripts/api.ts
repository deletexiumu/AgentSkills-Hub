/**
 * X API v2 client with auto-pagination, rate limit handling, and token refresh.
 */

import { loadConfig, saveConfig, type Config } from "./config";

const BASE_URL = "https://api.x.com/2";

/** Refresh the access token using the refresh token */
async function refreshToken(config: Config): Promise<Config> {
  console.log("Refreshing access token...");

  const headers: Record<string, string> = {
    "Content-Type": "application/x-www-form-urlencoded",
  };
  if (config.client_secret) {
    headers["Authorization"] = `Basic ${Buffer.from(`${config.client_id}:${config.client_secret}`).toString("base64")}`;
  }
  const resp = await fetch("https://api.x.com/2/oauth2/token", {
    method: "POST",
    headers,
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: config.refresh_token,
      client_id: config.client_id,
    }),
  });

  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`Token refresh failed (${resp.status}): ${err}`);
  }

  const data = await resp.json();
  config.access_token = data.access_token;
  config.refresh_token = data.refresh_token;
  config.token_expires_at = Math.floor(Date.now() / 1000) + data.expires_in;
  saveConfig(config);
  console.log("Token refreshed successfully.");
  return config;
}

/** Ensure the access token is valid, refresh if needed */
async function ensureValidToken(config: Config): Promise<Config> {
  const now = Math.floor(Date.now() / 1000);
  // Refresh 5 minutes before expiry
  if (config.token_expires_at && now >= config.token_expires_at - 300) {
    return await refreshToken(config);
  }
  return config;
}

/** Make an authenticated GET request to X API */
export async function apiGet(
  path: string,
  params?: Record<string, string>
): Promise<any> {
  let config = loadConfig();
  config = await ensureValidToken(config);

  const url = new URL(`${BASE_URL}${path}`);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      url.searchParams.set(k, v);
    }
  }

  const resp = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${config.access_token}` },
    signal: AbortSignal.timeout(30_000),
  });

  if (resp.status === 429) {
    const resetAt = Number(resp.headers.get("x-rate-limit-reset")) * 1000;
    const waitMs = Math.min(Math.max(resetAt - Date.now(), 1000), 900_000);
    console.log(`Rate limited. Waiting ${Math.ceil(waitMs / 1000)}s...`);
    await Bun.sleep(waitMs);
    return apiGet(path, params);
  }

  if (resp.status === 401) {
    // Try refresh once
    config = await refreshToken(config);
    const retryResp = await fetch(url.toString(), {
      headers: { Authorization: `Bearer ${config.access_token}` },
      signal: AbortSignal.timeout(30_000),
    });
    if (!retryResp.ok) {
      throw new Error(`API error ${retryResp.status}: ${await retryResp.text()}`);
    }
    return retryResp.json();
  }

  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${await resp.text()}`);
  }

  return resp.json();
}

/**
 * Fetch all pages from a paginated X API endpoint.
 * Returns { data, includes } merged across all pages.
 */
export async function fetchAllPages(
  path: string,
  params: Record<string, string> = {},
  maxResults = 100
): Promise<{ data: any[]; includes: Record<string, any[]> }> {
  const allData: any[] = [];
  const allIncludes: Record<string, any[]> = {};
  let paginationToken: string | undefined;
  let page = 0;

  do {
    page++;
    const queryParams = { ...params, max_results: String(maxResults) };
    if (paginationToken) {
      queryParams.pagination_token = paginationToken;
    }

    console.log(`  Fetching page ${page}...`);
    const json = await apiGet(path, queryParams);

    if (json.data) {
      allData.push(...json.data);
    }

    // Merge includes
    if (json.includes) {
      for (const [key, items] of Object.entries(json.includes)) {
        if (!allIncludes[key]) allIncludes[key] = [];
        allIncludes[key].push(...(items as any[]));
      }
    }

    paginationToken = json.meta?.next_token;
    console.log(`  Got ${json.data?.length ?? 0} items (total: ${allData.length})`);
  } while (paginationToken);

  return { data: allData, includes: allIncludes };
}

/** Make an authenticated POST request to X API */
export async function apiPost(
  path: string,
  body: Record<string, any>
): Promise<any> {
  let config = loadConfig();
  config = await ensureValidToken(config);

  const url = `${BASE_URL}${path}`;

  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${config.access_token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(30_000),
  });

  if (resp.status === 401) {
    config = await refreshToken(config);
    const retryResp = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30_000),
    });
    if (!retryResp.ok) {
      throw new Error(`API error ${retryResp.status}: ${await retryResp.text()}`);
    }
    return retryResp.json();
  }

  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${await resp.text()}`);
  }

  return resp.json();
}

