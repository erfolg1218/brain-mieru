"""
Obsidian Vault 自動リンク更新スクリプト
- 新規・更新された .md ファイルを検出
- Claude API で関連ノートを判定
- 各ノート末尾の「## 関連ノート」セクションに [[リンク]] を追記（重複なし）
- 実行ログを output/obsidian-update.log に保存
"""

import sys
import io
import os
import re
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
import anthropic

# Windows コンソールで絵文字・日本語を正しく出力
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 設定 ──────────────────────────────────────────
VAULT = Path(r"C:\Users\taisei10\Documents\Obsidian Vault")
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

STATE_FILE = SCRIPT_DIR / "state.json"
LOG_FILE = OUTPUT_DIR / "obsidian-update.log"

EXCLUDE_DIRS = {".obsidian", ".claude", ".smtcmp_json_db"}
JST = timezone(timedelta(hours=9))

load_dotenv(Path(r"C:\Users\taisei10\Desktop\brain-mieru\x-briefing\.env"))
load_dotenv(Path(r"C:\Users\taisei10\Desktop\AI-Shokunin\agent-zemi\.env"), override=False)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ── ログ設定 ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("obsidian-linker")


# ── ファイル探索 ─────────────────────────────────
def should_exclude(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def get_all_md_files() -> list[Path]:
    return sorted(p for p in VAULT.rglob("*.md") if not should_exclude(p))


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def find_changed_files(all_files: list[Path], state: dict) -> list[Path]:
    """新規または更新されたファイルを返す（mtime比較）"""
    changed = []
    for path in all_files:
        rel = path.relative_to(VAULT).as_posix()
        mtime = path.stat().st_mtime
        prev = state.get(rel)
        if prev is None or abs(prev - mtime) > 1:
            changed.append(path)
    return changed


# ── 関連ノートセクションの読み書き ─────────────
RELATED_SECTION_RE = re.compile(
    r"\n*## 関連ノート\n(.*?)(?=\n## |\Z)",
    re.DOTALL,
)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def extract_existing_links(content: str) -> tuple[list[str], str]:
    """既存「## 関連ノート」から [[リンク]] を抽出し、そのセクションを除いた本文を返す"""
    match = RELATED_SECTION_RE.search(content)
    if not match:
        return [], content.rstrip() + "\n"
    section_body = match.group(1)
    links = WIKILINK_RE.findall(section_body)
    # 末尾の空白 .md を除去
    links = [l.split("|")[0].strip().removesuffix(".md") for l in links]
    content_without = RELATED_SECTION_RE.sub("", content).rstrip() + "\n"
    return links, content_without


def write_related_section(path: Path, all_links: list[str], content_body: str):
    section = "\n## 関連ノート\n\n" + "\n".join(f"- [[{l}]]" for l in all_links) + "\n"
    new_content = content_body.rstrip() + "\n" + section
    path.write_text(new_content, encoding="utf-8")


# ── Claude で関連ノート判定 ──────────────────────
def suggest_related_notes(
    client: anthropic.Anthropic,
    self_stem: str,
    file_content: str,
    vault_index: list[str],
) -> list[str]:
    """Claude API にノート内容と vault 一覧を渡して関連ノートを得る"""
    content_preview = file_content[:3500]
    index_lines = "\n".join(f"- {name}" for name in vault_index if name != self_stem)

    prompt = f"""以下はObsidian Vault内のノート「{self_stem}」の冒頭です。

===ノート内容===
{content_preview}
===ここまで===

以下はVault内の他の全ノート名です：
{index_lines}

上記ノートと強く関連する他のノートを最大5件まで選んでJSON配列だけで返してください。
判断基準：
- 同じトピック・案件・プロジェクトを扱っている
- 同じ人物・組織・製品が登場する
- 設計書 ⇔ 実装ログ、サマリー ⇔ 詳細のような補完関係

関連ノートが無ければ空配列 [] を返してください。
他の文章・説明・マークダウンは一切不要。JSON配列のみ。

例: ["ノート名1", "ノート名2"]"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()

    # JSON配列を抽出
    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        candidates = json.loads(match.group())
    except json.JSONDecodeError:
        return []

    if not isinstance(candidates, list):
        return []

    vault_set = set(vault_index)
    return [c for c in candidates if isinstance(c, str) and c in vault_set and c != self_stem]


# ── メイン ────────────────────────────────────────
def main():
    start = datetime.now(JST)
    log.info("")
    log.info(f"=== 実行開始 {start.strftime('%Y-%m-%d %H:%M:%S')} JST ===")

    if not ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY が見つかりません（.env 設定を確認）")
        return

    all_files = get_all_md_files()
    log.info(f"Vault内の .md ファイル: {len(all_files)} 件")

    state = load_state()
    changed = find_changed_files(all_files, state)
    log.info(f"新規・更新ファイル: {len(changed)} 件")

    if not changed:
        log.info("更新対象なし。終了。")
        return

    vault_index = [p.stem for p in all_files]
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    processed = 0
    errors = 0
    added_total = 0

    for path in changed:
        rel = path.relative_to(VAULT).as_posix()
        try:
            content = path.read_text(encoding="utf-8")

            # 短すぎるファイルはスキップ（state は更新）
            if len(content.strip()) < 50:
                log.info(f"  ⏭ {rel}: 短すぎ（スキップ）")
                state[rel] = path.stat().st_mtime
                continue

            # Claude で関連ノートを取得
            new_links = suggest_related_notes(client, path.stem, content, vault_index)

            if new_links:
                existing, body = extract_existing_links(content)
                merged = list(existing)
                added_this = 0
                for link in new_links:
                    if link not in merged:
                        merged.append(link)
                        added_this += 1

                if added_this > 0:
                    write_related_section(path, merged, body)
                    log.info(f"  ✅ {rel}: +{added_this}件 {new_links}")
                    added_total += added_this
                else:
                    log.info(f"  ✓ {rel}: 変更なし（既存と同じ）")
            else:
                log.info(f"  – {rel}: 関連ノートなし")

            state[rel] = path.stat().st_mtime
            processed += 1

        except Exception as e:
            log.error(f"  ⚠ {rel}: {type(e).__name__}: {e}")
            errors += 1

    save_state(state)

    end = datetime.now(JST)
    duration = (end - start).total_seconds()
    log.info(
        f"=== 完了: 処理{processed}件 / エラー{errors}件 / "
        f"リンク追加{added_total}件 / {duration:.1f}秒 ==="
    )


if __name__ == "__main__":
    main()
