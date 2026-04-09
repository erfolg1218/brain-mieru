# brain-mieru 技術仕様書

**プロジェクト名：** brain-mieru（脳の可視化）  
**バージョン：** 1.0.0  
**作成日：** 2026年04月09日  
**分類：** 個人用AIエージェント / 情報自動収集システム  

---

## 1. プロジェクト概要

### 1.1 目的

プラント・公共事業の電気設備工事に従事する技術者が、業務に直結する情報（AI動向・補助金・官公庁発表）を毎日自動収集・整理・通知する個人用「情報参謀システム」を構築する。

### 1.2 課題設定

| 課題 | Before | After |
|------|--------|-------|
| 情報収集 | 毎日手動でX・官公庁サイトを巡回 | 自動収集・LINE通知 |
| 補助金チェック | 見落としが多い・不定期 | 15サイトを毎日09:00に自動監視 |
| ナレッジ管理 | .mdファイルがCドライブに散在 | Obsidian Vaultに自動整理・リンク生成 |
| 情報の鮮度 | 気づいた時には申請期限切れ | 申請期限付きでNotionに自動格納 |

### 1.3 設計思想

```
「見に行く」から「勝手に届く」へ
情報収集を仕組みに任せ、判断だけに集中する
```

---

## 2. システムアーキテクチャ

### 2.1 全体構成図

```
┌─────────────────────────────────────────────────────────┐
│                   情報収集源                              │
│  X（旧Twitter）/ 官公庁サイト / 補助金ポータル            │
└──────────────────┬──────────────────────────────────────┘
                   │ Playwright (headless Chromium)
                   ▼
┌─────────────────────────────────────────────────────────┐
│              Claude API（分析・要約・分類）               │
│           claude-haiku-4-5 / claude-sonnet-4-6           │
└───┬───────────────┬──────────────────┬──────────────────┘
    │               │                  │
    ▼               ▼                  ▼
┌───────┐    ┌──────────┐    ┌──────────────────┐
│ LINE  │    │  Notion  │    │ Obsidian Vault   │
│ 即時  │    │  DB格納  │    │ .mdファイル保存   │
│ 通知  │    │ 重複排除 │    │ 自動リンク生成   │
└───────┘    └──────────┘    └──────────────────┘
```

### 2.2 サブシステム構成

| サブシステム | スクリプト | 実行頻度 | 役割 |
|-------------|-----------|---------|------|
| x-briefing | `x-briefing/main.py` | 08:00 / 20:00 | X投稿収集・要約・通知 |
| hojokin | `hojokin/main.py` | 09:00 | 補助金情報収集・格納 |
| obsidian-linker | `obsidian-linker/main.py` | 23:00 | ナレッジリンク自動更新 |

### 2.3 ツール役割分担

| ツール | 役割 | 現場アナロジー |
|--------|------|--------------|
| Claude API | 分析・要約・分類エンジン | 段取りを考える番頭 |
| Playwright | Webスクレイピング | 現場を巡回する作業員 |
| Notion | 構造化データストア | 図面・仕様書の棚 |
| Obsidian | ナレッジグラフ | 頭の中の段取り図 |
| LINE Messaging API | プッシュ通知 | 現場の無線 |
| Windows タスクスケジューラ | ジョブスケジューラ | 朝礼のタイムキーパー |

---

## 3. 技術スタック

### 3.1 言語・ランタイム

| 技術 | バージョン | 用途 |
|------|-----------|------|
| Python | 3.12 | メイン実装言語 |
| Windows PowerShell | 5.1 | タスクスケジューラ設定 |

### 3.2 主要ライブラリ

| ライブラリ | バージョン | 用途 |
|-----------|-----------|------|
| `playwright` | latest | headless Chromiumによるスクレイピング |
| `anthropic` | latest | Claude API クライアント |
| `python-dotenv` | latest | .env管理 |
| `pandas` | latest | accounts.xlsx読み込み・データ処理 |
| `openpyxl` | latest | Excel(.xlsx)操作 |
| `requests` | latest | Notion API REST通信 |

### 3.3 外部API・サービス

| サービス | 用途 | 認証方式 |
|---------|------|---------|
| Anthropic Claude API | テキスト分析・要約・重要度判定 | APIキー（Bearer） |
| LINE Messaging API | Push通知送信 | Channel Access Token |
| Notion API | DBページ作成・重複チェック | Internal Integration Token |

### 3.4 インフラ

| 要素 | 構成 |
|------|------|
| 実行環境 | Windows 11 PC（オンプレミス） |
| スケジューラ | Windows タスクスケジューラ（4ジョブ） |
| ストレージ | Cドライブ（ローカル）＋ Googleドライブ（ストリーミング） |
| バージョン管理 | GitHub（プライベートリポジトリ） |

---

## 4. サブシステム詳細仕様

### 4.1 x-briefing（Xブリーフィングシステム）

#### 概要
X（旧Twitter）の指定アカウントを巡回し、直近24時間の投稿をClaude APIで要約・重要度判定してLINEに通知する。

#### 処理フロー

