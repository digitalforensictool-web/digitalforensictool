#!/usr/bin/env python3
"""Refreshes data/releases.json from public GitHub data.

For every tool in data/tools.json that has a "repo", this reads:
  - the repository record (stars, licence, archived flag, last code update)
  - the latest stable release and its downloadable files

It then picks at most one clear download per operating system. When the choice
is not clear it picks nothing, and the site shows a link to the release page.

No tool files are downloaded or stored. Only links and facts are recorded.

Uses only the Python standard library. A token is optional but raises the
request limit: set GITHUB_TOKEN (GitHub Actions provides one automatically).

    python scripts/refresh.py            # refresh everything
    python scripts/refresh.py --limit 5  # refresh only the 5 stalest tools
    python scripts/refresh.py --only autopsy,hayabusa
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""

SKIP_SUFFIXES = (
    ".sha256", ".sha256sum", ".sha512", ".sha1", ".md5", ".sig", ".asc", ".pem", ".minisig", ".crt",
    ".txt", ".json", ".yml", ".yaml", ".xml", ".sbom", ".spdx", ".jsonl", ".blockmap", ".pdb", ".md",
    ".pdf", ".apk", ".aab", ".ipa", ".whl", ".jar", ".nupkg", ".vsix",
)
SKIP_TOKENS = {"symbols", "debug", "dbg", "debuginfo", "source", "sources", "src", "sdk", "docs", "doc", "test", "tests",
               "plugin", "plugins", "addon", "addons", "extras", "models", "zsync"}
OS_EXT = {
    "windows": (".exe", ".msi", ".msix"),
    "macos": (".dmg", ".pkg"),
    "linux": (".appimage", ".deb", ".rpm", ".snap", ".flatpak"),
}
OS_TOKENS = {
    "windows": {"windows", "win", "win64", "win32", "win10", "win11", "mingw", "mingw64", "msvc", "x64win"},
    "macos": {"macos", "mac", "darwin", "osx", "macosx", "apple"},
    "linux": {"linux", "lin", "ubuntu", "debian", "manylinux", "musl", "appimage"},
}
ARCHIVE_EXT = (".zip", ".7z", ".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".tar.zst", ".gz", ".xz")
GOOD_ARCH = {"x64", "amd64", "win64", "64bit", "universal", "universal2"}
OTHER_ARCH = {"arm", "armv7", "armv6", "armhf", "i386", "i686", "x86", "win32", "32bit", "ia32", "riscv64", "ppc64le", "s390x", "mips"}
ARM64 = {"arm64", "aarch64"}


def tokens(name):
    low = name.lower().replace("x86_64", "amd64").replace("x86-64", "amd64")
    return set(t for t in re.split(r"[^a-z0-9]+", low) if t)


def has_unknown_extension(low):
    """True when the name ends in a short file extension we do not recognise, such as .bin or .sh."""
    if "." not in low:
        return False
    suffix = low.rsplit(".", 1)[1]
    return len(suffix) <= 5 and suffix.isalpha()


def detect_os(name):
    """Returns 'windows', 'macos', 'linux', or None when unknown or ambiguous."""
    low = name.lower()
    if low.endswith(SKIP_SUFFIXES):
        return None
    toks = tokens(low)
    if toks & SKIP_TOKENS:
        return None
    found = set()
    for os_name, exts in OS_EXT.items():
        if low.endswith(exts):
            found.add(os_name)
    for os_name, words in OS_TOKENS.items():
        if toks & words:
            found.add(os_name)
    if len(found) != 1:
        return None
    os_name = found.pop()
    if not (low.endswith(OS_EXT[os_name]) or low.endswith(ARCHIVE_EXT)) and has_unknown_extension(low):
        return None
    return os_name


def score(name, os_name):
    low = name.lower()
    toks = tokens(low)
    s = 0.0
    if low.endswith(OS_EXT[os_name]):
        s += 3
    elif low.endswith(ARCHIVE_EXT):
        s += 2
    else:
        s += 1
    if os_name == "linux" and low.endswith(".appimage"):
        s += 0.5
    if toks & {"setup", "installer", "install"}:
        s += 0.5
    if toks & GOOD_ARCH:
        s += 1
    if toks & OTHER_ARCH:
        s -= 1.5
    if toks & ARM64:
        s += 0.5 if os_name == "macos" else -1
    if "musl" in toks:
        s -= 0.25
    return s


def classify_assets(assets, prefer=None):
    """Picks one clear file per operating system. Ties mean no pick."""
    picked = {}
    buckets = {"windows": [], "macos": [], "linux": []}
    for a in assets:
        name = a.get("name") or ""
        url = a.get("browser_download_url") or ""
        if not name or not url.startswith("https://github.com/"):
            continue
        os_name = detect_os(name)
        if os_name:
            buckets[os_name].append((score(name, os_name), name, url, a.get("size") or 0))
    # An explicit "asset_prefer" pattern in tools.json wins over the automatic guess. It may also
    # rescue a file whose name carries two system words (for example mac_apt-windows-x64.exe).
    for os_name, pat in (prefer or {}).items():
        if os_name not in buckets:
            continue
        found = []
        for a in assets:
            name = a.get("name") or ""
            url = a.get("browser_download_url") or ""
            if name and url.startswith("https://github.com/") and re.search(pat, name, re.I):
                found.append((score(name, os_name), name, url, a.get("size") or 0))
        if found:
            buckets[os_name] = found
    for os_name, cands in buckets.items():
        if not cands:
            continue
        cands.sort(key=lambda c: (-c[0], c[1]))
        top = [c for c in cands if c[0] == cands[0][0]]
        if len(top) > 1:
            # Several files look equally good. Accept one only if it is the plain
            # variant: every word in its name also appears in each of the others.
            plain = [c for c in top if all(tokens(c[1]) < tokens(o[1]) for o in top if o is not c)]
            if len(plain) != 1:
                continue
            top = plain
        _, name, url, size = top[0]
        picked[os_name] = {"name": name, "url": url, "size": size}
    return picked


class RateLimited(Exception):
    pass


def api(path):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "tool-directory-refresh"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request(API + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code in (403, 429) and err.headers.get("x-ratelimit-remaining") == "0":
            raise RateLimited()
        return err.code, None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, None


def refresh_tool(tool, now):
    repo = tool["repo"]
    status, d = api("/repos/" + repo)
    if status == 404:
        return {"repo": repo, "missing": True, "checked": now}
    if status != 200 or not d:
        return None
    entry = {
        "repo": repo,
        "full_name": d.get("full_name"),
        "repo_mismatch": (d.get("full_name") or "").lower() != repo.lower(),
        "stars": d.get("stargazers_count"),
        "license": (d.get("license") or {}).get("spdx_id"),
        "archived": bool(d.get("archived")),
        "fork": bool(d.get("fork")),
        "pushed_at": d.get("pushed_at"),
        "checked": now,
        "release": None,
    }
    if entry["repo_mismatch"]:
        return entry
    status, rel = api("/repos/%s/releases/latest" % repo)
    if status == 200 and rel and not rel.get("draft") and not rel.get("prerelease"):
        entry["release"] = {
            "tag": rel.get("tag_name"),
            "name": rel.get("name"),
            "published_at": rel.get("published_at"),
            "url": rel.get("html_url"),
            "assets": classify_assets(rel.get("assets") or [], tool.get("asset_prefer")),
        }
    elif status not in (200, 404):
        return None
    return entry


# Hosts that refuse scripted requests (403) or time out for scripts but work in a browser.
KNOWN_BLOCKED_HOSTS = {"www.kroll.com", "cellebrite.com", "www.cellebrite.com", "sourceforge.net", "guymager.sourceforge.io",
                       "foremost.sourceforge.net", "steghide.sourceforge.net", "eraser.heidi.ie", "support.passware.com",
                       "www.cisco.com", "www.mythicsoft.com"}


def check_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; link-check)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as err:
        return err.code
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=0, help="refresh only this many tools, stalest first")
    ap.add_argument("--only", default="", help="comma-separated tool ids to refresh, for example autopsy,hayabusa")
    ap.add_argument("--no-links", action="store_true", help="skip checking non-GitHub websites")
    args = ap.parse_args()

    tools = json.load(open(DATA / "tools.json", encoding="utf-8"))
    path = DATA / "releases.json"
    old = json.load(open(path, encoding="utf-8")) if path.exists() else {}
    entries = dict(old.get("tools") or {})
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    ids = {t["id"] for t in tools}
    for stale in [k for k in entries if k not in ids]:
        del entries[stale]

    gh_tools = [t for t in tools if t.get("repo")]
    gh_tools.sort(key=lambda t: (entries.get(t["id"]) or {}).get("checked") or "")
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    if only:
        unknown = only - ids
        if unknown:
            sys.exit("Unknown tool ids: " + ", ".join(sorted(unknown)))
        gh_tools = [t for t in gh_tools if t["id"] in only]
    if args.limit:
        gh_tools = gh_tools[:args.limit]

    done = failed = 0
    limited = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(refresh_tool, t, now): t for t in gh_tools}
        for fut in concurrent.futures.as_completed(futures):
            t = futures[fut]
            try:
                entry = fut.result()
            except RateLimited:
                limited = True
                continue
            if entry is None:
                failed += 1
                continue
            entries[t["id"]] = entry
            done += 1

    review = []
    for t in tools:
        en = entries.get(t["id"])
        if not en:
            continue
        if en.get("missing"):
            review.append((t["id"], "Repository not found: %s" % t["repo"]))
        elif en.get("repo_mismatch"):
            review.append((t["id"], "Repository moved from %s to %s. Download buttons are off until tools.json is updated by a person." % (t["repo"], en.get("full_name"))))
        else:
            if en.get("archived"):
                review.append((t["id"], "Project is archived by its developer."))
            if en.get("fork"):
                review.append((t["id"], "Repository is a fork. Confirm it is the official one."))
            if t["type"] == "open-source" and not t.get("licence") and en.get("license") in (None, "NOASSERTION"):
                review.append((t["id"], "GitHub does not report a recognised licence. Confirm the licence by hand and add a \"licence\" field in tools.json."))

    if not args.no_links and not args.limit and not only:
        web = [t for t in tools if t.get("url")]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for t, status in zip(web, pool.map(lambda x: check_url(x["url"]), web)):
                if status in (404, 410):
                    review.append((t["id"], "Website returned %d: %s" % (status, t["url"])))
                elif status == 0 and urllib.parse.urlparse(t["url"]).netloc.lower() in KNOWN_BLOCKED_HOSTS:
                    continue
                elif status == 0:
                    review.append((t["id"], "Website did not respond (may be temporary): %s" % t["url"]))

    out = {"generated": now, "tools": {k: entries[k] for k in sorted(entries)}}
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)

    lines = ["# Review list", "", "Generated %s. Items here need a person to look at them." % now, ""]
    lines += ["- **%s**: %s" % item for item in sorted(review)] or ["Nothing needs review."]
    (DATA / "review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    with_release = sum(1 for en in entries.values() if en.get("release"))
    with_buttons = sum(1 for en in entries.values() if (en.get("release") or {}).get("assets"))
    print("Refreshed %d of %d GitHub tools (%d failed and kept their old data)." % (done, len(gh_tools), failed))
    print("Total with a release: %d. With direct download buttons: %d. Review items: %d." % (with_release, with_buttons, len(review)))
    if limited:
        print("GitHub's request limit was reached. Run again later, or set GITHUB_TOKEN for a higher limit.")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
