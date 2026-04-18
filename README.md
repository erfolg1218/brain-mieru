# brain-mieru
脳の可視化プロジェクト

## フェーズ2：Xブリーフィング自動化
- Playwright で特定アカウントを自動巡回（X API不要）
- Claude API で要約・重要度判定
- 毎日 8:00 / 20:00 にLINE通知
- Obsidian の daily/ フォルダに自動保存

## セットアップ

### 1. 依存パッケージのインストール

```
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. 必要な .env キー

`x-briefing/.env` に以下のキーを設定してください（プロジェクト全体でこのファイルを共通利用します）。

| キー | 用途 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API 認証 |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API の Push 送信トークン |
| `LINE_USER_ID` | 通知先ユーザーID |
| `NOTION_API_KEY` | Notion インテグレーションのシークレット |
| `NOTION_DATABASE_ID` | X情報DB の ID |
| `NOTION_HOJOKIN_DB_ID` | 補助金マスターDB の ID |

`.env` は **絶対に Git にコミットしない**こと（`.gitignore` 済み）。

## 実行方法

### Xブリーフィング（手動実行）

```
python x-briefing/main.py
```

### 補助金スクレイピング

```
hojokin\run.bat
```

タスクスケジューラで **毎日 09:00** に自動実行されます（タスク名: `brain-mieru-hojokin`）。

### Obsidian 自動リンク更新

```
obsidian-linker\run.bat
```

タスクスケジューラで **毎日 23:00** に自動実行されます（タスク名: `brain-mieru-obsidian`）。

## 自動実行スケジュール一覧

| タスク名 | 実行時刻 | スクリプト |
|---|---|---|
| brain-mieru-morning | 毎日 08:00 | x-briefing\run.bat |
| brain-mieru-evening | 毎日 20:00 | x-briefing\run.bat |
| brain-mieru-hojokin | 毎日 09:00 | hojokin\run.bat |
| brain-mieru-obsidian | 毎日 23:00 | obsidian-linker\run.bat |
