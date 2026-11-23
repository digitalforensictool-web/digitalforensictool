#!/usr/bin/env python3
"""Builds the static website from the files in data/ into site/.

Uses only the Python standard library. Run from anywhere:
    python scripts/build.py
"""
import datetime
import html
import json
import shutil
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "site"

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
    return "free", "Free, closed source", "Free, closed source"


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

NAV = [("categories", "Categories", "index.html#categories"), ("tools", "All tools", "tools.html"),
       ("alternatives", "Alternatives", "alternatives.html"), ("inside", "Inside commercial tools", "inside.html"),
       ("practice", "Practice", "practice.html"), ("learn", "Learn", "learn.html"), ("about", "About", "about.html")]
if WORKFLOWS:
    NAV.insert(2, ("workflows", "Workflows", "workflows.html"))


def page(path, title, desc, body, current=""):
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
<meta property="og:type" content="website">
<meta name="theme-color" content="#1437C8">
<meta name="format-detection" content="telephone=no">
<script>document.documentElement.className="js"</script>
{canonical}
<link rel="icon" href="{favicon}">
<link rel="stylesheet" href="{px}assets/style.css">
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
<nav aria-label="Footer"><a href="{px}nist.html">Browse by NIST functionality</a><a href="{px}about.html">About and disclaimer</a><a href="{px}about.html#corrections">Corrections and removal requests</a><a href="{px}about.html#privacy">Privacy</a>{maint}</nav>
</div></footer>
<script src="{px}assets/app.js" defer></script>
</body>
</html>
""".format(title=e(full_title), desc=e(desc), canonical=canonical, favicon=FAVICON, px=px, logo=ICON_LOGO,
           name=e(NAME), nav=nav, suggest=e(suggest), body=body, menu_icon=ICON_MENU,
           maint=('<span style="padding:10px 0">Maintained by %s</span>' % e(maint)) if maint else "")
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
                     " ".join(CAT[c]["name"] for c in t["categories"]), " ".join(t["platforms"])]).lower()
    foot = ""
    if t.get("similar_to"):
        foot = '<div class="foot"><span class="label">Similar job to</span><br>%s</div>' % e(", ".join(t["similar_to"]))
    return ('<article class="card" data-item data-name="{name_l}" data-text="{text}" data-type="{type}" '
            'data-level="{level}" data-plat="{plat}" data-stars="{stars}" data-updated="{upd}">'
            '<div class="top"><div><h3><a href="{px}tools/{id}.html">{name}</a></h3><div class="by">by {dev}</div></div>'
            '<span class="badge {cls}">{badge}</span></div>'
            '<p class="sum">{sum}</p>{tags}{foot}</article>').format(
        name_l=e(t["name"].lower()), text=e(text), type=eff_type(t), level=t["level"],
        plat=e(" ".join(p.lower() for p in t["platforms"])), stars=r.get("stars") or 0, upd=e(r.get("pushed_at") or ""),
        px=px, id=t["id"], name=e(t["name"]), dev=e(t["developer"]), cls=cls, badge=badge, sum=e(t["summary"]),
        tags=tool_tags(t), foot=foot)


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
                                      ("source-published", "Source published"), ("free-closed", "Free, closed source")]),
            group("level", "Level", [("all", "All"), ("beginner", "Beginner"), ("intermediate", "Intermediate"),
                                     ("advanced", "Advanced")])]
    if platforms:
        more.append(group("plat", "Runs on", [("all", "All"), ("windows", "Windows"), ("linux", "Linux"),
                                              ("macos", "macOS"), ("web", "Web")]))
    rows.append('<div class="more" id="more-filters">%s</div>' % "".join(more))
    return '<div class="filters" data-filters="%s">%s</div>' % (target, "".join(rows))


def tool_list(tools, px, placeholder):
    tools = sorted(tools, key=lambda t: t["name"].lower())
    return (filters("#list", placeholder) +
            '<p class="count" data-count aria-live="polite">%d tools shown</p>' % len(tools) +
            '<div class="grid" id="list">%s</div>' % "".join(card(t, px) for t in tools) +
            '<p class="empty" data-empty hidden>No tools match these filters. Clear the search or choose "All".</p>')


# ---------------------------------------------------------------- pages

def build_home():
    cat_cards = []
    for i, c in enumerate(CATS):
        members = [t for t in TOOLS if c["id"] in t["categories"]]
        lead = [t for t in members if t["categories"][0] == c["id"]] + [t for t in members if t["categories"][0] != c["id"]]
        eg = ", ".join(t["name"] for t in lead[:3])
        cat_cards.append('<a class="cat" href="categories/%s.html"><span class="hex"><span>0x%02X</span><span>%d tools</span></span>'
                         '<span class="n">%s</span><span class="eg">%s</span></a>' % (c["id"], i, len(members), e(c["name"]), e(eg)))
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
    body = """
