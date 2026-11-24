"""External link check for the built site. Run by hand: python scripts/linkcheck.py

Reads site/**/*.html, tests every unique https:// link and writes link-report.csv.
403, 429 and 999 mean a site refuses scripts, so they are listed as "blocked", not dead.
Exit code is 1 only when a link is dead (404, 410 or a DNS failure).
"""
import concurrent.futures
import csv
import re
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
UA = "Mozilla/5.0 (compatible; digitalforensictool-linkcheck)"
BLOCKED = {403, 429, 999}
DEAD = {404, 410}


def links():
    found = {}
    for f in sorted(SITE.rglob("*.html")):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'href="(https://[^"#]+)', text):
            found.setdefault(m.group(1).replace("&amp;", "&"), f.relative_to(SITE).as_posix())
    return found


def fetch(url, method):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.status


def check(url):
    for method in ("HEAD", "GET"):
        try:
            return fetch(url, method), ""
        except urllib.error.HTTPError as err:
            code = err.code
            if method == "HEAD" and code not in (404, 410):
                continue
            return code, ""
        except (socket.gaierror,) as err:
            return 0, "dns: %s" % err
        except urllib.error.URLError as err:
            if isinstance(err.reason, socket.gaierror):
                return 0, "dns: %s" % err.reason
            if method == "HEAD":
                continue
            return -1, str(err.reason)
        except (TimeoutError, OSError, ValueError) as err:
            if method == "HEAD":
                continue
            return -1, str(err)
    return -1, "no answer"


def main():
    if not SITE.exists():
        sys.exit("Run python scripts/build.py first.")
    found = links()
    print("Checking %d unique external links..." % len(found))
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        for (url, page), (code, note) in zip(found.items(), pool.map(check, found)):
            if code == 0 or code in DEAD:
                state = "dead"
            elif code in BLOCKED:
                state = "blocked"
            elif 200 <= code < 400:
                state = "ok"
            else:
                state = "check"
            rows.append((state, code, url, page, note))
    rows.sort()
    with open(ROOT / "link-report.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["state", "status", "url", "first_page", "note"])
        w.writerows(rows)
    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    print(", ".join("%s: %d" % kv for kv in sorted(counts.items())))
    for r in rows:
        if r[0] == "dead":
            print("DEAD  %s  (%s)" % (r[2], r[3]))
    sys.exit(1 if counts.get("dead") else 0)


if __name__ == "__main__":
    main()
