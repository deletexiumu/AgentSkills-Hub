#!/usr/bin/env bun
/**
 * Sync X bookmarks to local JSON archive.
 *
 * Usage:
 *   bun scripts/sync-bookmarks.ts [--data-dir /custom/path] [--folder <folder_id>]
 */

import { writeFileSync, existsSync, readFileSync } from "fs";
import { join } from "path";
import { fetchAllPages, apiGet } from "./api";
import { loadConfig, getDataDir, parseDataDir, ensureDir, today } from "./config";

interface BookmarkedTweet {
  id: string;
  text: string;
  author_id: string;
  created_at?: string;
  public_metrics?: {
    retweet_count: number;
    reply_count: number;
    like_count: number;
    quote_count: number;
  };
  entities?: any;
  referenced_tweets?: any[];
  attachments?: any;
  // Resolved from includes
  author_name?: string;
  author_username?: string;
}

async function syncBookmarks() {
  const config = loadConfig();
  const dataDir = getDataDir(parseDataDir());
  const bookmarksDir = join(dataDir, "bookmarks");
  ensureDir(bookmarksDir);

  const dateStr = today();
  const folderId = parseFolderFlag();

  console.log(`=== Sync Bookmarks (${dateStr}) ===\n`);
  console.log(`User: @${config.username} (ID: ${config.user_id})`);
  if (folderId) console.log(`Folder: ${folderId}`);
  console.log(`Data dir: ${bookmarksDir}\n`);

  // Fetch bookmarks
  const path = folderId
    ? `/users/${config.user_id}/bookmarks/folders/${folderId}`
    : `/users/${config.user_id}/bookmarks`;

  const tweetFields = [
    "id", "text", "author_id", "created_at", "public_metrics",
    "entities", "referenced_tweets", "attachments",
  ].join(",");

  const result = await fetchAllPages(path, {
    "tweet.fields": tweetFields,
    expansions: "author_id,attachments.media_keys",
    "user.fields": "id,name,username,profile_image_url",
    "media.fields": "url,preview_image_url,type",
  }, 100);

  // Resolve author info from includes
  const userMap = new Map<string, { name: string; username: string }>();
  if (result.includes?.users) {
    for (const u of result.includes.users) {
      userMap.set(u.id, { name: u.name, username: u.username });
    }
  }

  const tweets: BookmarkedTweet[] = result.data.map((t: any) => ({
    ...t,
    author_name: userMap.get(t.author_id)?.name,
    author_username: userMap.get(t.author_id)?.username,
  }));

  console.log(`\nTotal bookmarks: ${tweets.length}`);

  // Save daily snapshot
  const suffix = folderId ? `-folder-${folderId}` : "";
  const snapshotPath = join(bookmarksDir, `${dateStr}${suffix}.json`);
  writeFileSync(
    snapshotPath,
    JSON.stringify(
      {
        date: dateStr,
        folder_id: folderId || null,
        count: tweets.length,
        tweets,
        includes: result.includes,
      },
      null,
      2
    )
  );
  console.log(`Snapshot saved: ${snapshotPath}`);

  // Update latest
  const latestPath = join(bookmarksDir, `latest${suffix}.json`);
  writeFileSync(
    latestPath,
    JSON.stringify(
      {
        date: dateStr,
        folder_id: folderId || null,
        count: tweets.length,
        tweets,
        includes: result.includes,
      },
      null,
      2
    )
  );

  // Detect new bookmarks
  detectNewBookmarks(bookmarksDir, dateStr, tweets, suffix);

  console.log("\nDone.");
}

function detectNewBookmarks(
  dir: string,
  currentDate: string,
  currentTweets: BookmarkedTweet[],
  suffix: string
) {
  const { readdirSync } = require("fs");
  const pattern = suffix
    ? new RegExp(`^\\d{4}-\\d{2}-\\d{2}${suffix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\.json$`)
    : /^\d{4}-\d{2}-\d{2}\.json$/;

  const files: string[] = readdirSync(dir)
    .filter((f: string) => pattern.test(f) && !f.startsWith(currentDate))
    .sort()
    .reverse();

  if (files.length === 0) {
    console.log("\nNo previous snapshot — skipping change detection.");
    return;
  }

  const prevData = JSON.parse(readFileSync(join(dir, files[0]), "utf-8"));
  const prevIds = new Set((prevData.tweets || []).map((t: any) => t.id));

  const newBookmarks = currentTweets.filter((t) => !prevIds.has(t.id));
  const removed = (prevData.tweets || []).filter(
    (t: any) => !currentTweets.find((ct) => ct.id === t.id)
  );

  if (newBookmarks.length === 0 && removed.length === 0) {
    console.log(`\nNo changes since ${files[0].replace(".json", "")}.`);
    return;
  }

  console.log(`\n--- Changes since ${files[0].replace(".json", "")} ---`);
  if (newBookmarks.length > 0) {
    console.log(`\n  New bookmarks (+${newBookmarks.length}):`);
    for (const t of newBookmarks.slice(0, 10)) {
      const author = t.author_username ? `@${t.author_username}` : t.author_id;
      console.log(`    + [${author}] ${t.text?.substring(0, 80)}...`);
    }
    if (newBookmarks.length > 10) {
      console.log(`    ... and ${newBookmarks.length - 10} more`);
    }
  }
  if (removed.length > 0) {
    console.log(`\n  Removed (-${removed.length})`);
  }
}

function parseFolderFlag(): string | undefined {
  const idx = process.argv.indexOf("--folder");
  if (idx !== -1 && process.argv[idx + 1]) {
    return process.argv[idx + 1];
  }
  return undefined;
}

await syncBookmarks();
