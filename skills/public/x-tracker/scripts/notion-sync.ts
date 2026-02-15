#!/usr/bin/env bun
/**
 * Sync X tracker data to Notion databases.
 *
 * This script generates JSON payloads and instructions for Claude to execute
 * via Notion MCP tools. It does NOT directly call Notion API — instead it
 * outputs structured data that Claude can use with mcp__plugin_Notion_notion tools.
 *
 * Usage:
 *   bun scripts/notion-sync.ts following [--data-dir /custom/path]
 *   bun scripts/notion-sync.ts bookmarks [--data-dir /custom/path]
 *   bun scripts/notion-sync.ts all [--data-dir /custom/path]
 */

import { existsSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";
import { loadConfig, getDataDir, parseDataDir, ensureDir } from "./config";

interface NotionPage {
  properties: Record<string, any>;
}

async function syncToNotion(type: "following" | "bookmarks" | "all") {
  const config = loadConfig();
  const dataDir = getDataDir(parseDataDir());

  console.log(`=== Notion Sync (${type}) ===\n`);

  if (type === "following" || type === "all") {
    await prepareFollowingSync(dataDir, config);
  }

  if (type === "bookmarks" || type === "all") {
    await prepareBookmarksSync(dataDir, config);
  }
}

async function prepareFollowingSync(dataDir: string, config: any) {
  const latestPath = join(dataDir, "following", "latest.json");
  if (!existsSync(latestPath)) {
    console.log("No following data. Run sync-following.ts first.");
    return;
  }

  const data = JSON.parse(readFileSync(latestPath, "utf-8"));
  const users = data.users || [];
  console.log(`Preparing ${users.length} following records for Notion...\n`);

  const dbId = config.notion?.following_db_id;
  if (!dbId) {
    console.log("WARNING: No following_db_id in config.");
    console.log("Set notion.following_db_id in config.json, or let Claude create the database.\n");
  }

  // Generate Notion pages payload
  const pages: NotionPage[] = users.map((u: any) => ({
    properties: {
      Name: u.name || u.username,
      Username: u.username,
      "User ID": u.id,
      Bio: u.description || "",
      "Profile Image": u.profile_image_url || "",
      Followers: u.public_metrics?.followers_count ?? 0,
      Following: u.public_metrics?.following_count ?? 0,
      Tweets: u.public_metrics?.tweet_count ?? 0,
      Location: u.location || "",
      Website: u.url || "",
      Status: "active",
      "First Seen": data.date,
      "Last Seen": data.date,
      "Created At": u.created_at?.split("T")[0] || "",
    },
  }));

  const outputPath = join(dataDir, "following", "notion-payload.json");
  writeFileSync(
    outputPath,
    JSON.stringify(
      {
        database_id: dbId || "TO_BE_SET",
        sync_date: data.date,
        total: pages.length,
        pages,
      },
      null,
      2
    )
  );

  console.log(`Following Notion payload: ${outputPath}`);
  console.log(`Records: ${pages.length}`);
  if (dbId) {
    console.log(`Target DB: ${dbId}`);
  }
}

async function prepareBookmarksSync(dataDir: string, config: any) {
  const latestPath = join(dataDir, "bookmarks", "latest.json");
  if (!existsSync(latestPath)) {
    console.log("No bookmarks data. Run sync-bookmarks.ts first.");
    return;
  }

  const data = JSON.parse(readFileSync(latestPath, "utf-8"));
  const tweets = data.tweets || [];
  console.log(`Preparing ${tweets.length} bookmark records for Notion...\n`);

  const dbId = config.notion?.bookmarks_db_id;
  if (!dbId) {
    console.log("WARNING: No bookmarks_db_id in config.");
    console.log("Set notion.bookmarks_db_id in config.json, or let Claude create the database.\n");
  }

  const pages: NotionPage[] = tweets.map((t: any) => {
    const contentTitle = (t.text || "").substring(0, 100);
    return {
      properties: {
        Content: contentTitle,
        "Full Text": t.text || "",
        "Tweet URL": `https://x.com/${t.author_username || "i"}/status/${t.id}`,
        "Tweet ID": t.id,
        Author: t.author_username || "",
        "Author Name": t.author_name || "",
        Category: [], // To be filled by AI classification
        Metrics: t.public_metrics
          ? `❤️${t.public_metrics.like_count} 🔄${t.public_metrics.retweet_count} 💬${t.public_metrics.reply_count}`
          : "",
        "Has Media": !!(t.attachments?.media_keys?.length > 0),
        "Bookmarked Date": data.date,
        "Tweet Date": t.created_at?.split("T")[0] || "",
        "Synced At": new Date().toISOString().split("T")[0],
      },
    };
  });

  const outputPath = join(dataDir, "bookmarks", "notion-payload.json");
  writeFileSync(
    outputPath,
    JSON.stringify(
      {
        database_id: dbId || "TO_BE_SET",
        sync_date: data.date,
        total: pages.length,
        pages,
      },
      null,
      2
    )
  );

  console.log(`Bookmarks Notion payload: ${outputPath}`);
  console.log(`Records: ${pages.length}`);
  if (dbId) {
    console.log(`Target DB: ${dbId}`);
  }
}

// CLI
const type = process.argv[2] as "following" | "bookmarks" | "all";
if (!["following", "bookmarks", "all"].includes(type)) {
  console.log("Usage: bun scripts/notion-sync.ts <following|bookmarks|all>");
  process.exit(1);
}

await syncToNotion(type);
