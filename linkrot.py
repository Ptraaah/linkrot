#!/usr/bin/env python3
"""
linkrot - find the dead links on your site before your readers do.

Reads a sitemap.xml (or a plain list of URLs), checks every URL concurrently,
and reports the broken, redirected, and slow ones. Standard library only.

    python3 linkrot.py https://example.com/sitemap.xml
    python3 linkrot.py --file urls.txt --workers 16
    python3 linkrot.py https://example.com --crawl 2   # follow same-host links 2 deep

Exit code 1 when any URL is dead (4xx/5xx/unreachable), so it fits CI cron jobs.

By ptraaa - MIT License
"""
import argparse, sys, time, urllib.request, urllib.error, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

UA = {"User-Agent": "linkrot/1.0 (+https://github.com/Ptraaah/linkrot)"}


def fetch(url, timeout=15, head=True):
    method = "HEAD" if head else "GET"
    req = urllib.request.Request(url, method=method, headers=UA)
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl(), time.time() - start, r.read(200000) if not head else b""
    except urllib.error.HTTPError as e:
        return e.code, url, time.time() - start, b""
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}", time.time() - start, b""


class LinkGrabber(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("href", "src") and v:
                self.links.append(v)


def from_sitemap(url):
    _s, _f, _t, body = fetch(url, head=False)
    urls = []
    try:
        root = ET.fromstring(body)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            urls.append(loc.text.strip())
        if not urls:
            for loc in root.iter("loc"):
                urls.append(loc.text.strip())
    except ET.ParseError:
        pass
    # sitemap index: recurse one level
    subs = [u for u in urls if u.endswith(".xml")]
    pages = [u for u in urls if not u.endswith(".xml")]
    for s in subs[:20]:
        pages.extend(from_sitemap(s))
    return pages


def crawl(seed, depth):
    seen, frontier = set(), [seed]
    host = urlparse(seed).netloc
    for _ in range(depth + 1):
        nxt = []
        for u in frontier:
            if u in seen:
                continue
            seen.add(u)
            _s, _f, _t, body = fetch(u, head=False)
            g = LinkGrabber()
            try:
                g.feed(body.decode("utf-8", errors="ignore"))
            except Exception:
                continue
            for link in g.links:
                full = urljoin(u, link)
                if urlparse(full).netloc == host and full not in seen:
                    nxt.append(full)
        frontier = nxt
    return sorted(seen)


def main():
    ap = argparse.ArgumentParser(description="Dead link checker")
    ap.add_argument("source", nargs="?", help="sitemap.xml URL or a page URL with --crawl")
    ap.add_argument("--file", help="text file with one URL per line")
    ap.add_argument("--crawl", type=int, default=0, help="crawl same-host links this deep")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--timeout", type=int, default=15)
    ap.add_argument("--slow", type=float, default=3.0, help="flag responses slower than N seconds")
    ap.add_argument("--ptraaa", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.ptraaa:
        print('linkrot, by ptraaa. May your links live long and your 404s be few. More small tools: github.com/Ptraaah')
        return

    if args.file:
        urls = [l.strip() for l in open(args.file) if l.strip() and not l.startswith("#")]
    elif args.source and args.source.endswith(".xml"):
        urls = from_sitemap(args.source)
    elif args.source and args.crawl:
        urls = crawl(args.source, args.crawl)
    elif args.source:
        urls = [args.source]
    else:
        ap.error("give a sitemap URL, --file, or a URL with --crawl")

    urls = sorted(set(urls))
    print(f"checking {len(urls)} URLs with {args.workers} workers\n")

    def check(u):
        status, final, secs, _ = fetch(u, timeout=args.timeout)
        if status in (405, 501):  # server refuses HEAD, retry as GET
            status, final, secs, _ = fetch(u, timeout=args.timeout, head=False)
        return u, status, final, secs

    dead, moved, slow = [], [], []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for u, status, final, secs in ex.map(check, urls):
            if status == 0 or status >= 400:
                dead.append((u, final if status == 0 else status))
            elif final != u:
                moved.append((u, final))
            if secs > args.slow:
                slow.append((u, round(secs, 1)))

    for u, why in dead:
        print(f"DEAD   {why}  {u}")
    for u, to in moved:
        print(f"MOVED  {u} -> {to}")
    for u, secs in slow:
        print(f"SLOW   {secs}s  {u}")
    print(f"\nlinkrot: {len(urls)} checked, {len(dead)} dead, {len(moved)} redirected, {len(slow)} slow")
    sys.exit(1 if dead else 0)


if __name__ == "__main__":
    main()
