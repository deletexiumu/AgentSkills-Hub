# AgentSkills-Hub

汎用的なエージェントスキル開発・管理リポジトリ：仕様、テンプレート、スクリプトツールを提供し、配布可能なスキルを素早く作成、検証、パッケージ化できます。

**[English](README.md) | [中文](README_zh.md)**

## 主な特徴

- **多言語サポート（中/英/日）**：すべての公開スキルが中国語、英語、日本語出力をサポート
- **ゼロ依存で実行**：コア機能はPython 3.10+のみで動作、サードパーティパッケージ不要
- **グレースフルデグラデーション**：LLM/ネットワークなしでも動作；オプションでAI翻訳機能
- **本番環境対応テンプレート**：実証済みのスキルテンプレート、i18nサポート内蔵

## インストール

### ワンラインインストール（推奨）

[skills.sh](https://skills.sh) を使用して直接インストール：

```bash
# このリポジトリのすべてのスキルをインストール
npx skills add deletexiumu/AgentSkills-Hub

# または特定のスキルをインストール
npx skills add deletexiumu/AgentSkills-Hub/ai-news-digest
npx skills add deletexiumu/AgentSkills-Hub/smart-data-query
npx skills add deletexiumu/AgentSkills-Hub/x-ai-digest
```

### 手動インストール

```bash
# Claude Code の場合
mkdir -p ~/.claude/skills
git clone https://github.com/deletexiumu/AgentSkills-Hub.git
cp -R AgentSkills-Hub/skills/public/* ~/.claude/skills/

# Codex の場合
mkdir -p ~/.codex/skills
cp -R AgentSkills-Hub/skills/public/* ~/.codex/skills/
```

詳細：`docs/skill-installation.md` を参照。

---

## クイックスタート（独自スキルの作成）

新しいスキルを作成（例：`skills/public` に配置）：

```bash
python3 scripts/init_skill.py my-skill --path skills/public --resources scripts,references,assets
```

検証とパッケージ化：

```bash
python3 scripts/validate_skill.py skills/public/my-skill
python3 scripts/validate_i18n.py skills/public/my-skill   # i18n検証
python3 scripts/package_skill.py skills/public/my-skill dist
```

詳細なワークフローと仕様については：`docs/skill-workflow.md` を参照。

---

## 利用可能なスキル

| スキル | 説明 | ハイライト |
|--------|------|-----------|
| `ai-news-digest` | マルチソースAIニュース集約とダイジェスト生成 | 20以上のソース、自動重複排除、5カテゴリ、画像エクスポート |
| `smart-data-query` | スマートDWH Q&A、実行可能なSQL出力 | 自動イテレーション、ビジネス質問票、Q&Aログ |
| `x-ai-digest` | XプラットフォームAIニューススクレイパー | ブラウザ自動化、シェアカード生成 |

---

## ai-news-digest

> **複数ソースからのAIニュース収集と要約生成、重複排除・分類・出典追跡機能付き。**

20以上のAI分野の情報源（OpenAI、Anthropic、DeepMind、Google AI、TechCrunch、Hugging Faceなど）から自動的にニュースを取得し、インテリジェントに重複排除・分類して、Markdown/JSON/画像形式のデイリーブリーフィングを生成します。

### なぜ ai-news-digest を選ぶ？

| メリット | 説明 |
|---------|------|
| **20以上の厳選ソース** | OpenAI、Anthropic、DeepMind、Google AI、Meta AI、TechCrunch、Hugging Face、arXivなど |
| **スマート重複排除** | 複数ソースからの同一ニュースを自動マージ、相互参照を保持 |
| **5つのテーマカテゴリ** | 研究 / 製品 / オープンソース / 資金調達 / 政策 - 自動分類 |
| **多言語出力** | 中国語、英語、日本語 - `--lang zh/en/ja` を使用 |
| **自然言語による時間指定** | "today"、"昨日"、"2026-01-20" - すべてサポート |
| **ゼロ依存** | コア機能はPython 3.10+のみ必要 |
| **複数の出力形式** | Markdown、JSON、シェア可能なPNG画像 |
| **グレースフルデグラデーション** | LLMなしでも動作；オプションでAI翻訳（Anthropic/OpenAI） |

### 使用例

**Claude Code / Codex での会話：**

```
# 中文
"用 ai-news-digest 生成今天的 AI 资讯简报"

# English
"Use ai-news-digest to generate today's AI news in English"

# 日本語
"ai-news-digest で今日のAIニュース要約を日本語で作成して"
```

**CLI：**

```bash
cd skills/public/ai-news-digest/scripts

# デフォルト（中国語）
python run.py --day today

# 英語出力
python run.py --day yesterday --lang en

# 日本語出力
python run.py --day 今日 --lang ja

# シェア画像をエクスポート
python run.py --day today --format image --image-preset landscape
```

### インストール

```bash
# ワンラインインストール（推奨）
npx skills add deletexiumu/AgentSkills-Hub/ai-news-digest

# または手動でClaude Codeにインストール
mkdir -p ~/.claude/skills
cp -R skills/public/ai-news-digest ~/.claude/skills/ai-news-digest
```

詳細：[ai-news-digest/SKILL.md](skills/public/ai-news-digest/SKILL.md)

---

## smart-data-query

> **スマートデータクエリスキル：ビジネス要件+DWHカタログを入力し、実行可能なSQLクエリを出力。**

自然言語のビジネス要件をプロダクション対応のSQLクエリに変換、データウェアハウスカタログをインテリジェントに検索して実現。

### なぜ smart-data-query を選ぶ？

| メリット | 説明 |
|---------|------|
| **カタログ対応** | ADS/DWS/DWTテーブル、DDL、ETLスクリプトからインデックスを構築 |
| **段階的ロード** | 関連テーブルのみをロード、コンテキストを最小化 |
| **マルチダイアレクト対応** | Hive、SparkSQL、GaussDB - 構文の違いを処理 |
| **ビジネス質問票** | 構造化テンプレートで要件の漏れを防止 |
| **Q&Aログ** | 各セッションを記録、イテレーションと改善に活用 |
| **自動イテレーション** | Badケースが質問票テンプレートの自動最適化をトリガー |
| **静的検証** | フィールド存在性、JOINキー、パーティションプルーニングをチェック |

### 使用例

```
# 中文
"用 smart-data-query：查最近7天各渠道新增用户数"

# English
"Use smart-data-query: SQL for daily active users by channel"

# 日本語
"smart-data-query：チャネル別DAUを取得するSQLを作成して"
```

詳細：[smart-data-query/SKILL.md](skills/public/smart-data-query/SKILL.md)

---

## x-ai-digest

> **Xプラットフォームの「おすすめ」からAI関連投稿を収集し、日次要約と返信提案を生成。**

ログイン済みブラウザに接続し、Xの推奨フィードからAI関連の投稿をスクレイプ、構造化されたデイリーブリーフィングとインテリジェントな返信提案を生成。

### なぜ x-ai-digest を選ぶ？

| メリット | 説明 |
|---------|------|
| **リアルタイムXコンテンツ** | ライブの「おすすめ」フィードをスクレイプ、キャッシュデータではない |
| **AIトピックフィルタリング** | AI関連コンテンツをスマートなキーワードマッチングで抽出 |
| **返信提案** | AI生成の返信アイデア、元の投稿の言語で |
| **シェアカード生成** | WeChat/SNSシェア用の美しいPNGカード |
| **ブラウザ統合** | 既存のログインを使用、APIキー不要 |
| **多言語出力** | 要約と提案は中/英/日をサポート |

### 使用例

```
# 中文
"用 x-ai-digest 抓取今天的 AI 热点"

# English
"Use x-ai-digest to summarize AI posts from yesterday in English"

# 日本語
"x-ai-digest で今日のAI関連投稿を日本語で要約して"
```

詳細：[x-ai-digest/SKILL.md](skills/public/x-ai-digest/SKILL.md)

---

## i18n 仕様

すべての公開スキルは [i18n仕様](docs/skill-i18n.md) に従います：

- **Frontmatter**：`description: [ZH] 中文；[EN] English；[JA] 日本語`
- **呼び出し例ブロック**：3言語での呼び出し例
- **CLIパラメータ**：`--lang auto|zh|en|ja`
- **自然言語**：3言語での時間表現（today/今天/今日）

i18n準拠を検証：

```bash
python scripts/validate_i18n.py skills/public/ai-news-digest
```

---

## コントリビューション

1. このリポジトリをフォーク
2. `scripts/init_skill.py` を使用してスキルを作成
3. `docs/skill-i18n.md` のi18n仕様に従う
4. `validate_skill.py` と `validate_i18n.py` で検証
5. プルリクエストを提出

## ライセンス

MIT
