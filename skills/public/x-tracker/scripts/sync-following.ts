#!/usr/bin/env bun
/**
 * Sync X following list to local JSON archive.
 *
 * Usage:
 *   bun scripts/sync-following.ts [--data-dir /custom/path]
 */

import { writeFileSync, existsSync, readFileSync } from "fs";
import { join } from "path";
import { fetchAllPages } from "./api";
import { loadConfig, getDataDir, parseDataDir, ensureDir, today } from "./config";

interface FollowingUser {
  id: string;
  name: string;
  username: string;
  description?: string;
  profile_image_url?: string;
  public_metrics?: {
    followers_count: number;
    following_count: number;
    tweet_count: number;
  };
  created_at?: string;
  location?: string;
  url?: string;
  verified?: boolean;
}

async function syncFollowing() {
  const config = loadConfig();
  const dataDir = getDataDir(parseDataDir());
  const followingDir = join(dataDir, "following");
  ensureDir(followingDir);

  const dateStr = today();
  console.log(`=== Sync Following List (${dateStr}) ===\n`);
  console.log(`User: @${config.username} (ID: ${config.user_id})`);
  console.log(`Data dir: ${followingDir}\n`);

  // Fetch all following
  const userFields = [
    "id", "name", "username", "description", "profile_image_url",
    "public_metrics", "created_at", "location", "url", "verified",
  ].join(",");

  const result = await fetchAllPages(
    `/users/${config.user_id}/following`,
    { "user.fields": userFields },
    1000
  );

  const users: FollowingUser[] = result.data;
  console.log(`\nTotal following: ${users.length}`);

  // Save daily snapshot
  const snapshotPath = join(followingDir, `${dateStr}.json`);
  writeFileSync(snapshotPath, JSON.stringify({ date: dateStr, count: users.length, users }, null, 2));
  console.log(`Snapshot saved: ${snapshotPath}`);

  // Update latest
  const latestPath = join(followingDir, "latest.json");
  writeFileSync(latestPath, JSON.stringify({ date: dateStr, count: users.length, users }, null, 2));

  // Detect changes from previous snapshot
  detectChanges(followingDir, dateStr, users);

  console.log("\nDone.");
}

function detectChanges(dir: string, currentDate: string, currentUsers: FollowingUser[]) {
  // Find previous snapshot
  const latestPath = join(dir, "latest.json");
  // Look for files named YYYY-MM-DD.json that are not today
  const { readdirSync } = require("fs");
  const files: string[] = readdirSync(dir)
    .filter((f: string) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f) && f !== `${currentDate}.json`)
    .sort()
    .reverse();

  if (files.length === 0) {
    console.log("\nNo previous snapshot found — skipping change detection.");
    return;
  }

  const prevPath = join(dir, files[0]);
  const prevData = JSON.parse(readFileSync(prevPath, "utf-8"));
  const prevUsers: FollowingUser[] = prevData.users || [];

  const prevIds = new Set(prevUsers.map((u) => u.id));
  const currIds = new Set(currentUsers.map((u) => u.id));

  const newFollows = currentUsers.filter((u) => !prevIds.has(u.id));
  const unfollowed = prevUsers.filter((u) => !currIds.has(u.id));

  if (newFollows.length === 0 && unfollowed.length === 0) {
    console.log(`\nNo changes since ${files[0].replace(".json", "")}.`);
    return;
  }

  console.log(`\n--- Changes since ${files[0].replace(".json", "")} ---`);
  if (newFollows.length > 0) {
    console.log(`\n  New follows (+${newFollows.length}):`);
    for (const u of newFollows) {
      console.log(`    + @${u.username} (${u.name})`);
    }
  }
  if (unfollowed.length > 0) {
    console.log(`\n  Unfollowed (-${unfollowed.length}):`);
    for (const u of unfollowed) {
      console.log(`    - @${u.username} (${u.name})`);
    }
  }
}

await syncFollowing();
