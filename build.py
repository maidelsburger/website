#!/usr/bin/env python3
"""Build the static website from data/*.json + templates/ into the output directory.

Usage:  python3 build.py            # build
        python3 build.py --serve    # build and serve locally at http://localhost:8000
"""
import json, shutil, sys, datetime, http.server, functools
from pathlib import Path
from collections import defaultdict
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent
DATA, TEMPLATES = ROOT / "data", ROOT / "templates"


def load(name):
    with open(DATA / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def pretty_date(s):
    try:
        return datetime.date.fromisoformat(s).strftime("%B %-d, %Y")
    except Exception:
        return s


def supsub(text):
    """Render ^{...} as superscript and _{...} as subscript, escaping everything else."""
    import re
    from markupsafe import Markup, escape
    t = str(escape(text))
    t = re.sub(r"\^\{([^}]+)\}", r"<sup>\1</sup>", t)
    t = re.sub(r"_\{([^}]+)\}", r"<sub>\1</sub>", t)
    t = re.sub(r"\*\{([^}]+)\}", r"<em>\1</em>", t)
    return Markup(t)


def obfuscate(email):
    """Display form of an email: replaces @ with (at) to slow down scrapers."""
    return email.replace("@", " (at) ")


def check_assets(obj, where):
    """Blank out references to asset files that don't exist yet, so templates fall back to placeholders."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v.startswith("assets/") and not (ROOT / v).exists():
                print(f"  note: {where}: missing file '{v}' (showing placeholder)")
                obj[k] = ""
            else:
                check_assets(v, where)
    elif isinstance(obj, list):
        for v in obj:
            check_assets(v, where)


def build():
    site = load("site")
    research = load("research")
    people = load("people")
    pubs = load("publications")
    news = load("news")
    teaching, positions, funding = load("teaching"), load("positions"), load("funding")

    for name, obj in [("site", site), ("research", research), ("people", people),
                      ("publications", pubs), ("news", news), ("funding", funding)]:
        check_assets(obj, name)

    research_by_id = {r["id"]: r for r in research}
    members = people["members"]
    alumni = people.get("alumni", [])
    people_by_id = {m["id"]: m for m in members}

    # Validate references early so typos in JSON show up as clear errors.
    for m in members + alumni:
        for t in m.get("projects", []):
            assert t in research_by_id, f"{m['name']}: unknown project '{t}'"
    for p in pubs:
        for t in p.get("topics", []):
            assert t in research_by_id, f"publication {p['id']}: unknown topic '{t}'"
    for n in news:
        for t in n.get("topics", []):
            assert t in research_by_id, f"news {n['id']}: unknown topic '{t}'"

    news.sort(key=lambda n: n["date"], reverse=True)
    pubs.sort(key=lambda p: (p["year"], p.get("id")), reverse=True)

    heroes = site.get("hero_images") or ([site["hero_image"]] if site.get("hero_image") else [])
    site["hero_images"] = [h for h in heroes if (ROOT / h).exists()]

    out = ROOT / site.get("output_dir", "_site")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    shutil.copytree(ROOT / "static", out / "static")
    if (ROOT / "assets").exists():
        shutil.copytree(ROOT / "assets", out / "assets", ignore=shutil.ignore_patterns(".*"))

    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    env.filters["pretty_date"] = pretty_date
    env.filters["obfuscate"] = obfuscate
    env.filters["supsub"] = supsub
    common = dict(site=site, research=research, research_by_id=research_by_id,
                  people_by_id=people_by_id, year=datetime.date.today().year)

    def render(template, path, page_id, **ctx):
        depth = path.count("/")
        rel = "../" * depth
        html = env.get_template(template).render(rel=rel, page_path=path, page_id=page_id, **common, **ctx)
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")

    # Home
    render("index.html", "index.html", "home", news=news, highlights=[p for p in pubs if p.get("highlight")])

    # Research
    render("research.html", "research.html", "research")
    for r in research:
        render("research_topic.html", f"research/{r['id']}.html", "research", r=r,
               topic_people=[m for m in members if r["id"] in m.get("projects", [])],
               topic_alumni=[a for a in alumni if r["id"] in a.get("projects", [])],
               topic_pubs=[p for p in pubs if r["id"] in p.get("topics", [])],
               topic_news=[n for n in news if r["id"] in n.get("topics", [])])

    # News
    by_year = defaultdict(list)
    for n in news:
        by_year[n["date"][:4]].append(n)
    render("news.html", "news.html", "news", news_by_year=sorted(by_year.items(), reverse=True))
    for i, n in enumerate(news):
        render("news_item.html", f"news/{n['id']}.html", "news", n=n,
               prev=news[i + 1] if i + 1 < len(news) else None, next=news[i - 1] if i > 0 else None)

    # Group
    cats = site["people_categories"]
    grouped = [(c, [m for m in members if m["category"] == c]) for c in cats]
    grouped = [(c, ms) for c, ms in grouped if ms]
    unknown = [m["name"] for m in members if m["category"] not in cats]
    assert not unknown, f"members with unknown category: {unknown}"
    render("group.html", "group.html", "group", grouped=grouped, alumni=alumni)

    # Publications
    preprints = [p for p in pubs if p.get("type") == "preprint"]
    pby = defaultdict(list)
    for p in pubs:
        if p.get("type") != "preprint":
            pby[p["year"]].append(p)
    render("publications.html", "publications.html", "publications",
           preprints=preprints, pubs_by_year=sorted(pby.items(), reverse=True))

    render("teaching.html", "teaching.html", "teaching", teaching=teaching)
    render("positions.html", "positions.html", "positions", positions=positions)
    render("contact.html", "contact.html", "contact")
    render("funding.html", "funding.html", "funding", funding=funding)
    for fp in funding["projects"]:
        if fp.get("slug") and fp.get("paragraphs"):
            render("funding_project.html", f"funding/{fp['slug']}.html", "funding", p=fp)
    render("simple.html", "imprint.html", "imprint", title="Imprint",
           paragraphs=["Responsible for content: " + site["pi"]["name"] + ".", "Please replace this text with the legally required imprint of your institution."])
    render("simple.html", "privacy.html", "privacy", title="Privacy policy",
           paragraphs=["This website does not use cookies or tracking. Please replace with your institution's privacy policy."])

    n_pages = sum(1 for _ in out.rglob("*.html"))
    print(f"Built {n_pages} pages into {out.relative_to(ROOT)}/")
    return out


if __name__ == "__main__":
    out = build()
    if "--serve" in sys.argv:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
        print("Serving at http://localhost:8000  (Ctrl-C to stop)")
        http.server.ThreadingHTTPServer(("localhost", 8000), handler).serve_forever()
