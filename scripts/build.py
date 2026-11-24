#!/usr/bin/env python3
"""Builds the static website from the files in data/ into site/.

Uses only the Python standard library. Run from anywhere:
    python scripts/build.py
"""
import re
import datetime
import html
import json
import os
import shutil
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = Path(os.environ["SITE_OUT"]) if os.environ.get("SITE_OUT") else ROOT / "site"

e = html.escape


def load(name, default=None):
    path = DATA / name
    if not path.exists():
        if default is not None:
            return default
        sys.exit("Missing data file: %s" % path)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


SITE = load("site.json")
CATS = load("categories.json")
TOOLS = load("tools.json")
INTEG = load("commercial-integrations.json")
LEARN = load("learn-sources.json")
PRACTICE = load("practice.json")
NIST = load("nist-functionalities.json", {"source": "", "functionalities": []})
RELDATA = load("releases.json", {"generated": None, "tools": {}})
REL = RELDATA.get("tools", {})

PREVIEW = "--preview" in sys.argv
MAX_PER_CATEGORY = 25
CATEGORY_SHOWN = 10


def load_folder(name):
    """Optional content folders. Entries marked "draft": true are built only with --preview."""
    found = {}
    if (DATA / name).is_dir():
        for p in sorted((DATA / name).glob("*.json")):
            with open(p, encoding="utf-8") as fh:
                item = json.load(fh)
            if item.get("draft") and not PREVIEW:
                continue
            found[p.stem] = item
    return found


GUIDES = load_folder("guides")
WORKFLOWS = load_folder("workflows")
BASICS = load_folder("basics")

CAT = {c["id"]: c for c in CATS}
TOOL = {t["id"]: t for t in TOOLS}
NAME = SITE["name"]
REPO = SITE.get("github_repo", "").strip()
BASE = SITE.get("base_url", "").strip().rstrip("/")
WARNINGS = []

LEVELS = {"beginner": "Beginner", "intermediate": "Intermediate", "advanced": "Advanced"}
SENSITIVE = {
    "passwords": "Use password recovery tools only on devices and data you are authorised to examine.",
    "malware": "Analyse suspicious files only inside an isolated virtual machine, never on your everyday computer.",
    "osint": "Collect only publicly available information, and follow the law and your institution's ethics rules.",
}


# ---------------------------------------------------------------- helpers

def fmt_date(iso):
    if not iso:
        return ""
    try:
        d = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    return "%d %s %d" % (d.day, d.strftime("%b"), d.year)


def fmt_size(n):
    if not n:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def fmt_count(n):
    if n is None:
        return ""
    return ("%.1fk" % (n / 1000.0)) if n >= 1000 else str(n)


def rel_of(t):
    r = REL.get(t["id"])
    if not r or r.get("repo_mismatch") or r.get("missing"):
        return None
    return r


def eff_type(t):
    return t["type"]


def licence(t):
    """Returns (css class, badge text, long text)."""
    ty = eff_type(t)
    r = rel_of(t)
    spdx = r.get("license") if r else None
    if spdx in ("NOASSERTION", "NONE"):
        spdx = None
    spdx = t.get("licence") or spdx
    if ty == "open-source":
        return "oss", "Open source", "Open source" + (" (%s)" % spdx if spdx else "")
    if ty == "source-published":
        return "src", "Free, source published", "Free, source published" + (" (%s)" % spdx if spdx else "")
    if ty == "free-resource":
        return "src", "Free resource", "Free public resource (data or programme, not software)"
    return "free", "Free, closed source", "Free, closed source"


NOTICE_LABEL = {"deprecated": "Deprecated", "maintenance": "Maintenance mode", "unmaintained": "Not maintained"}


def notice_badge(t):
    n = t.get("notice")
    if not n:
        return ""
    return '<span class="badge warn">%s</span>' % NOTICE_LABEL.get(n.get("level"), "Note")


def activity(t):
    r = rel_of(t)
    if not r:
        return None
    if r.get("archived"):
        return "Archived"
    pushed = r.get("pushed_at")
    if not pushed:
        return None
    try:
        d = datetime.datetime.fromisoformat(pushed.replace("Z", "+00:00"))
    except ValueError:
        return None
    days = (datetime.datetime.now(datetime.timezone.utc) - d).days
    if days <= 180:
        return "Active"
    if days <= 730:
        return "Quiet"
    return "Not updated for over 2 years"


def source_url(t):
    return ("https://github.com/" + t["repo"]) if "repo" in t else t["url"]


def issue_url(kind, title):
    if not REPO:
        return None
    return "https://github.com/%s/issues/new?template=%s.yml&title=%s" % (
        REPO, kind, urllib.parse.quote(title))


ICON_DL = '<svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M8 2v8M4.5 7L8 10.5 11.5 7M2.5 13.5h11"/></svg>'
ICON_LOGO = '<svg aria-hidden="true" width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="#FFD84A" stroke-width="2"><rect x="3" y="3" width="22" height="22" rx="4"/><circle cx="12.5" cy="12.5" r="4.5"/><path d="M16 16l5 5"/></svg>'
ICON_SEARCH = '<svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="#3B4A7A" stroke-width="2"><circle cx="9" cy="9" r="6"/><path d="M14 14l4 4"/></svg>'
FAVICON = "data:image/svg+xml," + urllib.parse.quote(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28"><rect width="28" height="28" rx="6" fill="#1437C8"/>'
    '<circle cx="12.5" cy="12.5" r="5" fill="none" stroke="#FFD84A" stroke-width="2.5"/>'
    '<path d="M16.5 16.5l5 5" stroke="#FFD84A" stroke-width="2.5"/></svg>')

ICON_MENU = ('<svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round"><path d="M3 5.5h14M3 10h14M3 14.5h14"/></svg>')

NAV = [("tools", "Tools", "tools.html"), ("practice", "Practice", "practice.html"), ("about", "About", "about.html")]
if WORKFLOWS:
    NAV.insert(1, ("workflows", "Workflows", "workflows.html"))
if BASICS:
    NAV.insert(0, ("basics", "Basics", "basics.html"))
NAV.insert(0, ("home", "Home", "index.html"))


def ld(obj):
    """JSON-LD script tag. The closing-tag sequence is escaped so page text cannot end the script early."""
    return '<script type="application/ld+json">%s</script>' % json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def page(path, title, desc, body, current="", head="", og_type="website"):
    if len(desc) > 158:
        desc = desc[:155].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    depth = path.count("/")
    px = "../" * depth
    if path == "404.html" and BASE:
        px = BASE + "/"
    full_title = NAME if path == "index.html" else "%s · %s" % (title, NAME)
    nav = "".join('<a href="%s%s"%s>%s</a>' % (px, href, ' aria-current="page"' if key == current else "", e(label))
                  for key, label, href in NAV)
    suggest = issue_url("suggest-tool", "Tool suggestion: ") or (px + "about.html#suggest")
    canonical = ('<link rel="canonical" href="%s/%s">' % (BASE, "" if path == "index.html" else path)) if BASE else ""
    maint = SITE.get("maintainer", "").strip()
    doc = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{og_url}">
<meta property="og:site_name" content="{name}">
{og_image}<meta name="twitter:card" content="summary_large_image">
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta name="theme-color" content="#1437C8" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0B1020" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="light dark">
<meta name="format-detection" content="telephone=no">
<script>document.documentElement.className="js"</script>
{canonical}
<link rel="icon" href="{favicon}">
<link rel="apple-touch-icon" href="{px}assets/apple-touch-icon.png">
<link rel="stylesheet" href="{px}assets/style.css">
{head}
</head>
<body id="top">
<a class="skip" href="#main">Skip to content</a>
<header class="site-head"><div class="wrap">
<a class="brand" href="{px}index.html">{logo}<span>{name}</span></a>
<button type="button" class="menu-btn" aria-expanded="false" aria-controls="site-nav">{menu_icon}<span>Menu</span></button>
<nav class="nav" id="site-nav" aria-label="Main">{nav}<a class="btn primary small" href="{suggest}">Suggest a tool</a></nav>
</div></header>
<main id="main">
{body}
</main>
<footer class="site-foot"><div class="wrap">
<p class="about">{name} is an independent educational resource. It is not affiliated with, sponsored by or endorsed by any vendor or project listed here. Credit for every tool belongs to its developers. Product names are trademarks of their owners. Downloads come from third parties: validate every tool yourself before using it on real evidence.</p>
<nav aria-label="Footer" class="foot-cols">
<div><div class="label">Learn</div>{basics_link}{wf_link}<a href="{px}learn.html">Learn</a><a href="{px}practice.html">Practice</a><a href="{px}lab.html">Evidence lab</a></div>
<div><div class="label">Tools</div><a href="{px}index.html#categories">Categories</a><a href="{px}compare.html">Compare tools</a><a href="{px}alternatives.html">Alternatives</a><a href="{px}inside.html">Inside commercial tools</a><a href="{px}vendor-free.html">Free tools from vendors</a><a href="{px}toolbox.html">Pocket toolbox</a><a href="{px}nist.html">Browse by NIST functionality</a></div>
<div><div class="label">Project</div><a href="{px}about.html">About and disclaimer</a><a href="{px}about.html#corrections">Corrections and removal requests</a><a href="{px}about.html#privacy">Privacy</a>{contribute}{maint}<span class="updated">Last updated: {built}</span></div>
</nav>
</div></footer>
<script src="{px}assets/app.js" defer></script>
</body>
</html>
""".format(title=e(full_title), desc=e(desc), canonical=canonical, head=head, og_type=og_type,
           og_url=e("%s/%s" % (BASE, "" if path == "index.html" else path)) if BASE else "",
           og_image=('<meta property="og:image" content="%s/assets/og-image.png">\n<meta property="og:image:width" content="1200">'
                     '<meta property="og:image:height" content="630">\n<meta property="og:image:alt" content="%s: free and open-source digital forensics tools for students">\n'
                     % (BASE, e(NAME))) if BASE else "", favicon=FAVICON, px=px, logo=ICON_LOGO,
           name=e(NAME), nav=nav, suggest=e(suggest), body=body, menu_icon=ICON_MENU,
           basics_link=('<a href="%sbasics.html">Basics</a><a href="%sglossary.html">Glossary</a>' % (px, px)) if BASICS else "",
           wf_link=('<a href="%sworkflows.html">Workflows</a>' % px) if WORKFLOWS else "",
           contribute=('<a href="https://github.com/%s" rel="noopener">Contribute on GitHub</a>' % e(REPO)) if REPO else "",
           built=datetime.date.today().strftime("%d %b %Y").lstrip("0"),
           maint=('<span>Maintained by %s</span>' % e(maint)) if maint else "")
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(doc, encoding="utf-8")
    PAGES.append(path)


PAGES = []


def tool_tags(t):
    tags = [LEVELS[t["level"]], t["interface"]] + t["platforms"]
    return '<div class="tags">%s</div>' % "".join('<span class="tag">%s</span>' % e(x) for x in tags)


def card(t, px):
    cls, badge, _ = licence(t)
    r = rel_of(t) or {}
    text = " ".join([t["name"], t["developer"], t["summary"], " ".join(t.get("similar_to", [])),
                     " ".join(CAT[c]["name"] for c in t["categories"]), " ".join(t["platforms"]),
                     t.get("licence_note", "")]).lower()
    foot = ""
    if t.get("similar_to"):
        foot = '<div class="foot"><span class="label">Similar job to</span><br>%s</div>' % e(", ".join(t["similar_to"]))
    return ('<article class="card" data-item data-name="{name_l}" data-text="{text}" data-type="{type}" '
            'data-level="{level}" data-plat="{plat}" data-stars="{stars}" data-updated="{upd}">'
            '<div class="top"><div><h3><a href="{px}tools/{id}.html">{name}</a></h3><div class="by">by {dev}</div></div>'
            '<span class="badge {cls}">{badge}</span></div>{nb}'
            '<p class="sum">{sum}</p>{tags}{foot}</article>').format(
        name_l=e(t["name"].lower()), text=e(text), type=eff_type(t), level=t["level"],
        plat=e(" ".join(p.lower() for p in t["platforms"])), stars=r.get("stars") or 0, upd=e(r.get("pushed_at") or ""),
        px=px, id=t["id"], name=e(t["name"]), dev=e(t["developer"]), cls=cls, badge=badge, sum=e(t["summary"]),
        tags=tool_tags(t), foot=foot, nb=('<div class="tags">%s</div>' % notice_badge(t)) if t.get('notice') else '')


def filters(target, placeholder, platforms=True):
    def group(key, label, options):
        btns = "".join('<button type="button" class="chip" data-value="%s" aria-pressed="%s">%s</button>'
                       % (v, "true" if v == "all" else "false", e(l)) for v, l in options)
        return '<div class="row" data-group="%s"><span class="label">%s</span>%s</div>' % (key, label, btns)
    rows = ['<div class="row"><label class="label" for="q">Search</label>'
            '<input id="q" type="search" placeholder="%s" autocomplete="off">'
            '<label class="label" for="sort" style="flex:0 0 auto">Sort</label>'
            '<select id="sort" data-sort><option value="name">Name</option><option value="stars">Most starred</option>'
            '<option value="updated">Recently updated</option></select>'
            '<button type="button" class="chip filter-toggle" aria-expanded="false" aria-controls="more-filters">Filters</button></div>'
            % e(placeholder)]
    more = [
            group("type", "Licence", [("all", "All"), ("open-source", "Open source"),
                                      ("source-published", "Source published"), ("free-closed", "Free, closed source"),
                                      ("free-resource", "Free resource")]),
            group("level", "Level", [("all", "All"), ("beginner", "Beginner"), ("intermediate", "Intermediate"),
                                     ("advanced", "Advanced")])]
    if platforms:
        more.append(group("plat", "Runs on", [("all", "All"), ("windows", "Windows"), ("linux", "Linux"),
                                              ("macos", "macOS"), ("web", "Web")]))
    rows.append('<div class="more" id="more-filters">%s</div>' % "".join(more))
    return '<div class="filters" data-filters="%s">%s</div>' % (target, "".join(rows))


def tool_list(tools, px, placeholder, limit=0):
    if limit and len(tools) > limit:
        order = {"beginner": 0, "intermediate": 1, "advanced": 2}
        tools = sorted(tools, key=lambda t: (order.get(t["level"], 3), -((REL.get(t["id"]) or {}).get("stars") or 0), t["name"].lower()))
        lim = ' data-limit="%d"' % limit
    else:
        tools = sorted(tools, key=lambda t: t["name"].lower())
        lim = ""
    return (filters("#list", placeholder) +
            '<p class="count" data-count aria-live="polite">%d tools shown</p>' % len(tools) +
            '<div class="grid" id="list"%s>%s</div>' % (lim, "".join(card(t, px) for t in tools)) +
            '<p class="empty" data-empty hidden>No tools match these filters. Clear the search or choose "All".</p>')


# ---------------------------------------------------------------- pages

def build_home():
    cat_cards = []
    cat_html = {}
    for i, c in enumerate(CATS):
        members = [t for t in TOOLS if c["id"] in t["categories"]]
        lead = [t for t in members if t["categories"][0] == c["id"]] + [t for t in members if t["categories"][0] != c["id"]]
        eg = ", ".join(t["name"] for t in lead[:3])
        cat_html[c["id"]] = ('<a class="cat" href="categories/%s.html"><span class="hex"><span>0x%02X</span><span>%d tools</span></span>'
                             '<span class="n">%s</span><span class="eg">%s</span></a>' % (c["id"], i, len(members), e(c["name"]), e(eg)))
    groups = [("Acquire and recover", ["imaging", "forensic-copy", "write-blocking", "recovery", "sanitization"]),
              ("Analyse systems", ["suites", "windows", "macos", "linux", "memory", "timeline", "logs", "database", "string-search",
                                   "incident-response", "passwords", "utilities", "validation"]),
              ("Mobile, cloud and messages", ["android", "ios", "messaging", "email", "browser", "cloud", "gps"]),
              ("Network and the web", ["network", "wifi", "voip", "p2p", "remote", "osint", "crypto"])]
    used = {c for _, ids in groups for c in ids}
    groups.append(("Media, malware and other", [c["id"] for c in CATS if c["id"] not in used]))
    cat_cards = "".join('<h3 class="cat-group">%s</h3><div class="grid cats">%s</div>' % (e(g), "".join(cat_html[i] for i in ids if i in cat_html))
                        for g, ids in groups if any(i in cat_html for i in ids))
    rows = []
    for n, it in enumerate(INTEG["integrations"][:3]):
        rows.append('<div class="card row-card"><span class="k">EXHIBIT %s</span><div class="v">'
                    '<div class="t">%s <span>%s</span> %s</div><p class="sum">%s</p>'
                    '<div class="src-line">Source: <a href="%s" rel="noopener">%s</a></div></div></div>'
                    % ("ABC"[n], e(it["product"]), e(it["relation"]), e(it["open_source"]), e(it["statement"]),
                       e(it["source_url"]), e(it["source_label"])))
    featured = "".join(card(TOOL[i], "") for i in SITE.get("featured", []) if i in TOOL)
    oss = sum(1 for t in TOOLS if eff_type(t) == "open-source")
    checked = fmt_date(RELDATA.get("generated"))
    explore = "".join('<a href="%s"><strong>%s</strong><span>%s</span></a>' % x for x in [
        ("basics.html", "Basics", "What is imaging? A write blocker? Start here")] * int(bool(BASICS)) + [
        ("map.html", "Evidence map", "Tap a laptop or phone to see where evidence lives")] * int((DATA / "xray.json").exists() and (PREVIEW or not json.load(open(DATA / "xray.json", encoding="utf-8")).get("draft"))) + [
        ("workflows.html", "Case workflows", "Step by step, with practice data")] * int(bool(WORKFLOWS)) + [
        ("lab.html", "Evidence lab", "Try it: read photo metadata and more"),
        ("compare.html", "Compare tools", "Two or three tools side by side"),
        ("toolbox.html", "Pocket toolbox", "Timestamp, hash and text decoders")] + [
        ("hotseat.html", "Examiner's hot seat", "Hard viva and court questions")] * int((DATA / "hotseat.json").exists() and (PREVIEW or not json.load(open(DATA / "hotseat.json", encoding="utf-8")).get("draft"))))
    wf_home = ""
    if WORKFLOWS:
        wf_home = ('<section class="section" id="workflows"><div class="section-head"><h2>Start from the question</h2>'
                   '<a href="workflows.html" style="font-weight:600">All case workflows</a></div>'
                   '<p class="muted" style="max-width:760px;margin-bottom:18px">Step-by-step workflows: the tool for each step, where the evidence is stored, and public data to practise on.</p>'
                   '<div class="grid">%s</div></section>'
                   % "".join('<article class="card"><h3><a href="workflows/%s.html">%s</a></h3><p class="sum">%s</p>'
                             '<div class="tags"><span class="tag">%s</span><span class="tag">%d steps</span></div></article>'
                             % (wid, e(w["title"]), e(w["lead"]), e(w["level"]), len(w["steps"]))
                             for wid, w in list(WORKFLOWS.items())[:6]))
    start_here = ('<section class="section" id="start"><div class="section-head"><h2>Start here</h2></div><div class="grid">'
                  '<article class="card"><h3><a href="%s">New to forensics?</a></h3><p class="sum">Learn the basic ideas in plain words: imaging, write blockers, hashes and custody.</p></article>'
                  '<article class="card"><h3><a href="%s">Practising for a viva?</a></h3><p class="sum">Hard questions with careful answers, in the examiner\'s hot seat.</p></article>'
                  '<article class="card"><h3><a href="%s">Doing a case study?</a></h3><p class="sum">Step-by-step workflows with the free tool for each step and public data to practise on.</p></article>'
                  '</div></section>' % ("basics.html" if BASICS else "tools.html", "hotseat.html" if (DATA / "hotseat.json").exists() else "learn.html",
                                        "workflows.html" if WORKFLOWS else "tools.html"))
    dated = []
    for t in TOOLS:
        rr = (rel_of(t) or {}).get("release") or {}
        if rr.get("published_at"):
            dated.append((rr["published_at"], t, rr.get("tag", "")))
    dated.sort(key=lambda x: x[0], reverse=True)
    recent_html = ""
    if dated:
        recent_html = ('<section class="section"><div class="section-head"><h2>Recently updated tools</h2></div><ul class="list-plain recent">%s</ul></section>'
                       % "".join('<li><a href="tools/%s.html">%s</a> <span class="muted">%s, released %s</span></li>'
                                 % (t["id"], e(t["name"]), e(tag), fmt_date(when)) for when, t, tag in dated[:5]))
    body = """
