# Digital Forensic Tools

The source of https://digitalforensictool.org. The site name, domain and contact details are set in one file, `data/site.json`.

A free, category-wise directory of open-source and free digital forensics tools for bachelor's and master's students. Each tool page says what the tool does, who built it, its licence, where to download it, and which commercial product does a similar job.

## See the site on your computer

1. Open the `site` folder.
2. Double-click `index.html`.

The `site` folder is produced by the build. If it is missing or out of date, run:

```
python scripts/build.py
```

Python 3.9 or newer is the only requirement. Nothing else needs installing.

## Folder map

| Folder | What it holds |
| --- | --- |
| `data/` | Everything the site shows. Edit these files to change the content. |
| `scripts/` | `build.py` makes the site, `refresh.py` updates versions and download links, `check.py` tests the result. |
| `static/` | Stylesheet, script and fonts. |
| `tests/` | Tests for the download-file picker. |
| `.github/` | The daily update and publish workflow, and the "Suggest a tool" and "Report a problem" forms. |
| `site/` | The built website. Generated, not edited by hand, and not stored in the repository. |

## The data files

| File | Purpose |
| --- | --- |
| `site.json` | Site name, domain, repository, maintainer, contact email, featured tools. |
| `categories.json` | The categories and their introductions. |
| `nist-functionalities.json` | Maps the functionality names used by the NIST tool catalog to the categories here. |
| `tools.json` | One entry per tool. |
| `commercial-integrations.json` | Cases where a commercial product uses an open-source tool. Every entry must have a vendor source link or the build stops. |
| `practice.json` | Free practice evidence. |
| `learn-sources.json` | Recommended learning sites. |
| `releases.json` | Written by `refresh.py`. Versions, download links, stars and activity. Do not edit by hand. |
| `review.md` | Written by `refresh.py`. Things a person should look at, such as a moved repository. |

### Adding a tool

Add an entry to `data/tools.json`:

```json
{
  "id": "example-tool",
  "name": "Example Tool",
  "developer": "Person or organisation",
  "repo": "owner/repository",
  "type": "open-source",
  "categories": ["memory"],
  "interface": "CLI",
  "level": "intermediate",
  "platforms": ["Windows", "Linux"],
  "summary": "One or two sentences in our own words.",
  "similar_to": ["Commercial Product"],
  "install": "pip install example-tool"
}
```

- Use `"repo"` for a GitHub project, or `"url"` for any other official website. Never both.
- `type` is `open-source`, `source-published` or `free-closed`.
- `level` is `beginner`, `intermediate` or `advanced`.
- `similar_to` and `install` are optional.

## How updates work

`.github/workflows/update.yml` runs every day and on every change:

1. Runs the tests.
2. `refresh.py` reads each tool's latest release from GitHub and picks one clear download per operating system. If the choice is not clear it picks none, and the page links to the release page instead.
3. `build.py` rebuilds the site.
4. `check.py` stops the publish if there is a broken internal link or wording the site must not use.
5. The site is published to GitHub Pages.

Download links are only ever taken from the repository recorded in `tools.json`. If a repository moves or disappears, its download buttons switch off and the tool is listed in `data/review.md`.

## Rules the site follows

1. Link to the developer's own download. Never host tool files.
2. Say "does a similar job to", never "equivalent to".
3. Publish a commercial-integration claim only with the vendor's own page as the source.
4. Write every description in our own words.
5. Credit the developer and show the licence on every tool page.
6. State clearly that the site is independent and not affiliated with any vendor.
7. No cookies, no analytics, nothing loaded from third-party servers.

## Fonts

Inter, Space Grotesk and JetBrains Mono are included under the SIL Open Font License. The licence texts are in `static/fonts/`.
