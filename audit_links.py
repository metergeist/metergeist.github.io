#!/usr/bin/env python3
"""
Link audit tool for metergeist.com

Scans all HTML files, extracts internal and external links,
checks HTTP status codes, stores results in SQLite, and
generates link_summary.md.

Usage:
    python3 audit_links.py              # Full audit (scan + check external links)
    python3 audit_links.py --local-only # Scan links without checking external URLs
    python3 audit_links.py --summary    # Regenerate summary from existing DB
    python3 audit_links.py --broken     # Show only broken links from DB
"""

import argparse
import html
import os
import re
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

SITE_ROOT = Path(__file__).parent
BASE_URL = "https://metergeist.com"
DB_PATH = SITE_ROOT / "link_audit.db"
SUMMARY_PATH = SITE_ROOT / "link_summary.md"
USER_AGENT = "metergeist-link-checker/1.0 (+https://metergeist.com)"

# Files to skip (internal tools, not published content)
SKIP_FILES = {"dashboard.html", "film-audit.html", "audit_links.py"}


class LinkExtractor(HTMLParser):
    """Extract all <a href> links and the page title from HTML."""

    def __init__(self):
        super().__init__()
        self.links = []  # [(href, link_text)]
        self.title = ""
        self._in_a = False
        self._current_href = None
        self._current_text_parts = []
        self._in_title = False
        self._title_parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            if href:
                self._in_a = True
                self._current_href = href
                self._current_text_parts = []
        elif tag == "title":
            self._in_title = True
            self._title_parts = []

    def handle_data(self, data):
        if self._in_a:
            self._current_text_parts.append(data)
        if self._in_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._in_a:
            text = " ".join(self._current_text_parts).strip()
            text = " ".join(text.split())  # normalize whitespace
            self.links.append((self._current_href, text))
            self._in_a = False
            self._current_href = None
            self._current_text_parts = []
        elif tag == "title" and self._in_title:
            self.title = " ".join(self._title_parts).strip()
            self._in_title = False

    def handle_entityref(self, name):
        char = html.unescape(f"&{name};")
        if self._in_a:
            self._current_text_parts.append(char)
        if self._in_title:
            self._title_parts.append(char)

    def handle_charref(self, name):
        char = html.unescape(f"&#{name};")
        if self._in_a:
            self._current_text_parts.append(char)
        if self._in_title:
            self._title_parts.append(char)


def init_db():
    """Create or update the SQLite database schema."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pages (
            url TEXT PRIMARY KEY,
            file_path TEXT,
            title TEXT,
            link_count INTEGER DEFAULT 0,
            last_scanned TEXT
        );

        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT NOT NULL,
            target_url TEXT NOT NULL,
            link_text TEXT,
            link_type TEXT CHECK(link_type IN ('internal', 'external')),
            http_status INTEGER,
            last_checked TEXT,
            UNIQUE(source_url, target_url, link_text)
        );

        CREATE TABLE IF NOT EXISTS check_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_url TEXT NOT NULL,
            http_status INTEGER,
            response_time_ms INTEGER,
            checked_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_url);
        CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_url);
        CREATE INDEX IF NOT EXISTS idx_links_status ON links(http_status);
        CREATE INDEX IF NOT EXISTS idx_history_url ON check_history(target_url);
        CREATE INDEX IF NOT EXISTS idx_history_time ON check_history(checked_at);
    """)
    conn.commit()
    return conn


def find_html_files():
    """Find all publishable HTML files in the site."""
    files = []
    for path in sorted(SITE_ROOT.rglob("*.html")):
        rel = path.relative_to(SITE_ROOT)
        parts = rel.parts
        # Skip hidden dirs, node_modules, etc.
        if any(p.startswith(".") or p.startswith("_") or p == "node_modules" for p in parts):
            continue
        if rel.name in SKIP_FILES:
            continue
        files.append(path)
    return files


