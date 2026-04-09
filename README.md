# brain-mieru（脳の可視化）

> 情報収集・整理・通知を自動化し、知見が複利で増え続ける個人用「情報参謀システム」

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![Claude API](https://img.shields.io/badge/Claude-claude--haiku--4--5-purple)](https://anthropic.com)
[![Playwright](https://img.shields.io/badge/Playwright-latest-green)](https://playwright.dev)
[![Notion API](https://img.shields.io/badge/Notion-API-black)](https://developers.notion.com)

---

## 概要

電気設備工事の現場番頭が、毎日の情報収集・補助金チェック・業界トレンドの把握を
**完全自動化**するために構築した個人用AIエージェントシステム。

「見に行く」から「勝手に届く」へ。

---

## システム構成

```
brain-mieru/
├── x-briefing/          # X（旧Twitter）情報収集・LINE通知
├── hojokin/             # 補助金スクレイピング・Notion格納
└── obsidian-linker/     # Obsidian自動リンク更新
```

---

## 自動実行スケジュール

| 時刻 | 処理 |
|------|------|
| 08:00 | Xブリーフィング（朝） |
| 09:00 | 補助金スクレイピング |
| 20:00 | Xブリーフィング（夜） |
| 23:00 | Obsidian自動リンク更新 |

---

## セットアップ

```bash
pip install playwright anthropic python-dotenv pandas openpyxl requests
playwright install chromium
```

`.env` を `x-briefing/` に作成して各APIキーを設定してください（`.env.example` 参照）。

---

## Skills（Claude Code連携）

本リポジトリには3つのClaudeスキルが含まれています。
詳細は各 `SKILL.md` を参照してください。

| スキル | 説明 |
|--------|------|
| `x-briefing` | Xアカウント監視・通知管理 |
| `hojokin-scraper` | 補助金サイト監視・管理 |
| `obsidian-auto-store` | .mdファイル自動格納 |

---

## ライセンス

Private / 個人利用
