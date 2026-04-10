"""
Xブリーフィング自動化
- Playwright で各アカウントを巡回しツイートを取得
- Claude API で日本語要約・重要度判定
- LINE Push Message で通知
- output/ に Obsidian 用 Markdown を保存
"""

import sys
import io
import os
import re
import json
import requests
import pandas as pd

# Windows コンソールで絵文字・日本語を正しく出力するための設定
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import anthropic

# ── 設定 ─────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")
load_dotenv(Path(r"C:\Users\taisei10\Desktop\AI-Shokunin\agent-zemi\.env"), override=False)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_X_DB_ID = os.getenv("NOTION_DATABASE_ID")

ACCOUNTS_XLSX = Path(__file__).parent / "accounts.xlsx"
MAX_TWEETS_PER_ACCOUNT = 5


def load_accounts() -> list[dict]:
    """accounts.xlsx から active=true のアカウントを読み込む"""
    df = pd.read_excel(ACCOUNTS_XLSX)
    accounts = []
    for _, row in df.iterrows():
        # active は pandas により bool 化されることがあるので両対応
        active_raw = row["active"]
        if isinstance(active_raw, bool):
            is_active = active_raw
        else:
            is_active = str(active_raw).strip().lower() == "true"
        if not is_active:
            continue
        handle = str(row["account"]).strip().lstrip("@")
        accounts.append({
            "handle": handle,
            "category": str(row["category"]).strip(),
            "priority": str(row["priority"]).strip(),
        })
    print(f"📋 accounts.xlsx: {len(accounts)} アカウントを読み込み")
    return accounts
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

JST = timezone(timedelta(hours=9))


# ── 1. Playwright でツイート取得 ──────────────────────
def scrape_tweets(account: str, hours: int = 24) -> list[dict]:
    """指定アカウントの直近 hours 時間以内のツイートを最大5件取得"""
    url = f"https://x.com/{account}"
    tweets = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
        )
        page = ctx.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            # ツイートが読み込まれるまで待機（ログイン壁が出る場合もある）
            try:
                page.wait_for_selector('article[data-testid="tweet"]', timeout=20_000)
            except Exception:
                # ログイン要求ダイアログを閉じて再試行
                close_btn = page.query_selector('[data-testid="xMigrationBottomBar"] button, [role="button"][aria-label="Close"]')
                if close_btn:
                    close_btn.click()
                    page.wait_for_timeout(2000)
                page.wait_for_selector('article[data-testid="tweet"]', timeout=10_000)

            # 少しスクロールして追加読み込み
            for _ in range(3):
                page.mouse.wheel(0, 800)
                page.wait_for_timeout(1500)

            articles = page.query_selector_all('article[data-testid="tweet"]')
            cutoff = datetime.now(JST) - timedelta(hours=hours)

            for article in articles:
                if len(tweets) >= MAX_TWEETS_PER_ACCOUNT:
                    break

                # 投稿時刻を取得
                time_el = article.query_selector("time")
                if not time_el:
                    continue
                dt_str = time_el.get_attribute("datetime")
                if not dt_str:
                    continue
                tweet_time = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(JST)

                if tweet_time < cutoff:
                    continue

                # テキスト取得
                text_el = article.query_selector('[data-testid="tweetText"]')
                text = text_el.inner_text() if text_el else ""
                if not text.strip():
                    continue

                tweets.append({
                    "account": account,
                    "time": tweet_time.strftime("%Y-%m-%d %H:%M"),
                    "text": text.strip(),
                })

        except Exception as e:
            print(f"  ⚠ @{account} の取得に失敗: {e}")
        finally:
            browser.close()

    return tweets


def scrape_all_accounts(accounts: list[dict]) -> list[dict]:
    """全アカウントを巡回してツイートを収集"""
    all_tweets = []
    for acc in accounts:
        handle = acc["handle"]
        print(f"📡 @{handle} [{acc['category']}|優先度{acc['priority']}] を取得中...")
        tweets = scrape_tweets(handle)
        # カテゴリ・優先度を各ツイートに付与
        for t in tweets:
            t["category"] = acc["category"]
            t["csv_priority"] = acc["priority"]
        print(f"   → {len(tweets)} 件取得")
        all_tweets.extend(tweets)
    return all_tweets


