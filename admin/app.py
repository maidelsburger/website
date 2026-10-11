#!/usr/bin/env python3
"""Local admin interface: add group members and publications via a browser form.

Run:  python3 admin/app.py      then open http://localhost:8080
Nothing is uploaded anywhere; it only edits data/*.json, saves files into assets/ and rebuilds _site/.
"""
import json, base64, io, re, sys, unicodedata, datetime, subprocess, webbrowser
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PORT = 8080

PORTRAIT_SIZE = (450, 600)     # 3:4, matches .portrait in style.css
PUB_IMAGE_SIZE = (600, 600)    # 1:1, matches .pub-img
NEWS_IMAGE_SIZE = (900, 600)   # 3:2, matches .thumb


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def save(name, obj):
    (DATA / f"{name}.json").write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def save_image(data_url, target: Path, size):
    """data_url: already-cropped PNG from the browser canvas. Resized to `size` and saved as JPEG."""
    if not data_url:
        return ""
    raw = base64.b64decode(data_url.split(",", 1)[1])
    im = Image.open(io.BytesIO(raw)).convert("RGB").resize(size, Image.LANCZOS)
    target.parent.mkdir(parents=True, exist_ok=True)
    im.save(target, "JPEG", quality=88, optimize=True)
    return str(target.relative_to(ROOT))