<div class="wrap">
<section class="hero">
<div class="label y">{tagline}</div>
<h1>Open-source forensic tools, sorted the way you study.</h1>
<p class="lead">What each tool does, who built it, where to download it, and which commercial product does a similar job. No scattered blogs, no guesswork.</p>
<form class="search" action="tools.html" method="get" role="search">
<div class="box">{icon}<label for="hq" class="skip">Search tools</label><input id="hq" name="q" type="search" placeholder="Search {nround}+ free tools, for example WhatsApp, RAM or PCAP" autocomplete="off"></div>
<button class="btn primary" type="submit">Search</button>
</form>
<div class="chips"><span class="muted">Popular:</span><a href="categories/windows.html">Windows</a><a href="categories/android.html">Android</a><a href="categories/memory.html">Memory</a><a href="categories/network.html">Network</a><a href="categories/imaging.html">Disk imaging</a><a href="categories/osint.html">OSINT</a></div>
<div class="explore">{explore}</div>
<div class="stats"><span><b>{n}</b> tools</span><span><b>{oss}</b> open source</span><span><b>{ncat}</b> categories</span>{checked}</div>
</section>
{start}
<section class="section" id="categories">
<div class="section-head"><h2>Browse by category</h2><span class="mono muted" style="font-size:13px">{ncat} categories · offset 0x00 – 0x{last:02X} · <a href="nist.html">browse by NIST functionality</a></span></div>
{cats}
</section>
{wf}
{recent}
</div>
<section class="band" id="inside"><div class="wrap split">
<div class="side"><div class="label y">Inside commercial tools</div>
<h2 style="font-size:32px">Many paid tools build on open source.</h2>
<p class="muted">Commercial suites give you a polished interface and support. Under that interface, many of them run or accept the same open-source engines and rule formats you can download today. Every claim here links to the vendor's own documentation.</p>
<p><a href="inside.html" style="font-weight:600">See all documented integrations</a></p></div>
<div class="main">{rows}</div>
</div></section>
<div class="wrap">
<section class="section" style="padding-top:56px">
<div class="section-head"><h2>Start with these</h2><a href="tools.html" style="font-weight:600">View all {n} tools</a></div>
<div class="grid">{featured}</div>
</section>
<section class="section">
<div class="section-head"><h2>Compare tools side by side</h2><a href="compare.html" style="font-weight:600">Open the compare page</a></div>
<p class="muted" style="max-width:760px;margin-bottom:16px">Pick two or three tools and see what each one does, which functions it is listed under, its licence, platforms and project activity. Facts only, no scores.</p>
<div class="chips">{cmp}</div>
</section>
<section class="section">
<div class="section-head"><h2>Know a paid tool? Find a free one.</h2><a href="alternatives.html" style="font-weight:600">Open the alternative finder</a></div>
<p class="muted" style="max-width:760px">Type the name of a commercial product and see free tools that do a similar job, with honest notes on what "similar" means.</p>
</section>
</div>
""".format(nround=(len(TOOLS) // 10) * 10, start=start_here, recent=recent_html, wf=wf_home, explore=explore, cmp="".join(compare_presets("")), tagline=e(SITE["tagline"]), icon=ICON_SEARCH, n=len(TOOLS), oss=oss, ncat=len(CATS), last=len(CATS) - 1,
           checked=('<span>links checked <b>%s</b></span>' % checked) if checked else "",
           cats=cat_cards, rows="".join(rows), featured=featured)
    home_ld = ld({"@context": "https://schema.org", "@type": "WebSite", "name": NAME, "url": (BASE + "/") if BASE else "",
                  "potentialAction": {"@type": "SearchAction", "target": (BASE + "/tools.html?q={search_term_string}") if BASE else "tools.html?q={search_term_string}",
                                      "query-input": "required name=search_term_string"}})
    page("index.html", NAME, SITE["description"], body, "", head=home_ld)


def build_tools_index():
    body = ('<div class="wrap"><div class="page-head"><h1>All tools</h1>'
            '<p class="lead">%d free and open-source tools. Search by name, artifact or task, then narrow by licence, level and platform.</p>'
            '<p><a class="btn small" href="compare.html">Compare tools side by side</a></p></div>'
            '%s</div>' % (len(TOOLS), tool_list(TOOLS, "", "Name, artifact or task, for example prefetch")))
    page("tools.html", "All tools", "Search every free and open-source digital forensics tool in the directory.", body, "tools")


def build_categories():
    for i, c in enumerate(CATS):
        members = [t for t in TOOLS if c["id"] in t["categories"]]
        note = ""
        if c["id"] in SENSITIVE:
            note = '<p class="note">%s</p>' % e(SENSITIVE[c["id"]])
        body = ('<div class="wrap"><div class="page-head">'
                '<div class="crumbs"><a href="../index.html">Home</a> / <a href="../index.html#categories">Categories</a> / %s</div>'
                '<div class="mono" style="color:var(--yellow);font-size:13px">0x%02X</div><h1>%s</h1><p class="lead">%s</p>%s%s</div>%s</div>'
                % (e(c["name"]), i, e(c["name"]), e(c["intro"]), note,
                   ('<p><a class="btn small" href="../compare.html?c=%s">Compare tools in this category</a></p>' % c["id"]) if len(members) > 1 else "",
                   tool_list(members, "../", "Search this category", CATEGORY_SHOWN)))
        page("categories/%s.html" % c["id"], c["name"],
             "%s: free and open-source tools. %s" % (c["name"], c["intro"]), body, "categories")


def download_block(t):
    r = rel_of(t)
    parts = []
    n = t.get("notice")
    if n:
        succ = n.get("successor")
        succ_html = (' Use <a href="%s.html">%s</a> instead.' % (e(succ), e(TOOL[succ]["name"]))) if succ in TOOL else ""
        src = (' <a href="%s" rel="noopener">Source</a>' % e(n["source"])) if n.get("source") else ""
        parts.append('<p><span class="badge warn">%s</span> %s%s%s</p>' % (NOTICE_LABEL.get(n.get("level"), "Note"), e(n["text"]), succ_html, src))
    raw = REL.get(t["id"]) or {}
    if "repo" in t and (raw.get("missing") or raw.get("repo_mismatch")):
        parts.append('<p><span class="badge warn">Under review</span> The project\'s repository has moved or could not be found at the last check, so download links are switched off until a person confirms the new location.</p>')
        parts.append('<div class="btns"><a class="btn" href="https://github.com/%s" rel="noopener">Open the recorded repository</a></div>' % e(t["repo"]))
    elif "repo" in t:
        repo_url = "https://github.com/" + t["repo"]
        release = r.get("release") if r else None
        assets = (release or {}).get("assets") or {}
        known = {p.lower() for p in t["platforms"]} & {"windows", "macos", "linux"}
        if known:
            assets = {k: v for k, v in assets.items() if k in known}
        if r and r.get("archived"):
            parts.append('<p><span class="badge warn">No longer maintained</span> The developer has archived this project. It may still work, but it gets no fixes.</p>')
        if t.get("download_url"):
            host = urllib.parse.urlparse(t["download_url"]).netloc
            parts.append('<div class="btns"><a class="btn primary" href="%s" rel="noopener">%s Official download page</a>'
                         '<a class="btn" href="%s" rel="noopener">Source code</a></div>' % (e(t["download_url"]), ICON_DL, e(repo_url)))
            parts.append('<p class="muted" style="font-size:14px">The developer publishes downloads on %s%s.</p>'
                         % (e(host), (", latest version " + e(release["tag"])) if release and release.get("tag") else ""))
        elif release and assets:
            oses = []
            for key, label in (("windows", "Windows"), ("macos", "macOS"), ("linux", "Linux")):
                a = assets.get(key)
                if a:
                    oses.append('<div class="os"><a class="btn primary" href="%s" rel="noopener">%s %s</a>'
                                '<span class="file">%s%s</span></div>'
                                % (e(a["url"]), ICON_DL, label, e(a["name"]),
                                   (" · " + fmt_size(a.get("size"))) if a.get("size") else ""))
            parts.append('<div class="btns">%s</div>' % "".join(oses))
            parts.append('<p class="muted" style="font-size:14px">Version %s, released %s. <a href="%s" rel="noopener">All files for this release</a></p>'
                         % (e(release.get("tag", "")), fmt_date(release.get("published_at")), e(release["url"])))
        elif release:
            parts.append('<div class="btns"><a class="btn primary" href="%s" rel="noopener">%s Download page for %s</a>'
                         '<a class="btn" href="%s" rel="noopener">Source code</a></div>'
                         % (e(release["url"]), ICON_DL, e(release.get("tag", "latest release")), e(repo_url)))
            parts.append('<p class="muted" style="font-size:14px">Released %s. Choose the file for your system on the release page.</p>'
                         % fmt_date(release.get("published_at")))
        elif r:
            parts.append('<div class="btns"><a class="btn primary" href="%s" rel="noopener">%s Source repository</a></div>' % (e(repo_url), ICON_DL))
            parts.append('<p class="muted" style="font-size:14px">This project has no packaged release on GitHub. Follow the install instructions in its repository.</p>')
        else:
            parts.append('<div class="btns"><a class="btn primary" href="%s/releases" rel="noopener">%s Releases on GitHub</a>'
                         '<a class="btn" href="%s" rel="noopener">Source code</a></div>' % (e(repo_url), ICON_DL, e(repo_url)))
        parts.append('<p class="file">Files come directly from github.com/%s. %s does not host or modify them.</p>'
                     % (e(t["repo"]), e(NAME)))
    else:
        parts.append('<div class="btns"><a class="btn primary" href="%s" rel="noopener">%s Official website</a></div>'
                     % (e(t["url"]), ICON_DL))
        host = urllib.parse.urlparse(t["url"]).netloc
        parts.append('<p class="file">Opens %s. %s does not host this tool.</p>' % (e(host), e(NAME)))
    if t.get("install"):
        parts.append('<div><div class="label" style="margin-bottom:6px">Install by command</div><div class="cmd-row">'
                     '<pre class="cmd">%s</pre><button type="button" class="btn small" data-copy="%s">Copy</button></div></div>'
                     % (e(t["install"]), e(t["install"])))
    return '<div class="dl"><div class="label y">Get it</div>%s</div>' % "".join(parts)


def guide_sections(t, g):
    """Extra sections for a tool that has a full guide in data/guides/<id>.json."""
    out, jump = [], []

    def section(anchor, title, inner):
        jump.append('<a href="#%s">%s</a>' % (anchor, e(title)))
        out.append('<section id="%s"><h2>%s</h2>%s</section>' % (anchor, e(title), inner))

    use = "".join("<li>%s</li>" % e(x) for x in g.get("use_when", []))
    section("about", "What it is",
            '<p style="font-size:17px;color:var(--soft)">%s</p>%s'
            % (e(g.get("lead") or t["summary"]),
               ('<div class="note" style="margin-top:14px"><strong>Use it when</strong><ul class="tight">%s</ul></div>' % use) if use else ""))

    figs = []
    for sh in g.get("screenshots", []):
        if (ROOT / "static" / "screenshots" / sh["file"]).exists():
            figs.append('<figure class="shot"><a href="../assets/screenshots/%s"><img src="../assets/screenshots/%s" alt="%s" loading="lazy"></a>'
                        '<figcaption>%s</figcaption></figure>' % (e(sh["file"]), e(sh["file"]), e(sh["caption"]), e(sh["caption"])))
        elif PREVIEW:
            figs.append('<figure class="shot"><div class="shot-empty">Screenshot to add<br><span class="mono">%s</span></div>'
                        '<figcaption>%s</figcaption></figure>' % (e(sh["file"]), e(sh["caption"])))
    more = ('<p style="margin-top:12px"><a href="%s" rel="noopener">See the project\'s own screenshots</a></p>'
            % e(g["project_screenshots_url"])) if g.get("project_screenshots_url") else ""
    if figs or more:
        section("screens", "What it looks like", ('<div class="shots">%s</div>' % "".join(figs) if figs else "") + more)

    if g.get("features"):
        cards = "".join('<div class="card"><h3>%s</h3><ul class="tight">%s</ul></div>'
                        % (e(f["title"]), "".join("<li>%s</li>" % e(i) for i in f["items"])) for f in g["features"])
        section("features", "What it can do", '<div class="grid">%s</div>' % cards)

    if g.get("formats") or g.get("requirements"):
        inner = ""
        if g.get("formats"):
            inner += '<div class="tags on-blue" style="font-size:13px">%s</div>' % "".join('<span class="tag">%s</span>' % e(f) for f in g["formats"])
        if g.get("requirements"):
            inner += '<p class="muted" style="margin-top:12px"><strong style="color:var(--text)">What you need.</strong> %s</p>' % e(g["requirements"])
        section("evidence", "Evidence it opens", inner)

    if g.get("steps"):
        steps = []
        for n, st in enumerate(g["steps"], 1):
            cmd = ('<div class="cmd-row" style="margin-top:8px"><pre class="cmd">%s</pre>'
                   '<button type="button" class="btn small" data-copy="%s">Copy</button></div>' % (e(st["cmd"]), e(st["cmd"]))) if st.get("cmd") else ""
            steps.append('<li><span class="num">%d</span><div><h3>%s</h3><p>%s</p>%s</div></li>' % (n, e(st["title"]), e(st["text"]), cmd))
        inner = '<ol class="steps">%s</ol>' % "".join(steps)
        if g.get("options"):
            inner += ('<h3 style="margin:22px 0 10px;font-size:18px">Useful options</h3><div class="opts">%s</div>'
                      % "".join('<div><code>%s</code><span>%s</span></div>' % (e(o["cmd"]), e(o["what"])) for o in g["options"]))
        section("howto", "How to use it", inner)

    if g.get("cases"):
        section("cases", "Cases where it helps",
                '<div class="grid">%s</div>' % "".join('<div class="card"><h3>%s</h3><p class="sum">%s</p></div>'
                                                      % (e(c["title"]), e(c["why"])) for c in g["cases"]))

    if g.get("strengths") or g.get("limits"):
        def col(title, items, cls):
            return ('<div class="card %s"><h3>%s</h3><ul class="tight">%s</ul></div>'
                    % (cls, title, "".join("<li>%s</li>" % e(i) for i in items)))
        section("limits", "Strengths and limits",
                '<div class="grid two">%s%s</div>' % (col("Strengths", g.get("strengths", []), ""), col("Limits to know", g.get("limits", []), "")))

    pairs = [(TOOL[w["id"]], w.get("note", "")) for w in g.get("works_with", []) if w["id"] in TOOL]
    if pairs:
        section("with", "Works well with",
                '<ul class="list-plain">%s</ul>' % "".join('<li><a href="%s.html" style="font-weight:600">%s</a> <span class="muted">%s</span></li>'
                                                          % (x["id"], e(x["name"]), e(note)) for x, note in pairs))

    if g.get("learn"):
        note = ('<p class="muted" style="font-size:13px;margin-top:12px">%s Last reviewed %s.</p>'
                % (e(g.get("sources_note", "")), fmt_date(g.get("reviewed")))) if g.get("reviewed") else ""
        section("learn", "Learn more",
                '<ul class="list-plain">%s</ul>%s' % ("".join('<li><a href="%s" rel="noopener">%s</a></li>' % (e(l["url"]), e(l["label"])) for l in g["learn"]), note))

    nav = '<nav class="jump" aria-label="On this page"><span class="label">On this page</span>%s</nav>' % "".join(jump)
    return [draft_banner(g), nav] + out


def build_tool_pages():
    by_tool = {}
    for it in INTEG["integrations"] + INTEG.get("open_on_open", []):
        for tid in it.get("tool_ids", []):
            by_tool.setdefault(tid, []).append(it)
    for t in TOOLS:
        cls, badge, lic_long = licence(t)
        r = rel_of(t) or {}
        primary = CAT[t["categories"][0]]
        notes = [SENSITIVE[c] for c in t["categories"] if c in SENSITIVE]
        if t["interface"] == "Web" and "repo" not in t:
            notes.append("This is an online service run by a third party. Do not upload real case evidence to it.")
        main = [download_block(t)]
        if t["id"] in GUIDES:
            main += guide_sections(t, GUIDES[t["id"]])
        else:
            main.append('<section><h2>What it does</h2><p style="font-size:17px;color:var(--soft)">%s</p></section>' % e(t["summary"]))
        if notes:
            main.append('<section>%s</section>' % "".join('<p class="note" style="margin-bottom:10px">%s</p>' % e(n) for n in notes))
        related = [x for x in TOOLS if x["id"] != t["id"] and primary["id"] in x["categories"]]
        related.sort(key=lambda x: (x["categories"][0] != primary["id"], -(REL.get(x["id"], {}).get("stars") or 0)))
        if related:
            main.append('<section><h2>More in %s</h2><div class="grid">%s</div>'
                        '<p style="margin-top:14px"><a href="../categories/%s.html" style="font-weight:600">See all tools in %s</a></p></section>'
                        % (e(primary["name"]), "".join(card(x, "../") for x in related[:4]), primary["id"], e(primary["name"])))

        side = []
        for it in by_tool.get(t["id"], []):
            side.append('<div class="card hl"><div class="label" style="color:var(--blue)">Inside other tools</div>'
                        '<div class="row-card"><div class="t">%s <span>%s</span> %s</div></div><p class="sum">%s</p>'
                        '<div class="src-line">Source: <a href="%s" rel="noopener">%s</a>, checked %s</div></div>'
                        % (e(it["product"]), e(it["relation"]), e(it["open_source"]), e(it["statement"]),
                           e(it["source_url"]), e(it["source_label"]), fmt_date(it.get("checked"))))
        used = [(wid, w) for wid, w in WORKFLOWS.items() if any(t["id"] in st.get("tools", []) for st in w.get("steps", []))]
        if used:
            side.append('<div class="card"><div class="label">Used in workflows</div><ul class="list-plain">%s</ul></div>'
                        % "".join('<li><a href="../workflows/%s.html">%s</a></li>' % (wid, e(w["title"])) for wid, w in used))
        facts = [("Developer", e(t["developer"])), ("Licence", e(lic_long))] + \
                ([("Editions and terms", e(t["licence_note"]))] if t.get("licence_note") else []) + \
                [("Interface", e(t["interface"])),
                 ("Runs on", e(", ".join(t["platforms"]))), ("Level", LEVELS[t["level"]]),
                 ("Category", ", ".join('<a href="../categories/%s.html">%s</a>' % (c, e(CAT[c]["name"])) for c in t["categories"])),
                 ("Source", '<a href="%s" rel="noopener">%s</a>' % (e(source_url(t)), e(t.get("repo") or urllib.parse.urlparse(t["url"]).netloc)))]
        if r.get("stars") is not None:
            facts.append(("GitHub stars", fmt_count(r["stars"])))
        if r.get("pushed_at"):
            facts.append(("Last code update", fmt_date(r["pushed_at"])))
        act = activity(t)
        if act:
            facts.append(("Activity", act))
        if r.get("checked"):
            facts.append(("Last checked", fmt_date(r["checked"])))
        side.append('<div class="card"><div class="label">Facts</div><dl class="facts">%s</dl></div>'
                    % "".join("<div><dt>%s</dt><dd>%s</dd></div>" % (k, v) for k, v in facts))
        if t.get("similar_to"):
            side.append('<div class="card"><div class="label">Does a similar job to</div><p class="sum"><strong>%s</strong></p>'
                        '<p class="sum" style="font-size:13px">"Similar job" means it covers some of the same tasks. It does not mean the same features, support or court acceptance. '
                        '<a href="../alternatives.html">How we compare</a></p></div>' % e(", ".join(t["similar_to"])))
        side.append('<div class="card"><div class="label">Credit</div><p class="sum">Built and maintained by <strong>%s</strong>. '
                    'If this tool helps your studies, cite it in your reports%s.</p></div>'
                    % (e(t["developer"]), " and star the project" if "repo" in t else ""))
        side.append('<p><a class="btn small" href="../compare.html?t=%s">Compare with another tool</a></p>' % t["id"])
        rep = issue_url("report-problem", "Problem on page: " + t["name"]) or "../about.html#corrections"
        side.append('<p style="font-size:14px"><a href="%s">Report a problem with this page</a></p>' % e(rep))

        body = ('<div class="wrap"><div class="page-head">'
                '<div class="crumbs"><a href="../index.html">Home</a> / <a href="../categories/%s.html">%s</a> / %s</div>'
                '<h1>%s</h1><p class="muted">by %s</p>'
                '<div class="tags on-blue" style="font-size:12px"><span class="badge %s">%s</span>%s%s</div></div>'
                '<div class="tool-layout"><div class="tool-main">%s</div><aside class="tool-side" aria-label="Tool facts">%s</aside></div></div>'
                % (primary["id"], e(primary["name"]), e(t["name"]), e(t["name"]), e(t["developer"]), cls, badge, notice_badge(t),
                   "".join('<span class="tag">%s</span>' % e(x) for x in [LEVELS[t["level"]], t["interface"]] + t["platforms"]),
                   "".join(main), "".join(side)))
        app = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": t["name"], "applicationCategory": "SecurityApplication",
               "operatingSystem": ", ".join(t["platforms"]), "author": {"@type": "Organization", "name": t["developer"]}, "url": source_url(t)}
        if t.get("licence") and eff_type(t) != "free-resource":
            app["license"] = t["licence"]
        if eff_type(t) != "free-resource":
            app["offers"] = {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
        head = ld(app)
        if BASE:
            head += ld({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE + "/"},
                {"@type": "ListItem", "position": 2, "name": primary["name"], "item": "%s/categories/%s.html" % (BASE, primary["id"])},
                {"@type": "ListItem", "position": 3, "name": t["name"], "item": "%s/tools/%s.html" % (BASE, t["id"])}]})
        page("tools/%s.html" % t["id"], t["name"], "%s by %s. %s" % (t["name"], t["developer"], t["summary"]), body, "tools", head=head)


def draft_banner(item):
    if not item.get("draft"):
        return ""
    return '<p class="note" style="border-color:var(--yellow);color:var(--yellow)">Draft preview. This page is not on the live site yet.</p>'


def build_workflows():
    if not WORKFLOWS:
        return
    cards = []
    for wid, w in WORKFLOWS.items():
        cards.append('<article class="card" data-section="%s"><div class="top"><h3><a href="workflows/%s.html">%s</a></h3>%s</div>'
                     '<div class="by">Evidence: %s</div><p class="sum">%s</p>'
                     '<div class="tags"><span class="tag">%s</span><span class="tag">%d steps</span></div></article>'
                     % (e((w["title"] + " " + w["evidence"] + " " + w["lead"] + " " + w["short"]).lower()), wid, e(w["title"]), '<span class="badge warn">Draft</span>' if w.get("draft") else "",
                        e(w["evidence"]), e(w["lead"]), e(w["level"]), len(w["steps"])))
    body = ('<div class="wrap"><div class="page-head"><h1>Case workflows</h1>'
            '<p class="lead">Start from the question you need to answer. Each workflow gives the steps in order, the free tool for each step, '
            'where the evidence is stored, and a public practice image to try it on.</p>'
            '<div class="stats"><span><b>%d</b> workflows</span></div>'
            '<div class="filters"><div class="row"><label class="label" for="wq">Find a workflow</label>'
            '<input id="wq" type="search" data-section-filter placeholder="For example USB, email, memory or phone" autocomplete="off"></div></div></div>'
            '<section class="section" style="padding-top:8px"><div class="grid">%s</div><p class="empty" data-empty hidden>No match yet. Try a shorter word.</p></section></div>' % (len(WORKFLOWS), "".join(cards)))
    page("workflows.html", "Case workflows", "Step-by-step forensic workflows for students, using free and open-source tools and public practice data.", body, "workflows")

    for wid, w in WORKFLOWS.items():
        main, jump = [], []

        def section(anchor, title, inner):
            jump.append('<a href="#%s">%s</a>' % (anchor, e(title)))
            main.append('<section id="%s"><h2>%s</h2>%s</section>' % (anchor, e(title), inner))

        section("answers", "What you will be able to answer",
                '<ul class="tight on-blue">%s</ul>' % "".join("<li>%s</li>" % e(a) for a in w["answers"]))
        section("need", "What you need",
                '<ul class="tight on-blue">%s</ul>' % "".join("<li>%s</li>" % e(a) for a in w["need"]))

        steps = []
        for n, st in enumerate(w["steps"], 1):
            extra = ""
            if st.get("cmd"):
                for one in (st["cmd"] if isinstance(st["cmd"], list) else [st["cmd"]]):
                    extra += ('<div class="cmd-row" style="margin-top:10px"><pre class="cmd">%s</pre>'
                              '<button type="button" class="btn small" data-copy="%s">Copy</button></div>' % (e(one), e(one)))
            if st.get("paths"):
                extra += '<div class="paths">%s</div>' % "".join("<code>%s</code>" % e(p) for p in st["paths"])
            if st.get("note"):
                extra += '<p class="step-note">%s</p>' % e(st["note"])
            chips = "".join('<a class="tool-chip" href="../tools/%s.html">%s</a>' % (tid, e(TOOL[tid]["name"]))
                            for tid in st.get("tools", []) if tid in TOOL)
            if chips:
                extra += '<div class="tool-chips"><span class="label">Tools</span>%s</div>' % chips
            steps.append('<li><span class="num">%d</span><div><h3>%s</h3><p>%s</p>%s</div></li>' % (n, e(st["title"]), e(st["text"]), extra))
        section("steps", "Steps", '<ol class="steps">%s</ol>' % "".join(steps))

        if w.get("artifacts"):
            section("artifacts", "Where the evidence is stored",
                    '<div class="opts arts">%s</div>' % "".join(
                        '<div><code>%s</code><span><strong>%s</strong><br>%s</span></div>' % (e(a["name"]), e(a["where"]), e(a["tells"]))
                        for a in w["artifacts"]))
        if w.get("verify"):
            section("verify", "Check your result",
                    '<div class="card"><ul class="tight" style="margin-top:0">%s</ul></div>' % "".join("<li>%s</li>" % e(x) for x in w["verify"]))
        if w.get("mistakes"):
            section("mistakes", "Common mistakes",
                    '<div class="card"><ul class="tight" style="margin-top:0">%s</ul></div>' % "".join("<li>%s</li>" % e(x) for x in w["mistakes"]))
        if w.get("report_line"):
            section("report", "Write it up",
                    '<div class="card"><p class="sum">A short, careful way to state this kind of finding in a report. Change the details to match your own results.</p>'
                    '<blockquote class="reportline">%s</blockquote></div>' % e(w["report_line"]))
        if w.get("limits"):
            section("limits", "What this does not prove",
                    '<div class="card"><ul class="tight" style="margin-top:0">%s</ul></div>' % "".join("<li>%s</li>" % e(x) for x in w["limits"]))
        pr = w.get("practice")
        if pr:
            ans = (' <a class="btn small on-card" href="%s" rel="noopener">Published answers</a>' % e(pr["answers_url"])) if pr.get("answers_url") else ""
            section("practice", "Practise on public data",
                    '<div class="card hl"><h3>%s</h3><div class="by">by %s</div><p class="sum">%s</p><p class="sum"><strong>Your task.</strong> %s</p>%s'
                    '<div class="card-btns"><a class="btn small on-card solid" href="%s" rel="noopener">Open the data set</a>%s</div></div>'
                    % (e(pr["name"]), e(pr["by"]), e(pr["text"]), e(pr["task"]),
                       ('<p class="sum" style="font-size:13.5px">%s</p>' % e(pr["note"])) if pr.get("note") else "", e(pr["url"]), ans))
        nxt = [n for n in w.get("next", []) if n]
        if nxt:
            items = "".join('<li>%s</li>' % (('<a href="%s.html" style="font-weight:600">%s</a> <span class="muted">%s</span>' % (n["workflow"], e(WORKFLOWS[n["workflow"]]["title"]), e(n["text"])))
                                              if n.get("workflow") in WORKFLOWS else e(n["text"])) for n in nxt)
            section("next", "Where to go next", '<ul class="tight on-blue">%s</ul>' % items)
        if w.get("learn"):
            section("learn", "Sources and further reading",
                    '<ul class="list-plain">%s</ul><p class="muted" style="font-size:13px;margin-top:12px">%s Last reviewed %s.</p>'
                    % ("".join('<li><a href="%s" rel="noopener">%s</a></li>' % (e(l["url"]), e(l["label"])) for l in w["learn"]),
                       e(w.get("sources_note", "")), fmt_date(w.get("reviewed"))))

        tool_ids = []
        for st in w["steps"]:
            for tid in st.get("tools", []):
                if tid in TOOL and tid not in tool_ids:
                    tool_ids.append(tid)
        side = ['<div class="card"><div class="label">At a glance</div><dl class="facts">%s</dl></div>'
                % "".join("<div><dt>%s</dt><dd>%s</dd></div>" % (k, e(v)) for k, v in
                          [("Evidence", w["evidence"]), ("Level", w["level"]), ("Time", w["time"]), ("Steps", str(len(w["steps"])))]),
                '<div class="card"><div class="label">Tools in this workflow</div><ul class="list-plain">%s</ul></div>'
                % "".join('<li><a href="../tools/%s.html">%s</a> <span style="color:var(--ink-muted);font-size:13px">%s</span></li>'
                          % (tid, e(TOOL[tid]["name"]), e(licence(TOOL[tid])[1])) for tid in tool_ids)]
        rep_url = issue_url("report-problem", "Problem on page: " + w["title"]) or "../about.html#corrections"
        side.append('<p style="font-size:14px"><a href="%s">Report a problem with this page</a></p>' % e(rep_url))

        nav = '<nav class="jump" aria-label="On this page"><span class="label">On this page</span>%s</nav>' % "".join(jump)
        body = ('<div class="wrap"><div class="page-head">'
                '<div class="crumbs"><a href="../index.html">Home</a> / <a href="../workflows.html">Workflows</a> / %s</div>'
                '<div class="label y">Case workflow</div><h1>%s</h1><p class="lead">%s</p>%s%s</div>'
                '<div class="tool-layout"><div class="tool-main">%s%s</div><aside class="tool-side" aria-label="Workflow facts">%s</aside></div></div>'
                % (e(w.get("short", w["title"])), e(w["title"]), e(w["lead"]), draft_banner(w),
                   '<p class="note">This workflow was written from the tools\' documentation and published references. It has not yet been checked step by step on the practice data. If a step does not match what you see, please report it.</p>' if w.get("untested") else "",
                   nav, "".join(main), "".join(side)))
        page("workflows/%s.html" % wid, w["title"], w["lead"], body, "workflows")


COMPARE_PRESETS = [("autopsy", "iped"), ("hayabusa", "chainsaw"), ("volatility3", "memprocfs"),
                   ("ftk-imager", "guymager"), ("aleapp", "andriller"), ("registry-explorer", "regripper")]


def compare_presets(px):
    links = []
    for pair in COMPARE_PRESETS:
        if all(i in TOOL for i in pair):
            links.append('<a href="%scompare.html?t=%s">%s</a>' % (px, ",".join(pair), e(" and ".join(TOOL[i]["name"] for i in pair))))
    return links


def build_compare():
    data = {"cats": {c["id"]: c["name"] for c in CATS}, "tools": []}
    for t in sorted(TOOLS, key=lambda x: x["name"].lower()):
        r = rel_of(t) or {}
        release = r.get("release") or {}
        item = {"id": t["id"], "name": t["name"], "dev": t["developer"], "lic": licence(t)[2], "iface": t["interface"],
                "level": LEVELS[t["level"]], "plat": t["platforms"], "cats": t["categories"], "sum": t["summary"],
                "sim": t.get("similar_to", []), "guide": t["id"] in GUIDES,
                "wf": [[wid, w.get("short", w["title"])] for wid, w in WORKFLOWS.items()
                       if any(t["id"] in st.get("tools", []) for st in w.get("steps", []))]}
        if release.get("tag"):
            item["rel"] = release["tag"]
            item["reldate"] = fmt_date(release.get("published_at") or release.get("published"))
        if r.get("pushed_at"):
            item["upd"] = fmt_date(r["pushed_at"])
        if r.get("stars") is not None:
            item["stars"] = fmt_count(r["stars"])
        act = activity(t)
        if act:
            item["act"] = act
        data["tools"].append(item)
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    checked = fmt_date(RELDATA.get("generated"))
    presets = "".join(compare_presets(""))
    body = ('<div class="wrap"><div class="page-head"><h1>Compare tools</h1>'
            '<p class="lead">Pick two or three tools and see their facts side by side: what each one does, which functions it is listed under, licence, platforms and how active the project is.</p>'
            '<p class="note" style="max-width:820px"><strong>Facts only, no scores.</strong> This page does not rank tools or say which one is best. '
            '"Not listed" means this directory does not list the tool under that function. It does not mean the tool cannot do it. '
            'Always check the project\'s own documentation before you rely on a tool.</p></div>'
            '<section class="section" style="padding-top:8px">'
            '<div class="filters" id="cmp" data-checked="%s">'
            '<div class="row"><label class="label" for="cmp-cat">Show tools from</label><select id="cmp-cat"><option value="">All categories</option>%s</select></div>'
            '<div class="row cmp-picks"><span class="label">Tools</span>'
            '<select id="cmp-a" aria-label="First tool"></select><select id="cmp-b" aria-label="Second tool"></select>'
            '<select id="cmp-c" aria-label="Third tool (optional)"></select></div></div>'
            '<noscript><p class="note">The compare table needs JavaScript. Every tool page lists the same facts.</p></noscript>'
            '<div id="cmp-out" aria-live="polite"></div>'
            '<div class="chips" style="margin-top:22px"><span class="muted">Try:</span>%s</div>'
            '</section></div><script type="application/json" id="cmp-data">%s</script>'
            % (e(checked), "".join('<option value="%s">%s</option>' % (c["id"], e(c["name"])) for c in CATS), presets, blob))
    page("compare.html", "Compare tools", "Compare free and open-source digital forensics tools side by side: functions, licence, platforms and project activity.", body, "compare")


XRAY_DEVICES = [
    ("laptop", "Laptop or PC", "Where a user works: browsers, programs, logins, documents and the drive."),
    ("phone", "Phone", "Chats, photos, location and app data kept in a pocket computer."),
    ("storage", "USB and memory cards", "Small storage that moves files from place to place."),
    ("network", "Network and servers", "Logs and captures from routers, firewalls and servers."),
    ("cloud", "Cloud accounts", "Evidence held by online services, not on the device."),
    ("wearable", "Smartwatch", "Health, movement and notification data on the wrist."),
    ("drone", "Drone", "Flight logs, camera media and controller data."),
    ("car", "Car", "Infotainment, paired phones, location and vehicle data."),
    ("camera", "Camera and smart home", "CCTV recorders, smart cameras and home devices."),
    ("database", "Databases", "Business and app databases keep records, logs and traces of changes."),
    ("voice", "Voice and calls", "Phone calls, voicemail, VoIP, recordings and voice assistants."),
    ("media", "Photos, video and audio", "Media files carry hidden details about who made them, when, where and with what."),
    ("special", "Other evidence", "Suspicious files, encrypted data, crypto wallets, online traces and hidden data."),
]
XRAY_LIFE = {"volatile": "Lost when power is off", "overwrite": "Stays until overwritten", "device": "Stays on the device",
             "provider": "Held by a provider", "network": "Travels over the network"}
# Hotspot positions for devices whose parts do not give x and y (assigned in the order of the data file).
XRAY_SLOTS = {
    "storage": [(150, 110), (150, 235), (150, 350), (440, 150), (440, 300)],
    "network": [(160, 90), (160, 205), (160, 320), (450, 95), (450, 215), (450, 335)],
    "cloud": [(190, 175), (310, 125), (440, 175), (210, 290), (330, 330), (450, 290)],
    "drone": [(310, 115), (310, 225), (130, 330), (310, 345), (490, 330)],
    "car": [(310, 95), (310, 195), (310, 295), (310, 385), (130, 215), (490, 215)],
    "camera": [(130, 125), (130, 320), (330, 125), (330, 320), (510, 215)],
    "database": [(150, 100), (150, 225), (150, 350), (450, 100), (450, 225), (450, 350)],
    "voice": [(130, 110), (130, 240), (130, 370), (450, 110), (450, 240), (450, 370)],
    "media": [(140, 110), (140, 240), (140, 370), (450, 110), (450, 240), (450, 370)],
    "special": [(130, 110), (310, 110), (490, 110), (130, 300), (310, 300), (490, 300)],
    "wearable": [(120, 130), (120, 215), (120, 300), (120, 385), (120, 470)],
}
XRAY_SVG = {
    "laptop": ("0 0 620 450", ""),
    "phone": ("0 0 240 620", "phone"),
    "wearable": ("0 0 240 620", "phone"),
    "storage": ("0 0 620 450", '<rect class="shell" x="40" y="40" width="210" height="140" rx="14"/><rect class="glass" x="62" y="64" width="150" height="92" rx="6"/><rect class="shell" x="250" y="74" width="62" height="72" rx="6"/><rect class="faint" x="262" y="84" width="14" height="22"/><rect class="faint" x="288" y="84" width="14" height="22"/>'
                '<rect class="shell" x="60" y="230" width="190" height="150" rx="12"/><path class="faint" d="M80 250h150M80 290h150M80 330h150"/>'
                '<path class="shell" d="M380 60h120l36 36v160a10 10 0 0 1-10 10H380a10 10 0 0 1-10-10V70a10 10 0 0 1 10-10z"/><path class="faint" d="M392 80v34M410 80v34M428 80v34M446 80v34"/>'
                '<rect class="faint" x="392" y="150" width="112" height="70" rx="6"/><path class="faint" d="M392 200h112"/>'
                '<rect class="shell" x="380" y="280" width="170" height="110" rx="14"/><circle class="faint" cx="465" cy="335" r="34"/><circle class="faint" cx="465" cy="335" r="8"/>'),
    "network": ("0 0 620 450", '<rect class="shell" x="50" y="30" width="230" height="390" rx="14"/><rect class="glass" x="68" y="48" width="194" height="106" rx="6"/><rect class="glass" x="68" y="164" width="194" height="106" rx="6"/><rect class="glass" x="68" y="280" width="194" height="106" rx="6"/>'
                '<path class="faint" d="M84 70h90M84 90h120M84 186h90M84 206h120M84 302h90M84 322h120"/><circle class="faint" cx="238" cy="70" r="6"/><circle class="faint" cx="238" cy="186" r="6"/><circle class="faint" cx="238" cy="302" r="6"/>'
                '<rect class="shell" x="340" y="60" width="220" height="70" rx="10"/><path class="faint" d="M360 110h18M390 110h18M420 110h18M450 110h18M486 112l18-52M520 112l18-52"/>'
                '<rect class="shell" x="340" y="180" width="220" height="70" rx="10"/><path class="faint" d="M360 215h180"/><rect class="shell" x="340" y="300" width="220" height="70" rx="10"/><path class="faint" d="M360 335c20-26 40-26 60 0s40 26 60 0"/>'
                '<path class="faint" d="M280 100h60M280 215h60M280 335h60"/>'),
    "cloud": ("0 0 620 450", '<path class="shell" d="M170 340c-70 0-110-40-110-90s40-84 92-84c10-60 66-100 130-100 72 0 122 44 134 100 60 0 104 36 104 90 0 50-44 84-104 84z"/>'
              '<path class="faint" d="M150 380v36M310 372v44M470 380v36M110 416h400"/>'),
    "drone": ("0 0 620 450", '<circle class="faint" cx="150" cy="70" r="46"/><circle class="faint" cx="470" cy="70" r="46"/><path class="shell" d="M180 92l92 48M440 92l-92 48"/>'
              '<rect class="shell" x="250" y="60" width="120" height="110" rx="26"/><rect class="glass" x="278" y="180" width="64" height="64" rx="12"/><circle class="faint" cx="310" cy="212" r="16"/>'
              '<rect class="shell" x="60" y="270" width="150" height="130" rx="18"/><path class="faint" d="M84 330h102M84 360h102"/><circle class="faint" cx="110" cy="298" r="10"/><circle class="faint" cx="160" cy="298" r="10"/>'
              '<rect class="shell" x="260" y="290" width="100" height="120" rx="14"/><rect class="glass" x="272" y="304" width="76" height="80" rx="6"/>'
              '<rect class="shell" x="440" y="290" width="86" height="100" rx="8"/><path class="faint" d="M456 290v22M474 290v22M492 290v22M510 290v22"/>'),
    "car": ("0 0 620 450", '<rect class="shell" x="210" y="24" width="200" height="404" rx="80"/><rect class="glass" x="228" y="70" width="164" height="70" rx="22"/><rect class="glass" x="228" y="150" width="164" height="150" rx="14"/><rect class="glass" x="228" y="310" width="164" height="70" rx="22"/>'
            '<rect class="faint" x="170" y="70" width="40" height="70" rx="12"/><rect class="faint" x="410" y="70" width="40" height="70" rx="12"/><rect class="faint" x="170" y="320" width="40" height="70" rx="12"/><rect class="faint" x="410" y="320" width="40" height="70" rx="12"/>'),
    "database": ("0 0 620 450", '<path class="shell" d="M70 70c0-30 160-30 160 0v90c0 30-160 30-160 0z"/><path class="faint" d="M70 70c0 30 160 30 160 0M70 115c0 30 160 30 160 0"/>'
                 '<path class="shell" d="M70 210c0-30 160-30 160 0v90c0 30-160 30-160 0z"/><path class="faint" d="M70 210c0 30 160 30 160 0M70 255c0 30 160 30 160 0"/>'
                 '<rect class="shell" x="360" y="50" width="200" height="140" rx="10"/><path class="faint" d="M360 90h200M360 130h200M420 50v140M490 50v140"/>'
                 '<rect class="shell" x="360" y="210" width="200" height="90" rx="10"/><path class="faint" d="M380 240h160M380 266h110"/>'
                 '<rect class="shell" x="360" y="320" width="200" height="90" rx="10"/><path class="faint" d="M380 350h60M380 376h120M470 340l20 20-20 20"/>'
                 '<path class="faint" d="M230 110h130M230 255h130M230 370h130"/>'),
    "voice": ("0 0 620 450", '<path class="shell" d="M70 70c40-30 90-30 130 0l-18 36c-12-10-34-10-46 0z"/><rect class="shell" x="60" y="200" width="150" height="110" rx="14"/><path class="faint" d="M84 230h102M84 256h102M84 282h60"/>'
              '<rect class="shell" x="80" y="340" width="110" height="70" rx="10"/><path class="faint" d="M96 376h78M96 360h30"/>'
              '<rect class="shell" x="400" y="50" width="100" height="150" rx="50"/><path class="faint" d="M370 130c0 50 30 80 80 80s80-30 80-80M450 210v30M420 240h60"/>'
              '<rect class="shell" x="360" y="270" width="190" height="130" rx="12"/><path class="faint" d="M380 335h20l10-34 14 70 14-52 12 30 12-20 14 14 16-24 12 16"/>'
              '<path class="faint" d="M210 255h150"/>'),
    "media": ("0 0 620 450", '<rect class="shell" x="50" y="40" width="190" height="140" rx="10"/><path class="faint" d="M62 160l50-60 34 36 26-24 56 48M190 78a12 12 0 1 0 0.1 0"/>'
              '<rect class="shell" x="50" y="190" width="190" height="130" rx="10"/><rect class="faint" x="80" y="206" width="130" height="14"/><path class="faint" d="M66 240h160M66 262h160M66 284h110"/>'
              '<rect class="shell" x="60" y="330" width="170" height="90" rx="10"/><path class="faint" d="M76 375h14l8-26 12 52 12-36 10 18h16l8-14 10 20 12-30 8 16h16"/>'
              '<rect class="shell" x="360" y="40" width="200" height="140" rx="8"/><path class="faint" d="M380 40v140M420 40v140M500 40v140M540 40v140M380 70h40M380 110h40M380 150h40M500 70h40M500 110h40M500 150h40"/><path class="faint" d="M446 84l32 26-32 26z"/>'
              '<rect class="shell" x="360" y="190" width="200" height="130" rx="10"/><path class="faint" d="M380 255h20l10-34 14 70 14-52 12 30 12-20 14 14 16-24 12 16h30"/>'
              '<rect class="shell" x="440" y="330" width="40" height="64" rx="20"/><path class="faint" d="M420 372c0 26 20 40 40 40s40-14 40-40M460 412v18M436 430h48"/>'),
    "special": ("0 0 620 450", '<path class="shell" d="M80 50h90l34 34v110a8 8 0 0 1-8 8H80a8 8 0 0 1-8-8V58a8 8 0 0 1 8-8z"/><path class="faint" d="M96 110h92M96 134h92M96 158h60"/>'
                '<rect class="shell" x="250" y="96" width="120" height="100" rx="14"/><path class="faint" d="M280 96v-26a30 30 0 0 1 60 0v26"/><circle class="faint" cx="310" cy="146" r="10"/>'
                '<circle class="shell" cx="490" cy="130" r="64"/><path class="faint" d="M466 150v-40h24a10 10 0 0 1 0 20h-24M490 94v10M490 156v10"/>'
                '<circle class="shell" cx="130" cy="330" r="60"/><path class="faint" d="M70 330h120M130 270c-30 30-30 90 0 120M130 270c30 30 30 90 0 120"/>'
                '<path class="shell" d="M250 280c0-14 120-14 120 0v90c0 14-120 14-120 0z"/><path class="faint" d="M250 280c0 14 120 14 120 0M250 325c0 14 120 14 120 0"/>'
                '<rect class="shell" x="430" y="270" width="120" height="120" rx="12"/><path class="faint" d="M446 306h88M446 330h60M446 354h74"/>'),
    "camera": ("0 0 620 450", '<rect class="shell" x="50" y="60" width="170" height="90" rx="14"/><circle class="faint" cx="150" cy="105" r="28"/><path class="faint" d="M220 105h40v50"/>'
               '<rect class="shell" x="60" y="250" width="150" height="130" rx="14"/><circle class="faint" cx="135" cy="315" r="34"/><circle class="faint" cx="135" cy="315" r="10"/>'
               '<rect class="shell" x="270" y="70" width="170" height="110" rx="12"/><path class="faint" d="M290 100h130M290 124h130M290 148h70"/><circle class="faint" cx="414" cy="150" r="6"/>'
               '<rect class="shell" x="270" y="250" width="170" height="130" rx="12"/><path class="faint" d="M290 280h130M290 304h130M290 328h90"/>'
               '<rect class="shell" x="480" y="150" width="80" height="130" rx="40"/><circle class="faint" cx="520" cy="215" r="14"/>'),
}


def build_xray():
    """Evidence map: see-through devices. Tap a part to see what evidence lives there."""
    f = DATA / "xray.json"
    if not f.exists():
        return
    with open(f, encoding="utf-8") as fh:
        x = json.load(fh)
    if x.get("draft") and not PREVIEW:
        return
    parts = x["parts"]
    present = [d for d in XRAY_DEVICES if any(p["device"] == d[0] for p in parts)]
    # positions
    seen = {}
    for p in parts:
        if "x" not in p:
            i = seen.get(p["device"], 0)
            slots = XRAY_SLOTS.get(p["device"], [])
            if i >= len(slots):
                sys.exit("Evidence map: device %s has more parts than hotspots" % p["device"])
            p["x"], p["y"] = slots[i]
            seen[p["device"]] = i + 1

    def spots(device):
        out = []
        for p in parts:
            if p["device"] != device:
                continue
            out.append('<a class="spot" href="#part-%s" data-part="%s" aria-label="%s"><circle class="ring" cx="%d" cy="%d" r="22"/>'
                       '<circle class="dot" cx="%d" cy="%d" r="11"/><text x="%d" y="%d" text-anchor="middle">%s</text></a>'
                       % (p["id"], p["id"], e(p["label"]), p["x"], p["y"], p["x"], p["y"], p["x"], p["y"] + 44, e(p["label"])))
        return "".join(out)

    laptop_art = ('<rect class="shell" x="40" y="24" width="540" height="270" rx="16"/>'
                  '<rect class="glass" x="58" y="42" width="504" height="234" rx="8"/>'
                  '<path class="shell" d="M14 318 H606 L582 432 H38 Z"/>'
                  '<path class="faint" d="M40 318 V294 M580 318 V294"/>'
                  '<rect class="faint" x="64" y="338" width="112" height="70" rx="8"/><circle class="faint" cx="120" cy="373" r="24"/>'
                  '<rect class="faint" x="222" y="346" width="96" height="54" rx="4"/><path class="faint" d="M234 400v10M250 400v10M266 400v10M282 400v10M298 400v10"/>'
                  '<path class="faint" d="M380 392c16-30 44-30 60 0M392 398c10-18 26-18 36 0"/>'
                  '<rect class="faint" x="514" y="358" width="52" height="28" rx="4"/>'
                  '<rect class="faint" x="84" y="64" width="132" height="92" rx="6"/><path class="faint" d="M84 82h132"/>'
                  '<rect class="faint" x="264" y="64" width="132" height="92" rx="6"/><path class="faint" d="M300 96l24 14-24 14z"/>'
                  '<rect class="faint" x="84" y="172" width="132" height="86" rx="6"/><path class="faint" d="M100 196h100M100 214h100M100 232h64"/>'
                  '<rect class="faint" x="264" y="172" width="132" height="86" rx="6"/><path class="faint" d="M264 180l66 44 66-44"/>'
                  '<path class="faint" d="M452 100h56l-6 70h-44zM444 100h72M468 90h24"/>')
    phone_art = ('<rect class="shell" x="24" y="14" width="192" height="592" rx="30"/><rect class="glass" x="38" y="50" width="164" height="520" rx="10"/>'
                 '<path class="faint" d="M100 32h40"/><circle class="faint" cx="120" cy="588" r="8"/>')
    watch_art = ('<rect class="faint" x="88" y="2" width="64" height="70" rx="10"/><rect class="faint" x="88" y="548" width="64" height="70" rx="10"/>'
                 '<rect class="shell" x="30" y="70" width="180" height="480" rx="44"/><rect class="glass" x="46" y="92" width="148" height="436" rx="32"/><path class="faint" d="M210 280h12v50h-12"/>')
    arts = {"laptop": laptop_art, "phone": phone_art, "wearable": watch_art}
    svgs = []
    for did, label, _intro in present:
        vb, art = XRAY_SVG[did]
        if did in arts:
            art = arts[did]
            vb = XRAY_SVG[did][0]
        cls = "xray phone" if did in ("phone", "wearable") else "xray"
        svgs.append('<svg class="%s xdev" data-device="%s" viewBox="%s" role="group" aria-label="%s: tap a part">%s%s</svg>'
                    % (cls, did, vb, e(label), art, spots(did)))

    dev_label = {d[0]: d[1] for d in XRAY_DEVICES}
    panels = []
    for p in parts:
        tools = "".join('<a class="tool-chip" href="tools/%s.html">%s</a>' % (tid, e(TOOL[tid]["name"])) for tid in p["tools"] if tid in TOOL)
        wfs = "".join('<li><a href="workflows/%s.html">%s</a></li>' % (wid, e(WORKFLOWS[wid]["title"])) for wid in p.get("workflows", []) if wid in WORKFLOWS)
        bas = "".join('<li><a href="basics/%s.html">%s</a></li>' % (bid, e(BASICS[bid]["title"])) for bid in p.get("basics", []) if bid in BASICS)
        life = XRAY_LIFE.get(p.get("life", ""), "")
        panels.append('<section class="card xpanel" id="part-%s" data-panel="%s" data-device="%s"><div class="top"><div class="label">%s</div>%s</div><h2>%s</h2>'
                      '<h3>What you can find here</h3><ul class="tight">%s</ul>%s'
                      '<h3>Free tools that read it</h3><div class="tool-chips on-card">%s</div>%s%s%s'
                      '<p><a href="categories/%s.html" style="font-weight:600">See all tools for %s</a></p></section>'
                      % (p["id"], p["id"], p["device"], e(dev_label[p["device"]]), ('<span class="badge life-%s">%s</span>' % (p["life"], e(life))) if life else "",
                         e(p["label"]), "".join("<li>%s</li>" % e(i) for i in p["finds"]),
                         ('<h3>How it is collected</h3><p>%s</p>' % e(p["how"])) if p.get("how") else "",
                         tools,
                         ('<h3>Step-by-step workflow</h3><ul class="list-plain">%s</ul>' % wfs) if wfs else "",
                         ('<h3>Learn the basics</h3><ul class="list-plain">%s</ul>' % bas) if bas else "",
                         ('<div class="note xtip"><strong>Examiner tip.</strong> %s</div>' % e(p["tip"])) if p.get("tip") else "",
                         p["category"], e(CAT[p["category"]]["name"])))
    tabs = "".join('<button type="button" class="xtab" role="tab" data-device="%s" aria-selected="false">%s</button>' % (d[0], e(d[1])) for d in present)
    intro = "".join('<p class="xintro" data-device="%s">%s</p>' % (d[0], e(d[2])) for d in present)
    legend = "".join('<span class="badge life-%s">%s</span>' % (k, e(v)) for k, v in XRAY_LIFE.items())
    body = ('<div class="wrap"><div class="page-head"><div class="label y">Evidence map</div><h1>Where does the evidence live?</h1>'
            '<p class="lead">Choose a device, then tap any part to see what an investigator can find there, how long it lasts, and which free tool reads it.</p>%s'
            '<div class="xtabs" role="tablist" aria-label="Choose a device">%s</div><div class="xlegend"><span class="muted">How long it lasts:</span>%s</div></div>'
            '<div class="xray-layout"><div class="xray-stage">%s%s</div><div class="xray-panels" aria-live="polite">'
            '<p class="xhint">Tap a yellow dot to start.</p>%s</div></div></div>'
            % (draft_banner(x), tabs, legend, intro, "".join(svgs), "".join(panels)))
    page("map.html", "Evidence map", "See-through devices: choose a laptop, phone, drone, car, cloud account and more, tap a part to see what evidence it holds and which free tool reads it.", body, "map")


def build_hotseat():
    f = DATA / "hotseat.json"
    if not f.exists():
        return False
    with open(f, encoding="utf-8") as fh:
        h = json.load(fh)
    if h.get("draft") and not PREVIEW:
        return False
    groups = []
    for g in h["groups"]:
        cards = "".join('<details class="qa"><summary>%s</summary><p>%s</p><p class="rem"><strong>Remember:</strong> %s</p></details>'
                        % (e(c["q"]), e(c["a"]), e(c["remember"])) for c in g["cards"])
        groups.append('<section><h2>%s</h2><div class="qa-list">%s</div></section>' % (e(g["title"]), cards))
    body = ('<div class="wrap"><div class="page-head"><div class="label y">Practice for viva and court</div><h1>The examiner\'s hot seat</h1>'
            '<p class="lead">The hard questions a defence lawyer, a judge or a viva examiner asks a forensic examiner. Try to answer each one aloud, then tap it to see a model answer.</p>'
            '<p class="note" style="max-width:820px">These are general study answers about forensic method. They are not legal advice. Follow the law and procedure of your country and your lab.</p>%s</div>'
            '<div class="prose wide" style="padding-bottom:64px">%s</div></div>' % (draft_banner(h), "".join(groups)))
    page("hotseat.html", "The examiner's hot seat", "Hard questions asked of digital forensic examiners in a viva or in court, with model answers for students.", body, "hotseat")
    return True


BRANCHES = [
    ("foundations", "Foundations", "The ideas every examiner uses: process, custody, hashes and good practice."),
    ("imaging", "Imaging and acquisition", "How evidence is copied without changing it."),
    ("disk", "Disks and file systems", "Where data lives on a drive, and how deleted data can come back."),
    ("windows", "Windows artifacts", "What Windows records about users and programs."),
    ("memory", "Memory (RAM)", "Evidence that exists only while a computer is running."),
    ("mobile", "Mobile devices", "Phones and tablets: extraction, locks, databases and apps."),
    ("network", "Network", "Traffic, logs and what can be seen on the wire."),
    ("cloud", "Cloud, email, logs and timelines", "Evidence that lives online or in records across many systems."),
    ("specialist", "Specialist topics", "Malware, metadata, hiding, passwords, crypto, drones, vehicles and calls."),
]
BRANCH = {b[0]: b for b in BRANCHES}


def basics_order():
    """Topics in the order of data/basics-order, else the order of the topic list file."""
    ids = list(BASICS)
    order = {}
    f = DATA / "basics-order.txt"
    if f.exists():
        order = {x.strip(): i for i, x in enumerate(f.read_text(encoding="utf-8").split("\n")) if x.strip()}
    return sorted(ids, key=lambda i: (order.get(i, 10 ** 6), i))


def build_basics():
    if not BASICS:
        return
    ids = basics_order()
    by_branch = {}
    for i in ids:
        by_branch.setdefault(BASICS[i]["branch"], []).append(i)
    # topic pages
    for b, members in by_branch.items():
        for n, tid in enumerate(members):
            g = BASICS[tid]
            out, jump = [], []

            def section(anchor, title, inner):
                jump.append('<a href="#%s">%s</a>' % (anchor, e(title)))
                out.append('<section id="%s"><h2>%s</h2>%s</section>' % (anchor, e(title), inner))

            for k, sec in enumerate(g["sections"]):
                inner = "".join("<p>%s</p>" % e(t) for t in sec["text"])
                if sec.get("points"):
                    inner += '<ul class="tight-list">%s</ul>' % "".join("<li>%s</li>" % e(x) for x in sec["points"])
                section("s%d" % (k + 1), sec["title"], inner)
            c = g.get("compare")
            if c:
                head = "".join("<th>%s</th>" % e(h) for h in c["headers"])
                rows = "".join("<tr><th scope=\"row\">%s</th>%s</tr>" % (e(r[0]), "".join("<td>%s</td>" % e(x) for x in r[1:])) for r in c["rows"])
                section("compare", c["title"], '<div class="cmp-wrap"><table class="cmp"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, rows))
            if g.get("example"):
                section("example", "Example", '<div class="note"><p>%s</p></div>' % e(g["example"]))
            section("mistakes", "Common mistakes", '<ul class="tight-list">%s</ul>' % "".join("<li>%s</li>" % e(x) for x in g["mistakes"]))
            section("terms", "Key terms", '<dl class="terms">%s</dl>' % "".join("<dt>%s</dt><dd>%s</dd>" % (e(t["term"]), e(t["meaning"])) for t in g["terms"]))
            section("viva", "Questions you may be asked",
                    '<div class="qa-list">%s</div>' % "".join('<details class="qa"><summary>%s</summary><p>%s</p></details>' % (e(x["q"]), e(x["a"])) for x in g["exam"]))
            tl = [TOOL[x] for x in g.get("tools", []) if x in TOOL]
            if tl:
                section("tools", "Free tools to practise with",
                        '<div class="tool-chips">%s</div>' % "".join('<a class="tool-chip" href="../tools/%s.html">%s</a>' % (x["id"], e(x["name"])) for x in tl))
            rel = [r for r in g.get("related", []) if r in BASICS]
            if rel:
                section("related", "Read next",
                        '<div class="grid">%s</div>' % "".join(
                            '<article class="card"><h3><a href="%s.html">%s</a></h3><p class="sum">%s</p></article>'
                            % (r, e(BASICS[r]["title"]), e(BASICS[r]["quick"][:150].rsplit(" ", 1)[0] + ("..." if len(BASICS[r]["quick"]) > 150 else ""))) for r in rel))
            section("learn", "Learn more",
                    '<ul class="list-plain">%s</ul><p class="muted" style="font-size:13px;margin-top:12px">%s Last reviewed %s. '
                    'Procedures and laws differ by country and agency. Follow your own lab\'s procedure.</p>'
                    % ("".join('<li><a href="%s" rel="noopener">%s</a></li>' % (e(l["url"]), e(l["label"])) for l in g["learn"]),
                       e(g.get("sources_note", "")), fmt_date(g.get("reviewed"))))
            prev_t = BASICS[members[n - 1]] if n else None
            next_t = BASICS[members[n + 1]] if n + 1 < len(members) else None
            pn = ""
            if prev_t or next_t:
                pn = '<nav class="pn" aria-label="Next and previous">%s%s</nav>' % (
                    ('<a href="%s.html"><span class="label">Previous</span>%s</a>' % (prev_t["id"], e(prev_t["title"]))) if prev_t else "<span></span>",
                    ('<a href="%s.html"><span class="label">Next</span>%s</a>' % (next_t["id"], e(next_t["title"]))) if next_t else "<span></span>")
            body = ('<div class="wrap"><div class="page-head"><div class="crumbs"><a href="../index.html">Home</a> / <a href="../basics.html">Basics</a> / <a href="../basics.html#%s">%s</a></div>'
                    '<h1>%s</h1><div class="answer"><span class="label y">Short answer</span><p>%s</p></div></div>'
                    '%s<nav class="jump" aria-label="On this page"><span class="label">On this page</span>%s</nav>'
                    '<div class="prose wide basic">%s</div>%s</div>'
                    % (b, e(BRANCH[b][1]), e(g["title"]), e(g["quick"]), draft_banner(g), "".join(jump), "".join(out), pn))
            art = {"@context": "https://schema.org", "@type": "Article", "headline": g["title"], "description": g["quick"],
                   "inLanguage": "en", "publisher": {"@type": "Organization", "name": NAME}}
            if g.get("reviewed"):
                art["dateModified"] = g["reviewed"]
            page("basics/%s.html" % tid, g["title"], g["quick"][:200], body, "basics", head=ld(art), og_type="article")
    # index
    sections = []
    for key, name, intro in BRANCHES:
        members = by_branch.get(key, [])
        if not members:
            continue
        cards = "".join('<article class="card" data-section="%s"><h3><a href="basics/%s.html">%s</a></h3><p class="sum">%s</p></article>'
                        % (e((BASICS[i]["title"] + " " + BASICS[i]["quick"] + " " + " ".join(t["term"] for t in BASICS[i]["terms"])).lower()),
                           i, e(BASICS[i]["title"]), e(BASICS[i]["quick"][:140].rsplit(" ", 1)[0] + ("..." if len(BASICS[i]["quick"]) > 140 else ""))) for i in members)
        sections.append('<section id="%s" class="basic-group"><div class="section-head"><h2>%s</h2><span class="muted">%d topics</span></div>'
                        '<p class="muted" style="max-width:760px;margin-bottom:16px">%s</p><div class="grid">%s</div></section>' % (key, e(name), len(members), e(intro), cards))
    start = [i for i in ["digital-forensics-overview", "what-is-forensic-imaging", "write-blocker", "physical-image", "logical-image", "hash-values",
                         "mobile-extraction-levels", "packet-capture-pcap"] if i in BASICS]
    chips = "".join('<a href="basics/%s.html">%s</a>' % (i, e(BASICS[i]["title"])) for i in start)
    jumpb = "".join('<a href="#%s">%s</a>' % (k, e(n)) for k, n, _ in BRANCHES if k in by_branch)
    body = ('<div class="wrap"><div class="page-head"><div class="label y">Start here</div><h1>Digital forensics basics</h1>'
            '<p class="lead">Short, plain-English answers to the questions every student asks first: what is imaging, what is a write blocker, what is a logical or physical image, and the same for mobile, network, memory and more.</p>'
            '<p class="note" style="max-width:820px">These pages teach general method for study. Procedures and laws differ by country and agency, and none of this is legal advice. Follow your own lab\'s procedure.</p>'
            '<div class="chips"><span class="muted">Popular:</span>%s</div>'
            '<div class="filters"><div class="row"><label class="label" for="bq">Search the basics</label>'
            '<input id="bq" type="search" data-section-filter placeholder="For example hash, write blocker or SQLite" autocomplete="off"></div></div>'
            '<nav class="jump" aria-label="Branches"><span class="label">Branches</span>%s<a href="glossary.html">Glossary</a></nav></div>'
            '%s<p class="empty" data-empty hidden>No match yet. Try a shorter word, or open the <a href="glossary.html">glossary</a>.</p></div>' % (chips, jumpb, "".join(sections)))
    page("basics.html", "Digital forensics basics", "Plain-English answers for students: forensic imaging, write blockers, logical and physical images, mobile, network, memory and more.", body, "basics")
    # glossary
    terms = {}
    for i in ids:
        for t in BASICS[i]["terms"]:
            terms.setdefault(t["term"].strip(), []).append((t["meaning"], i))
    letters = {}
    for term in sorted(terms, key=str.lower):
        letters.setdefault(term[0].upper(), []).append(term)
    gl = []
    for L in sorted(letters):
        items = ""
        for term in letters[L]:
            meaning, src = terms[term][0]
            more = "".join(' <a href="basics/%s.html">%s</a>' % (i, e(BASICS[i]["title"])) for _, i in terms[term][:2])
            items += ('<div class="gl" data-section="%s" id="t-%s"><dt>%s</dt><dd>%s<span class="muted gl-src">Read: %s</span></dd></div>'
                      % (e((term + " " + meaning).lower()), re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-"), e(term), e(meaning), more.strip()))
        gl.append('<section><h2 class="gl-letter" id="L%s">%s</h2><dl class="terms">%s</dl></section>' % (L, L, items))
    az = "".join('<a href="#L%s">%s</a>' % (L, L) for L in sorted(letters))
    body = ('<div class="wrap"><div class="page-head"><div class="crumbs"><a href="index.html">Home</a> / <a href="basics.html">Basics</a> / Glossary</div><h1>Forensics glossary</h1>'
            '<p class="lead">%d terms from the Basics pages, in plain English.</p>'
            '<div class="filters"><div class="row"><label class="label" for="gq">Find a term</label><input id="gq" type="search" data-section-filter placeholder="For example hash or HPA" autocomplete="off"></div></div>'
            '<nav class="jump az" aria-label="Letters"><span class="label">Jump to</span>%s</nav></div>'
            '<div class="prose wide" style="padding-bottom:64px">%s<p class="empty" data-empty hidden>No term found.</p></div></div>' % (len(terms), az, "".join(gl)))
    page("glossary.html", "Forensics glossary", "Plain-English definitions of digital forensics terms for students.", body, "basics")


def build_lab():
    def link(wid, label):
        return ('<a href="workflows/%s.html">%s</a>' % (wid, label)) if wid in WORKFLOWS else ""
    def tl(*ids):
        return "".join('<a class="tool-chip" href="tools/%s.html">%s</a>' % (i, e(TOOL[i]["name"])) for i in ids if i in TOOL)
    def basic(bid):
        return ('<a href="basics/%s.html">%s</a>' % (bid, e(BASICS[bid]["title"]))) if bid in BASICS else ""
    body = """<div class="wrap"><div class="page-head"><div class="label y">Hands-on practice</div><h1>Evidence lab</h1>
