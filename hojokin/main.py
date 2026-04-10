"""
補助金スクレイピングシステム
- sites.csv で監視サイトを管理
- Playwright で各サイトの新着情報を取得
- キーワードフィルタで補助金関連を抽出
- Claude API で要約・重要度判定
- LINE Push Message で通知
- output/ と Obsidian Vault に保存
"""

import sys
import io
import os
import re
import csv
import json
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import anthropic

# Windows コンソールで絵文字・日本語を正しく出力するための設定
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 設定 ─────────────────────────────────────────────
load_dotenv(Path(r"C:\Users\taisei10\Desktop\brain-mieru\x-briefing\.env"))
load_dotenv(Path(r"C:\Users\taisei10\Desktop\AI-Shokunin\agent-zemi\.env"), override=False)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_HOJOKIN_DB_ID")

SITES_CSV = Path(__file__).parent / "sites.csv"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

OBSIDIAN_DIR = Path(r"C:\Users\taisei10\Documents\Obsidian Vault\hojokin")
OBSIDIAN_DIR.mkdir(exist_ok=True)

JST = timezone(timedelta(hours=9))

KEYWORDS = ["補助金", "助成金", "公募", "IT導入", "ものづくり", "省エネ", "DX", "デジタル"]

# ── カテゴリ別スクレイピング設定 ─────────────────────
# 各カテゴリごとに a タグから抽出するキーワードと取得件数上限を定義
CATEGORY_CONFIG: dict[str, dict] = {
    "経産省":       {"keywords": ["補助金", "公募", "ものづくり"],          "limit": None},
    "国交省":       {"keywords": ["補助", "支援", "設備", "工事"],          "limit": None},
    "NEDO":        {"keywords": ["公募", "省エネ", "再エネ"],              "limit": None},
    "自治体":       {"keywords": ["補助金", "助成金", "支援金"],            "limit": 5},
    "中小企業庁":    {"keywords": ["補助金", "助成金", "公募", "IT導入", "ものづくり"], "limit": None},
    "デジタル庁":    {"keywords": ["補助金", "DX", "デジタル", "公募"],      "limit": None},
    "補助金ポータル": {"keywords": ["補助金", "助成金", "公募"],             "limit": None},
}
DEFAULT_CATEGORY_CONFIG = {"keywords": ["補助金", "助成金", "公募"], "limit": None}

# カテゴリ別タイムアウト（ms）。経産省は重いので60秒、他は30秒デフォルト。
CATEGORY_TIMEOUTS: dict[str, int] = {
    "経産省": 60_000,
}
DEFAULT_TIMEOUT_MS = 30_000