# ── 2. Claude API で要約・重要度判定 ──────────────────
def analyze_with_claude(tweets: list[dict]) -> list[dict]:
    """Claude API で各ツイートを日本語要約し重要度を判定"""
    if not tweets:
        return []

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    tweets_text = ""
    for i, t in enumerate(tweets, 1):
        tweets_text += f"[{i}] @{t['account']} ({t['time']})\n{t['text']}\n\n"

    prompt = f"""以下はX (旧Twitter) の投稿一覧です。
それぞれについて、以下の形式でJSON配列として出力してください。
他の文章は一切不要です。JSONのみ返してください。

出力形式:
[
  {{
    "index": 1,
    "account": "@アカウント名",
    "time": "投稿時刻",
    "summary": "日本語で1〜2文の要約",
    "importance": "高 or 中 or 低"
  }}
]

重要度の基準:
- 高: 新製品発表、重大ニュース、業界を変えるような発表、AI関連の大きなアップデート
- 中: 注目すべき意見、興味深い技術的知見、話題のトピック
- 低: 日常的なコメント、リプライ、軽い雑談

投稿一覧:
{tweets_text}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # JSON 部分を抽出（```json ... ``` 対応）
    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not json_match:
        print("⚠ Claude の応答からJSONを抽出できませんでした")
        return []

    results = json.loads(json_match.group())
    return results


# ── 3. LINE 通知 ──────────────────────────────────────
def send_line_push(message: str):
    """LINE Messaging API の Push Message で送信"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}",
    }
    body = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message}],
    }
    resp = requests.post(url, headers=headers, json=body, timeout=10)
    if resp.status_code == 200:
        print("✅ LINE通知を送信しました")
    else:
        print(f"⚠ LINE通知失敗: {resp.status_code} {resp.text}")


# ── 4. Notion 連携 ────────────────────────────────────
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def notion_url_exists(tweet_url: str) -> bool:
    """同じ元URLが既にNotionDBに登録済みか確認"""
    if not tweet_url:
        return False
    payload = {
        "filter": {"property": "元URL", "url": {"equals": tweet_url}},
        "page_size": 1,
    }
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_X_DB_ID}/query",
        headers=NOTION_HEADERS,
        json=payload,
        timeout=15,
    )
    if resp.status_code != 200:
        return False
    return len(resp.json().get("results", [])) > 0


def build_tweet_url(account: str, time_str: str) -> str:
    """アカウント名からツイートページURLを生成"""
    handle = account.lstrip("@")
    return f"https://x.com/{handle}"


def add_tweet_to_notion(item: dict, account_map: dict | None, now: datetime) -> bool:
    """1件のツイート分析結果をNotionDBに追加"""
    account = item.get("account", "").lstrip("@")
    tweet_url = build_tweet_url(account, item.get("time", ""))

    # 重複チェック（アカウント+要約で簡易チェック）
    summary = item.get("summary", "")
    title = summary[:100] if summary else item.get("text", "")[:100]

    # 元URLで重複チェック（同一アカウントの同日データ）
    check_url = f"https://x.com/{account}/status/{now.strftime('%Y%m%d')}-{title[:20]}"
    if notion_url_exists(check_url):
        print(f"  ⏭ 重複スキップ: @{account}")
        return False

    # カテゴリ取得
    category = ""
    if account_map and account in account_map:
        category = account_map[account].get("category", "")

    properties = {
        "名前": {
            "title": [{"text": {"content": title}}],
        },
        "アカウント": {
            "rich_text": [{"text": {"content": f"@{account}"}}],
        },
        "要約": {
            "rich_text": [{"text": {"content": summary[:2000]}}],
        },
        "取得日": {
            "date": {"start": now.strftime("%Y-%m-%d")},
        },
        "元URL": {
            "url": check_url,
        },
    }

    # カテゴリ（セレクト）
    if category in ("テック", "AI公式", "AI日本語"):
        properties["カテゴリ"] = {"select": {"name": category}}

    # 重要度（セレクト）
    importance = item.get("importance", "")
    if importance in ("高", "中", "低"):
        properties["重要度"] = {"select": {"name": importance}}

    payload = {
        "parent": {"database_id": NOTION_X_DB_ID},
        "properties": properties,
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=NOTION_HEADERS,
        json=payload,
        timeout=15,
    )

    if resp.status_code == 200:
        print(f"  ✅ Notion追加: @{account} - {title[:30]}")
        return True
    else:
        print(f"  ⚠ Notion追加失敗: {resp.status_code} {resp.text[:100]}")
        return False