def file_to_url(file_path):
    """Convert a local file path to its canonical URL."""
    rel = file_path.relative_to(SITE_ROOT)
    if rel.name == "index.html":
        parent = str(rel.parent)
        if parent == ".":
            return BASE_URL + "/"
        return BASE_URL + "/" + parent + "/"
    return BASE_URL + "/" + str(rel)


def classify_link(href, page_url):
    """Classify a link as internal, external, or None (skip).

    Returns (link_type, resolved_url) or (None, None) for skippable links.
    """
    if not href:
        return None, None
    href = href.strip()
    if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:") or href.startswith("tel:"):
        return None, None

    resolved = urljoin(page_url, href)
    parsed = urlparse(resolved)

    if parsed.netloc in ("metergeist.com", "www.metergeist.com", ""):
        # Strip fragment for internal links
        clean = parsed._replace(fragment="").geturl()
        return "internal", clean
    else:
        return "external", resolved


def check_url(url, timeout=15):
    """Check a URL's HTTP status. Returns (status_code, response_time_ms)."""
    ctx = ssl.create_default_context()
    start = time.time()

    # Try HEAD first (faster)
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        elapsed = int((time.time() - start) * 1000)
        return resp.status, elapsed
    except urllib.error.HTTPError as e:
        # Some servers reject HEAD, try GET for 403/405
        if e.code in (403, 405):
            pass
        else:
            elapsed = int((time.time() - start) * 1000)
            return e.code, elapsed
    except Exception:
        pass

    # Fallback to GET
    start = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        elapsed = int((time.time() - start) * 1000)
        return resp.status, elapsed
    except urllib.error.HTTPError as e:
        elapsed = int((time.time() - start) * 1000)
        return e.code, elapsed
    except Exception:
        elapsed = int((time.time() - start) * 1000)
        return 0, elapsed  # 0 = connection failed


def check_internal_link(target_url):
    """Check if an internal link resolves to a local file."""
    parsed = urlparse(target_url)
    path = parsed.path

    if path.endswith("/"):
        local_path = SITE_ROOT / path.lstrip("/") / "index.html"
    else:
        local_path = SITE_ROOT / path.lstrip("/")

    return 200 if local_path.exists() else 404


