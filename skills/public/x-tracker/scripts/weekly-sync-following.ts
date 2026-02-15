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
import { fetchAllPages, apiGet } from "./api";
import { loadConfig, getDataDir, parseDataDir, ensureDir, today } from "./config";
import { syncFollowingToNotion } from "./notion";

const WEB3_RE = /web\s*3|crypto|blockchain|nft|defi\b|degen|wagmi|hodl|solana|ethereum|\beth\b|btc|bitcoin|token(?!ize)|airdrop|meme\s*coin|加密|币圈|撸毛|空投|挖矿|链上|公链|合约交易|depin|rwa\b|binance|币安|okx|bybit|bitget|weex|coinbase|交易所|韭菜|on.chain|memecoin|pump\.fun|gmgn|dex\b|cex\b|staking|yield\b|liquidity|mint\b|rug\b|fomo|alpha.call|做多|做空|杠杆.*币|多空|合约.*u本位|u本位|开单|爆仓/i;

const TECH_RE = /\bAI\b|artificial.intelligen|machine.learning|deep.learning|LLM|GPT|NLP|computer.vision|data.scien|AGI|neural|人工智能|大模型|智能体|深度学习|prompt|anthropic|openai|deepseek|claude|gemini|midjourney|stable.diffusion|diffusion|transformer|agent|rag\b|vibe.codi|developer|engineer|programm|coding|coder|\bcode\b|software|frontend|backend|fullstack|devops|open.source|github|startup|saas|product.design|UX|UI\b|indie.dev|hacker|rust\b|python|javascript|typescript|react\b|vue\b|swift|golang|docker|kubernetes|linux|api\b|sdk\b|infra|cloud|serverless|database|程序员|工程师|开发者|独立开发|产品经理|技术|编程|互联网|科技|前端|后端|运维|架构|算法|开源|创业|tech|computer|silicon|chip|semiconductor|GPU|CUDA|robotics|自动驾驶|芯片|半导体|机器人|IoT|AR\b|VR\b|research|论文|paper|模型|训练|推理|fine.tun|vLLM|inference|deploy|embed|vector|retriev|search|vision|generat|segment|detect|recogni/i;

const MIN_FOLLOWERS = 50000;

function loadManualExcludes(dataDir: string): Set<string> {
  const p = join(dataDir, "following", "manual_exclude.json");
  if (!existsSync(p)) return new Set();
  const data = JSON.parse(readFileSync(p, "utf-8"));
  return new Set((data.usernames || []).map((u: string) => u.toLowerCase()));
}

function loadManualIncludes(dataDir: string): Set<string> {
  const p = join(dataDir, "following", "manual_include.json");
  if (!existsSync(p)) return new Set();
  const data = JSON.parse(readFileSync(p, "utf-8"));
  return new Set((data.usernames || []).map((u: string) => u.toLowerCase()));
}

function loadPending(dataDir: string): any[] {
  const p = join(dataDir, "following", "pending.json");
  if (!existsSync(p)) return [];
  const data = JSON.parse(readFileSync(p, "utf-8"));
  return data.users || [];
}

function savePending(dataDir: string, users: any[]) {
  const p = join(dataDir, "following", "pending.json");
  writeFileSync(p, JSON.stringify({
    updated: new Date().toISOString(), count: users.length, users,
  }, null, 2));
}

function isQualified(user: any, manualExcludes: Set<string>): boolean {
  if (manualExcludes.has(user.username.toLowerCase())) return false;
  const followers = user.public_metrics?.followers_count || 0;
  if (followers < MIN_FOLLOWERS) return false;
  const text = [user.description, user.name, user.username].filter(Boolean).join(" ");
  if (WEB3_RE.test(text)) return false;
  if (!TECH_RE.test(text)) return false;
  return true;
}

