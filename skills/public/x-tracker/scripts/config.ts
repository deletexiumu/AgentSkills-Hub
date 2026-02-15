/**
 * Config management for x-tracker.
 *
 * Directory layout:
 *   {PROJECT_ROOT}/              — project root (parent of skill dir)
 *   {PROJECT_ROOT}/x-tracker/    — skill directory (SKILL.md, scripts, etc.)
 *   {PROJECT_ROOT}/data/         — default data storage
 *   {PROJECT_ROOT}/digests/      — digest output
 *   {PROJECT_ROOT}/config.json   — config file (gitignored)
 */

import { existsSync, readFileSync, writeFileSync } from "fs";
import { join, dirname } from "path";

export interface Config {
  client_id: string;
  client_secret?: string;
  access_token: string;
  refresh_token: string;
  token_expires_at: number;
  user_id: string;
  username: string;
  data_dir: string;
  redirect_uri?: string;
  notion?: {
    token?: string;
    x_info_db_id?: string;
    x_info_data_source_id?: string;
    following_db_id?: string;
    bookmarks_db_id?: string;
  };
}

/** Resolve the skill directory (where scripts/ lives) */
export function getSkillDir(): string {
  return dirname(dirname(Bun.main));
}

/** Resolve the project root (parent of skill dir) */
export function getProjectRoot(): string {
  return dirname(getSkillDir());
}

/** Config file path in project root */
export function getConfigPath(): string {
  return join(getProjectRoot(), "config.json");
}

/** Resolve data directory (default: {PROJECT_ROOT}/data/, overridable) */
export function getDataDir(overrideDir?: string): string {
  if (overrideDir) return overrideDir;
  try {
    const config = loadConfig();
    if (config.data_dir && config.data_dir !== "./data") return config.data_dir;
  } catch {}
  return join(getProjectRoot(), "data");
}

export function loadConfig(): Config {
  const configPath = getConfigPath();
  if (!existsSync(configPath)) {
    console.error(`Config not found: ${configPath}`);
    console.error('Run "bun scripts/auth.ts init" to create config.');
    process.exit(1);
  }
  return JSON.parse(readFileSync(configPath, "utf-8"));
}

export function saveConfig(config: Config): void {
  writeFileSync(getConfigPath(), JSON.stringify(config, null, 2));
}

/** Parse --data-dir flag from CLI args */
export function parseDataDir(): string | undefined {
  const idx = process.argv.indexOf("--data-dir");
  if (idx !== -1 && process.argv[idx + 1]) {
    return process.argv[idx + 1];
  }
  return undefined;
}

/** Ensure directory exists */
export function ensureDir(dir: string): void {
  const { mkdirSync } = require("fs");
  mkdirSync(dir, { recursive: true });
}

/** Today's date as YYYY-MM-DD */
export function today(): string {
  return new Date().toISOString().split("T")[0];
}
