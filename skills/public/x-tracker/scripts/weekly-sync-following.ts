#!/usr/bin/env bun
/**
 * Weekly sync: fetch following list (IDs only where possible),
 * compare locally, only fetch full user info for genuinely new follows.
 * Auto-add qualified ones (>=50K followers, AI/tech/dev, not web3).
 * New users get their latest 10 tweets fetched immediately.
 *
 * Optimization: uses cached user data from latest.json whenever possible,
 * only calls user lookup API for IDs not found locally.
 *
 * Usage:
 *   bun scripts/weekly-sync-following.ts [--data-dir /custom/path]
 */

import { existsSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";
import { fetchAllPages } from "./api";
import { loadConfig, getDataDir, parseDataDir, ensureDir, today } from "./config";

function loadManualIncludes(dataDir: string): Set<string> {
  const p = join(dataDir, "following", "manual_include.json");
  if (!existsSync(p)) return new Set();
  const data = JSON.parse(readFileSync(p, "utf-8"));
  return new Set((data.usernames || []).map((u: string) => u.toLowerCase()));
}

async function weeklySyncFollowing() {
  const config = loadConfig();
  const dataDir = getDataDir(parseDataDir());
  const followingDir = join(dataDir, "following");
  const tweetsDir = join(dataDir, "following-tweets");
  ensureDir(followingDir);
  ensureDir(tweetsDir);

  const dateStr = today();
  const manualIncludes = loadManualIncludes(dataDir);
  console.log(`=== Daily Following Sync (${dateStr}) ===\n`);
  console.log(`User: @${config.username}`);
  if (manualIncludes.size > 0) console.log(`Manual includes: ${manualIncludes.size}`);

  // Step 1: Fetch following list with MINIMAL fields (just id + username)
  console.log("\n--- Step 1: Fetch following IDs ---");
  const result = await fetchAllPages(
    `/users/${config.user_id}/following`,
    { "user.fields": "id,username" },
    1000
  );
  const currentFollowing: { id: string; username: string }[] = result.data;
  const currentIds = new Set(currentFollowing.map(u => u.id));
  console.log(`Current following: ${currentFollowing.length}`);

  // Step 2: Local diff — compare with cached latest.json
  console.log("\n--- Step 2: Local diff ---");
  const latestPath = join(followingDir, "latest.json");
  let cachedUsers: Map<string, any> = new Map();
  if (existsSync(latestPath)) {
    const latest = JSON.parse(readFileSync(latestPath, "utf-8"));
    for (const u of latest.users || []) {
      cachedUsers.set(u.id, u);
    }
  }

  const filteredPath = join(followingDir, "filtered.json");
  let filtered: any = { users: [] };
  if (existsSync(filteredPath)) {
    filtered = JSON.parse(readFileSync(filteredPath, "utf-8"));
  }
  const filteredIds = new Set(filtered.users.map((u: any) => u.id));
  const cachedIds = new Set(cachedUsers.keys());

  // Find truly new IDs (not in local cache at all)
  const newIds = currentFollowing.filter(u => !cachedIds.has(u.id));
  // Find unfollowed from filtered list
  const removedFromFiltered = filtered.users.filter((u: any) => !currentIds.has(u.id));
  // IDs in cache but not in filtered (known users, already evaluated and rejected)
  const knownButNotFiltered = currentFollowing.filter(u => cachedIds.has(u.id) && !filteredIds.has(u.id));

  console.log(`Cached users: ${cachedUsers.size}`);
  console.log(`Filtered (tracked): ${filteredIds.size}`);
  console.log(`New follows (not in cache): ${newIds.length}`);
  console.log(`Unfollowed from tracked: ${removedFromFiltered.length}`);

  if (newIds.length === 0 && removedFromFiltered.length === 0) {
    console.log("\nNo changes detected. Skipping API calls.");
    console.log("Done.");
    return;
  }

  // Step 3: Skipped — no longer fetches user info via /users endpoint (users.read removed)
  // New follows are saved with basic info (id, username) only
  if (newIds.length > 0) {
    console.log(`\n--- Step 3: Skipped (users.read removed) ---`);
    console.log(`  ${newIds.length} new follows saved with basic info only`);
    for (const u of newIds) {
      if (!cachedUsers.has(u.id)) {
        cachedUsers.set(u.id, u); // basic: { id, username }
      }
    }
  }

  // Update latest.json with merged cache (current follows only)
  const updatedLatestUsers = currentFollowing
    .map(u => cachedUsers.get(u.id) || u);
  writeFileSync(latestPath, JSON.stringify({
    date: dateStr, count: updatedLatestUsers.length, users: updatedLatestUsers
  }, null, 2));
  writeFileSync(join(followingDir, `${dateStr}.json`), JSON.stringify({
    date: dateStr, count: updatedLatestUsers.length, users: updatedLatestUsers
  }, null, 2));

  // Step 4: Skipped — qualification requires user details (public_metrics, description)
  // Without users.read scope, new follows must be managed manually:
  //   bun scripts/manage-following.ts add <username>
  if (newIds.length > 0) {
    console.log(`\n  ${newIds.length} new follow(s) detected (manual review needed):`);
    for (const u of newIds) {
      console.log(`    ? @${u.username}`);
    }
    console.log(`  To track: bun scripts/manage-following.ts add <username>`);
  }

  // Handle unfollowed: remove from filtered, but protect manual_include users
  const removable = removedFromFiltered.filter(
    (u: any) => !manualIncludes.has(u.username.toLowerCase())
  );
  const protected_ = removedFromFiltered.filter(
    (u: any) => manualIncludes.has(u.username.toLowerCase())
  );

  if (removable.length > 0) {
    console.log("\n  Removing (unfollowed):");
    for (const u of removable) {
      console.log(`    - @${u.username}`);
    }
  }
  if (protected_.length > 0) {
    console.log("\n  Kept (manual include, unfollowed):");
    for (const u of protected_) {
      console.log(`    ~ @${u.username} [manual]`);
    }
  }

  // Update filtered list: keep current follows + manual_include protected users
  // Do NOT auto-add newQualified (they go to pending)
  const updatedFiltered = [
    ...filtered.users.filter((u: any) =>
      currentIds.has(u.id) || manualIncludes.has(u.username.toLowerCase())
    ),
  ].sort((a: any, b: any) => (b.public_metrics?.followers_count || 0) - (a.public_metrics?.followers_count || 0));

  writeFileSync(filteredPath, JSON.stringify({
    date: dateStr,
    filter: { categories: ["AI", "Tech", "Developer"], exclude: ["web3", "politics", "media"] },
    count: updatedFiltered.length,
    users: updatedFiltered,
  }, null, 2));
  console.log(`\nFiltered list updated: ${updatedFiltered.length} users`);

  // Step 5: No longer auto-fetches tweets for new users.
  // Tweets are fetched when user is approved via: bun scripts/manage-following.ts approve <username>

  console.log("\nDone.");
}

await weeklySyncFollowing();
