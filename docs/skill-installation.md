# Skill 安装与加载（Claude / Codex）

说明：根据本仓库约定，skill 目录（`skills/**`）中不放安装指南类文档；因此本文档放在 `docs/`。

## Codex CLI（推荐）

以 `smart-data-query` 为例：

1) 校验 skill（建议每次改动后都跑一次）

```bash
python3 scripts/validate_skill.py skills/public/smart-data-query
```

2) 安装到 Codex 的个人技能目录（两种方式任选其一）

- 方式 A：复制（最简单）

```bash
mkdir -p ~/.codex/skills
cp -R skills/public/smart-data-query ~/.codex/skills/smart-data-query
```

- 方式 B：软链接（适合本地开发联调）

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)/skills/public/smart-data-query" ~/.codex/skills/smart-data-query
```

3) 加载/使用

- 重启 Codex，让它重新扫描 `~/.codex/skills/`。
- 在对话中显式触发：输入 `$smart-data-query` 或直接说明“使用 smart-data-query skill”。

## Claude（Claude Chat / Claude Code）

Claude 的安装/加载方式与 Codex 不同，常见有两类：
- **本地目录安装（开发/自用最常见）**：把 skill 文件夹放到 `~/.claude/skills/`，重启 Claude（或对应客户端）即可加载。
- **官方分发/托管**：Claude Code 插件、Claude.ai 上传、Claude API 上传/引用。

### 本地目录安装（推荐用于本地开发/三方模型兼容）

以 `smart-data-query` 为例：

1) 校验（建议）

```bash
python3 scripts/validate_skill.py skills/public/smart-data-query
```

2) 安装到 `~/.claude/skills/`（两种方式任选其一）

- 方式 A：复制

```bash
mkdir -p ~/.claude/skills
cp -R skills/public/smart-data-query ~/.claude/skills/smart-data-query
```

- 方式 B：软链接（适合开发联调）

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skills/public/smart-data-query" ~/.claude/skills/smart-data-query
```

3) 重启 Claude Code / Claude Desktop / 你使用的三方客户端，使其重新扫描 `~/.claude/skills/`。

4) 使用：在对话中提到 skill 名称或按客户端的“skills 触发语法”显式启用即可。

### Claude Code（插件方式，用于分发）

本仓库已提供 Claude Code 插件清单：`.claude-plugin/marketplace.json`（marketplace 名称：`agentskills`，插件名：`smart-data-query`）。

1) 在 Claude Code 中把本仓库注册为 marketplace（要求该仓库可被 Claude Code 访问，例如 GitHub 仓库）：

```
/plugin marketplace add <owner>/<repo>
```

2) 安装插件：

```
/plugin install smart-data-query@agentskills
```

3) 使用：
- 在对话中直接提到 skill 名称即可，例如“使用 `smart-data-query` 做智能问数”。

### Claude.ai（上传/使用 Skills）

按官方说明在 Claude.ai 中上传或启用 skills（入口与权限以官方帮助文档为准）：
- `https://support.claude.com/en/articles/12512180-using-skills-in-claude`

为了便于上传，建议先打包：

```bash
python3 scripts/package_skill.py skills/public/smart-data-query dist
```

产物是 `dist/smart-data-query.skill`（本质是 zip 包）；如界面只接受 `.zip`，可将其重命名为 `.zip` 后再上传。

### Claude API（上传 Skills）

按官方 Skills API 文档上传并在请求中引用：
- `https://docs.claude.com/en/api/skills-guide`

文档中明确支持“上传目录”或“上传 zip 文件”的方式。
