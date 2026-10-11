# Group website generator

A pure-HTML website built from JSON data files with a small Python script. No server-side code is needed on the web host – just upload the `_site/` folder.

## Folder layout

```
data/            ← everything you edit: the content of the site
  site.json        general settings: group name, base URL, navigation, addresses, rsync target
  people.json      group members and alumni
  publications.json
  news.json
  research.json    research directions (each gets its own page)
  teaching.json, positions.json, funding.json
assets/          ← your files (photos, PDFs, figures); copied 1:1 into the site
  people/  publications/  news/  research/  theses/  cvs/  funding/
templates/       ← Jinja2 HTML templates (look & structure)
static/css/style.css  ← the style sheet (colours etc. are variables at the top)
build.py         ← builds the site into _site/
deploy.sh        ← builds and uploads with rsync
admin/app.py     ← local web form for adding members and papers
_site/           ← the generated website (never edit by hand – it is overwritten)
```

## Everyday use

```bash
python3 build.py --serve      # build and preview at http://localhost:8000
./deploy.sh                   # build and rsync to the server set in data/site.json
python3 admin/app.py          # form-based interface to add members / papers (opens browser)
```

Requirements: Python 3, `jinja2`, `Pillow` (`python3 -m pip install --user jinja2 Pillow`).

## Editing content

* All links inside the site are relative, so it works in any sub-folder of your web server.
  `base_url` in `site.json` is only used for the canonical URL in the page header.
* **Research topics** are the glue: members (`projects`), publications (`topics`), news (`topics`)
  and open positions (`project`) refer to research topics by their `id`. Each topic page automatically
  lists its team, publications and news. The build aborts with a clear message if an id is misspelled.
* **People** are grouped by `category` (order defined in `site.json → people_categories`).
  Move someone to `alumni` by cutting the entry from `members` and adding `{name, role, projects, left, now}`.
* **Publications**: `type` is `journal`, `preprint` or `other`; `highlight: true` shows the paper on the homepage.
* **Images**: paths are relative to the project folder, e.g. `assets/people/jane-doe.jpg`.
  Expected aspect ratios: portraits 3:4, publication images 1:1, news/research teasers 3:2, hero 16:6.
  Missing images fall back to grey placeholders.

## Changing the look

Edit `static/css/style.css` – the colours, fonts and widths are CSS variables at the top of the file.
Page structure lives in `templates/`; `base.html` holds header/nav/footer, `_macros.html` the reusable
cards (person, publication, news item).
