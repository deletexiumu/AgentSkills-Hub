#!/usr/bin/env bun
/**
 * Incremental bookmark sync.
 * Fetches newest bookmarks, stops when hitting a known ID.
 * Classifies tweets (原创/长文/线程/回复/引用) with enriched data.
 * Merges into daily file, records latest ID for next run.
 *
 * Usage:
 *   bun scripts/sync-bookmarks-incremental.ts [--data-dir /custom/path]
 */

import { existsSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";
import { apiGet } from "./api";
import { loadConfig, getDataDir, parseDataDir, ensureDir, today } from "./config";
import { syncBookmarksToNotion } from "./notion";
import {
  classifyTweet,
  buildIncludesMaps,
  assignThreadPositions,
  TWEET_FIELDS,
  USER_FIELDS,
  MEDIA_FIELDS,
  type EnrichedTweet,
} from "./tweet-utils";

async function syncBookmarksIncremental() {
  const config = loadConfig();
  const dataDir = getDataDir(parseDataDir());
  const bookmarksDir = join(dataDir, "bookmarks");
  ensureDir(bookmarksDir);

  const dateStr = today();
  const ts = new Date().toISOString().slice(11, 19);

  // Load last known bookmark ID
  const statePath = join(bookmarksDir, "state.json");
  let state: { last_id: string | null; last_sync: string } = { last_id: null, last_sync: "" };
  if (existsSync(statePath)) {
    state = JSON.parse(readFileSync(statePath, "utf-8"));
  }

  console.log(`=== Sync Bookmarks Incremental (${dateStr} ${ts}) ===\n`);
  console.log(`User: @${config.username}`);
  console.log(`Last known ID: ${state.last_id || "(none - first run)"}`);
  console.log(`Data dir: ${bookmarksDir}\n`);

  // Fetch bookmarks page by page, stop when hitting known ID
  const newBookmarks: EnrichedTweet[] = [];
  const allIncludesTweets: any[] = [];
  const allIncludesUsers: any[] = [];
  let paginationToken: string | undefined;
  let page = 0;
  let hitKnown = false;

  do {
    page++;
    const params: Record<string, string> = {
      max_results: "100",
      "tweet.fields": TWEET_FIELDS,
      expansions: "author_id,attachments.media_keys,referenced_tweets.id,referenced_tweets.id.author_id",
      "user.fields": USER_FIELDS + ",profile_image_url",
      "media.fields": MEDIA_FIELDS,
    };
    if (paginationToken) {
      params.pagination_token = paginationToken;
    }

    console.log(`  Fetching page ${page}...`);
    const json = await apiGet(`/users/${config.user_id}/bookmarks`, params);
    const tweets: any[] = json.data || [];

    // Collect includes for classification
    if (json.includes?.tweets) allIncludesTweets.push(...json.includes.tweets);
    if (json.includes?.users) allIncludesUsers.push(...json.includes.users);

    if (tweets.length === 0) break;

    // Check each tweet — stop at known ID
    for (const t of tweets) {
      if (state.last_id && t.id === state.last_id) {
        hitKnown = true;
        break;
      }
      // Store raw tweet for now, classify after all includes are collected
      newBookmarks.push(t as any);
    }

    console.log(
      `  Got ${tweets.length} items, new so far: ${newBookmarks.length}${hitKnown ? " (hit known)" : ""}`
    );

    if (hitKnown) break;
    paginationToken = json.meta?.next_token;
  } while (paginationToken);

  if (newBookmarks.length === 0) {
    console.log("\nNo new bookmarks.");
    state.last_sync = new Date().toISOString();
    writeFileSync(statePath, JSON.stringify(state, null, 2));
    console.log("Done.");
    return;
  }

  // Build includes maps and classify
  const { tweetsMap, usersMap } = buildIncludesMaps({
    tweets: allIncludesTweets,
    users: allIncludesUsers,
  });

  // Classify and enrich each bookmark
  const classifiedBookmarks: EnrichedTweet[] = newBookmarks.map((raw: any) => {
    const authorId = raw.author_id || "";
    const classified = classifyTweet(raw, authorId, tweetsMap, usersMap);
    // Resolve author info
    const author = usersMap.get(authorId);
    if (author) {
      classified.author_name = author.name;
      classified.author_username = author.username;
    }
    return classified;
  });

  // Update last_id to newest bookmark
  state.last_id = classifiedBookmarks[0].id;
  state.last_sync = new Date().toISOString();

  // Merge into daily file
  const dailyPath = join(bookmarksDir, `${dateStr}.json`);
  let existingDaily: EnrichedTweet[] = [];
  if (existsSync(dailyPath)) {
    const prev = JSON.parse(readFileSync(dailyPath, "utf-8"));
    existingDaily = prev.bookmarks || [];
  }

  // Deduplicate by ID
  const bookmarkMap = new Map<string, EnrichedTweet>();
  for (const b of existingDaily) bookmarkMap.set(b.id, b);
  for (const b of classifiedBookmarks) bookmarkMap.set(b.id, b);
  const mergedBookmarks = Array.from(bookmarkMap.values()).sort(
    (a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "")
  );
  assignThreadPositions(mergedBookmarks);

  writeFileSync(
    dailyPath,
    JSON.stringify(
      {
        date: dateStr,
        last_updated: new Date().toISOString(),
        count: mergedBookmarks.length,
        bookmarks: mergedBookmarks,
      },
      null,
      2
    )
  );

  // Also update latest.json (cumulative)
  const latestPath = join(bookmarksDir, "latest.json");
  let allBookmarks: EnrichedTweet[] = [];
  if (existsSync(latestPath)) {
    const prev = JSON.parse(readFileSync(latestPath, "utf-8"));
    allBookmarks = prev.bookmarks || prev.tweets || [];
  }
  const allMap = new Map<string, EnrichedTweet>();
  for (const b of allBookmarks) allMap.set(b.id, b);
  for (const b of classifiedBookmarks) allMap.set(b.id, b);
  const allMerged = Array.from(allMap.values()).sort(
    (a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "")
  );

  writeFileSync(
    latestPath,
    JSON.stringify(
      {
        date: dateStr,
        last_updated: new Date().toISOString(),
        count: allMerged.length,
        bookmarks: allMerged,
      },
      null,
      2
    )
  );

  // Save state
  writeFileSync(statePath, JSON.stringify(state, null, 2));

  // Sync to Notion
  let notionCount = 0;
  console.log(`\n--- Notion Sync ---`);
  try {
    notionCount = await syncBookmarksToNotion(classifiedBookmarks);
    console.log(`  Notion: ${notionCount} new bookmarks pushed`);
  } catch (err: any) {
    console.error(`  Notion sync error: ${err.message}`);
  }

  // Print summary
  console.log(`\n--- Summary ---`);
  console.log(`New bookmarks: ${classifiedBookmarks.length}`);
  console.log(`Daily total: ${mergedBookmarks.length}`);
  console.log(`All-time total: ${allMerged.length}`);
  console.log(`Notion pushed: ${notionCount}`);
  console.log(`Latest ID: ${state.last_id}`);
  console.log("Done.");
}

await syncBookmarksIncremental();