# ── サイト読み込み ────────────────────────────────────
def load_sites() -> list[dict]:
    """sites.csv から active=true のサイトを読み込む汎用ループ

    CSV columns: site_name,url,category,priority,active,memo,added_date
    """
    sites = []
    with open(SITES_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("active", "").strip().lower() != "true":
                continue
            sites.append({
                "name": row["site_name"].strip(),
                "url": row["url"].strip(),
                "category": (row.get("category") or "").strip() or "その他",
                "priority": (row.get("priority") or "中").strip(),
            })
    # カテゴリ別の件数を集計してログ
    by_cat: dict[str, int] = {}
    for s in sites:
        by_cat[s["category"]] = by_cat.get(s["category"], 0) + 1
    print(f"📋 sites.csv: {len(sites)} サイトを読み込み")
    for cat, n in by_cat.items():
        print(f"   ├ {cat}: {n}件")
    return sites


# ── 1. Playwright でスクレイピング ────────────────────
def contains_keyword(text: str, keywords: list[str]) -> bool:
    """テキストに指定キーワードのいずれかが含まれるか判定"""
    return any(kw in text for kw in keywords)


def extract_links_by_keywords(
    page,
    base_url: str,
    keywords: list[str],
    limit: int | None,
) -> list[dict]:
    """ページ内の <a> タグを走査してキーワード一致リンクを抽出

    汎用ヘルパー。カテゴリ別関数から呼ばれる。
    """
    results: list[dict] = []
    seen: set[str] = set()

    try:
        links = page.query_selector_all("a")
    except Exception:
        return results

    for link in links:
        try:
            title = (link.inner_text() or "").strip()
        except Exception:
            continue

        # 空・短すぎ・重複を除外
        if not title or len(title) < 5 or title in seen:
            continue

        # キーワードフィルタ
        if not contains_keyword(title, keywords):
            continue

        seen.add(title)

        try:
            href = link.get_attribute("href") or ""
        except Exception:
            href = ""
        if href and not href.startswith("http"):
            href = urljoin(base_url, href)

        results.append({"title": title, "url": href})

        if limit is not None and len(results) >= limit:
            break

    return results


# ── カテゴリ別スクレイピング関数 ─────────────────────
def scrape_meti(page, site: dict) -> list[dict]:
    """経産省: meti.go.jp の a タグから「補助金・公募・ものづくり」"""
    return extract_links_by_keywords(
        page, site["url"],
        keywords=["補助金", "公募", "ものづくり"],
        limit=None,
    )


def scrape_mlit(page, site: dict) -> list[dict]:
    """国交省: mlit.go.jp の a タグから「補助・支援・設備・工事」"""
    return extract_links_by_keywords(
        page, site["url"],
        keywords=["補助", "支援", "設備", "工事"],
        limit=None,
    )


def scrape_nedo(page, site: dict) -> list[dict]:
    """NEDO: nedo.go.jp の a タグから「公募・省エネ・再エネ」"""
    return extract_links_by_keywords(
        page, site["url"],
        keywords=["公募", "省エネ", "再エネ"],
        limit=None,
    )


def scrape_jichitai(page, site: dict) -> list[dict]:
    """自治体: 各URLの a タグから「補助金・助成金・支援金」(1サイト5件上限)"""
    return extract_links_by_keywords(
        page, site["url"],
        keywords=["補助金", "助成金", "支援金"],
        limit=5,
    )


def scrape_generic(page, site: dict) -> list[dict]:
    """その他カテゴリ用の汎用スクレイパー"""
    config = CATEGORY_CONFIG.get(site.get("category", ""), DEFAULT_CATEGORY_CONFIG)
    return extract_links_by_keywords(
        page, site["url"],
        keywords=config["keywords"],
        limit=config["limit"],
    )


# カテゴリ → スクレイピング関数のディスパッチテーブル
CATEGORY_SCRAPERS = {
    "経産省":   scrape_meti,
    "国交省":   scrape_mlit,
    "NEDO":    scrape_nedo,
    "自治体":   scrape_jichitai,
}


def scrape_site(site: dict) -> list[dict]:
    """指定サイトをカテゴリに応じてスクレイピング"""
    items: list[dict] = []
    category = site.get("category", "その他")
    scraper = CATEGORY_SCRAPERS.get(category, scrape_generic)

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
            timeout_ms = CATEGORY_TIMEOUTS.get(category, DEFAULT_TIMEOUT_MS)
            page.goto(site["url"], wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(3000)

            # 少しスクロールして遅延読み込みを発火
            for _ in range(2):
                page.mouse.wheel(0, 600)
                page.wait_for_timeout(1000)

            links = scraper(page, site)
            for link in links:
                items.append({
                    "source": site["name"],
                    "category": category,
                    "title": link["title"],
                    "url": link["url"],
                })

        except Exception as e:
            print(f"  ⚠ {site['name']} の取得に失敗: {e}")
        finally:
            browser.close()

    return items


def scrape_all_sites(sites: list[dict]) -> list[dict]:
    """全サイトを巡回して補助金情報を収集（汎用ループ）"""
    all_items = []
    for site in sites:
        print(f"🔍 [{site['category']}] {site['name']} を巡回中...")
        items = scrape_site(site)
        print(f"   → {len(items)} 件ヒット")
        all_items.extend(items)
    return all_items


# ── 2. Claude API で要約・重要度判定 ──────────────────
def analyze_with_claude(items: list[dict]) -> list[dict]:
    """Claude API で各項目を要約し重要度を判定"""
    if not items:
        return []

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += (
            f"[{i}] [{item.get('category','?')}/{item['source']}] {item['title']}\n"
            f"URL: {item['url']}\n\n"
        )

    prompt = f"""あなたは電気設備工事業・プラント工事・建設業の会社を支援する参謀AIです。
以下は日本の政府系サイトから取得した補助金・助成金関連の新着情報です。
オーナーは電気設備工事士（プラント・公共事業）なので、その業種に役立つ補助金を優先的に抽出・評価してください。

【優先フィルタ】以下に該当するものは importance="高" を強く推奨:
- 電気設備工事・電気工事・配電・受変電・高圧設備に関するもの
- プラント工事・機械設備・計装・制御・産業設備に関するもの
- 建設業・建築・土木・インフラ整備・公共事業に関するもの
- 省エネ設備・再エネ設備・EV充電設備・蓄電池の導入支援
- 建設業DX・現場の生産性向上・施工管理ツール・BIM/CIM 導入
- 中小建設業者向けの事業承継・人材育成・安全衛生・働き方改革

【除外方針】以下は importance="低" または出力スキップ推奨:
- 小売・飲食・観光のみを対象とした補助金
- 農業・漁業のみを対象とした補助金
- 過去の採択結果・イベント終了報告・事務的なお知らせ

出力形式（JSON配列のみ、他の文章は一切不要）:
[
  {{
    "index": 1,
    "source": "サイト名",
    "title": "情報タイトル",
    "url": "URL",
    "summary": "日本語で1〜2文の要約（対象者・金額・締切があれば含める）",
    "importance": "高 or 中 or 低",
    "deadline": "申請期限（YYYY-MM-DD形式、不明ならnull）",
    "amount": "補助金額（例: '最大450万円', '上限50万円'、不明なら空文字）",
    "categories": ["事業内容タグ。該当するものを選択: 電気工事, プラント, 建設業, 設備投資, 省エネ, 再エネ, DX推進, IT導入, 人材育成, 研究開発, 販路開拓, 創業支援, その他"],
    "relevance": "電気工事・プラント・建設業にどう役立つかを1行で（無関係なら空文字）"
  }}
]

重要度の基準:
- 高: 電気工事・プラント・建設業に直結する補助金、または大型の新規公募開始
- 中: 中小企業全般向けの補助金、制度改正、公募予告、中規模助成金
- 低: 無関係業種向け、過去の採択結果、一般的なお知らせ

情報一覧:
{items_text}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not json_match:
        print("⚠ Claude の応答からJSONを抽出できませんでした")
        return []

    results = json.loads(json_match.group())

    # Claude の出力にカテゴリ列を引き継ぐ（元 items から index で紐付け）
    for r in results:
        idx = r.get("index", 0) - 1
        if 0 <= idx < len(items):
            r["category"] = items[idx].get("category", "その他")
        else:
            r.setdefault("category", "その他")

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


def notion_url_exists(url: str) -> bool:
    """同じ公式URLが既にNotionDBに登録済みか確認"""
    if not url:
        return False
    payload = {
        "filter": {
            "property": "公式URL",
            "url": {"equals": url},
        },
        "page_size": 1,
    }
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query",
        headers=NOTION_HEADERS,
        json=payload,
        timeout=15,
    )
    if resp.status_code != 200:
        return False
    return len(resp.json().get("results", [])) > 0


def add_to_notion(item: dict) -> bool:
    """1件の補助金情報をNotionDBに追加"""
    url = item.get("url", "")

    # 重複チェック
    if url and notion_url_exists(url):
        print(f"  ⏭ 重複スキップ: {item.get('title', '')[:30]}")
        return False

    # 事業内容タグ
    categories = item.get("categories", [])
    if not categories:
        categories = ["その他"]

    # プロパティ構築
    properties = {
        "名前": {
            "title": [{"text": {"content": item.get("title", "不明")[:100]}}],
        },
        "概要": {
            "rich_text": [{"text": {"content": item.get("summary", "")[:2000]}}],
        },
        "事業内容": {
            "rich_text": [{"text": {"content": ", ".join(categories)}}],
        },
        "対象事業": {
            "rich_text": [{"text": {"content": "建設業 / 全業種"}}],
        },
    }

    # 公式URL（空でなければ設定）
    if url:
        properties["公式URL"] = {"url": url}

    # 申請期限（検出できた場合のみ）
    deadline = item.get("deadline")
    if deadline and deadline != "null":
        properties["申請期限"] = {"date": {"start": deadline}}

    # 補助金額（検出できた場合のみ）
    amount = item.get("amount", "")
    if amount:
        properties["補助金額"] = {
            "rich_text": [{"text": {"content": amount}}],
        }

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=NOTION_HEADERS,
        json=payload,
        timeout=15,
    )

    if resp.status_code == 200:
        print(f"  ✅ Notion追加: {item.get('title', '')[:40]}")
        return True
    else:
        print(f"  ⚠ Notion追加失敗: {resp.status_code} {resp.text[:100]}")
        return False


def save_to_notion(results: list[dict]):
    """全結果をNotionに保存（重複チェック付き）"""
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        print("⚠ Notion APIキーまたはDatabase IDが未設定です")
        return

    print("\n📝 Notionに保存中...")
    added = 0
    skipped = 0
    for r in results:
        if add_to_notion(r):
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
IMPORTANCE_MARK = {"高": "🔴", "中": "🟡", "低": "🟢"}

CATEGORY_EMOJI = {
    "経産省":       "🏭 経産省",
    "国交省":       "🏗 国交省",
    "NEDO":        "⚡ NEDO",
    "自治体":       "🏛 自治体",
    "中小企業庁":    "🏢 中小企業庁",
    "デジタル庁":    "💻 デジタル庁",
    "補助金ポータル": "🔎 補助金ポータル",
    "その他":       "📌 その他",
}
# 通知の並び順（電気工事・プラント・建設業に近い順）
CATEGORY_ORDER = [
    "経産省", "国交省", "NEDO", "自治体",
    "中小企業庁", "デジタル庁", "補助金ポータル", "その他",
]

IMPORTANCE_RANK = {"高": 0, "中": 1, "低": 2}


def format_briefing(results: list[dict], now: datetime) -> str:
    """ブリーフィングのテキストをカテゴリ別に整形"""
    header = f"💰 補助金情報 {now.strftime('%Y-%m-%d')}"

    # カテゴリ別にグループ化
    by_category: dict[str, list[dict]] = {}
    for r in results:
        cat = r.get("category") or "その他"
        by_category.setdefault(cat, []).append(r)

    # 各カテゴリ内は重要度順でソート
    for cat in by_category:
        by_category[cat].sort(
            key=lambda x: IMPORTANCE_RANK.get(x.get("importance", "低"), 2)
        )

    # サマリー行
    total = len(results)
    high_count = sum(1 for r in results if r.get("importance") == "高")

    lines = [header, f"📊 全{total}件 / 🔴重要{high_count}件"]

    # 定義順＋余ったカテゴリを後ろに
    ordered_cats = [c for c in CATEGORY_ORDER if c in by_category]
    extra_cats = [c for c in by_category if c not in CATEGORY_ORDER]
    all_cats = ordered_cats + extra_cats

    for cat in all_cats:
        items = by_category[cat]
        label = CATEGORY_EMOJI.get(cat, f"📌 {cat}")
        lines.append("")
        lines.append(f"{label} ({len(items)}件)")
        for r in items:
            imp = r.get("importance", "低")
            mark = IMPORTANCE_MARK.get(imp, "")
            source = r.get("source", "不明")
            summary = r.get("summary", r.get("title", ""))
            url = r.get("url", "")
            lines.append(f"  {mark} [{source}] {summary}")
            if url:
                lines.append(f"     {url}")

    if not by_category:
        lines.append("")
        lines.append("新着の補助金情報はありませんでした。")

    return "\n".join(lines)


def format_markdown(results: list[dict], now: datetime) -> str:
    """Obsidian 用の詳細 Markdown をカテゴリ別に生成"""
    lines = [
        f"# 補助金情報 {now.strftime('%Y-%m-%d')}",
        "",
        f"取得時刻: {now.strftime('%Y-%m-%d %H:%M')} JST",
        "",
    ]

    # カテゴリ別にグループ化
    by_category: dict[str, list[dict]] = {}
    for r in results:
        cat = r.get("category") or "その他"
        by_category.setdefault(cat, []).append(r)
    for cat in by_category:
        by_category[cat].sort(
            key=lambda x: IMPORTANCE_RANK.get(x.get("importance", "低"), 2)
        )

    ordered_cats = [c for c in CATEGORY_ORDER if c in by_category]
    extra_cats = [c for c in by_category if c not in CATEGORY_ORDER]

    for cat in ordered_cats + extra_cats:
        label = CATEGORY_EMOJI.get(cat, f"📌 {cat}")
        lines.append(f"## {label} ({len(by_category[cat])}件)")
        lines.append("")
        for r in by_category[cat]:
            imp = r.get("importance", "低")
            mark = IMPORTANCE_MARK.get(imp, "")
            source = r.get("source", "不明")
            title = r.get("title", "")
            summary = r.get("summary", "")
            url = r.get("url", "")
            amount = r.get("amount", "")
            deadline = r.get("deadline")
            relevance = r.get("relevance", "")

            lines.append(f"### {mark} [{source}] {title}")
            lines.append("")
            lines.append(summary)
            meta_bits = []
            if amount:
                meta_bits.append(f"補助金額: {amount}")
            if deadline and deadline != "null":
                meta_bits.append(f"申請期限: {deadline}")
            if meta_bits:
                lines.append("")
                lines.append(" / ".join(meta_bits))
            if relevance:
                lines.append("")
                lines.append(f"💡 {relevance}")
            if url:
                lines.append("")
                lines.append(f"[詳細リンク]({url})")
            lines.append("")

    return "\n".join(lines)


def save_files(line_text: str, md_text: str, now: datetime):
    """output/ と Obsidian Vault に保存"""
    filename = f"{now.strftime('%Y-%m-%d')}.md"

    # output/ に保存
    out_path = OUTPUT_DIR / filename
    out_path.write_text(md_text, encoding="utf-8")
    print(f"💾 保存: {out_path}")

    # Obsidian Vault に保存
    obs_path = OBSIDIAN_DIR / filename
    obs_path.write_text(md_text, encoding="utf-8")
    print(f"💾 保存: {obs_path}")


# ── メイン ────────────────────────────────────────────
def main():
    now = datetime.now(JST)
    print(f"🕐 実行時刻: {now.strftime('%Y-%m-%d %H:%M')} JST\n")

    # 0. サイト読み込み
    sites = load_sites()
    if not sites:
        print("⚠ sites.csv に有効なサイトがありません")
        return

    # 1. スクレイピング
    items = scrape_all_sites(sites)
    print(f"\n📊 合計 {len(items)} 件の補助金関連情報を取得\n")

    if not items:
        msg = f"💰 補助金情報 {now.strftime('%Y-%m-%d')}\n\n新着の補助金情報はありませんでした。"
        send_line_push(msg)
        save_files(msg, f"# 補助金情報 {now.strftime('%Y-%m-%d')}\n\n新着なし", now)
        return

    # 2. Claude で要約・重要度判定
    print("🤖 Claude で分析中...\n")
    results = analyze_with_claude(items)

    # 3. フォーマット
    line_text = format_briefing(results, now)
    md_text = format_markdown(results, now)
    print("─" * 40)
    print(line_text)
    print("─" * 40)

    # 4. LINE 通知
    send_line_push(line_text)

    # 5. ファイル保存
    save_files(line_text, md_text, now)

    # 6. Notion に保存
    save_to_notion(results)

    print("\n✅ 完了")


if __name__ == "__main__":
    main()