def scan_pages(conn):
    """Scan all HTML files, extract links, and store in the database."""
    now = datetime.utcnow().isoformat() + "Z"
    files = find_html_files()
    print(f"Scanning {len(files)} HTML files...")

    # Clear old link data (we rebuild on each scan)
    conn.execute("DELETE FROM links")
    conn.execute("DELETE FROM pages")
    conn.commit()

    total_links = 0
    for file_path in files:
        page_url = file_to_url(file_path)
        rel_path = str(file_path.relative_to(SITE_ROOT))

        content = file_path.read_text(encoding="utf-8", errors="replace")
        extractor = LinkExtractor()
        try:
            extractor.feed(content)
        except Exception as e:
            print(f"  Warning: parse error in {rel_path}: {e}")
            continue

        # Store page
        conn.execute(
            "INSERT OR REPLACE INTO pages (url, file_path, title, link_count, last_scanned) VALUES (?, ?, ?, ?, ?)",
            (page_url, rel_path, extractor.title, len(extractor.links), now),
        )

        # Store links
        for href, text in extractor.links:
            link_type, resolved = classify_link(href, page_url)
            if link_type is None:
                continue

            # Check internal links immediately (fast, local file check)
            status = None
            checked = None
            if link_type == "internal":
                status = check_internal_link(resolved)
                checked = now

            conn.execute(
                """INSERT OR REPLACE INTO links (source_url, target_url, link_text, link_type, http_status, last_checked)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (page_url, resolved, text, link_type, status, checked),
            )
            total_links += 1

        conn.commit()

    print(f"Found {total_links} links across {len(files)} pages.")
    return total_links


def check_external_links(conn):
    """Check all external links and record results."""
    now = datetime.utcnow().isoformat() + "Z"
    rows = conn.execute(
        "SELECT DISTINCT target_url FROM links WHERE link_type = 'external' ORDER BY target_url"
    ).fetchall()

    print(f"\nChecking {len(rows)} unique external URLs...")
    checked = 0
    broken = 0

    for (url,) in rows:
        checked += 1
        status, response_ms = check_url(url)

        # Update all link rows pointing to this URL
        conn.execute(
            "UPDATE links SET http_status = ?, last_checked = ? WHERE target_url = ?",
            (status, now, url),
        )

        # Record in history
        conn.execute(
            "INSERT INTO check_history (target_url, http_status, response_time_ms, checked_at) VALUES (?, ?, ?, ?)",
            (url, status, response_ms, now),
        )

        icon = "ok" if 200 <= status < 400 else "BROKEN" if status in (0, 404, 410) else "warn"
        if icon == "BROKEN":
            broken += 1
        if icon != "ok":
            print(f"  [{status:>3}] {url}")
        elif checked % 10 == 0:
            print(f"  ...checked {checked}/{len(rows)}")

        conn.commit()
        time.sleep(0.3)  # rate limit

    print(f"Done. {broken} broken, {checked - broken} ok out of {checked} URLs.")


def generate_summary(conn):
    """Generate link_summary.md from the database."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    pages = conn.execute(
        "SELECT url, file_path, title, link_count FROM pages ORDER BY file_path"
    ).fetchall()

    # Stats
    total_links = conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]
    internal_count = conn.execute("SELECT COUNT(*) FROM links WHERE link_type='internal'").fetchone()[0]
    external_count = conn.execute("SELECT COUNT(*) FROM links WHERE link_type='external'").fetchone()[0]
    broken_internal = conn.execute(
        "SELECT COUNT(*) FROM links WHERE link_type='internal' AND http_status=404"
    ).fetchone()[0]
    broken_external = conn.execute(
        "SELECT COUNT(*) FROM links WHERE link_type='external' AND http_status IN (0, 404, 410)"
    ).fetchone()[0]
    unchecked = conn.execute(
        "SELECT COUNT(*) FROM links WHERE link_type='external' AND http_status IS NULL"
    ).fetchone()[0]

    lines = []
    lines.append(f"# metergeist.com Link Audit")
    lines.append(f"")
    lines.append(f"Generated: {now}")
    lines.append(f"")
    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Pages scanned | {len(pages)} |")
    lines.append(f"| Total links | {total_links} |")
    lines.append(f"| Internal links | {internal_count} |")
    lines.append(f"| External links | {external_count} |")
    lines.append(f"| Broken internal | {broken_internal} |")
    lines.append(f"| Broken external | {broken_external} |")
    if unchecked:
        lines.append(f"| Unchecked external | {unchecked} |")
    lines.append(f"")

    # Broken links section (if any)
    broken_rows = conn.execute(
        """SELECT l.source_url, l.target_url, l.link_text, l.http_status, l.link_type
           FROM links l
           WHERE l.http_status IN (0, 404, 410)
              OR (l.link_type = 'internal' AND l.http_status = 404)
           ORDER BY l.http_status, l.source_url"""
    ).fetchall()

    if broken_rows:
        lines.append(f"## Broken Links")
        lines.append(f"")
        lines.append(f"| Status | Source | Target | Link Text |")
        lines.append(f"|--------|--------|--------|-----------|")
        for source, target, text, status, ltype in broken_rows:
            src_short = source.replace(BASE_URL, "")
            tgt_short = target.replace(BASE_URL, "") if ltype == "internal" else target
            text_short = (text[:40] + "...") if len(text) > 43 else text
            lines.append(f"| {status} | `{src_short}` | `{tgt_short}` | {text_short} |")
        lines.append(f"")

    # Warnings (403, 5xx)
    warn_rows = conn.execute(
        """SELECT l.source_url, l.target_url, l.link_text, l.http_status
           FROM links l
           WHERE l.link_type = 'external'
             AND l.http_status IS NOT NULL
             AND l.http_status NOT IN (0, 200, 301, 302, 303, 307, 308, 404, 410)
           ORDER BY l.http_status, l.source_url"""
    ).fetchall()

    if warn_rows:
        lines.append(f"## Warnings (non-200, non-404)")
        lines.append(f"")
        lines.append(f"| Status | Source | Target | Link Text |")
        lines.append(f"|--------|--------|--------|-----------|")
        for source, target, text, status in warn_rows:
            src_short = source.replace(BASE_URL, "")
            text_short = (text[:40] + "...") if len(text) > 43 else text
            lines.append(f"| {status} | `{src_short}` | `{target}` | {text_short} |")
        lines.append(f"")

    # Per-page breakdown
    lines.append(f"## Pages")
    lines.append(f"")

    for page_url, file_path, title, link_count in pages:
        page_short = page_url.replace(BASE_URL, "")
        lines.append(f"### `{page_short}`")
        lines.append(f"")
        lines.append(f"**{title}** ({link_count} links)")
        lines.append(f"")

        page_links = conn.execute(
            """SELECT target_url, link_text, link_type, http_status
               FROM links WHERE source_url = ? ORDER BY link_type, target_url""",
            (page_url,),
        ).fetchall()

        if not page_links:
            lines.append(f"No links found.")
            lines.append(f"")
            continue

        # Internal links
        internal = [(t, txt, s) for t, txt, lt, s in page_links if lt == "internal"]
        if internal:
            lines.append(f"**Internal ({len(internal)}):**")
            for target, text, status in internal:
                tgt_short = target.replace(BASE_URL, "")
                icon = "x" if status == 404 else " "
                lines.append(f"- [{icon}] `{tgt_short}` — {text}")
            lines.append(f"")

        # External links
        external = [(t, txt, s) for t, txt, lt, s in page_links if lt == "external"]
        if external:
            lines.append(f"**External ({len(external)}):**")
            for target, text, status in external:
                if status is None:
                    icon = "?"
                elif 200 <= status < 400:
                    icon = " "
                elif status in (0, 404, 410):
                    icon = "x"
                else:
                    icon = "!"
                lines.append(f"- [{icon}] [{status or '?'}] {target} — {text}")
            lines.append(f"")

    content = "\n".join(lines) + "\n"
    SUMMARY_PATH.write_text(content, encoding="utf-8")
    print(f"\nSummary written to {SUMMARY_PATH}")