<p class="lead">Small experiments you can do right now. Pick a file, see what it hides, and learn what to look for. Everything runs on your own device. No file is uploaded.</p>
<p class="note" style="max-width:820px">Use your own photos or practice files only. Do not open real case evidence in a web page. On real cases, work on a verified copy with a proper tool.</p></div>
<div class="grid two lab-grid" style="padding-bottom:64px">
<section class="card tb" id="image"><div class="label">Lab 1</div><h2>Does this photo hide something?</h2>
<p class="sum">Photos often carry a hidden block of information called EXIF metadata: the camera, the time, sometimes the place. Choose a JPEG or PNG, or use our sample photo.</p>
<div class="lab-btns"><button type="button" class="btn small on-card solid" id="lab-img-sample">Use the sample photo</button><button type="button" class="btn small on-card" id="lab-img-dl">Download the sample</button></div>
<label class="label" for="lab-img">Or choose your own photo</label><input id="lab-img" type="file" accept="image/jpeg,image/png">
<div id="lab-img-prev" class="lab-prev"></div><div class="tb-out lab-out" id="lab-img-out" aria-live="polite">The details will appear here.</div>
<div class="note"><strong>Try this.</strong> Use the sample photo. Find the time it was taken and the time it was saved again. Then find the GPS position and write down in one sentence what it proves and what it does not.</div>
<p class="sum" style="font-size:13.5px">Next: %s %s %s</p><div class="tool-chips on-card">%s</div></section>
<section class="card tb" id="signature"><div class="label">Lab 2</div><h2>Is this file what its name says?</h2>
<p class="sum">Every file type starts with a few fixed bytes, a signature. Choose any file to see its first bytes and what type they say it is. A name that does not match the content is worth a closer look.</p>
<label class="label" for="lab-sig">File</label><input id="lab-sig" type="file">
<div class="tb-out lab-out" id="lab-sig-out" aria-live="polite">The result will appear here.</div>
<div class="note"><strong>Try this.</strong> Make a copy of a photo and rename it to end in .pdf. Choose the copy here. What does the lab say?</div>
<p class="sum" style="font-size:13.5px">Next: %s %s</p><div class="tool-chips on-card">%s</div></section>
<section class="card tb" id="compare"><div class="label">Lab 3</div><h2>Are these two files identical?</h2>
<p class="sum">A hash value is a fingerprint of a file. If two files give the same SHA-256, they are identical. This is how examiners show that a copy matches the original.</p>
<label class="label" for="lab-cmp-a">File A</label><input id="lab-cmp-a" type="file"><label class="label" for="lab-cmp-b">File B</label><input id="lab-cmp-b" type="file">
<div class="tb-out lab-out" id="lab-cmp-out" aria-live="polite">Choose two files.</div>
<div class="note"><strong>Try this.</strong> Download the sample photo twice and compare the two copies. Then open one copy in an image editor, save it again and compare once more.</div>
<p class="sum" style="font-size:13.5px">Next: %s %s</p><div class="tool-chips on-card">%s</div></section>
<section class="card tb" id="strings"><div class="label">Lab 4</div><h2>What text is inside this file?</h2>
<p class="sum">Programs and documents often contain readable text: paths, names, web addresses, error messages. Examiners pull this out first to get a feeling for a file. This lab reads the first 4 MB.</p>
<label class="label" for="lab-str">File</label><input id="lab-str" type="file">
<div class="lab-row"><label class="label" for="lab-str-min">Shortest string</label><input id="lab-str-min" type="number" min="4" max="40" value="8" style="max-width:90px">
<label class="lab-check"><input type="checkbox" id="lab-str-wide"> also Windows (UTF-16) text</label></div>
<label class="label" for="lab-str-q">Filter</label><input id="lab-str-q" type="search" placeholder="For example http or .dll" autocomplete="off">
<div class="tb-out lab-out" id="lab-str-out" aria-live="polite">The strings will appear here.</div>
<div class="note"><strong>Try this.</strong> Choose a small program or a Word document you made yourself. Filter for "http" or "C:". What can you learn without opening it?</div>
<p class="sum" style="font-size:13.5px">Next: %s</p><div class="tool-chips on-card">%s</div></section>
</div><script src="assets/lab.js" defer></script><noscript><p class="note">The evidence lab needs JavaScript.</p></noscript></div>""" % (
        link("photo-metadata", "Photo metadata workflow"), basic("image-and-video-metadata"), basic("hash-values"), tl("exiftool", "mediainfo", "sherloq", "forensically"),
        basic("file-carving"), basic("image-formats"), tl("detect-it-easy", "binwalk", "cyberchef"),
        basic("hash-values"), basic("evidence-integrity"), tl("hashdeep", "quickhash", "ftk-imager"),
        basic("malware-analysis-basics"), tl("floss", "bstrings", "cyberchef"))
    body = body.replace("Next:  ", "Next: ").replace("Next:  ", "Next: ")
    page("lab.html", "Evidence lab", "Hands-on practice in your browser: read photo metadata, check a file signature, compare file hashes and pull text out of a file. Nothing is uploaded.", body, "lab")


def build_toolbox():
    body = """<div class="wrap"><div class="page-head"><div class="label y">Runs in your browser</div><h1>Pocket toolbox</h1>
