---
name: hojokin-scraper
description: brain-mieruプロジェクトの補助金スクレイピングシステムを管理・運用するSkill。「補助金サイトを追加したい」「スクレイピングの結果を確認したい」「新しい自治体を監視対象に加えたい」「hojokinスクリプトを修正して」「sites.csvを更新して」「補助金情報をNotionに格納したい」「経産省・国交省・NEDO・自治体の補助金を自動収集したい」などの依頼で必ず使うこと。brain-mieruプロジェクトの補助金関連作業（追加・修正・テスト・確認）は全てこのSkillを参照する。
---

# hojokin-scraper Skill

brain-mieruプロジェクトにおける補助金スクレイピングシステムの管理・運用・拡張を担うSkill。

---

## システム概要

```
監視サイト（sites.csv）
        ↓  Playwright でスクレイピング（毎日 09:00）
        ↓  Claude API で電気工事・プラント優先フィルタリング
        ↓
    ├── LINE Push通知（カテゴリ別フォーマット）
    ├── output/ に .md 保存
    ├── Obsidian Vault/hojokin/ に保存
    └── Notion 補助金マスターDB に格納（重複チェック付き）
```

---

## ファイル構成

```
C:\Users\taisei10\Desktop\brain-mieru\hojokin\
├── main.py        ← メインスクリプト
├── sites.csv      ← 監視サイトリスト（ここを編集して追加）
├── run.bat        ← タスクスケジューラ用
└── output\        ← 取得データ保存先
```

**.env の場所：** `x-briefing\.env`（hojokin/main.py もここを参照）

```env
ANTHROPIC_API_KEY=...
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_USER_ID=...
NOTION_API_KEY=ntn_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_HOJOKIN_DB_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## sites.csv 構成

| 列名 | 説明 | 例 |
|------|------|-----|
| site_name | サイト名（日本語OK） | `経産省_公募情報` |
| url | スクレイピング対象URL | `https://www.meti.go.jp/...` |
| category | カテゴリ分類 | `経産省` / `国交省` / `NEDO` / `自治体` / `補助金ポータル` / `中小企業庁` |
| priority | 優先度 | `高` / `中` / `低` |
| active | 有効/無効 | `true` / `false` |
| memo | 備考 | `安定稼働中・47件実績` |
| added_date | 追加日 | `2026-04-09` |

### 現在の監視サイト（15件）

| サイト名 | カテゴリ | 優先度 | 件数実績 |
|---------|---------|--------|---------|
| Jグランツ | 補助金ポータル | 高 | 1件 ※MCP版切替予定 |
| ミラサポplus | 中小企業庁 | 高 | 47件 |
| デジタル庁 | デジタル庁 | 中 | 3件 |
| 経産省_公募情報 | 経産省 | 高 | 変動 |
| 国交省_公募情報 | 国交省 | 高 | 13件 |
| NEDO_公募 | NEDO | 高 | 12件 |
| 東京都・神奈川・埼玉・千葉・大阪・兵庫・愛知・静岡・福岡 | 自治体 | 中 | 各1-5件 |

---

## サイト追加の手順

```
1. sites.csv を開く
2. 末尾に1行追加（カンマ区切り）
3. active=true で保存
4. テスト実行して確認
```

### よくある追加パターン

**省庁系：**
```csv
環境省_補助金,https://www.env.go.jp/policy/j-hiroba/,環境省,中,true,省エネ・ZEB・再エネ関連,2026-04-XX
```

**自治体系（汎用）：**
```csv
XX県_補助金,https://www.pref.XX.lg.jp/shien/,自治体,中,true,XX県中小企業支援,2026-04-XX
```

**scrape_jichitai() 関数が自動適用される（1サイト5件上限）**

---

## main.py の主要関数

| 関数名 | 役割 |
|--------|------|
| `load_sites()` | sites.csv を読み込み（active=trueのみ） |
| `scrape_site(url, site_name)` | 汎用スクレイパー（Playwright） |
| `scrape_meti()` | 経産省専用（タイムアウト60秒） |
| `scrape_mlit()` | 国交省専用 |
| `scrape_nedo()` | NEDO専用 |
| `scrape_jichitai(url, name)` | 自治体汎用（1サイト5件上限） |
| `analyze_with_claude(items)` | Claude APIでフィルタリング |
| `send_line_notification(results)` | LINEカテゴリ別通知 |
| `save_to_notion(items)` | NotionDB格納（重複チェック） |
| `save_to_obsidian(results)` | Obsidian Vault/hojokin/に保存 |

### Claude分析プロンプトのフィルタ条件

```
優先抽出：電気設備工事・プラント設備・建設業・省エネ設備・中小企業向け
除外：農業・観光・飲食・医療等の無関係な補助金
```

---

## Notion 補助金マスターDB

**DB ID：** `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
**インテグレーション：** brain-mieru
**重複チェック：** URL基準（同一URLは2回目以降スキップ）

| プロパティ | 種類 |
|----------|------|
| 名前 | タイトル |
| 事業内容 | テキスト |
| 公式URL | URL |
| 申請期限 | 日付 |
| 補助金額 | テキスト |
| 補助率 | テキスト |
| 対象業種 | テキスト |
| 概要 | テキスト |

---

## タスクスケジューラ

| タスク名 | 実行時刻 | バッチ |
|---------|---------|-------|
| brain-mieru-hojokin | 毎日 09:00 | hojokin\run.bat |

**確認コマンド：**
```powershell
Get-ScheduledTask -TaskName "brain-mieru-hojokin" | Select-Object State
```

**削除コマンド（必要時）：**
```powershell
Unregister-ScheduledTask -TaskName "brain-mieru-hojokin" -Confirm:$false
```

---

## テスト実行

```powershell
# brain-mieru\hojokin\ フォルダで実行
python main.py

# 出力確認
# - LINEにカテゴリ別通知が届くか
# - output\YYYY-MM-DD-hojokin.md が生成されるか
# - Notion補助金DBにページが追加されるか（重複スキップ確認）
# - Obsidian Vault\hojokin\ に.mdが保存されるか
```

---

## 既知の制約・注意事項

- **Gドライブへの直接操作は不可** → エクスプローラー経由のみ
- **経産省はタイムアウト60秒設定**（通常より遅い）
- **自治体URLは変更が多い** → 0件の場合はURLを再確認
- **Notion APIから `parent: workspace` へのDB作成は不可**
- **JグランツはMCP版切替予定**（現在はスクレイピング）

### URL変更が発生した場合の対処

```
1. sites.csv の該当URLを新URLに更新
2. active=false → テスト → 問題なければ true に戻す
3. 必要ならスクレイピング関数を追加
```

---

## 応用編（未着手）

- [ ] 環境省・農水省の省エネ補助金追加
- [ ] JグランツMCP版への切り替え
- [ ] 申請期限が近い補助金を優先通知する機能
- [ ] 補助金マスターDB にカレンダービューを追加

---

## このSkillを使う時のClaude の動き方

1. **追加依頼** → sites.csv に1行追加 → テスト実行を提案
2. **修正依頼** → 該当関数を特定 → main.py を最小限修正
3. **確認依頼** → output/ の最新ファイルを確認 → 結果を報告
4. **エラー対応** → URLを確認 → active=false で無効化 → 代替URLを提案
5. **コードを書く前に「どのファイルを修正するか」を明示する**
6. **.envのキーをコードに直書きしない（os.getenv() を使う）**
