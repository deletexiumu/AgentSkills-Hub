/**
 * Notion API client for pushing X tracker data.
 * Uses Internal Integration token for direct API access.
 */

import { loadConfig } from "./config";
import type { EnrichedTweet } from "./tweet-utils";

const NOTION_API = "https://api.notion.com/v1";
const NOTION_VERSION = "2022-06-28";

function getHeaders() {
  const config = loadConfig();
  const token = config.notion?.token;
  if (!token) throw new Error("No Notion token in config.json");
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION,
  };
}

function getDbId(): string {
  const config = loadConfig();
  const id = config.notion?.x_info_db_id;
  if (!id) throw new Error("No notion.x_info_db_id in config.json");
  return id;
}

// --- Database creation ---

/** Create new X资讯 database with full schema */
export async function createXInfoDatabase(parentPageId: string): Promise<string | null> {
  const resp = await fetch(`${NOTION_API}/databases`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({
      parent: { page_id: parentPageId },
      title: [{ text: { content: "X资讯" } }],
      properties: {
        标题: { title: {} },
        类型: {
          select: {
            options: [
              { name: "关注", color: "blue" },
              { name: "推文", color: "green" },
              { name: "书签", color: "yellow" },
            ],
          },
        },
        推文类型: {
          select: {
            options: [
              { name: "原创", color: "default" },
              { name: "长文", color: "purple" },
              { name: "线程", color: "orange" },
              { name: "回复", color: "pink" },
              { name: "引用", color: "red" },
            ],
          },
        },
        作者: { rich_text: {} },
        内容: { rich_text: {} },
        URL: { url: {} },
        点赞: { number: {} },
        转发: { number: {} },
        粉丝数: { number: {} },
        "Tweet ID": { rich_text: {} },
        conversation_id: { rich_text: {} },
        原文ID: { rich_text: {} },
        原文作者: { rich_text: {} },
        原文内容: { rich_text: {} },
        线程序号: { number: {} },
        发布时间: { date: {} },
        同步时间: { date: {} },
      },
    }),
  });

  if (!resp.ok) {
    const err = await resp.text();
    console.error(`Notion create DB failed: ${resp.status} ${err}`);
    return null;
  }

  const data = await resp.json();
  return data.id;
}

// --- Query helpers ---

/** Query database for existing pages by field value to avoid duplicates */
export async function queryExistingIds(
  type: "推文" | "书签" | "关注",
  idField: string,
  ids: string[]
): Promise<Set<string>> {
  if (ids.length === 0) return new Set();

  const dbId = getDbId();
  const existing = new Set<string>();

  for (let i = 0; i < ids.length; i += 100) {
    const chunk = ids.slice(i, i + 100);
    const filter: any = {
      and: [
        { property: "类型", select: { equals: type } },
        {
          or: chunk.map((id) => ({
            property: idField,
            rich_text: { equals: id },
          })),
        },
      ],
    };

    const resp = await fetch(`${NOTION_API}/databases/${dbId}/query`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ filter, page_size: 100 }),
    });

    if (!resp.ok) {
      console.error(`Notion query failed: ${resp.status} ${await resp.text()}`);
      continue;
    }

    const data = await resp.json();
    for (const page of data.results || []) {
      const val = page.properties?.[idField]?.rich_text?.[0]?.plain_text;
      if (val) existing.add(val);
    }
  }

  return existing;
}

// --- Page creation ---

async function createPage(properties: any): Promise<boolean> {
  const dbId = getDbId();

  const resp = await fetch(`${NOTION_API}/pages`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({
      parent: { database_id: dbId },
      properties,
    }),
  });

  if (!resp.ok) {
    const err = await resp.text();
    console.error(`Notion create failed: ${resp.status} ${err}`);
    return false;
  }
  return true;
}

// --- Property builders ---

function richText(content: string) {
  return { rich_text: [{ text: { content } }] };
}

/** Build Notion properties for an enriched tweet or bookmark */
function buildTweetProperties(
  type: "推文" | "书签",
  tweet: EnrichedTweet,
  authorUsername?: string
) {
  const displayText = (tweet.full_text || tweet.text || "").substring(0, 100);
  const author = authorUsername || tweet.author_username || "";
  const tweetUrl = `https://x.com/${author || "i"}/status/${tweet.id}`;

  const props: Record<string, any> = {
    标题: { title: [{ text: { content: displayText } }] },
    类型: { select: { name: type } },
    推文类型: { select: { name: tweet.tweet_type || "原创" } },
    作者: richText(`@${author}`),
    内容: richText((tweet.full_text || tweet.text || "").substring(0, 2000)),
    URL: { url: tweetUrl },
    点赞: { number: tweet.public_metrics?.like_count ?? null },
    转发: { number: tweet.public_metrics?.retweet_count ?? null },
    "Tweet ID": richText(tweet.id),
    同步时间: { date: { start: new Date().toISOString() } },
  };

  if (tweet.conversation_id) {
    props.conversation_id = richText(tweet.conversation_id);
  }
  if (tweet.created_at) {
    props.发布时间 = { date: { start: tweet.created_at } };
  }
  if (tweet.original_tweet) {
    props.原文ID = richText(tweet.original_tweet.id);
    if (tweet.original_tweet.author_username) {
      props.原文作者 = richText(`@${tweet.original_tweet.author_username}`);
    }
    if (tweet.original_tweet.text) {
      props.原文内容 = richText(tweet.original_tweet.text.substring(0, 2000));
    }
  }
  if (tweet.thread_position != null) {
    props.线程序号 = { number: tweet.thread_position };
  }

  return props;
}

