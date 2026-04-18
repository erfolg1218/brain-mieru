# CLAUDE.md — brain-mieru プロジェクト引き継ぎ書

> このファイルはClaude Codeが起動時に自動読み込みする「現場説明書」です。
> セッションをまたいでも、このプロジェクトの番頭として動けるようにします。

---

## プロジェクト概要

**プロジェクト名：** brain-mieru（脳の可視化）
**目的：** 情報収集・整理・通知を自動化し、知見が複利で増え続ける個人用「情報参謀システム」
**オーナー：** 電気設備工事士（プラント・公共事業）/ Windows PC / Claude Maxプラン

---

## フォルダ構成

```
C:\Users\taisei10\Desktop\brain-mieru\
├── CLAUDE.md                  ← このファイル（ここに置く）
├── README.md
├── .gitignore
├── x-briefing\
│   ├── main.py                ← Xブリーフィングスクリプト（268行）
│   ├── accounts.xlsx          ← 監視アカウントリスト（ドロップダウン付きExcel）
│   ├── .env                   ← APIキー（gitignore済み・絶対コミットしない）
│   ├── run.bat
│   └── output\                ← 取得データ保存先
├── hojokin\
│   ├── main.py                ← 補助金スクレイピング
│   ├── sites.csv              ← 監視サイトリスト
│   ├── run.bat
│   └── output\
└── obsidian-linker\
    ├── main.py                ← Obsidian自動リンク更新
    ├── run.bat
    ├── state.json             ← 差分検知用mtime記録
    └── output\
```

---

## .env の場所と構成

**場所：** `x-briefing\.env`（このファイルは絶対にGitにpushしない）

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# LINE Messaging API
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_USER_ID=...

# Notion（脳の可視化ワークスペース）
NOTION_API_KEY=ntn_679...
NOTION_DATABASE_ID=33dfd32c-1a69-80e4-84fc-cd4ad3f2a6b7        # X情報DB
NOTION_HOJOKIN_DB_ID=33dfd32c-1a69-8044-bc0f-ccddd88006f9      # 補助金マスターDB
```

**LINE設定：**
- 送信元ボット：通知用受信箱（@799zlimw）
- 送信先：オーナーの個人LINE
- .envの元ファイル：`C:\Users\taisei10\Desktop\AI-Shokunin\agent-zemi\.env`

---

## タスクスケジューラ 登録済みタスク

| タスク名 | 実行時刻 | スクリプト |
|---------|---------|-----------|
| brain-mieru-morning | 毎日 08:00 | x-briefing\run.bat |
| brain-mieru-evening | 毎日 20:00 | x-briefing\run.bat |
| brain-mieru-hojokin | 毎日 09:00 | hojokin\run.bat |
| brain-mieru-obsidian | 毎日 23:00 | obsidian-linker\run.bat |

**タスク削除コマンド（必要時）：**
```powershell
Unregister-ScheduledTask -TaskName "brain-mieru-morning" -Confirm:$false
Unregister-ScheduledTask -TaskName "brain-mieru-evening" -Confirm:$false
Unregister-ScheduledTask -TaskName "brain-mieru-hojokin" -Confirm:$false
Unregister-ScheduledTask -TaskName "brain-mieru-obsidian" -Confirm:$false
```

---

## Notion 構成

```
脳の可視化（ワークスペース）
└── 脳の可視化（ページ）
    ├── 📡 X情報DB        ID: 33dfd32c-1a69-80e4-84fc-cd4ad3f2a6b7
    └── 💰 補助金マスターDB  ID: 33dfd32c-1a69-8044-bc0f-ccddd88006f9
```

**インテグレーション：** brain-mieru（内部インテグレーション）

---

## Obsidian Vault 構成

**パス：** `C:\Users\taisei10\Documents\Obsidian Vault\`

```
Obsidian Vault\
├── logs\        ← 対話履歴
├── knowledge\   ← 調査・リサーチ
├── sales\       ← 案件・営業・補助金
├── dev\         ← 設計書・実装ガイド
├── skills\      ← SKILL.md
├── memo\        ← メモ・カスタム指示
├── hojokin\     ← 補助金情報（自動保存先）
└── old\         ← 重複ファイル退避
```

**自動リンク更新：** 毎日23:00に `obsidian-linker\main.py` が差分検知して実行

---

## Xブリーフィング 監視アカウント

| アカウント | カテゴリ | 優先度 |
|-----------|---------|--------|
| @AnthropicAI | AI公式 | 高 |
| @claudeai | AI公式 | 高 |
| @OpenAI | AI公式 | 高 |
| @elonmusk | テック | 高 |
| @sundarpichai | テック | 高 |
| @shota7180 | AI日本語 | 中 |
| @ManusAI_JP | AI日本語 | 中 |
| @masahirochaen | AI日本語 | 中 |
| @yanagi_shiftai | AI日本語 | 中（ログイン壁・要対応） |

アカウントの追加・変更は `x-briefing\accounts.csv` を直接編集すること。

---

## 補助金スクレイピング 監視サイト

| サイト | 件数実績 | 備考 |
|--------|---------|------|
| Jグランツ | 1件 | MCP版に切り替え予定 |
| ミラサポplus（中小企業庁） | 47件 | 安定稼働中 |
| デジタル庁 | 3件 | 安定稼働中 |

**追加予定（応用編）：** 経産省・国交省・自治体・メーカー助成金

---

## 既知の制約・注意事項

- **Gドライブ（ストリーミングモード）へのPowerShell操作は全滅**
  - `New-Item` / `Move-Item` / `Copy-Item` → エラー
  - Python `os.walk()` → 0件
  - 対処：エクスプローラーのドラッグ操作のみ有効
  - **結論：Obsidian VaultはCドライブ運用が安定**

- **Notion API制限**
  - `parent: workspace` でのDB作成は不可（API仕様）
  - UIで手動作成したページ配下にのみAPIからDB作成可能

- **Xスクレイピング**
  - 非ログイン状態だとアカウントによって表示制限あり
  - @yanagi_shiftaiはログイン壁で取得失敗中

---

## ロードマップ

| フェーズ | 内容 | 状態 |
|---------|------|------|
| 1 | Obsidian Vault整備（118ファイル） | ✅ 完了 |
| 2 | Xブリーフィング・LINE通知 | ✅ 完了 |
| 3A | タスクスケジューラ自動化 | ✅ 完了 |
| 3B | 補助金スクレイピング | ✅ 完了 |
| 3C | Notion新ワークスペース接続 | ✅ 完了 |
| 4 | Obsidian自動リンク更新（毎日23:00） | ✅ 完了 |
| 5 | Skill化・GitHub push | ✅ 完了 |
| A | CLAUDE.md・Memoryミラー | ✅ 完了（このファイル） |
| 応用 | 経産省・国交省・自治体・JグランツMCP | 未着手 |

---

## GitHub

- リポジトリ：`erflog1218/keiji-skills`
- push済みSkill：`obsidian-auto-store`
- **注意：.env・output/・__pycache__/ は絶対にpushしない**

---

## このプロジェクトでClaude Codeが意識すること

1. コードを書く前に「どのスクリプトを修正するか」を明示する
2. .envのキーを直接コードに書かない（必ず `os.getenv()` を使う）
3. 会社名・固有名詞が出る場合はGitHub pushを考慮してマスク提案をする
4. スクリプト実行前に「実行していいか確認」を取る
5. G:ドライブへの直接操作は避ける（エクスプローラー経由を案内する）

---

*作成日：2026年04月09日*
*更新時は末尾に更新日・内容を追記すること*