def show_broken(conn):
    """Print broken links from the database."""
    rows = conn.execute(
        """SELECT l.source_url, l.target_url, l.link_text, l.http_status, l.link_type,
                  p.file_path
           FROM links l
           JOIN pages p ON p.url = l.source_url
           WHERE l.http_status IN (0, 404, 410)
           ORDER BY l.link_type, l.http_status, l.source_url"""
    ).fetchall()

    if not rows:
        print("No broken links found.")
        return

    print(f"\n{'='*70}")
    print(f" BROKEN LINKS ({len(rows)} found)")
    print(f"{'='*70}\n")

    for source, target, text, status, ltype, fpath in rows:
        src_short = source.replace(BASE_URL, "")
        print(f"  [{status}] {ltype.upper()}")
        print(f"       URL: {target}")
        print(f"      Text: {text}")
        print(f"    Source: {fpath}")
        print(f"      Page: {src_short}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Link audit tool for metergeist.com")
    parser.add_argument("--local-only", action="store_true", help="Scan links without checking external URLs")
    parser.add_argument("--summary", action="store_true", help="Regenerate summary from existing DB data")
    parser.add_argument("--broken", action="store_true", help="Show broken links from DB")
    args = parser.parse_args()

    os.chdir(SITE_ROOT)
    conn = init_db()

    if args.summary:
        generate_summary(conn)
        conn.close()
        return

    if args.broken:
        show_broken(conn)
        conn.close()
        return

    scan_pages(conn)

    if not args.local_only:
        check_external_links(conn)

    generate_summary(conn)
    show_broken(conn)
    conn.close()


if __name__ == "__main__":
    main()
