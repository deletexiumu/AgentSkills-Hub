#!/usr/bin/env bun
/**
 * Daily following check: compare latest.json (current) with all.json (baseline),
 * detect new follows, notify via Discord, then update all.json = latest.json.
 *
 * NO X API calls — purely local JSON comparison.
 *
 * Files:
 *   latest.json       — current following list (updated by sync-following.ts)
 *   all.json          — baseline from last run
 *   manual_exclude.json — usernames to ignore (no notification)
 *   manual_include.json — usernames to always keep in filtered
 *
 * Usage:
 *   bun scripts/weekly-sync-following.ts [--data-dir /custom/path]
 */

import { existsSync, readFileSync, writeFileSync, copyFileSync } from "fs";
import { join } from "path";
import { getDataDir, parseDataDir, ensureDir, today } from "./config";

function loadUsernames(path: string): Set<string> {
  if (!existsSync(path)) return new Set();
  const data = JSON.parse(readFileSync(path, "utf-8"));
  return new Set((data.usernames || []).map((u: string) => u.toLowerCase()));
}

async function notifyDiscord(message: string) {
  const token = process.env.DISCORD_BOT_TOKEN;
  const channelId = process.env.DISCORD_CHANNEL_ID;
  if (!token || !channelId) {
    console.log("[discord] skipped — missing DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID");
    return;
  }

  try {
    const resp = await fetch(`https://discord.com/api/v10/channels/${channelId}/messages`, {
      method: "POST",
      headers: {
        Authorization: `Bot ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ content: message }),
    });
    if (resp.ok) {
      console.log(`[discord] sent (http=${resp.status})`);
    } else {
      console.error(`[discord] failed (http=${resp.status})`, await resp.text());
    }
  } catch (e) {
    console.error("[discord] notification failed:", e);
  }
}

async function checkFollowing() {
  const dataDir = getDataDir(parseDataDir());
  const followingDir = join(dataDir, "following");
  ensureDir(followingDir);

  const dateStr = today();
  console.log(`=== Following Check (${dateStr}) ===\n`);

  const latestPath = join(followingDir, "latest.json");
  const allPath = join(followingDir, "all.json");

  if (!existsSync(latestPath)) {
    console.error("latest.json not found. Run sync-following.ts first.");
    process.exit(1);
  }

  // Load latest (current following)
  const latest = JSON.parse(readFileSync(latestPath, "utf-8"));
  const latestUsers: { id: string; username: string; name?: string }[] = latest.users || [];
  const latestIds = new Map(latestUsers.map((u) => [u.id, u]));
  console.log(`Latest following: ${latestUsers.length}`);

  // Load all (baseline)
  let allIds = new Set<string>();
  if (existsSync(allPath)) {
    const all = JSON.parse(readFileSync(allPath, "utf-8"));
    allIds = new Set((all.users || []).map((u: any) => u.id));
    console.log(`Baseline (all.json): ${allIds.size}`);
  } else {
    console.log("all.json not found — treating as first run.");
  }

  // Load excludes
  const excludes = loadUsernames(join(followingDir, "manual_exclude.json"));
  console.log(`Manual excludes: ${excludes.size}`);

  // Diff: in latest but not in all
  const newUsers = latestUsers.filter(
    (u) => !allIds.has(u.id) && !excludes.has(u.username.toLowerCase())
  );
  // Also detect unfollowed: in all but not in latest
  const unfollowed = [...allIds].filter((id) => !latestIds.has(id));

  console.log(`\nNew follows: ${newUsers.length}`);
  console.log(`Unfollowed: ${unfollowed.length}`);

  if (newUsers.length > 0) {
    console.log("\n  New:");
    for (const u of newUsers) {
      console.log(`    + @${u.username} (${u.name || u.id})`);
    }

    const userList = newUsers.map((u) => `  @${u.username}`).join("\n");
    const msg = `📋 关注变动 (${dateStr})\n新增关注 ${newUsers.length} 人:\n${userList}\n\n如需加入跟踪列表:\nbun scripts/manage-following.ts add <username>`;
    await notifyDiscord(msg);
  }

  if (unfollowed.length > 0) {
    console.log("\n  Unfollowed IDs:");
    for (const id of unfollowed) {
      console.log(`    - ${id}`);
    }
  }

  if (newUsers.length === 0 && unfollowed.length === 0) {
    console.log("\nNo changes detected.");
  }

  // Update all.json = latest.json
  copyFileSync(latestPath, allPath);
  console.log(`\nall.json updated → ${latestUsers.length} users`);

  console.log("Done.");
}

await checkFollowing();