def save_to_notion(results: list[dict], account_map: dict | None, now: datetime):
    """全結果をNotionに保存"""
    if not NOTION_API_KEY:
        print("⚠ NOTION_API_KEY が未設定です")
        return

    print("\n📝 Notionに保存中...")
    added = 0
    skipped = 0
    for r in results:
        if add_tweet_to_notion(r, account_map, now):
            added += 1
        else:
            skipped += 1
    print(f"📝 Notion完了: {added}件追加 / {skipped}件スキップ")


# ── 5. フォーマット・保存 ─────────────────────────────
IMPORTANCE_EMOJI = {
    "高": "🔴 重要",
    "中": "🟡 注目",
    "低": "🟢 参考",
}


def format_briefing(results: list[dict], now: datetime, account_map: dict | None = None) -> str:
    """ブリーフィングのテキストを整形（account_map: handle→{category,priority}）"""
    header = f"📡 Xブリーフィング {now.strftime('%Y-%m-%d %H:%M')}\n"
    sections: dict[str, list[str]] = {"高": [], "中": [], "低": []}

    for r in results:
        imp = r.get("importance", "低")
        if imp not in sections:
            imp = "低"
        account = r.get("account", "")
        if not account.startswith("@"):
            account = f"@{account}"
        summary = r.get("summary", r.get("text", ""))
        # CSV のカテゴリを付与
        handle = account.lstrip("@")
        cat_tag = ""
        if account_map and handle in account_map:
            cat_tag = f"[{account_map[handle]['category']}] "
        sections[imp].append(f"{cat_tag}{account}：{summary}")

    lines = [header]
    for level in ["高", "中", "低"]:
        if sections[level]:
            lines.append(f"\n{IMPORTANCE_EMOJI[level]}")
            for entry in sections[level]:
                lines.append(f"  {entry}")

    if not any(sections.values()):
        lines.append("\n投稿はありませんでした。")

    return "\n".join(lines)


def save_markdown(text: str, now: datetime):
    """output/ に Markdown ファイルを保存"""
    hour = now.hour
    suffix = "morning" if hour < 12 else "evening"
    filename = f"{now.strftime('%Y-%m-%d')}-{suffix}.md"
    filepath = OUTPUT_DIR / filename

    filepath.write_text(text, encoding="utf-8")
    print(f"💾 保存: {filepath}")


# ── メイン ────────────────────────────────────────────
def main():
    now = datetime.now(JST)
    print(f"🕐 実行時刻: {now.strftime('%Y-%m-%d %H:%M')} JST\n")

    # 0. アカウント読み込み
    accounts = load_accounts()
    if not accounts:
        print("⚠ accounts.xlsx に有効なアカウントがありません")
        return
    account_map = {a["handle"]: a for a in accounts}

    # 1. スクレイピング
    tweets = scrape_all_accounts(accounts)
    print(f"\n📊 合計 {len(tweets)} 件のツイートを取得\n")

    if not tweets:
        msg = f"📡 Xブリーフィング {now.strftime('%Y-%m-%d %H:%M')}\n\n直近24時間の投稿はありませんでした。"
        send_line_push(msg)
        save_markdown(msg, now)
        return

    # 2. Claude で要約・重要度判定
    print("🤖 Claude で分析中...\n")
    results = analyze_with_claude(tweets)

    # 3. フォーマット
    briefing = format_briefing(results, now, account_map)
    print("─" * 40)
    print(briefing)
    print("─" * 40)

    # 4. LINE 通知
    send_line_push(briefing)

    # 5. Markdown 保存
    save_markdown(briefing, now)

    # 6. Notion に保存
    save_to_notion(results, account_map, now)

    print("\n✅ 完了")


if __name__ == "__main__":
    main()