<p class="lead">Small helpers for daily forensic work. Everything runs on your own device. Nothing you type or open here is sent anywhere.</p></div>
<div class="grid two" style="padding-bottom:64px">
<section class="card tb" id="time"><h2>Timestamp converter</h2><p class="sum">Paste a raw time value from a database or the registry and choose its format.</p>
<label class="label" for="tb-ts">Value</label><input id="tb-ts" inputmode="numeric" autocomplete="off" placeholder="For example 13350000000000000">
<label class="label" for="tb-fmt">Format</label><select id="tb-fmt">
<option value="unix">Unix seconds (since 1970)</option><option value="unixms">Unix milliseconds (Android, WhatsApp)</option>
<option value="prtime">Unix microseconds (Firefox)</option><option value="webkit">Chrome and Edge (microseconds since 1601)</option>
<option value="filetime">Windows FILETIME (100-nanosecond steps since 1601)</option><option value="mac">Apple seconds (since 2001)</option>
<option value="macns">Apple nanoseconds (since 2001)</option></select>
<div class="tb-out" id="tb-ts-out" aria-live="polite">The date will appear here.</div></section>
<section class="card tb" id="hash"><h2>File hash</h2><p class="sum">Choose a file to calculate its SHA-256 and SHA-1 values. The file stays on your device.</p>
<label class="label" for="tb-file">File</label><input id="tb-file" type="file">
<div class="tb-out" id="tb-hash-out" aria-live="polite">The hash values will appear here.</div>
<p class="sum" style="font-size:13px">Use a small file. Very large images need a desktop hashing tool.</p></section>
<section class="card tb" id="rot13"><h2>ROT13 decoder</h2><p class="sum">Windows stores UserAssist program names in ROT13. Paste the stored name to read it.</p>
<label class="label" for="tb-rot">Text</label><textarea id="tb-rot" rows="3" placeholder="For example P:\\\\Hfref\\\\Choyvp"></textarea>
<div class="tb-out" id="tb-rot-out" aria-live="polite">The decoded text will appear here.</div></section>
<section class="card tb" id="b64"><h2>Base64 and hex decoder</h2><p class="sum">Decode a Base64 or hex string to readable text.</p>
<label class="label" for="tb-b64">Text</label><textarea id="tb-b64" rows="3" placeholder="For example SGVsbG8="></textarea>
<div class="tb-out" id="tb-b64-out" aria-live="polite">The decoded text will appear here.</div></section>
</div><noscript><p class="note">The toolbox needs JavaScript.</p></noscript></div>"""
    page("toolbox.html", "Pocket toolbox", "Timestamp converter, file hash, ROT13 and Base64 decoders that run in your browser. Nothing is uploaded.", body, "toolbox")


def build_alternatives():
    groups = {}
    for t in TOOLS:
        for p in t.get("similar_to", []):
            groups.setdefault(p, []).append(t)
    sections = []
    for product in sorted(groups, key=str.lower):
        tools = sorted(groups[product], key=lambda t: t["name"].lower())
        key = (product + " " + " ".join(t["name"] for t in tools)).lower()
        sections.append('<section class="alt-group" data-section="%s"><div class="label y">If you know</div><h2>%s</h2>'
                        '<p class="muted">These free tools do a similar job for some tasks:</p><div class="grid">%s</div></section>'
                        % (e(key), e(product), "".join(card(t, "") for t in tools)))
    body = ('<div class="wrap"><div class="page-head"><h1>Free alternative finder</h1>'
            '<p class="lead">Type the name of a commercial product to see free and open-source tools that cover some of the same work.</p>'
            '<p class="note"><strong>What "similar job" means.</strong> The free tool handles some of the same tasks. It does not mean equal features, the same supported devices, vendor support or acceptance by a court. '
            'Commercial suites usually add acquisition methods, automation and training that free tools do not. Product names are trademarks of their owners and are used only to describe what a tool does.</p></div>'
            '<div class="filters"><div class="row"><label class="label" for="aq">Product</label>'
            '<input id="aq" type="search" data-section-filter placeholder="For example AXIOM, EnCase or Cellebrite" autocomplete="off"></div></div>'
            '%s<p class="empty" data-empty hidden>No match yet. Try a shorter name, or <a href="tools.html">search all tools</a>.</p></div>'
            % "".join(sections))
    page("alternatives.html", "Free alternative finder",
         "Find free and open-source digital forensics tools that do a similar job to well-known commercial products.", body, "alternatives")


def build_inside():
    GROUPS = ["Computer and mobile forensics suites", "Incident response, EDR and SIEM", "Network and cloud security", "Libraries and third-party notices"]

    def row(it):
        links = ", ".join('<a href="tools/%s.html">%s</a>' % (i, e(TOOL[i]["name"])) for i in it.get("tool_ids", []) if i in TOOL)
        key = " ".join([it["product"], it.get("vendor", ""), it["open_source"], it["statement"]]).lower()
        return ('<div class="card row-card" data-section="%s"><div class="v"><div class="t">%s <span>%s</span> %s</div>'
                '<p class="sum">%s</p><div class="src-line">Source: <a href="%s" rel="noopener">%s</a>, checked %s</div>'
                '%s</div></div>' % (e(key), e(it["product"]), e(it["relation"]), e(it["open_source"]), e(it["statement"]),
                                    e(it["source_url"]), e(it["source_label"]), fmt_date(it.get("checked")),
                                    ('<p class="sum" style="font-size:13px">In this directory: %s</p>' % links) if links else ""))
    items = sorted(INTEG["integrations"], key=lambda x: (x["product"].lower(), x["open_source"].lower()))
    secs = []
    for gname in GROUPS:
        mem = [x for x in items if x.get("group") == gname]
        if mem:
            secs.append('<section class="section" style="padding-top:8px"><div class="section-head"><h2>%s</h2><span class="muted">%d cases</span></div>'
                        '<div style="display:flex;flex-direction:column;gap:12px">%s</div></section>' % (e(gname), len(mem), "".join(row(x) for x in mem)))
    oo = INTEG.get("open_on_open", [])
    total = len(items) + len(oo)
    prods = len({x["product"] for x in items})
    body = ('<div class="wrap"><div class="page-head"><h1>Inside commercial tools</h1>'
            '<p class="lead">Documented cases where a commercial product runs, includes or accepts open-source tools and rule formats. Learning the open tool means you already understand what the paid feature does.</p>'
            '<p class="note">Each entry repeats only what the vendor\'s own page (or the open project\'s own documentation) says and links to it. Products change, so follow the source link for the current position. '
            'Nothing here suggests a vendor endorses this site.</p>'
            '<div class="stats"><span><b>%d</b> documented cases</span><span><b>%d</b> commercial products</span></div>'
            '<p style="margin:8px 0 16px"><a class="btn small" href="vendor-free.html">Free tools given away by these vendors</a></p>'
            '<div class="filters"><div class="row"><label class="label" for="iq">Find a product or open tool</label>'
            '<input id="iq" type="search" data-section-filter placeholder="For example YARA, Velociraptor or Cellebrite" autocomplete="off"></div></div></div>'
            '%s<section class="section"><div class="section-head"><h2>Open source builds on open source</h2></div>'
            '<div style="display:flex;flex-direction:column;gap:12px">%s</div></section>'
            '<p class="empty" data-empty hidden>No match yet. Try a shorter word.</p></div>'
            % (total, prods, "".join(secs), "".join(row(x) for x in oo)))
    page("inside.html", "Inside commercial tools",
         "Documented examples of commercial digital forensics and security products that run or accept open-source tools, each with its vendor source.", body, "inside")


def build_vendor_free():
    f = DATA / "vendor-free-tools.json"
    if not f.exists():
        return False
    items = json.load(open(f, encoding="utf-8"))
    if not items:
        return False
    groups = {}
    for it in items:
        groups.setdefault(it["technology"], []).append(it)
    secs = []
    for tech in sorted(groups, key=str.lower):
        cards = []
        for it in sorted(groups[tech], key=lambda x: (x["vendor"].lower(), x["tool"].lower())):
            here = ('<p class="sum" style="font-size:13px">In this directory: <a href="tools/%s.html">%s page</a></p>' % (it["tool_id"], e(TOOL[it["tool_id"]]["name"]))) if it.get("tool_id") in TOOL else ""
            cards.append('<article class="card" data-section="%s"><div class="top"><div><h3>%s</h3><div class="by">by %s</div></div><span class="badge">%s</span></div>'
                         '<p class="sum">%s</p><div class="src-line" style="font-size:13px;color:var(--ink-muted)">Source: <a href="%s" rel="noopener">%s</a>, checked %s</div>%s</article>'
                         % (e((it["tool"] + " " + it["vendor"] + " " + tech + " " + it["what"]).lower()), e(it["tool"]), e(it["vendor"]), e(it["cost_note"]),
                            e(it["what"]), e(it["source_url"]), e(it["source_label"]), fmt_date(it.get("checked")), here))
        secs.append('<section class="section" style="padding-top:8px"><div class="section-head"><h2>%s</h2><span class="muted">%d tools</span></div><div class="grid">%s</div></section>'
                    % (e(tech), len(groups[tech]), "".join(cards)))
    body = ('<div class="wrap"><div class="page-head"><div class="crumbs"><a href="index.html">Home</a> / <a href="inside.html">Inside commercial tools</a> / Free vendor tools</div>'
            '<h1>Free tools from commercial vendors</h1>'
            '<p class="lead">Many companies that sell forensic and security products also give some tools away. Here they are, sorted by what they do.</p>'
            '<p class="note">Free does not always mean open source. Some need a registration form or limit use to non-commercial work, and terms can change. Always read the vendor page and licence before use. '
            'Every entry links to the vendor\'s own page. Nothing here suggests a vendor endorses this site.</p>'
            '<div class="stats"><span><b>%d</b> free tools</span><span><b>%d</b> vendors</span></div>'
            '<div class="filters"><div class="row"><label class="label" for="vq">Find a tool or vendor</label>'
            '<input id="vq" type="search" data-section-filter placeholder="For example Magnet, RAM or imaging" autocomplete="off"></div></div></div>'
            '%s<p class="empty" data-empty hidden>No match yet. Try a shorter word.</p></div>' % (len(items), len({x["vendor"] for x in items}), "".join(secs)))
    page("vendor-free.html", "Free tools from commercial vendors", "Free forensic and security tools given away by commercial vendors, sorted by what they do, each linked to the vendor's own page.", body, "inside")
    return True


def simple_list(items, who_key=None):
    out = []
    for it in items:
        by = ('<div class="by">by %s</div>' % e(it[who_key])) if who_key and it.get(who_key) else ""
        out.append('<article class="card"><h3><a href="%s" rel="noopener">%s</a></h3>%s<p class="sum">%s</p></article>'
                   % (e(it["url"]), e(it["name"]), by, e(it["what"])))
    return '<div class="grid">%s</div>' % "".join(out)


def build_nist():
    rows = []
    for f in NIST["functionalities"]:
        links = []
        for cid in f["categories"]:
            n = sum(1 for t in TOOLS if cid in t["categories"])
            links.append('<a href="categories/%s.html">%s</a> (%d)' % (cid, e(CAT[cid]["name"]), n))
        where = ", ".join(links) if links else "Not covered yet"
        note = ('<p class="sum" style="font-size:13px">%s</p>' % e(f["note"])) if f.get("note") else ""
        rows.append('<div class="card row-card"><div class="v"><div class="t">%s</div><p class="sum">Here: %s</p>%s'
                    '<div class="src-line"><a href="https://toolcatalog.nist.gov/search/index.php?ff_id=%d" rel="noopener">Same functionality in the NIST catalog</a></div></div></div>'
                    % (e(f["name"]), where, note, f["nist_id"]))
    body = ('<div class="wrap"><div class="page-head"><h1>Browse by NIST functionality</h1>'
            '<p class="lead">The NIST Computer Forensics Tools and Techniques Catalog groups tools by what they do. If you know that list, use it here: each functionality links to the matching category, which lists free and open-source tools only.</p>'
            '<p class="note">The functionality names are the ones NIST uses. The tool lists, descriptions and categories on this site are our own. This site is independent and is not affiliated with NIST.</p></div>'
            '<section class="section" style="padding-top:8px"><div style="display:flex;flex-direction:column;gap:12px">%s</div></section></div>' % "".join(rows))
    page("nist.html", "Browse by NIST functionality",
         "Find free and open-source forensic tools using the functionality names of the NIST Computer Forensics Tools and Techniques Catalog.", body, "categories")


def build_practice():
    body = ('<div class="wrap"><div class="page-head"><h1>Practice evidence</h1>'
            '<p class="lead">You cannot learn a tool without something to examine. These sources give you free disk images, memory dumps, logs and challenges, so you never need to practise on real or private data.</p></div>'
            '<section class="section" style="padding-top:8px">%s</section></div>' % simple_list(PRACTICE, "by"))
    page("practice.html", "Practice evidence", "Free forensic test images, memory samples, log samples and challenges for students.", body, "practice")


def build_learn():
    body = ('<div class="wrap"><div class="page-head"><h1>Learn</h1>'
            '<p class="lead">Good forensics writing is spread across many sites. These are reliable places to start, each with a note on what it is best for.</p></div>'
            '<section class="section" style="padding-top:8px">%s</section></div>' % simple_list(LEARN))
    page("learn.html", "Learn", "Reliable blogs, video channels and communities for learning digital forensics and incident response.", body, "learn")


def build_about():
    email = SITE.get("contact_email", "").strip()
    maint = SITE.get("maintainer", "").strip()
    if not email and not REPO:
        WARNINGS.append("No contact_email or github_repo in data/site.json: the About page has no working contact for corrections yet.")
    if email:
        contact = 'Email <a href="mailto:%s">%s</a>' % (e(email), e(email))
        if REPO:
            contact += ' or <a href="https://github.com/%s/issues">open an issue on GitHub</a>' % e(REPO)
    elif REPO:
        contact = '<a href="https://github.com/%s/issues">Open an issue on GitHub</a>' % e(REPO)
    else:
        contact = "Contact details will be published here before launch"
    suggest = ('<a href="%s">Use the suggestion form on GitHub</a>.' % e(issue_url("suggest-tool", "Tool suggestion: "))) if REPO else contact + "."
    body = """
