"""Quellen für die Mediathek."""
import json
import random
import re
import urllib.parse
import urllib.request
from pathlib import Path

from .library import CACHE, MEDIA

UA = "OpenWallpaper/0.5 (open source wallpaper app)"
MAX_ORIGINAL = 300 * 1048576
PER_PAGE = 24


class Results(list):
    total = None


def _get(url, timeout=30, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def _json(url, **kw):
    try:
        with _get(url, **kw) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RuntimeError("Zu viele Anfragen, bitte kurz warten") from e
        if e.code in (401, 403):
            raise RuntimeError("Zugriff abgelehnt, bitte den API-Schlüssel prüfen") from e
        raise RuntimeError(f"Server antwortet mit Fehler {e.code}") from e
    except urllib.error.URLError as e:
        raise RuntimeError("Keine Verbindung") from e


def _strip(html):
    return re.sub(r"<[^>]+>", "", html or "").strip()


def _stream(url, dest, progress):
    tmp = dest.with_suffix(dest.suffix + ".part")
    with _get(url, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 18):
            f.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)
    tmp.replace(dest)
    return dest


DE_EN = {
    "natur": "nature", "wald": "forest", "berg": "mountain", "berge": "mountains",
    "meer": "sea", "ozean": "ocean", "strand": "beach", "himmel": "sky",
    "wolke": "cloud", "wolken": "clouds", "sonnenuntergang": "sunset",
    "sonnenaufgang": "sunrise", "nacht": "night", "stadt": "city", "städte": "cities",
    "weltraum": "space", "all": "space", "stern": "star", "sterne": "stars",
    "mond": "moon", "sonne": "sun", "wasser": "water", "feuer": "fire",
    "schnee": "snow", "regen": "rain", "nebel": "fog", "blume": "flower",
    "blumen": "flowers", "tier": "animal", "tiere": "animals", "katze": "cat",
    "katzen": "cats", "hund": "dog", "hunde": "dogs", "vogel": "bird",
    "pferd": "horse", "wolf": "wolf", "fuchs": "fox", "auto": "car", "autos": "cars",
    "spiel": "game", "spiele": "games", "dunkel": "dark", "hell": "bright",
    "abstrakt": "abstract", "landschaft": "landscape",
    "herbst": "autumn", "frühling": "spring", "sommer": "summer", "see": "lake",
    "fluss": "river", "wasserfall": "waterfall", "wüste": "desert", "insel": "island",
    "brücke": "bridge", "straße": "street", "haus": "house", "architektur": "architecture",
    "technik": "technology", "roboter": "robot", "drache": "dragon",
    "mädchen": "girl", "junge": "boy", "frau": "woman", "mann": "man",
    "schwarz": "black", "weiß": "white", "rot": "red", "blau": "blue",
    "grün": "green", "gelb": "yellow", "lila": "purple", "rosa": "pink",
    "gebirge": "mountains", "tal": "valley", "hügel": "hills", "polarlicht": "aurora",
    "galaxie": "galaxy", "regenbogen": "rainbow",
    "gewitter": "storm", "sturm": "storm", "winter": "winter", "kunst": "art",
    "ruhig": "calm",
    "mensch": "people", "menschen": "people", "person": "people", "gesicht": "face",
    "tod": "skull", "totenkopf": "skull", "krieger": "warrior", "ritter": "knight",
    "magie": "magic", "zauberer": "wizard", "elf": "elf", "engel": "angel",
    "teufel": "demon", "dämon": "demon", "schiff": "ship", "flugzeug": "aircraft",
    "zug": "train", "motorrad": "motorcycle", "musik": "music", "essen": "food",
    "kaffee": "coffee", "buch": "books", "bücher": "books", "tür": "door",
    "fenster": "window", "spiegel": "mirror", "licht": "light", "schatten": "shadow",
    "farbe": "colorful", "bunt": "colorful", "gold": "gold", "silber": "silver",
}
_SUFFIXES = ("er", "e", "es", "en", "em", "n", "s")
_TOKEN = re.compile(r'"[^"]*"|\S+')


STOPWORDS = {"am", "im", "in", "an", "auf", "bei", "mit", "und", "der", "die", "das",
             "dem", "den", "von", "vom", "zu", "zum", "zur", "ein", "eine", "einer",
             "für", "über", "unter", "aus", "nach", "vor"}


def _lookup(word):
    w = word.lower()
    if w in DE_EN:
        return DE_EN[w]
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            stem = w[:-len(suf)]
            for cand in (stem, stem[:-1] + "e" + stem[-1:]):
                if cand in DE_EN:
                    return DE_EN[cand]
    for i in range(3, len(w) - 2):
        a, b = DE_EN.get(w[:i]), _lookup_simple(w[i:])
        if a and b and " " not in a + b:
            return f"{a} {b + 's' if w.endswith('er') and not b.endswith('s') else b}"
    return None


