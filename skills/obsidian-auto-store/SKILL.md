---
name: obsidian-auto-store
description: .mdファイルが会話の中で作成・生成・保存された時に、自動でObsidian Vaultの適切なフォルダに格納するSkill。「.mdファイルを作って」「保存して」「対話履歴をまとめて」「Markdownで出力して」などの流れで.mdファイルが生成される場面では必ずこのSkillを使うこと。ユーザーがObsidianへの格納を明示的に指示しなくても、.mdファイル生成後に自動で発動する。格納先フォルダはファイルの内容から自動判定する。
---

# obsidian-auto-store Skill

会話中に.mdファイルが生成された際、内容を解析してObsidian Vaultの適切なフォルダへ自動格納するSkill。

---

## Obsidian Vault パス

```
C:\Users\taisei10\Documents\Obsidian Vault\
```

---

## 格納先フォルダ判定ルール

| 判定条件（ファイル名・内容に含まれるキーワード） | 格納先 |
|----------------------------------------------|--------|
| 「対話履歴」「Claude」「ログ」「会話」 | `logs/` |
| 「補助金」「助成金」「公募」 | `hojokin/` |
| 「営業」「商談」「提案書」「見積」「案件」 | `sales/` |
| 「設計書」「実装」「スクリプト」「仕様」「アーキテクチャ」 | `dev/` |
| 「SKILL」「スキル」 | `skills/` |
| 「メモ」「カスタム指示」「備忘録」 | `memo/` |
| AI・テック・リサーチ・調査系 | `knowledge/` |
| 上記以外 | `logs/` |

---

## 格納手順

```
1. ファイル名・内容のキーワードから格納先フォルダを判定
2. 対象フォルダにファイルをコピー
3. 完了を報告（格納先パスを明示）
```

### コピーコマンド例

```powershell
Copy-Item "C:\path\to\file.md" "C:\Users\taisei10\Documents\Obsidian Vault\logs\file.md"
```

---

## 注意事項

- **Obsidian Vaultへの操作はCドライブのローカルパスを使うこと**
  - Gドライブ（Googleドライブ ストリーミング）への PowerShell 直接操作は不可
- 同名ファイルが既に存在する場合は上書き前に確認を取る
- `.obsidian/` フォルダは除外する

---

## 自動リンク更新との連携

格納後、`obsidian-linker/main.py` が毎日23:00に差分検知して
新規ファイルへの `[[関連ノート]]` リンクを自動生成する。
手動でリンクを付ける必要はない。