<div class="wrap">
<section class="hero">
<div class="label y">{tagline}</div>
<h1>Open-source forensic tools, sorted the way you study.</h1>
<p class="lead">What each tool does, who built it, where to download it, and which commercial product does a similar job. No scattered blogs, no guesswork.</p>
<form class="search" action="tools.html" method="get" role="search">
<div class="box">{icon}<label for="hq" class="skip">Search tools</label><input id="hq" name="q" type="search" placeholder="Try registry, RAM dump or WhatsApp" autocomplete="off"></div>
<button class="btn primary" type="submit">Search</button>
</form>
<div class="chips"><span class="muted">Popular:</span><a href="categories/memory.html">Memory forensics</a><a href="categories/android.html">Android</a><a href="categories/windows.html">Windows registry</a><a href="categories/incident-response.html">Incident response</a></div>
<div class="stats"><span><b>{n}</b> tools</span><span><b>{oss}</b> open source</span><span><b>{ncat}</b> categories</span>{checked}</div>
</section>
<section class="section" id="categories">
<div class="section-head"><h2>Browse by category</h2><span class="mono muted" style="font-size:13px">{ncat} categories · offset 0x00 – 0x{last:02X} · <a href="nist.html">browse by NIST functionality</a></span></div>
<div class="grid cats">{cats}</div>
</section>
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
<div class="section-head"><h2>Know a paid tool? Find a free one.</h2><a href="alternatives.html" style="font-weight:600">Open the alternative finder</a></div>
<p class="muted" style="max-width:760px">Type the name of a commercial product and see free tools that do a similar job, with honest notes on what "similar" means.</p>
</section>
</div>
""".format(tagline=e(SITE["tagline"]), icon=ICON_SEARCH, n=len(TOOLS), oss=oss, ncat=len(CATS), last=len(CATS) - 1,
           checked=('<span>links checked <b>%s</b></span>' % checked) if checked else "",
           cats="".join(cat_cards), rows="".join(rows), featured=featured)
    page("index.html", NAME, SITE["description"], body, "")


def build_tools_index():
    body = ('<div class="wrap"><div class="page-head"><h1>All tools</h1>'
            '<p class="lead">%d free and open-source tools. Search by name, artifact or task, then narrow by licence, level and platform.</p></div>'
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
                '<div class="mono" style="color:var(--yellow);font-size:13px">0x%02X</div><h1>%s</h1><p class="lead">%s</p>%s</div>%s</div>'
                % (e(c["name"]), i, e(c["name"]), e(c["intro"]), note,
                   tool_list(members, "../", "Search this category")))
        page("categories/%s.html" % c["id"], c["name"],
             "%s: free and open-source tools. %s" % (c["name"], c["intro"]), body, "categories")


def download_block(t):
    r = rel_of(t)
    parts = []
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
        facts = [("Developer", e(t["developer"])), ("Licence", e(lic_long)), ("Interface", e(t["interface"])),
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
        rep = issue_url("report-problem", "Problem on page: " + t["name"]) or "../about.html#corrections"
        side.append('<p style="font-size:14px"><a href="%s">Report a problem with this page</a></p>' % e(rep))

        body = ('<div class="wrap"><div class="page-head">'
                '<div class="crumbs"><a href="../index.html">Home</a> / <a href="../categories/%s.html">%s</a> / %s</div>'
                '<h1>%s</h1><p class="muted">by %s</p>'
                '<div class="tags on-blue" style="font-size:12px"><span class="badge %s">%s</span>%s</div></div>'
                '<div class="tool-layout"><div class="tool-main">%s</div><aside class="tool-side" aria-label="Tool facts">%s</aside></div></div>'
                % (primary["id"], e(primary["name"]), e(t["name"]), e(t["name"]), e(t["developer"]), cls, badge,
                   "".join('<span class="tag">%s</span>' % e(x) for x in [LEVELS[t["level"]], t["interface"]] + t["platforms"]),
                   "".join(main), "".join(side)))
        page("tools/%s.html" % t["id"], t["name"], "%s by %s. %s" % (t["name"], t["developer"], t["summary"]), body, "tools")


def draft_banner(item):
    if not item.get("draft"):
        return ""
    return '<p class="note" style="border-color:var(--yellow);color:var(--yellow)">Draft preview. This page is not on the live site yet.</p>'


def build_workflows():
    if not WORKFLOWS:
        return
    cards = []
    for wid, w in WORKFLOWS.items():
        cards.append('<article class="card"><h3><a href="workflows/%s.html">%s</a></h3><p class="sum">%s</p>'
                     '<div class="tags"><span class="tag">%s</span><span class="tag">%s</span><span class="tag">%d steps</span></div></article>'
                     % (wid, e(w["title"]), e(w["lead"]), e(w["level"]), e(w["evidence"]), len(w["steps"])))
    body = ('<div class="wrap"><div class="page-head"><h1>Case workflows</h1>'
            '<p class="lead">Start from the question you need to answer. Each workflow gives the steps in order, the free tool for each step, '
            'where the evidence is stored, and a public practice image to try it on.</p></div>'
            '<section class="section" style="padding-top:8px"><div class="grid">%s</div></section></div>' % "".join(cards))
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
                '<div class="label y">Case workflow</div><h1>%s</h1><p class="lead">%s</p>%s</div>'
                '<div class="tool-layout"><div class="tool-main">%s%s</div><aside class="tool-side" aria-label="Workflow facts">%s</aside></div></div>'
                % (e(w.get("short", w["title"])), e(w["title"]), e(w["lead"]), draft_banner(w), nav, "".join(main), "".join(side)))
        page("workflows/%s.html" % wid, w["title"], w["lead"], body, "workflows")


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
    def rows(items):
        out = []
        for it in items:
            links = ", ".join('<a href="tools/%s.html">%s</a>' % (i, e(TOOL[i]["name"])) for i in it.get("tool_ids", []) if i in TOOL)
            out.append('<div class="card row-card"><div class="v"><div class="t">%s <span>%s</span> %s</div>'
                       '<p class="sum">%s</p><div class="src-line">Source: <a href="%s" rel="noopener">%s</a>, checked %s</div>'
                       '%s</div></div>' % (e(it["product"]), e(it["relation"]), e(it["open_source"]), e(it["statement"]),
                                           e(it["source_url"]), e(it["source_label"]), fmt_date(it.get("checked")),
                                           ('<p class="sum" style="font-size:13px">In this directory: %s</p>' % links) if links else ""))
        return "".join(out)
    body = ('<div class="wrap"><div class="page-head"><h1>Inside commercial tools</h1>'
            '<p class="lead">Documented cases where a commercial product runs, includes or accepts open-source tools and rule formats. Learning the open tool means you already understand what the paid feature does.</p>'
            '<p class="note">Each entry repeats only what the vendor\'s own page says and links to it. Products change, so follow the source link for the current position. '
            'Nothing here suggests a vendor endorses this site.</p></div>'
            '<section class="section" style="padding-top:8px"><div style="display:flex;flex-direction:column;gap:12px">%s</div></section>'
            '<section class="section"><div class="section-head"><h2>Open source builds on open source</h2></div>'
            '<div style="display:flex;flex-direction:column;gap:12px">%s</div></section></div>'
            % (rows(INTEG["integrations"]), rows(INTEG.get("open_on_open", []))))
    page("inside.html", "Inside commercial tools",
         "Documented examples of commercial digital forensics products that run or accept open-source tools, each with its vendor source.", body, "inside")


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
    for it in INTEG["integrations"] + INTEG.get("open_on_open", []):
        if not it.get("source_url"):
            sys.exit("Integration entry for %s has no source_url. Entries without a source are not published." % it.get("product"))
    OUT.mkdir(exist_ok=True)
    assets = OUT / "assets"
    shutil.copytree(ROOT / "static", assets, dirs_exist_ok=True)
    build_home(); build_tools_index(); build_categories(); build_tool_pages()
    build_workflows(); build_alternatives(); build_inside(); build_nist(); build_practice(); build_learn(); build_about(); build_404()
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