```
accounts.xlsx 読み込み（active=true のみ）
    ↓
Playwright で各アカウントページへアクセス（非ログイン）
    ↓
直近24時間の投稿を最大5件スクレイピング（テキスト・URL・タイムスタンプ）
    ↓
Claude API (claude-haiku-4-5) で以下を生成：
  - 日本語要約（100文字以内）
  - 重要度判定（高/中/低）
    ↓
LINE Messaging API でPush通知（重要度別フォーマット）
    ↓
output/YYYY-MM-DD-{morning|evening}.md に保存
    ↓
Notion X情報DB に格納（URL重複チェック）
```

#### 監視アカウント設定（accounts.xlsx）

```
列構成：account / category / priority / active / memo / added_date
```

| アカウント | カテゴリ | 優先度 |
|-----------|---------|--------|
| @AnthropicAI | AI公式 | 高 |
| @OpenAI | AI公式 | 高 |
| @claudeai | AI公式 | 高 |
| @elonmusk | テック | 高 |
| @sundarpichai | テック | 高 |
| @shota7180 | AI日本語 | 中 |
| @ManusAI_JP | AI日本語 | 中 |
| @masahirochaen | AI日本語 | 中 |
| @yanagi_shiftai | AI日本語 | 中（ログイン壁・要対応） |

#### LINE通知フォーマット

```
📡 Xブリーフィング 2026-04-09 08:00

🔴 重要
[AI公式] @AnthropicAI：Claude 4を正式リリース

🟡 注目
[テック] @sundarpichai：Gemini 2.0の新機能を公開

🟢 参考
[AI日本語] @shota7180：プロンプト設計の最新手法を紹介
```

#### Notion X情報DB スキーマ

| プロパティ | 型 | 説明 |
|----------|-----|------|
| 名前 | title | 投稿の要約テキスト |
| アカウント | text | @アカウント名 |
| カテゴリ | select | AI公式 / テック / AI日本語 等 |
| 重要度 | select | 高 / 中 / 低 |
| 要約 | text | Claude APIによる日本語要約 |
| 取得日 | date | スクレイピング実行日 |
| 元URL | url | 元投稿のURL（重複チェックキー） |

---

### 4.2 hojokin（補助金スクレイピングシステム）

#### 概要
15の補助金サイトを毎日09:00に自動巡回し、電気設備工事・プラント向けの情報をClaude APIでフィルタリングしてNotionに格納・LINEに通知する。

#### 処理フロー

```
sites.csv 読み込み（active=true のみ・15サイト）
    ↓
カテゴリ別スクレイピング関数で並行取得
  - scrape_meti()       経産省（タイムアウト60秒）
  - scrape_mlit()       国交省
  - scrape_nedo()       NEDO
  - scrape_jichitai()   自治体汎用（1サイト5件上限）
    ↓
Claude API で優先フィルタリング
  優先抽出：電気設備工事・プラント設備・建設業・省エネ・中小企業向け
  除外：農業・観光・飲食・医療等の無関係補助金
    ↓
LINE Push通知（カテゴリ別フォーマット）
    ↓
output/YYYY-MM-DD-hojokin.md に保存
    ↓
Notion 補助金マスターDB に格納（URL重複チェック）
    ↓
Obsidian Vault/hojokin/ に保存
```

#### 監視サイト一覧（sites.csv）

| サイト名 | カテゴリ | 優先度 | 実績件数 |
|---------|---------|--------|---------|
| Jグランツ | 補助金ポータル | 高 | 1件 |
| ミラサポplus | 中小企業庁 | 高 | 47件 |
| デジタル庁 | デジタル庁 | 中 | 3件 |
| 経産省_公募情報 | 経産省 | 高 | 変動 |
| 国交省_公募情報 | 国交省 | 高 | 13件 |
| NEDO_公募 | NEDO | 高 | 12件 |
| 東京都〜福岡県（9自治体） | 自治体 | 中 | 各1-5件 |

#### Notion 補助金マスターDB スキーマ

| プロパティ | 型 | 説明 |
|----------|-----|------|
| 名前 | title | 補助金・事業名 |
| 事業内容 | text | 対象となる事業内容 |
| 公式URL | url | 公式ページURL（重複チェックキー） |
| 申請期限 | date | 申請締切日 |
| 補助金額 | text | 上限金額 |
| 補助率 | text | 補助率（例：2/3以内） |
| 対象業種 | text | 対象となる業種 |
| 概要 | text | Claude APIによる要約 |

---

### 4.3 obsidian-linker（Obsidian自動リンク更新システム）

#### 概要
Obsidian Vault内の.mdファイルを毎日23:00に差分検知し、関連ノート間に `[[リンク]]` を自動生成・更新する。

#### 処理フロー