def _lookup_simple(w):
    if w in DE_EN:
        return DE_EN[w]
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3 and w[:-len(suf)] in DE_EN:
            return DE_EN[w[:-len(suf)]]
    return None


def translate(query):
    out = []
    for tok in _TOKEN.findall(query or ""):
        if tok.startswith('"') or ":" in tok or tok.startswith("@"):
            out.append(tok)
            continue
        sign = tok[0] if tok[0] in "+-" else ""
        word = tok[len(sign):]
        if not sign and word.lower() in STOPWORDS:
            continue
        en = _lookup(word)
        if en and " " in en:
            out.extend(f"+{p}" if not sign else f"{sign}{p}" for p in en.split())
            continue
        out.append(sign + (en or word))
    return " ".join(out)


GENERIC_TAGS = {"digital art", "artwork", "illustration", "digital painting", "ultrawide",
                "wide screen", "widescreen", "4k", "8k", "simple background", "render",
                "cgi", "wallpaper", "ultra hd", "hd"}
CAT_DE = {"general": "Allgemein", "anime": "Anime", "people": "Menschen"}


class Wallhaven:
    name = "Wallhaven"
    media = "Bilder"
    has_filters = True
    sorts = [("Neueste", "date_added"), ("Beliebt · Monat", "toplist:1M"),
             ("Beliebt · Jahr", "toplist:1y"), ("Beliebt · Woche", "toplist:1w"),
             ("Meist angesehen", "views"), ("Meist favorisiert", "favorites"),
             ("Zufällig", "random"), ("Relevanz", "relevance")]
    categories = ["Anime", "Natur", "Spiele", "Stadt", "Weltraum", "Minimal",
                  "Dunkel", "Abstrakt"]
    hint = "Wallhaven durchsuchen, z. B. Wald, dark forest, -people"

    def __init__(self):
        self._seed = ""

    @staticmethod
    def _headers(cfg):
        key = (cfg.get("wallhaven_key") or "").strip()
        return {"X-API-Key": key} if key else {}

    def search(self, query, page, sort, cfg):
        purity = cfg.get("wh_purity", "100")
        if purity[2] == "1" and not cfg.get("wallhaven_key"):
            purity = purity[:2] + "0"
        if purity == "000":
            purity = "100"
        cats = cfg.get("wh_categories", "111")
        if cats == "000":
            cats = "111"
        q = translate(query)
        sort = sort or "date_added"
        if sort == "relevance" and not q:
            sort = "date_added"
        p = {"categories": cats, "purity": purity, "page": str(page + 1)}
        if q:
            p["q"] = q
        if sort.startswith("toplist"):
            p["sorting"], p["topRange"] = "toplist", (sort.split(":") + ["1M"])[1]
        else:
            p["sorting"] = sort
        if sort == "random":
            if page == 0 or not self._seed:
                self._seed = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=6))
            p["seed"] = self._seed
        if cfg.get("wh_atleast"):
            p["atleast"] = cfg["wh_atleast"]
        if cfg.get("wh_ratio"):
            p["ratios"] = cfg["wh_ratio"]
        data = _json("https://wallhaven.cc/api/v1/search?" + urllib.parse.urlencode(p),
                     headers=self._headers(cfg))
        out = Results()
        out.total = (data.get("meta") or {}).get("total")
        for w in data.get("data", []):
            out.append({
                "id": "wh" + w["id"],
                "title": f'{CAT_DE.get(w.get("category"), "Wallhaven")} · {w["id"]}',
                "remote": w["path"], "thumb_url": w["thumbs"]["large"],
                "source": self.name, "license": "Urheberrecht beim Urheber",
                "author": "", "url": w.get("url", ""), "purity": w.get("purity", "sfw"),
                "size": w.get("resolution", ""),
            })
        return out

    def details(self, result, cfg):
        wid = result["id"][2:]
        w = _json(f"https://wallhaven.cc/api/v1/w/{wid}", headers=self._headers(cfg))["data"]
        tags = [t for t in w.get("tags", [])]
        artist = next((t["name"] for t in tags if t.get("category") == "Artists"), "")
        names = [t["name"].replace(",", " ").strip() for t in tags
                 if t.get("category") != "Artists" and t["name"].lower() not in GENERIC_TAGS]
        title = ", ".join(n.title() for n in names[:3])
        return {"title": f"{title} · {wid}" if title else result["title"],
                "tags": names[:10], "author": artist, "detailed": True}

    def download(self, result, progress=None):
        dest = MEDIA / Path(urllib.parse.urlparse(result["remote"]).path).name
        return dest if dest.exists() else _stream(result["remote"], dest, progress)


