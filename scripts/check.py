#!/usr/bin/env python3
"""Checks the built site in site/ for broken internal links and risky wording.

    python scripts/check.py
Exits with an error if anything is wrong, so a bad build is never published.
"""
import html.parser
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE = Path(os.environ["SITE_OUT"]) if os.environ.get("SITE_OUT") else ROOT / "site"
BASE = json.load(open(ROOT / "data" / "site.json", encoding="utf-8")).get("base_url", "").strip().rstrip("/")

# Wording the site must never use about tools or vendors.
BANNED = [r"\bequivalent to\b", r"\bas good as\b", r"\breplaces?\b(?! a paid)", r"\bbetter than\b", r"\bcourt[- ]approved\b",
          r"\bcertified\b", r"\bguaranteed?\b", r"\bofficial partner\b", r"\bendorsed by\b(?! any)"]


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids, self.text = [], set(), []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        for key in ("href", "src", "action"):
            if a.get(key):
                self.links.append(a[key])
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)


def main():
    if not SITE.exists():
        sys.exit("site/ does not exist. Run scripts/build.py first.")
    pages = {}
    for path in SITE.rglob("*.html"):
        p = Links()
        p.feed(path.read_text(encoding="utf-8"))
        pages[path] = p
    errors = []
    external = set()
    for path, p in pages.items():
        rel = path.relative_to(SITE).as_posix()
        for link in p.links:
            if link.startswith(("mailto:", "data:")):
                continue
            if BASE and link.startswith(BASE + "/"):
                link = link[len(BASE) + 1:]
                target_base = SITE
            elif urlparse(link).scheme in ("http", "https"):
                external.add(link)
                if not link.startswith("https://"):
                    errors.append("%s: link is not https: %s" % (rel, link))
                continue
            else:
                target_base = path.parent
            url, frag = urldefrag(link)
            url = url.split("?", 1)[0]
            target = (target_base / url).resolve() if url else path
            if not target.exists():
                errors.append("%s: broken link to %s" % (rel, link))
            elif frag and target.suffix == ".html" and target in pages and frag not in pages[target].ids:
                errors.append("%s: missing anchor #%s in %s" % (rel, frag, url or rel))
        text = " ".join(p.text)
        for pattern in BANNED:
            m = re.search(pattern, text, re.I)
            if m:
                start = max(0, m.start() - 40)
                errors.append("%s: wording to avoid: ...%s..." % (rel, text[start:m.end() + 30].strip()))
    print("Checked %d pages, %d external links." % (len(pages), len(external)))
    if errors:
        print("%d problems:" % len(errors))
        for err in errors[:60]:
            print("  " + err)
        return 1
    print("No problems found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