```
state.json で前回実行時のmtimeを読み込み
    ↓
Vault内全.mdファイルのmtimeを比較 → 新規・更新ファイルを抽出
    ↓
Claude API (claude-haiku-4-5) に以下を渡す：
  - 対象ファイルの内容
  - Vault全体のノート名リスト
    ↓
関連ノートを判定 → [[ノート名]] 形式でリンク生成
    ↓
各ファイル末尾の「## 関連ノート」セクションに重複排除してマージ追記
    ↓
state.json を更新（次回差分検知のためのmtime記録）
    ↓
output/obsidian-update.log に実行ログ追記
```

#### Obsidian Vault 構成

```
C:\Users\taisei10\Documents\Obsidian Vault\
├── logs/        対話履歴・実行ログ
├── knowledge/   調査・リサーチメモ
├── sales/       案件・営業・提案書
├── dev/         設計書・実装ガイド
├── skills/      SKILL.mdファイル
├── memo/        メモ・カスタム指示
├── hojokin/     補助金情報（自動保存）
└── old/         重複ファイル退避
```

---

## 5. セキュリティ設計

### 5.1 シークレット管理

```
.env（gitignore済み・コミット禁止）
├── ANTHROPIC_API_KEY
├── LINE_CHANNEL_ACCESS_TOKEN
├── LINE_USER_ID
├── NOTION_API_KEY
├── NOTION_DATABASE_ID        # X情報DB
└── NOTION_HOJOKIN_DB_ID      # 補助金マスターDB
```

- コード内への直書きは一切禁止（`os.getenv()` 必須）
- `.env.example` でキー名のみ公開

### 5.2 .gitignore設定

```
.env
*.env
output/
__pycache__/
*.pyc
.claude/
```

---

## 6. セットアップ手順

### 6.1 前提条件

- Python 3.12+
- Windows 10/11
- 各サービスのアカウント（Anthropic / LINE Developers / Notion）

### 6.2 インストール

```bash
# リポジトリクローン
git clone https://github.com/erflog1218/keiji-skills.git

# 依存ライブラリインストール
pip install playwright anthropic python-dotenv pandas openpyxl requests

# Chromiumインストール
playwright install chromium
```

### 6.3 環境変数設定

```bash
# x-briefing/.env を作成（.env.example を参考に）
cp x-briefing/.env.example x-briefing/.env
# エディタでAPIキーを入力
```

### 6.4 タスクスケジューラ登録

PowerShell（管理者）で実行：

```powershell
# Xブリーフィング（朝）
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c C:\...\x-briefing\run.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At "08:00"
Register-ScheduledTask -TaskName "brain-mieru-morning" -Action $action -Trigger $trigger `
  -RunLevel Highest -Force

# 同様に evening(20:00) / hojokin(09:00) / obsidian(23:00) を登録
```

### 6.5 動作確認

```powershell
# 手動テスト実行
cd x-briefing && python main.py
cd hojokin    && python main.py
```

---

## 7. 運用・保守

### 7.1 日常運用

| 操作 | 方法 |
|------|------|
| 監視アカウント追加 | `accounts.xlsx` を開いて末尾に追記 |
| アカウント無効化 | `active` 列を `false` に変更 |
| 補助金サイト追加 | `sites.csv` に1行追記 |
| 補助金サイト無効化 | `active` 列を `false` に変更 |

### 7.2 トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| X取得0件 | 直近24h投稿なし / ログイン壁 | ログを確認・active=falseで無効化 |
| 補助金0件 | サイトURLの変更 | sites.csvのURLを最新に更新 |
| LINE未着信 | トークン期限切れ | .envのLINE_CHANNEL_ACCESS_TOKENを更新 |
| Notion格納失敗 | インテグレーション権限 | NotionでDB接続を再確認 |

### 7.3 既知の制約

- Googleドライブ（ストリーミングモード）への PowerShell 直接操作は不可
- Notion APIから `parent: workspace` への直接DB作成は不可（API仕様）
- X非ログイン状態では一部アカウントが取得不可（@yanagi_shiftai等）

---

## 8. 今後の拡張計画

| 優先度 | 拡張内容 | 概要 |
|--------|---------|------|
| 高 | Jグランツ MCP切り替え | スクレイピング→公式MCPサーバーへ移行 |
| 高 | 環境省・農水省補助金追加 | 省エネ・ZEB関連補助金の追加 |
| 中 | X ログイン対応 | ログイン壁アカウントの取得解消 |
| 中 | 申請期限アラート | 期限1週間前に優先通知する機能 |
| 低 | 複数LINEチャンネル対応 | カテゴリ別に通知先を分ける |

---

## 9. 成果・実績

| 指標 | 数値 |
|------|------|
| 自動収集サイト数 | 15サイト（補助金）+ 9アカウント（X） |
| 1回あたり補助金収集件数 | 80件取得 → Claude APIで10件厳選 |
| Notion DB格納実績 | X情報: 7件/回、補助金: 8件/回 |
| Obsidian Vault整備 | 118ファイル・6フォルダ・自動リンク生成 |
| 開発期間 | 約2日（2026年04月08〜09日） |
| タスクスケジューラ | 4ジョブ登録・完全自動稼働中 |

---

*作成日：2026年04月09日*  
*プロジェクトリポジトリ：github.com/erflog1218/keiji-skills*