def save_file(data_url, target: Path):
    if not data_url:
        return ""
    raw = base64.b64decode(data_url.split(",", 1)[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return str(target.relative_to(ROOT))


ROLE_TO_CATEGORY = {
    "Principal Investigator": "Research Group Leader",
    "Senior Scientist": "Senior Scientists", "PostDoc": "PostDocs", "PhD Student": "PhD Students",
    "Master Student": "Master Students", "Bachelor Student": "Bachelor Students",
    "Student Assistant": "Student Assistants", "Intern": "Master Students", "Guest": "Guests",
    "Engineer": "Engineers", "Technician": "Technicians",
    "Project Coordinator": "Project Coordinator", "Assistant": "Team Assistant",
}
ROLE_ARTICLE = {"PostDoc": "a postdoc", "PhD Student": "a doctoral student", "Master Student": "a master student",
                "Bachelor Student": "a bachelor student", "Student Assistant": "a student assistant",
                "Senior Scientist": "a senior scientist", "Intern": "an intern", "Guest": "a guest researcher"}


def add_member(f):
    people = load("people")
    research = {r["id"]: r for r in load("research")}
    pid = slug(f["name"])
    if any(m["id"] == pid for m in people["members"]):
        raise ValueError(f"A member with id '{pid}' already exists.")
    member = {
        "id": pid, "name": f["name"].strip(), "degree": f.get("degree", "").strip(),
        "category": ROLE_TO_CATEGORY[f["role"]], "role": f["role"],
        "affiliation": f.get("affiliation", ""), "email": f.get("email", "").strip(),
        "phone": f.get("phone", "").strip(), "office": f.get("office", "").strip(),
        "lab_phone": f.get("lab_phone", "").strip(), "lab": f.get("lab", "").strip(),
        "projects": f.get("projects", []),
        "photo": save_image(f.get("photo"), ROOT / "assets/people" / f"{pid}.jpg", PORTRAIT_SIZE),
        "education": f.get("education", "").strip(), "origin": f.get("origin", "").strip(),
        "joined": f.get("joined") or datetime.date.today().isoformat(),
        "thesis_pdf": save_file(f.get("thesis_pdf"), ROOT / "assets/theses" / f"{pid}-thesis.pdf"),
        "cv_pdf": save_file(f.get("cv_pdf"), ROOT / "assets/cvs" / f"{pid}-cv.pdf"),
        "google_scholar": f.get("google_scholar", "").strip(), "orcid": f.get("orcid", "").strip(),
        "website": f.get("website", "").strip(), "bio": f.get("bio", "").strip(),
    }
    people["members"].append(member)
    save("people", people)

    if f.get("add_news", True):
        news = load("news")
        proj = [research[t]["title"] for t in member["projects"]]
        exp = (" on the " + " and ".join(proj) + " experiment") if proj else ""
        origin = f" {member['name']} joins us from {member['origin']}." if member["origin"] else ""
        role_txt = ROLE_ARTICLE.get(member["role"], "a " + member["role"].lower())
        date = member["joined"]
        item = {
            "id": f"{date}-welcome-{pid}", "date": date,
            "title": f"Welcome {member['name']}!",
            "summary": f"{member['name']} joins our group{exp} as {role_txt}.",
            "body": [f"We are happy to welcome {member['name']}, who joins our group{exp} as {role_txt}.{origin}"],
            "image": member["photo"], "topics": member["projects"], "people": [pid], "link": "",
        }
        news.append(item)
        save("news", news)
    return member


def add_paper(f):
    pubs = load("publications")
    first_author = f["authors"].split(",")[0].strip().split()[-1] if f.get("authors") else "paper"
    pid = f.get("id") or slug(f"{first_author} {f['year']} {' '.join(f['title'].split()[:2])}")
    if any(p["id"] == pid for p in pubs):
        raise ValueError(f"A publication with id '{pid}' already exists.")
    pub = {
        "id": pid, "year": int(f["year"]), "title": f["title"].strip(), "authors": f["authors"].strip(),
        "journal": f.get("journal", "").strip(), "volume": f.get("volume", "").strip(), "pages": f.get("pages", "").strip(),
        "doi": f.get("doi", "").strip().replace("https://doi.org/", ""), "arxiv": f.get("arxiv", "").strip().replace("arXiv:", ""),
        "url": f.get("url", "").strip(),
        "pdf": save_file(f.get("pdf"), ROOT / "assets/publications" / f"{pid}.pdf"),
        "topics": f.get("topics", []),
        "image": save_image(f.get("image"), ROOT / "assets/publications" / f"{pid}.jpg", PUB_IMAGE_SIZE),
        "highlight": bool(f.get("highlight")), "type": f.get("type", "journal"),
    }
    pubs.append(pub)
    save("publications", pubs)
    if f.get("add_news"):
        news = load("news")
        date = datetime.date.today().isoformat()
        news.append({
            "id": f"{date}-paper-{pid}", "date": date,
            "title": f"New paper: {pub['title']}",
            "summary": f"Our paper \"{pub['title']}\" is now " + ("published in " + pub["journal"] if pub["journal"] else "online") + ".",
            "body": [f.get("news_text") or f"Our paper \"{pub['title']}\" by {pub['authors']} is now " + ("published in " + pub["journal"] if pub["journal"] else "available on arXiv") + "."],
            "image": save_image(f.get("image"), ROOT / "assets/news" / f"{pid}.jpg", NEWS_IMAGE_SIZE) if f.get("image") else "",
            "topics": pub["topics"], "people": [], "link": pub["url"] or (f"https://doi.org/{pub['doi']}" if pub["doi"] else ""),
        })
        save("news", news)
    return pub


def rebuild():
    r = subprocess.run([sys.executable, str(ROOT / "build.py")], capture_output=True, text=True)
    return r.stdout + r.stderr


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        body = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/config.json":
            self._send(json.dumps({
                "research": [{"id": r["id"], "title": r["title"]} for r in load("research")],
                "roles": list(ROLE_TO_CATEGORY), "affiliations": list(load("site")["affiliations"]),
            }), "application/json")
        else:
            self._send((Path(__file__).parent / "admin.html").read_text(encoding="utf-8"))

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        form = json.loads(self.rfile.read(n))
        try:
            if self.path == "/add-member":
                res = add_member(form)
            elif self.path == "/add-paper":
                res = add_paper(form)
            else:
                raise ValueError("unknown action")
            log = rebuild()
            self._send(json.dumps({"ok": True, "id": res["id"], "log": log}), "application/json")
        except Exception as e:
            self._send(json.dumps({"ok": False, "error": str(e)}), "application/json", 400)


if __name__ == "__main__":
    print(f"Admin interface: http://localhost:{PORT}   (Ctrl-C to stop)")
    webbrowser.open(f"http://localhost:{PORT}")
    ThreadingHTTPServer(("localhost", PORT), Handler).serve_forever()
