#!/usr/bin/env bun
/**
 * Manage the tracked following list.
 *
 * Commands:
 *   add <username>            — manually add user to tracked list
 *   remove <username>         — remove from tracked list, add to exclude
 *   pending                   — list users awaiting approval
 *   approve <username|--all>  — approve pending user(s) → tracked list
 *   reject <username|--all>   — reject pending user(s) → exclude list
 *   list                      — list all tracked users
 *
 * Usage:
 *   bun scripts/manage-following.ts <command> [args] [--data-dir /custom/path]
 */

import { existsSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";
import { apiGet } from "./api";
import { getDataDir, parseDataDir, ensureDir, today } from "./config";
import { syncFollowingToNotion, syncTweetsToNotion } from "./notion";
import {
  classifyTweet,
  buildIncludesMaps,
  assignThreadPositions,
  TWEET_FIELDS,
  TWEET_EXPANSIONS,
  USER_FIELDS,
  MEDIA_FIELDS,
  type EnrichedTweet,
} from "./tweet-utils";

const dataDir = getDataDir(parseDataDir());
const followingDir = join(dataDir, "following");
const tweetsDir = join(dataDir, "following-tweets");
ensureDir(followingDir);
ensureDir(tweetsDir);

const filteredPath = join(followingDir, "filtered.json");
const pendingPath = join(followingDir, "pending.json");
const manualIncludePath = join(followingDir, "manual_include.json");
const manualExcludePath = join(followingDir, "manual_exclude.json");

// --- Data helpers ---

function loadFiltered(): { users: any[]; [k: string]: any } {
  if (!existsSync(filteredPath)) return { users: [], date: today(), count: 0 };
  return JSON.parse(readFileSync(filteredPath, "utf-8"));
}

function saveFiltered(filtered: any) {
  filtered.date = today();
  filtered.count = filtered.users.length;
  writeFileSync(filteredPath, JSON.stringify(filtered, null, 2));
}

function loadPending(): any[] {
  if (!existsSync(pendingPath)) return [];
  const data = JSON.parse(readFileSync(pendingPath, "utf-8"));
  return data.users || [];
}

function savePending(users: any[]) {
  writeFileSync(
    pendingPath,
    JSON.stringify({ updated: new Date().toISOString(), count: users.length, users }, null, 2)
  );
}

function loadManualInclude(): Set<string> {
  if (!existsSync(manualIncludePath)) return new Set();
  const data = JSON.parse(readFileSync(manualIncludePath, "utf-8"));
  return new Set((data.usernames || []).map((u: string) => u.toLowerCase()));
}

function saveManualInclude(set: Set<string>) {
  writeFileSync(
    manualIncludePath,
    JSON.stringify({ usernames: [...set] }, null, 2)
  );
}

function loadManualExclude(): Set<string> {
  if (!existsSync(manualExcludePath)) return new Set();
  const data = JSON.parse(readFileSync(manualExcludePath, "utf-8"));
  return new Set((data.usernames || []).map((u: string) => u.toLowerCase()));
}

function saveManualExclude(set: Set<string>) {
  writeFileSync(
    manualExcludePath,
    JSON.stringify(
      { description: "Manually excluded usernames", usernames: [...set] },
      null,
      2
    )
  );
}

function formatFollowers(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(n);
}

// --- Fetch user info by username ---

async function fetchUserByUsername(username: string): Promise<any | null> {
  const clean = username.replace(/^@/, "");
  const userFields =
    "id,name,username,description,profile_image_url,public_metrics,created_at,location,url,verified";
  try {
    const json = await apiGet(`/users/by/username/${clean}`, {
      "user.fields": userFields,
    });
    return json.data || null;
  } catch (err: any) {
    console.error(`Failed to fetch @${clean}: ${err.message}`);
    return null;
  }
}

// --- Fetch & classify latest tweets for a user ---

async function fetchAndClassifyTweets(
  user: any,
  count: number = 10
): Promise<EnrichedTweet[]> {
  try {
    const json = await apiGet(`/users/${user.id}/tweets`, {
      max_results: String(Math.min(count, 100)),
      "tweet.fields": TWEET_FIELDS,
      expansions: TWEET_EXPANSIONS,
      "user.fields": USER_FIELDS,
      "media.fields": MEDIA_FIELDS,
      exclude: "replies",
    });
    const raw = json.data || [];
    const { tweetsMap, usersMap } = buildIncludesMaps(json.includes);
    const classified = raw.map((t: any) =>
      classifyTweet(t, user.id, tweetsMap, usersMap)
    );
    assignThreadPositions(classified);
    return classified;
  } catch (err: any) {
    console.error(`Failed to fetch tweets for @${user.username}: ${err.message}`);
    return [];
  }
}

// --- Add user to tracked list + fetch tweets + sync Notion ---

async function addUserToTracked(user: any) {
  const filtered = loadFiltered();

  // Check if already tracked
  if (filtered.users.some((u: any) => u.id === user.id)) {
    console.log(`@${user.username} already in tracked list.`);
    return;
  }

  // Add to filtered
  filtered.users.push(user);
  filtered.users.sort(
    (a: any, b: any) =>
      (b.public_metrics?.followers_count || 0) - (a.public_metrics?.followers_count || 0)
  );
  saveFiltered(filtered);

  // Add to manual_include
  const includes = loadManualInclude();
  includes.add(user.username.toLowerCase());
  saveManualInclude(includes);

  // Remove from exclude if present
  const excludes = loadManualExclude();
  if (excludes.has(user.username.toLowerCase())) {
    excludes.delete(user.username.toLowerCase());
    saveManualExclude(excludes);
  }

  // Sync to Notion
  try {
    const count = await syncFollowingToNotion([user]);
    if (count > 0) console.log(`  Notion: user pushed`);
  } catch (err: any) {
    console.error(`  Notion error: ${err.message}`);
  }

  // Fetch latest tweets
  console.log(`  Fetching latest 10 tweets...`);
  const tweets = await fetchAndClassifyTweets(user);
  if (tweets.length > 0) {
    // Update since_ids
    const sinceIdsPath = join(tweetsDir, "since_ids.json");
    let sinceIds: Record<string, string> = {};
    if (existsSync(sinceIdsPath)) {
      sinceIds = JSON.parse(readFileSync(sinceIdsPath, "utf-8"));
    }
    sinceIds[user.id] = tweets[0].id;
    writeFileSync(sinceIdsPath, JSON.stringify(sinceIds, null, 2));

    // Merge into daily file
    const dateStr = today();
    const dailyPath = join(tweetsDir, `${dateStr}.json`);
    let dailyData: any = { results: [] };
    if (existsSync(dailyPath)) {
      dailyData = JSON.parse(readFileSync(dailyPath, "utf-8"));
    }
    const resultsMap = new Map<string, any>();
    for (const r of dailyData.results) resultsMap.set(r.user_id, r);
    resultsMap.set(user.id, {
      user_id: user.id,
      username: user.username,
      name: user.name,
      followers_count: user.public_metrics?.followers_count || 0,
      tweets,
      latest_tweet_id: tweets[0].id,
    });
    const allResults = Array.from(resultsMap.values());
    writeFileSync(
      dailyPath,
      JSON.stringify(
        {
          date: dateStr,
          last_updated: new Date().toISOString(),
          user_count: allResults.length,
          total_tweets: allResults.reduce((s: number, r: any) => s + r.tweets.length, 0),
          results: allResults,
        },
        null,
        2
      )
    );

    // Sync tweets to Notion
    try {
      const notionTweets = tweets.map((t) => ({ tweet: t, authorUsername: user.username }));
      const pushed = await syncTweetsToNotion(notionTweets);
      console.log(`  ${tweets.length} tweets fetched, ${pushed} pushed to Notion`);
    } catch (err: any) {
      console.error(`  Notion tweet sync error: ${err.message}`);
    }
  } else {
    console.log(`  No tweets found`);
  }
}

// --- Commands ---

async function cmdAdd(username: string) {
  const clean = username.replace(/^@/, "");
  console.log(`Fetching @${clean}...`);
  const user = await fetchUserByUsername(clean);
  if (!user) {
    console.error(`User @${clean} not found.`);
    process.exit(1);
  }

  const f = user.public_metrics?.followers_count || 0;
  console.log(
    `  ${user.name} (@${user.username}) — ${formatFollowers(f)} followers`
  );
  console.log(`  "${(user.description || "").substring(0, 80)}"`);
  console.log();

  await addUserToTracked(user);
  console.log(`\nAdded @${user.username} to tracked list. [manual]`);
}

async function cmdRemove(username: string) {
  const clean = username.replace(/^@/, "").toLowerCase();
  const filtered = loadFiltered();

  const idx = filtered.users.findIndex(
    (u: any) => u.username.toLowerCase() === clean
  );
  if (idx === -1) {
    console.log(`@${clean} not in tracked list.`);
    return;
  }

  const removed = filtered.users.splice(idx, 1)[0];
  saveFiltered(filtered);

  // Add to exclude
  const excludes = loadManualExclude();
  excludes.add(clean);
  saveManualExclude(excludes);

  // Remove from manual_include
  const includes = loadManualInclude();
  if (includes.has(clean)) {
    includes.delete(clean);
    saveManualInclude(includes);
  }

  console.log(`Removed @${removed.username} from tracked list.`);
  console.log(`Added to exclude list (won't be auto-added again).`);
}

function cmdPending() {
  const pending = loadPending();
  if (pending.length === 0) {
    console.log("No pending users.");
    return;
  }

  console.log(`=== Pending Approval (${pending.length}) ===\n`);
  for (let i = 0; i < pending.length; i++) {
    const u = pending[i];
    const f = formatFollowers(u.public_metrics?.followers_count || 0);
    const desc = (u.description || "").substring(0, 60);
    const detected = u.detected_at || "unknown";
    console.log(`  ${(i + 1).toString().padStart(2)}. @${u.username.padEnd(22)} ${f.padStart(7)} | ${desc}`);
    console.log(`      detected: ${detected}`);
  }

  console.log(`\n  approve:  bun scripts/manage-following.ts approve <username>`);
  console.log(`  approve all: bun scripts/manage-following.ts approve --all`);
  console.log(`  reject:   bun scripts/manage-following.ts reject <username>`);
}

async function cmdApprove(target: string) {
  let pending = loadPending();
  if (pending.length === 0) {
    console.log("No pending users.");
    return;
  }

  const isAll = target === "--all";
  const toApprove: any[] = [];

  if (isAll) {
    toApprove.push(...pending);
    pending = [];
  } else {
    const clean = target.replace(/^@/, "").toLowerCase();
    const idx = pending.findIndex(
      (u: any) => u.username.toLowerCase() === clean
    );
    if (idx === -1) {
      console.log(`@${clean} not in pending list.`);
      return;
    }
    toApprove.push(pending.splice(idx, 1)[0]);
  }

  savePending(pending);

  for (const user of toApprove) {
    console.log(`\nApproving @${user.username}...`);
    await addUserToTracked(user);
    console.log(`  @${user.username} → tracked list`);
  }

  console.log(`\n${toApprove.length} user(s) approved.`);
}

async function cmdReject(target: string) {
  let pending = loadPending();
  if (pending.length === 0) {
    console.log("No pending users.");
    return;
  }

  const isAll = target === "--all";
  const toReject: any[] = [];

  if (isAll) {
    toReject.push(...pending);
    pending = [];
  } else {
    const clean = target.replace(/^@/, "").toLowerCase();
    const idx = pending.findIndex(
      (u: any) => u.username.toLowerCase() === clean
    );
    if (idx === -1) {
      console.log(`@${clean} not in pending list.`);
      return;
    }
    toReject.push(pending.splice(idx, 1)[0]);
  }

  savePending(pending);

  // Add all rejected to exclude
  const excludes = loadManualExclude();
  for (const u of toReject) {
    excludes.add(u.username.toLowerCase());
    console.log(`  Rejected @${u.username} → exclude list`);
  }
  saveManualExclude(excludes);

  console.log(`\n${toReject.length} user(s) rejected.`);
}

function cmdList() {
  const filtered = loadFiltered();
  const includes = loadManualInclude();
  const users = filtered.users || [];

  if (users.length === 0) {
    console.log("Tracked list is empty.");
    return;
  }

  console.log(`=== Tracked Following (${users.length}) ===\n`);
  for (let i = 0; i < users.length; i++) {
    const u = users[i];
    const f = formatFollowers(u.public_metrics?.followers_count || 0);
    const tag = includes.has(u.username.toLowerCase()) ? "[manual]" : "[auto]";
    console.log(`  ${(i + 1).toString().padStart(2)}. @${u.username.padEnd(22)} ${f.padStart(7)}  ${tag}`);
  }

  const pending = loadPending();
  if (pending.length > 0) {
    console.log(`\n  (${pending.length} pending approval — run: bun scripts/manage-following.ts pending)`);
  }
}

// --- Main ---

const args = process.argv.slice(2).filter((a) => a !== "--data-dir" && !a.startsWith("/"));
const cmd = args[0];
const arg = args[1];

switch (cmd) {
  case "add":
    if (!arg) {
      console.error("Usage: manage-following.ts add <username>");
      process.exit(1);
    }
    await cmdAdd(arg);
    break;

  case "remove":
    if (!arg) {
      console.error("Usage: manage-following.ts remove <username>");
      process.exit(1);
    }
    await cmdRemove(arg);
    break;

  case "pending":
    cmdPending();
    break;

  case "approve":
    if (!arg) {
      console.error("Usage: manage-following.ts approve <username|--all>");
      process.exit(1);
    }
    await cmdApprove(arg);
    break;

  case "reject":
    if (!arg) {
      console.error("Usage: manage-following.ts reject <username|--all>");
      process.exit(1);
    }
    await cmdReject(arg);
    break;

  case "list":
    cmdList();
    break;

  default:
    console.log(`Usage: manage-following.ts <command> [args]

Commands:
  add <username>            Add user to tracked list (manual)
  remove <username>         Remove from tracked list + add to exclude
  pending                   List users awaiting approval
  approve <username|--all>  Approve pending user(s) → tracked
  reject <username|--all>   Reject pending user(s) → exclude
  list                      List all tracked users`);
    break;
}