class Pixabay:
    name = "Pixabay"
    media = "Videos"
    has_filters = False
    sorts = [("Beliebt", "popular"), ("Neu", "latest")]
    categories = ["Natur", "Stadt", "Weltraum", "Wasser", "Abstrakt", "Feuer",
                  "Wolken", "Regen"]
    hint = "Pixabay durchsuchen"

    def search(self, query, page, sort, cfg):
        key = cfg.get("pixabay_key", "")
        if not key:
            raise RuntimeError("Pixabay braucht einen API-Schlüssel (Einstellungen)")
        p = {"key": key, "q": query, "order": sort or "popular", "lang": "de",
             "per_page": str(PER_PAGE), "page": str(page + 1), "min_width": "1280"}
        data = _json("https://pixabay.com/api/videos/?" + urllib.parse.urlencode(p))
        out = Results()
        out.total = data.get("totalHits")
        for h in data.get("hits", []):
            vids = h.get("videos", {})
            v = next((vids[k] for k in ("large", "medium", "small") if vids.get(k, {}).get("url")), None)
            if not v:
                continue
            thumb = v.get("thumbnail") or f'https://i.vimeocdn.com/video/{h.get("picture_id")}_640x360.jpg'
            out.append({
                "id": "px" + str(h["id"]),
                "title": (h.get("tags") or f'Pixabay {h["id"]}').split(",")[0].strip().title(),
                "remote": v["url"], "thumb_url": thumb,
                "source": self.name, "license": "Pixabay Content License",
                "author": h.get("user", ""), "url": h.get("pageURL", ""),
                "size": f'{v.get("width", 0)}x{v.get("height", 0)}',
            })
        return out

    def download(self, result, progress=None):
        dest = MEDIA / f'pixabay-{result["id"][2:]}.mp4'
        return dest if dest.exists() else _stream(result["remote"], dest, progress)


class Commons:
    name = "Wikimedia Commons"
    media = "Videos"
    has_filters = False
    sorts = [("Relevanz", "relevance")]
    categories = ["Natur", "Stadt", "Weltraum", "Wasser", "Wolken", "Zeitraffer"]
    hint = "Wikimedia Commons durchsuchen"
    API = "https://commons.wikimedia.org/w/api.php"
    VIDEO_MIME = {"video/webm", "video/mp4", "application/ogg"}

    def search(self, query, page, sort, cfg):
        params = {
            "action": "query", "format": "json", "formatversion": "2",
            "generator": "search", "gsrnamespace": "6", "gsrlimit": str(PER_PAGE),
            "gsroffset": str(page * PER_PAGE),
            "gsrsearch": f"{query} filetype:video", "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata", "iiurlwidth": "480",
        }
        data = _json(self.API + "?" + urllib.parse.urlencode(params))
        pages = sorted(data.get("query", {}).get("pages", []),
                       key=lambda p: p.get("index", 0))
        out = Results()
        for p in pages:
            info = (p.get("imageinfo") or [{}])[0]
            if info.get("mime") not in self.VIDEO_MIME:
                continue
            meta = info.get("extmetadata", {})
            title = re.sub(r"^File:|\.\w+$", "", p["title"]).replace("_", " ")
            out.append({
                "id": "c" + str(p["pageid"]), "title": title,
                "remote": info["url"], "thumb_url": info.get("thumburl"),
                "source": self.name,
                "license": _strip(meta.get("LicenseShortName", {}).get("value")),
                "author": _strip(meta.get("Artist", {}).get("value")),
                "url": info.get("descriptionurl", ""),
                "size": f'{info.get("width", 0)}x{info.get("height", 0)}',
            })
        return out

    @staticmethod
    def _best_url(url):
        url = url.split("?")[0]
        m = re.match(r"(https://upload\.wikimedia\.org/wikipedia/commons)/(.+/([^/]+))$", url)
        if not m:
            return url

        def head(u):
            try:
                req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=10) as r:
                    return int(r.headers.get("Content-Length") or 0)
            except Exception:  # noqa: BLE001
                return None

        for q in ("2160p.vp9", "1440p.vp9", "1080p.vp9", "720p.vp9", "480p.vp9"):
            cand = f"{m[1]}/transcoded/{m[2]}/{m[3]}.{q}.webm"
            if head(cand):
                return cand
        size = head(url)
        if size and size > MAX_ORIGINAL:
            raise RuntimeError(
                f"Nur das Original ({size // 1048576} MB) verfügbar, das ist zu groß")
        return url

    def download(self, result, progress=None):
        url = self._best_url(result["remote"])
        name = re.sub(r"[^\w.-]+", "_", Path(urllib.parse.urlparse(url).path).name)
        if not name.endswith((".webm", ".mp4", ".ogv")):
            name += ".webm"
        dest = MEDIA / name
        return dest if dest.exists() else _stream(url, dest, progress)


SOURCES = [Wallhaven(), Pixabay(), Commons()]


def fetch_thumb(url):
    dest = CACHE / ("t-" + re.sub(r"[^\w.-]+", "_", url)[-120:])
    if not dest.suffix:
        dest = dest.with_suffix(".jpg")
    if not dest.exists():
        with _get(url, timeout=20) as r:
            dest.write_bytes(r.read())
    return str(dest)
