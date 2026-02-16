#!/usr/bin/env bun
/**
 * OAuth 2.0 PKCE authentication for X API v2.
 *
 * Usage:
 *   bun scripts/auth.ts init     — Initialize config with client credentials
 *   bun scripts/auth.ts login    — Start OAuth flow, get tokens
 *   bun scripts/auth.ts refresh  — Manually refresh access token
 *   bun scripts/auth.ts status   — Check current auth status
 */

import { createHash, randomBytes } from "crypto";
import { existsSync, writeFileSync, readFileSync } from "fs";
import { getConfigPath, getSkillDir, loadConfig, saveConfig, type Config } from "./config";

const DEFAULT_REDIRECT_URI = "http://127.0.0.1:18923/callback";
const LOCAL_CALLBACK_PORT = 18923;
const SCOPES = "tweet.read tweet.write users.read follows.read bookmark.read offline.access";

async function initConfig() {
  const configPath = getConfigPath();
  if (existsSync(configPath)) {
    console.log(`Config already exists: ${configPath}`);
    console.log('Run "bun scripts/auth.ts login" to authenticate.');
    return;
  }

  console.log("=== X Tracker Config Initialization ===\n");
  console.log("Enter your X API OAuth 2.0 Client ID:");
  const clientId = (await readLine()).trim();

  if (!clientId) {
    console.error("Client ID is required.");
    process.exit(1);
  }

  const config: Config = {
    client_id: clientId,
    access_token: "",
    refresh_token: "",
    token_expires_at: 0,
    user_id: "",
    username: "",
    data_dir: "./data",
  };

  writeFileSync(configPath, JSON.stringify(config, null, 2));
  console.log(`\nConfig saved to: ${configPath}`);
  console.log('Next: run "bun scripts/auth.ts login" to authenticate.');
}

async function login() {
  const config = loadConfig();
  if (!config.client_id) {
    console.error('No client_id in config. Run "bun scripts/auth.ts init" first.');
    process.exit(1);
  }

  const redirectUri = config.redirect_uri || DEFAULT_REDIRECT_URI;

  // Generate PKCE challenge
  const codeVerifier = randomBytes(32).toString("base64url");
  const codeChallenge = createHash("sha256")
    .update(codeVerifier)
    .digest("base64url");
  const state = randomBytes(16).toString("hex");

  // Build authorization URL
  const authUrl = new URL("https://x.com/i/oauth2/authorize");
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("client_id", config.client_id);
  authUrl.searchParams.set("redirect_uri", redirectUri);
  authUrl.searchParams.set("scope", SCOPES);
  authUrl.searchParams.set("state", state);
  authUrl.searchParams.set("code_challenge", codeChallenge);
  authUrl.searchParams.set("code_challenge_method", "S256");

  const url = authUrl.toString();
  console.log("\n=== OAuth 2.0 Authorization ===\n");
  console.log("Opening browser...\n");
  console.log(url);

  // Auto-open browser
  const { spawn } = await import("child_process");
  spawn("open", [url], { stdio: "ignore", detached: true }).unref();

  console.log(`\nWaiting for callback on 127.0.0.1:${LOCAL_CALLBACK_PORT} ...\n`);

  // Start local callback server
  const authCode = await waitForCallback(state);

  // Exchange code for token
  console.log("Exchanging authorization code for tokens...");
  const tokenHeaders: Record<string, string> = {
    "Content-Type": "application/x-www-form-urlencoded",
  };
  if (config.client_secret) {
    tokenHeaders["Authorization"] = `Basic ${Buffer.from(`${config.client_id}:${config.client_secret}`).toString("base64")}`;
  }
  const tokenResp = await fetch("https://api.x.com/2/oauth2/token", {
    method: "POST",
    headers: tokenHeaders,
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code: authCode,
      redirect_uri: redirectUri,
      client_id: config.client_id,
      code_verifier: codeVerifier,
    }),
  });

  if (!tokenResp.ok) {
    const err = await tokenResp.text();
    console.error(`Token exchange failed (${tokenResp.status}): ${err}`);
    process.exit(1);
  }

  const tokenData = await tokenResp.json();
  config.access_token = tokenData.access_token;
  config.refresh_token = tokenData.refresh_token;
  config.token_expires_at =
    Math.floor(Date.now() / 1000) + tokenData.expires_in;

  // Try to get user info (requires users.read scope)
  const userResp = await fetch("https://api.x.com/2/users/me", {
    headers: { Authorization: `Bearer ${config.access_token}` },
  });
  if (userResp.ok) {
    const userData = await userResp.json();
    config.user_id = userData.data.id;
    config.username = userData.data.username;
  } else {
    console.log("Skipped user info fetch (users.read scope not available).");
  }

  saveConfig(config);
  console.log(`\nAuthenticated as @${config.username || "unknown"} (ID: ${config.user_id || "unknown"})`);
  console.log("Tokens saved to config.json");
}