/** Build Notion properties for a followed user */
function buildFollowingProperties(user: any) {
  const profileUrl = `https://x.com/${user.username}`;
  return {
    标题: {
      title: [{ text: { content: `${user.name} (@${user.username})` } }],
    },
    类型: { select: { name: "关注" } },
    作者: richText(`@${user.username}`),
    内容: richText((user.description || "").substring(0, 2000)),
    URL: { url: profileUrl },
    粉丝数: { number: user.public_metrics?.followers_count ?? null },
    "Tweet ID": richText(user.id),
    同步时间: { date: { start: new Date().toISOString() } },
  };
}

// --- Public sync functions ---

/** Sync following list to Notion (incremental: skip existing) */
export async function syncFollowingToNotion(users: any[]): Promise<number> {
  if (users.length === 0) return 0;

  const userIds = users.map((u) => u.id);
  const existing = await queryExistingIds("关注", "Tweet ID", userIds);
  const newUsers = users.filter((u) => !existing.has(u.id));

  if (newUsers.length === 0) return 0;

  let created = 0;
  for (const u of newUsers) {
    const props = buildFollowingProperties(u);
    if (await createPage(props)) created++;
  }
  return created;
}

/** Sync enriched tweets to Notion (incremental) */
export async function syncTweetsToNotion(
  tweets: { tweet: EnrichedTweet; authorUsername: string }[]
): Promise<number> {
  if (tweets.length === 0) return 0;

  const tweetIds = tweets.map((t) => t.tweet.id);
  const existing = await queryExistingIds("推文", "Tweet ID", tweetIds);
  const newTweets = tweets.filter((t) => !existing.has(t.tweet.id));

  if (newTweets.length === 0) return 0;

  let created = 0;
  for (const { tweet, authorUsername } of newTweets) {
    const props = buildTweetProperties("推文", tweet, authorUsername);
    if (await createPage(props)) created++;
  }
  return created;
}

// --- Page reading ---

/** Extract plain text from Notion rich_text array */
function extractRichText(richTexts: any[]): string {
  if (!richTexts) return "";
  return richTexts.map((rt: any) => rt.plain_text || "").join("");
}

/** Extract text content from a single block */
function extractBlockText(block: any): string {
  const type = block.type;
  if (!type) return "";

  const blockData = block[type];
  if (!blockData) return "";

  // Text-bearing block types
  const textTypes = [
    "paragraph", "heading_1", "heading_2", "heading_3",
    "bulleted_list_item", "numbered_list_item",
    "quote", "callout", "toggle", "code",
  ];

  if (textTypes.includes(type) && blockData.rich_text) {
    const prefix = type === "heading_1" ? "# " :
      type === "heading_2" ? "## " :
      type === "heading_3" ? "### " :
      type === "quote" ? "> " :
      type === "bulleted_list_item" ? "- " :
      type === "numbered_list_item" ? "1. " : "";
    return prefix + extractRichText(blockData.rich_text);
  }

  return "";
}

/** Recursively fetch all blocks for a page/block */
async function fetchAllBlocks(blockId: string): Promise<any[]> {
  const headers = getHeaders();
  const allBlocks: any[] = [];
  let startCursor: string | undefined;

  do {
    const url = new URL(`${NOTION_API}/blocks/${blockId}/children`);
    url.searchParams.set("page_size", "100");
    if (startCursor) url.searchParams.set("start_cursor", startCursor);

    const resp = await fetch(url.toString(), { headers });
    if (!resp.ok) {
      console.error(`Notion blocks fetch failed: ${resp.status} ${await resp.text()}`);
      break;
    }

    const data = await resp.json();
    for (const block of data.results || []) {
      allBlocks.push(block);
      // Recurse into blocks with children
      if (block.has_children) {
        const children = await fetchAllBlocks(block.id);
        allBlocks.push(...children);
      }
    }
    startCursor = data.has_more ? data.next_cursor : undefined;
  } while (startCursor);

  return allBlocks;
}

/** Read a Notion page's title and full text content */
export async function readPageContent(pageId: string): Promise<{
  title: string;
  content: string;
}> {
  const headers = getHeaders();

  // 1. Get page title
  const pageResp = await fetch(`${NOTION_API}/pages/${pageId}`, { headers });
  if (!pageResp.ok) {
    throw new Error(`Notion page fetch failed: ${pageResp.status} ${await pageResp.text()}`);
  }
  const page = await pageResp.json();

  let title = "";
  const titleProp = page.properties?.title || page.properties?.Name || page.properties?.["标题"];
  if (titleProp?.title) {
    title = extractRichText(titleProp.title);
  }

  // 2. Get all blocks and convert to text
  const blocks = await fetchAllBlocks(pageId);
  const lines = blocks.map(extractBlockText).filter(Boolean);

  return { title, content: lines.join("\n") };
}

/** Sync enriched bookmarks to Notion (incremental) */
export async function syncBookmarksToNotion(bookmarks: EnrichedTweet[]): Promise<number> {
  if (bookmarks.length === 0) return 0;

  const ids = bookmarks.map((b) => b.id);
  const existing = await queryExistingIds("书签", "Tweet ID", ids);
  const newBookmarks = bookmarks.filter((b) => !existing.has(b.id));

  if (newBookmarks.length === 0) return 0;

  let created = 0;
  for (const b of newBookmarks) {
    const props = buildTweetProperties("书签", b, b.author_username);
    if (await createPage(props)) created++;
  }
  return created;
}
