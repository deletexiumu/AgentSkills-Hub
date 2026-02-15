#!/usr/bin/env bun
/**
 * One-time script: push all existing data to Notion.
 * Handles: filtered following (45), tweets (461), bookmarks (99).
 * Incremental — skips any already-existing records in Notion.
 */

import { existsSync, readFileSync } from "fs";
import { join } from "path";
import { getDataDir, parseDataDir } from "./config";
import {
  syncFollowingToNotion,
  syncTweetsToNotion,
  syncBookmarksToNotion,
} from "./notion";

async function main() {
  const dataDir = getDataDir(parseDataDir());
  console.log("=== Notion Initial Push ===\n");

  // 1. Following
  const filteredPath = join(dataDir, "following", "filtered.json");
  if (existsSync(filteredPath)) {
    const filtered = JSON.parse(readFileSync(filteredPath, "utf-8"));
    const users = filtered.users || [];
    console.log(`Following: ${users.length} users`);
    try {
      const count = await syncFollowingToNotion(users);
      console.log(`  -> ${count} pushed to Notion`);
    } catch (err: any) {
      console.error(`  -> Error: ${err.message}`);
    }
  }

  // 2. Tweets
  const tweetsPath = join(dataDir, "following-tweets", "2026-02-14.json");
  if (existsSync(tweetsPath)) {
    const data = JSON.parse(readFileSync(tweetsPath, "utf-8"));
    const results = data.results || [];
    const tweetsForNotion: { tweet: any; authorUsername: string }[] = [];
    for (const r of results) {
      for (const t of r.tweets || []) {
        tweetsForNotion.push({ tweet: t, authorUsername: r.username });
      }
    }
    console.log(`\nTweets: ${tweetsForNotion.length} total`);
    // Push in batches to avoid timeout
    const BATCH = 50;
    let totalPushed = 0;
    for (let i = 0; i < tweetsForNotion.length; i += BATCH) {
      const batch = tweetsForNotion.slice(i, i + BATCH);
      try {
        const count = await syncTweetsToNotion(batch);
        totalPushed += count;
        console.log(`  -> Batch ${Math.floor(i / BATCH) + 1}: ${count} pushed (${totalPushed} total)`);
      } catch (err: any) {
        console.error(`  -> Batch ${Math.floor(i / BATCH) + 1} error: ${err.message}`);
      }
    }
  }

  // 3. Bookmarks
  const bookmarksPath = join(dataDir, "bookmarks", "latest.json");
  if (existsSync(bookmarksPath)) {
    const data = JSON.parse(readFileSync(bookmarksPath, "utf-8"));
    const bookmarks = data.bookmarks || data.tweets || [];
    console.log(`\nBookmarks: ${bookmarks.length} total`);
    // Push in batches
    const BATCH = 50;
    let totalPushed = 0;
    for (let i = 0; i < bookmarks.length; i += BATCH) {
      const batch = bookmarks.slice(i, i + BATCH);
      try {
        const count = await syncBookmarksToNotion(batch);
        totalPushed += count;
        console.log(`  -> Batch ${Math.floor(i / BATCH) + 1}: ${count} pushed (${totalPushed} total)`);
      } catch (err: any) {
        console.error(`  -> Batch ${Math.floor(i / BATCH) + 1} error: ${err.message}`);
      }
    }
  }

  console.log("\nDone.");
}

await main();
