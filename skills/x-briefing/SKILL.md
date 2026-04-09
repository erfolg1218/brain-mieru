---
name: x-briefing
description: brain-mieruプロジェクトのXブリーフィングシステムを管理・運用するSkill。「Xの監視アカウントを追加したい」「アカウントを無効化したい」「x-briefingのスクリプトを修正して」「accounts.xlsxを更新して」「LINE通知のフォーマットを変えたい」「X情報をNotionに格納したい」「Xブリーフィングが動いてるか確認して」などの依頼で必ず使うこと。brain-mieruプロジェクトのX情報収集・アカウント管理・LINE通知に関する作業は全てこのSkillを参照する。
---

# x-briefing Skill

brain-mieruプロジェクトにおけるXブリーフィングシステムの管理・運用・拡張を担うSkill。

---

## システム概要

```
監視アカウント（accounts.xlsx）
        ↓  Playwright でX巡回（非ログイン・headless）
        ↓  直近24時間以内の投稿を最大5件取得
        ↓  Claude API で日本語要約・重要度判定（高/中/低）
        ↓
    ├── LINE Push通知（重要度別フォーマット）
    ├── output/ に .md 保存（朝/夜）
    ├── Obsidian Vault/logs/ に自動保存
    └── Notion X情報DB に格納（重複チェック付き）

実行タイミング：毎日 08:00（morning）/ 20:00（evening）
```

---

## ファイル構成

```
C:\Users\taisei10\Desktop\brain-mieru\x-briefing\
├── main.py         ← メインスクリプト（268行）
├── accounts.xlsx   ← 監視アカウントリスト（ここを編集）
├── .env            ← APIキー（gitignore済み・絶対コミットしない）
├── run.bat         ← タスクスケジューラ用
└── output\         ← 取得データ保存先
    ├── YYYY-MM-DD-morning.md
    └── YYYY-MM-DD-evening.md
```

**.env 構成：**
```env
ANTHROPIC_API_KEY=...
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_USER_ID=...
NOTION_API_KEY=ntn_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx   # X情報DB
```

---

## accounts.xlsx 構成

| 列名 | 説明 | 選択肢 |
|------|------|--------|
| account | @付きアカウント名 | 例：`@AnthropicAI` |
| category | カテゴリ | AI公式 / テック / AI日本語 / 電気工事 / 建設業 / 補助金 |
| priority | 優先度 | 高 / 中 / 低 |
| active | 有効/無効 | true / false |
| memo | 備考 | 自由記述 |
| added_date | 追加日 | `YYYY-MM-DD` |

### 現在の監視アカウント（9件）

| アカウント | カテゴリ | 優先度 | 状態 |
|-----------|---------|--------|------|
| @AnthropicAI | AI公式 | 高 | 稼働中 |
| @claudeai | AI公式 | 高 | 稼働中 |
| @OpenAI | AI公式 | 高 | 稼働中 |
| @elonmusk | テック | 高 | 稼働中（直近0件あり） |
| @sundarpichai | テック | 高 | 稼働中 |
| @shota7180 | AI日本語 | 中 | 稼働中（5件実績） |
| @ManusAI_JP | AI日本語 | 中 | 稼働中 |
| @masahirochaen | AI日本語 | 中 | 稼働中 |
| @yanagi_shiftai | AI日本語 | 中 | ⚠️ ログイン壁で取得失敗中 |

---

## アカウント管理の手順

### 追加する場合
```
1. accounts.xlsx を開く
2. 末尾の空行に1行追加
3. category・priority をドロップダウンで選択
4. active を true に設定
5. 保存してテスト実行
```

### 無効化する場合
```
accounts.xlsx の該当行の active 列を true → false に変更
（行を削除しない → 履歴として残す）
```

---

## LINE通知フォーマット

```
📡 Xブリーフィング 2026-04-09 08:00

🔴 重要
[AI公式] @AnthropicAI：Claude 4を発表

🟡 注目
[テック] @sundarpichai：Gemini新機能を公開

🟢 参考
[AI日本語] @shota7180：プロンプト設計のコツを紹介
```

重要度の判定基準：
- **高（🔴）**：新モデル・新機能・大型アップデート・業界の重大発表
- **中（🟡）**：機能改善・研究発表・注目トレンド
- **低（🟢）**：参考情報・日常的な投稿

---

## Notion X情報DB

**DB ID：** `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
**インテグレーション：** brain-mieru
**重複チェック：** 元URL基準（同一URLは2回目以降スキップ）

| プロパティ | 種類 |
|----------|------|
| 名前 | タイトル |
| アカウント | テキスト |
| カテゴリ | セレクト |
| 重要度 | セレクト |
| 要約 | テキスト |
| 取得日 | 日付 |
| 元URL | URL |

---

## タスクスケジューラ

| タスク名 | 実行時刻 | バッチ |
|---------|---------|-------|
| brain-mieru-morning | 毎日 08:00 | x-briefing\run.bat |
| brain-mieru-evening | 毎日 20:00 | x-briefing\run.bat |

**確認コマンド：**
```powershell
Get-ScheduledTask -TaskName "brain-mieru-morning" | Select-Object State
Get-ScheduledTask -TaskName "brain-mieru-evening" | Select-Object State
```

**削除コマンド（必要時）：**
```powershell
Unregister-ScheduledTask -TaskName "brain-mieru-morning" -Confirm:$false
Unregister-ScheduledTask -TaskName "brain-mieru-evening" -Confirm:$false
```

---

## テスト実行

```powershell
# brain-mieru\x-briefing\ フォルダで実行
python main.py

# 確認ポイント
# - LINEに重要度別フォーマットで通知が届くか
# - output\YYYY-MM-DD-morning.md（または evening）が生成されるか
# - Notion X情報DBにページが追加されるか（重複スキップ確認）
```

---

## 既知の制約・注意事項

- **非ログイン状態だと一部アカウントで取得失敗**
  - @yanagi_shiftaiはログイン壁で現在取得不可
  - 対処：active=falseで無効化 or 将来的にログイン対応
- **直近24h投稿がない場合は0件**（エラーではない）
- **Gドライブへの直接操作は不可** → エクスプローラー経由のみ
- **accounts.xlsxの読み込み：** `pandas.read_excel()` を使用（read_csvではない）
- **active列の型：** boolとstr両対応済み（`isinstance(x, bool)` と文字列比較）

---

## main.py の主要処理フロー

```python
1. accounts.xlsx を読み込み（active=true のみ）
2. Playwright (headless Chromium) で各アカウントページへ
3. 直近24時間以内の投稿テキスト・URLを最大5件取得
4. Claude API (claude-haiku) で要約・重要度判定
5. LINE Push Message で通知送信
6. output/ に .md 保存
7. Notion X情報DB に格納（重複チェック）
8. Obsidian Vault/logs/ に保存
```

---

## 応用編（未着手）

- [ ] ログイン対応（@yanagi_shiftaiなどの取得失敗アカウント解消）
- [ ] カテゴリ別に別LINEチャンネルで通知
- [ ] 重要度「高」のみ即時通知する緊急モード

---

## このSkillを使う時のClaudeの動き方

1. **アカウント追加依頼** → accounts.xlsxへの追記内容を提示 → テスト実行を提案
2. **無効化依頼** → 該当アカウントのactive=falseへの変更を案内
3. **通知フォーマット変更** → main.pyの該当箇所を特定 → 最小限修正
4. **エラー対応** → ログイン壁かURLの問題かを切り分け → 対処を提案
5. **コードを書く前に「どのファイルを修正するか」を明示する**
6. **.envのキーをコードに直書きしない（os.getenv() を使う）**