async function refresh() {
  const config = loadConfig();
  if (!config.refresh_token) {
    console.error('No refresh token. Run "bun scripts/auth.ts login" first.');
    process.exit(1);
  }

  const refreshHeaders: Record<string, string> = {
    "Content-Type": "application/x-www-form-urlencoded",
  };
  if (config.client_secret) {
    refreshHeaders["Authorization"] = `Basic ${Buffer.from(`${config.client_id}:${config.client_secret}`).toString("base64")}`;
  }
  const resp = await fetch("https://api.x.com/2/oauth2/token", {
    method: "POST",
    headers: refreshHeaders,
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: config.refresh_token,
      client_id: config.client_id,
    }),
  });

  if (!resp.ok) {
    const err = await resp.text();
    console.error(`Refresh failed (${resp.status}): ${err}`);
    process.exit(1);
  }

  const data = await resp.json();
  config.access_token = data.access_token;
  config.refresh_token = data.refresh_token;
  config.token_expires_at = Math.floor(Date.now() / 1000) + data.expires_in;
  saveConfig(config);
  console.log("Token refreshed successfully.");
  console.log(
    `Expires at: ${new Date(config.token_expires_at * 1000).toISOString()}`
  );
}

async function status() {
  const config = loadConfig();
  const now = Math.floor(Date.now() / 1000);
  const expiresIn = config.token_expires_at - now;

  console.log("=== Auth Status ===");
  console.log(`User: @${config.username} (ID: ${config.user_id})`);
  console.log(`Client ID: ${config.client_id}`);
  console.log(
    `Token expires: ${new Date(config.token_expires_at * 1000).toISOString()}`
  );
  if (expiresIn > 0) {
    console.log(`Token valid for: ${Math.floor(expiresIn / 60)} minutes`);
  } else {
    console.log("Token EXPIRED — will auto-refresh on next API call");
  }
  console.log(`Data dir: ${config.data_dir}`);
}

/** Wait for OAuth callback */
function waitForCallback(expectedState: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const server = Bun.serve({
      port: LOCAL_CALLBACK_PORT,
      fetch(req) {
        const url = new URL(req.url);
        if (url.pathname !== "/callback" && url.pathname !== "/x-callback") {
          return new Response("Not found", { status: 404 });
        }

        const code = url.searchParams.get("code");
        const state = url.searchParams.get("state");
        const error = url.searchParams.get("error");

        if (error) {
          server.stop();
          reject(new Error(`OAuth error: ${error}`));
          return new Response(`Authorization failed: ${error}`, { status: 400 });
        }

        if (state !== expectedState) {
          server.stop();
          reject(new Error("State mismatch"));
          return new Response("State mismatch", { status: 400 });
        }

        if (!code) {
          server.stop();
          reject(new Error("No authorization code received"));
          return new Response("No code received", { status: 400 });
        }

        // Delay stop to ensure response is sent
        setTimeout(() => {
          server.stop();
          resolve(code);
        }, 100);

        return new Response(
          "<html><body><h1>Authorization successful!</h1><p>You can close this tab.</p></body></html>",
          { headers: { "Content-Type": "text/html" } }
        );
      },
    });
  });
}

/** Simple line reader from stdin */
function readLine(): Promise<string> {
  return new Promise((resolve) => {
    const chunks: Buffer[] = [];
    process.stdin.resume();
    process.stdin.on("data", (chunk) => {
      chunks.push(chunk);
      if (chunk.includes(10)) {
        // newline
        process.stdin.pause();
        resolve(Buffer.concat(chunks).toString());
      }
    });
  });
}

// CLI dispatch
const command = process.argv[2];
switch (command) {
  case "init":
    await initConfig();
    break;
  case "login":
    await login();
    break;
  case "refresh":
    await refresh();
    break;
  case "status":
    await status();
    break;
  default:
    console.log("Usage: bun scripts/auth.ts <init|login|refresh|status>");
    process.exit(1);
}