async function weeklySyncFollowing() {
  const config = loadConfig();
  const dataDir = getDataDir(parseDataDir());
  const followingDir = join(dataDir, "following");
  const tweetsDir = join(dataDir, "following-tweets");
  ensureDir(followingDir);
  ensureDir(tweetsDir);

  const dateStr = today();
  const manualExcludes = loadManualExcludes(dataDir);
  const manualIncludes = loadManualIncludes(dataDir);
  console.log(`=== Daily Following Sync (${dateStr}) ===\n`);
  console.log(`User: @${config.username}`);
  if (manualExcludes.size > 0) console.log(`Manual excludes: ${manualExcludes.size}`);
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

  // Step 3: Only fetch full user info for NEW IDs (not in cache)
  let newUsersData: any[] = [];
  if (newIds.length > 0) {
    console.log(`\n--- Step 3: Fetch info for ${newIds.length} new users ---`);
    // X API /users endpoint accepts up to 100 IDs per request
    const chunks: string[][] = [];
    const ids = newIds.map(u => u.id);
    for (let i = 0; i < ids.length; i += 100) {
      chunks.push(ids.slice(i, i + 100));
    }

    const userFields = "id,name,username,description,profile_image_url,public_metrics,created_at,location,url,verified";
    for (const chunk of chunks) {
      const json = await apiGet("/users", {
        ids: chunk.join(","),
        "user.fields": userFields,
      });
      if (json.data) {
        newUsersData.push(...json.data);
      }
      console.log(`  Fetched ${json.data?.length || 0} user profiles (batch)`);
    }

    // Add to cache
    for (const u of newUsersData) {
      cachedUsers.set(u.id, u);
    }
  }

  // Update latest.json with merged cache (current follows only)
  const updatedLatestUsers = currentFollowing
    .map(u => cachedUsers.get(u.id) || u)
    .filter(u => u.public_metrics); // only include users with full data
  writeFileSync(latestPath, JSON.stringify({
    date: dateStr, count: updatedLatestUsers.length, users: updatedLatestUsers
  }, null, 2));
  writeFileSync(join(followingDir, `${dateStr}.json`), JSON.stringify({
    date: dateStr, count: updatedLatestUsers.length, users: updatedLatestUsers
  }, null, 2));

  // Step 4: Evaluate new users for qualification → pending queue
  const newQualified = newUsersData.filter(u => isQualified(u, manualExcludes));
  console.log(`\nNew qualified (pending approval): ${newQualified.length}`);
  console.log(`New unqualified (skip): ${newUsersData.length - newQualified.length}`);

  // Load existing pending and merge (dedup by ID)
  const existingPending = loadPending(dataDir);
  const pendingIds = new Set(existingPending.map((u: any) => u.id));
  const trulyNewPending = newQualified.filter(u => !pendingIds.has(u.id) && !filteredIds.has(u.id));

  if (trulyNewPending.length > 0) {
    console.log("\n  New pending (awaiting approval):");
    for (const u of trulyNewPending) {
      u.detected_at = dateStr;
      const f = u.public_metrics?.followers_count || 0;
      const fStr = f >= 1000000 ? (f / 1000000).toFixed(1) + "M" : (f / 1000).toFixed(1) + "K";
      console.log(`    ? @${u.username.padEnd(22)} ${fStr.padStart(7)} | ${(u.description || "").substring(0, 50)}`);
    }
    savePending(dataDir, [...existingPending, ...trulyNewPending]);
    console.log(`\n  Pending total: ${existingPending.length + trulyNewPending.length}`);
    console.log(`  Review: bun scripts/manage-following.ts pending`);
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
    filter: { min_followers: MIN_FOLLOWERS, categories: ["AI", "Tech", "Developer"], exclude: ["web3", "politics", "media"] },
    count: updatedFiltered.length,
    users: updatedFiltered,
  }, null, 2));
  console.log(`\nFiltered list updated: ${updatedFiltered.length} users`);

  // Step 5: No longer auto-fetches tweets for new users.
  // Tweets are fetched when user is approved via: bun scripts/manage-following.ts approve <username>

  console.log("\nDone.");
}

await weeklySyncFollowing();