<div class="wrap"><div class="page-head"><h1>About {name}</h1>
<p class="lead">{name} is a free directory of open-source and free digital forensics tools for students. It exists so that nobody has to hunt through scattered blogs to find out what a tool does, who made it and where to get it.</p></div>
<div class="prose" style="padding-bottom:56px">
{maint}
<h2>How tools are chosen</h2>
<ul><li>The tool is free to download and use for learning.</li><li>It has a clear official home: the developer's own repository or website.</li><li>It is useful in digital forensics or incident response teaching.</li><li>It is not malware, an exploit kit, cracked software or a licence-bypass tool.</li></ul>
<h2>Download links</h2>
<p>This site hosts no tool files. Download buttons link directly to the developer's own release files or website. Version numbers, download links and project activity are refreshed automatically from public GitHub data. The date of the last check is shown on each tool page.</p>
<h2>"Similar job to" and commercial products</h2>
<p>Where a page says a free tool does a similar job to a commercial product, it means the free tool covers some of the same tasks. It does not mean the same features, support or court acceptance. Statements that a commercial product uses an open-source tool are published only with a link to the vendor's own page.</p>
<h2>Disclaimer</h2>
<p>{name} is an independent educational resource. It is not affiliated with, sponsored by or endorsed by any vendor, developer or project listed here. Product and company names are trademarks of their owners and are used only to identify the products. All information is provided as is, with no warranty. Tools are third-party software: check each licence, verify downloads and validate every tool yourself before relying on it in a real examination. Use these tools only on devices and data you are authorised to examine.</p>
<h2 id="corrections">Corrections and removal requests</h2>
<p>If you are a developer or vendor and want an entry corrected or removed, or you have found a mistake: {contact}. Requests from the owner of a tool or trademark are acted on promptly.</p>
<h2 id="suggest">Suggest a tool</h2>
<p>Know a good free tool that is missing? {suggest}</p>
<h2 id="privacy">Privacy</h2>
<p>This site uses no cookies, no analytics and no advertising, and it loads nothing from third-party servers. It is hosted on GitHub Pages, and GitHub may log visitor IP addresses as described in its own privacy statement.</p>
<h2>Credits</h2>
<p>Every tool listed here is the work of its developers, who are named on each page. Fonts: Inter, Space Grotesk and JetBrains Mono, used under the SIL Open Font License.</p>
</div></div>
""".format(name=e(NAME), contact=contact, suggest=suggest,
           maint=("<p>Maintained by %s.</p>" % e(maint)) if maint else "")
    page("about.html", "About and disclaimer", "What %s is, how tools are chosen, the disclaimer and how to request a correction." % NAME, body, "about")


def build_404():
    body = ('<div class="wrap"><div class="page-head" style="padding:72px 0"><div class="mono" style="color:var(--yellow);font-size:13px">0x404</div><h1>Page not found</h1>'
            '<p class="lead">That page does not exist. Try the <a href="%sindex.html">home page</a>.</p></div></div>' % ((BASE + "/") if BASE else ""))
    page("404.html", "Page not found", "Page not found.", body, "")
    PAGES.remove("404.html")


def main():
    for t in TOOLS:
        for c in t["categories"]:
            if c not in CAT:
                sys.exit("Tool %s uses unknown category %s" % (t["id"], c))
    for c in CATS:
        n = sum(1 for t in TOOLS if c["id"] in t["categories"])
        if n > MAX_PER_CATEGORY:
            sys.exit("Category %s lists %d tools. The limit is %d: split the category or raise MAX_PER_CATEGORY." % (c["id"], n, MAX_PER_CATEGORY))
    for it in INTEG["integrations"] + INTEG.get("open_on_open", []):
        if not it.get("source_url"):
            sys.exit("Integration entry for %s has no source_url. Entries without a source are not published." % it.get("product"))
    OUT.mkdir(exist_ok=True)
    for old in OUT.rglob("*.html"):  # drop pages left over from an earlier build
        try:
            old.unlink()
        except OSError:
            pass
    assets = OUT / "assets"
    shutil.copytree(ROOT / "static", assets, dirs_exist_ok=True)
    if (ROOT / "static" / "favicon.ico").exists():
        shutil.copy(ROOT / "static" / "favicon.ico", OUT / "favicon.ico")
    build_home(); build_tools_index(); build_categories(); build_tool_pages()
    build_workflows(); build_xray(); build_compare(); build_hotseat(); build_basics(); build_lab(); build_toolbox(); build_alternatives(); build_inside(); build_vendor_free(); build_nist(); build_practice(); build_learn(); build_about(); build_404()
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    domain = SITE.get("domain", "").strip()
    if domain:
        (OUT / "CNAME").write_text(domain + "\n", encoding="utf-8")
    if BASE:
        today = datetime.date.today().isoformat()
        urls = "".join("<url><loc>%s/%s</loc><lastmod>%s</lastmod></url>" % (BASE, "" if p == "index.html" else p, today) for p in PAGES)
        (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>' % urls, encoding="utf-8")
        (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % BASE, encoding="utf-8")
    else:
        WARNINGS.append("base_url is empty in data/site.json: no sitemap.xml was written. Set it once the domain is chosen.")
    if not REPO:
        WARNINGS.append("github_repo is empty in data/site.json: 'Suggest a tool' and 'Report a problem' links point to the About page for now.")
    print("Built %d pages into %s (%d tools, %d categories, release data for %d tools)."
          % (len(PAGES) + 1, OUT, len(TOOLS), len(CATS), len(REL)))
    for w in WARNINGS:
        print("NOTE: " + w)


if __name__ == "__main__":
    main()
