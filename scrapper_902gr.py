import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# # Fix Windows console encoding for Greek text
# if sys.platform == "win32":
#     sys.stdout.reconfigure(encoding="utf-8", errors="replace")
#     sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://www.902.gr"
SECTION = "/ergatiki-taxi"

DT_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}:\d{2})\b")

STOP_MARKERS = {
    "Δες ακόμα",
    "ΡΟΗ ΕΙΔΗΣΕΩΝ",
    "Αναζήτηση",
    "ΠΕΡΙΣΣΟΤΕΡΑ",
}

NOISE_STRINGS = {"Facebook logo", "Twitter logo", "Print Mail logo", "Print HTML logo", "Print PDF logo"}


def create_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "el-GR,el;q=0.9,en;q=0.8",
    })
    return sess


def fetch(sess: requests.Session, url: str) -> BeautifulSoup:
    r = sess.get(url, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def normalize_title(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    return s[:-len("| 902.gr")].strip() if s.endswith("| 902.gr") else s


def pick_published_at(strings: list[str], title: str | None) -> datetime | None:
    if title and title in strings:
        i = strings.index(title)
        window = strings[max(0, i - 15) : min(len(strings), i + 15)]
        for s in window:
            m = DT_RE.search(s)
            if m:
                return datetime.strptime(m.group(1) + " " + m.group(2), "%d/%m/%Y %H:%M")
    for s in strings:
        m = DT_RE.search(s)
        if m:
            return datetime.strptime(m.group(1) + " " + m.group(2), "%d/%m/%Y %H:%M")
    return None


def extract_body(strings: list[str], title: str | None) -> str | None:
    if not title or title not in strings:
        return None
    i = strings.index(title)
    out = []
    for s in strings[i + 1 :]:
        if s in STOP_MARKERS:
            break
        if s in NOISE_STRINGS:
            continue
        out.append(s)
    body = "\n".join(out).strip()
    return body if body else None


def extract_tags(soup: BeautifulSoup, strings: list[str], title: str | None) -> list[str]:
    main = soup.select_one("main") or soup
    tag_links = main.select('a[href*="/taxonomy/term/"], a[href*="/tags/"], a[href*="/tag/"]')
    tags = [a.get_text(" ", strip=True) for a in tag_links if a.get_text(strip=True)]
    tags = list(dict.fromkeys(tags))
    if tags:
        return tags

    if title and title in strings:
        i = strings.index(title)
        for s in reversed(strings[max(0, i - 10) : i]):
            if s in STOP_MARKERS or DT_RE.search(s):
                continue
            if 2 <= len(s) <= 50 and s.upper() == s and not s.isdigit():
                return [s]
    return []


def parse_article(sess: requests.Session, url: str) -> dict | None:
    soup = fetch(sess, url)
    main = soup.select_one("main") or soup
    strings = [s.strip() for s in main.stripped_strings if s and s.strip()]

    title = normalize_title(soup.title.string if soup.title else None)
    published_at = pick_published_at(strings, title)
    if not published_at:
        return None

    return {
        "url": url,
        "title": title,
        "published_at": published_at.isoformat(timespec="minutes"),
        "tags": extract_tags(soup, strings, title),
        "body": extract_body(strings, title),
    }


def scrape_articles(
    cutoff: datetime | None = None,
    max_pages: int | None = None,
    verbose: bool = False,
) -> list[dict]:
    """Scrape articles from 902.gr.
    
    Args:
        cutoff: Stop when articles are older than this date.
        max_pages: Stop after scraping this many pages.
        verbose: Print progress.
    
    At least one of cutoff or max_pages should be provided.
    """
    sess = create_session()
    seen: set[str] = set()
    articles: list[dict] = []
    page = 0

    while True:
        if max_pages is not None and page >= max_pages:
            break

        list_url = f"{BASE}{SECTION}" if page == 0 else f"{BASE}{SECTION}?page={page}"
        if verbose:
            print(f"Fetching page {page}: {list_url}")
        soup = fetch(sess, list_url)

        # Match both relative (/eidisi/ergatiki-taxi/) and absolute URLs
        links = set()
        for a in soup.select('a[href*="/eidisi/ergatiki-taxi/"]'):
            href = a["href"]
            if href.startswith("http"):
                links.add(href)
            else:
                links.add(urljoin(BASE, href))

        new_links = [u for u in links if u not in seen]
        if not new_links:
            break

        oldest_on_page = None

        for url in sorted(new_links):
            seen.add(url)
            item = parse_article(sess, url)
            if not item:
                continue

            dt = datetime.fromisoformat(item["published_at"])
            oldest_on_page = dt if oldest_on_page is None else min(oldest_on_page, dt)

            if cutoff is None or dt >= cutoff:
                articles.append(item)
                if verbose:
                    print(f"  [{len(articles)}] {item['title'][:60]}... ({item['published_at']})")

            time.sleep(0.4)

        if cutoff and oldest_on_page and oldest_on_page < cutoff:
            break

        page += 1
        time.sleep(0.8)

    return articles


def fetch_articles(
    *,
    days: int | None = None,
    since: str | datetime | None = None,
    pages: int | None = None,
    output: str | Path | None = None,
    verbose: bool = False,
) -> list[dict]:
    """
    Fetch articles from 902.gr.

    Args:
        days: Scrape articles from the last N days.
        since: Scrape articles since this date. Can be a datetime or 'YYYY-MM-DD' string.
        pages: Scrape exactly N pages (most efficient for bulk scraping).
        output: If provided, save articles to this file path as JSON.
        verbose: Print progress information.

    Returns:
        List of article dicts with keys: url, title, published_at, tags, body

    Note:
        You must specify at least one of: days, since, or pages.

    Examples:
        # Get last 7 days
        articles = fetch_articles(days=7)

        # Get historical data since a specific date
        articles = fetch_articles(since="2024-01-01")

        # Scrape by page count (efficient for bulk)
        articles = fetch_articles(pages=50)

        # Save to file
        articles = fetch_articles(days=7, output="weekly.json")
    """
    if days is None and since is None and pages is None:
        raise ValueError("Must specify at least one of: days, since, or pages")

    cutoff = None
    if since is not None:
        cutoff = datetime.strptime(since, "%Y-%m-%d") if isinstance(since, str) else since
    elif days is not None:
        cutoff = datetime.now() - timedelta(days=days)

    if verbose:
        if cutoff:
            print(f"Scraping articles since {cutoff.date()}")
        if pages:
            print(f"Scraping {pages} pages")

    articles = scrape_articles(cutoff=cutoff, max_pages=pages, verbose=verbose)

    if verbose:
        print(f"\nTotal articles: {len(articles)}")

    if output:
        output_path = Path(output)
        output_path.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
        if verbose:
            print(f"Saved to {output_path}")

    return articles


def main():
    parser = argparse.ArgumentParser(description="Scrape news articles from 902.gr")
    parser.add_argument("--days", type=int, help="Scrape articles from the last N days")
    parser.add_argument("--since", type=str, help="Scrape articles since date (YYYY-MM-DD)")
    parser.add_argument("--pages", type=int, help="Scrape exactly N pages")
    parser.add_argument("--output", "-o", type=str, help="Output file path (default: stdout as JSON)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print progress")
    args = parser.parse_args()

    if not args.days and not args.since and not args.pages:
        parser.error("Must specify at least one of: --days, --since, or --pages")

    articles = fetch_articles(
        days=args.days,
        since=args.since,
        pages=args.pages,
        output=args.output,
        verbose=args.verbose,
    )

    # Print to stdout only if no output file specified
    if not args.output:
        print(json.dumps(articles, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()