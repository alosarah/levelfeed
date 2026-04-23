import feedparser
import json
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────
#  ALL SOURCES
# ─────────────────────────────────────────
SOURCES = {

    # ── GENERAL GAMING NEWS ──────────────
    "general": [
        {"name": "IGN",               "url": "https://feeds.ign.com/ign/all"},
        {"name": "Eurogamer",         "url": "https://www.eurogamer.net/?format=rss"},
        {"name": "PC Gamer",          "url": "https://www.pcgamer.com/rss/"},
        {"name": "Kotaku",            "url": "https://kotaku.com/rss"},
        {"name": "Rock Paper Shotgun","url": "https://www.rockpapershotgun.com/feed"},
        {"name": "VGC",               "url": "https://www.videogameschronicle.com/feed/"},
        {"name": "GamesRadar",        "url": "https://www.gamesradar.com/rss/"},
        {"name": "GameSpot",          "url": "https://www.gamespot.com/feeds/news"},
        {"name": "Insider Gaming",    "url": "https://insider-gaming.com/feed/"},
    ],

    # ── PUBLISHERS (OFFICIAL) ────────────
    "publishers": [
        {"name": "EA Newsroom",       "url": "https://news.ea.com/rss/all"},
        {"name": "Ubisoft News",      "url": "https://news.ubisoft.com/en-us/rss"},
        {"name": "CD Projekt Blog",   "url": "https://www.cdprojekt.com/en/feed/"},
        {"name": "Square Enix",       "url": "https://www.square-enix-games.com/feed"},
        {"name": "Bethesda Blog",     "url": "https://bethesda.net/en/feed"},
    ],

    # ── NINTENDO ─────────────────────────
    "nintendo": [
        {"name": "Nintendo Everything","url": "https://nintendoeverything.com/feed"},
        {"name": "Nintendo Life",      "url": "https://www.nintendolife.com/feeds/latest"},
        {"name": "My Nintendo News",   "url": "https://mynintendonews.com/feed"},
        {"name": "Nintendo Wire",      "url": "https://nintendowire.com/feed"},
    ],

    # ── XBOX ─────────────────────────────
    "xbox": [
        {"name": "Xbox Wire (official)","url": "https://news.xbox.com/en-us/feed"},
        {"name": "Pure Xbox",           "url": "https://www.purexbox.com/feeds/latest"},
        {"name": "Windows Central",     "url": "https://www.windowscentral.com/rss.xml"},
        {"name": "True Achievements",   "url": "https://www.trueachievements.com/news/rss"},
    ],

    # ── PLAYSTATION ──────────────────────
    "playstation": [
        {"name": "PlayStation Blog (official)", "url": "https://blog.playstation.com/feed"},
        {"name": "PlayStation LifeStyle",       "url": "https://www.playstationlifestyle.net/feed"},
        {"name": "Push Square",                 "url": "https://www.pushsquare.com/feeds/latest"},
    ],

    # ── PC / NVIDIA / HARDWARE ───────────
    "hardware": [
        {"name": "NVIDIA Newsroom",   "url": "https://nvidianews.nvidia.com/rss/all"},
        {"name": "NVIDIA GeForce",    "url": "https://www.nvidia.com/en-us/geforce/news/rss/"},
        {"name": "PCGamesN",          "url": "https://www.pcgamesn.com/mainrss.xml"},
        {"name": "Wccftech",          "url": "https://wccftech.com/feed/"},
        {"name": "Tom's Hardware",    "url": "https://www.tomshardware.com/feeds/all"},
        {"name": "Digital Trends",    "url": "https://www.digitaltrends.com/gaming/feed/"},
    ],

    # ── ESPORTS ──────────────────────────
    "esports": [
        {"name": "Esports Insider",   "url": "https://esportsinsider.com/feed"},
        {"name": "HLTV (CS2)",        "url": "https://www.hltv.org/rss/news"},
        {"name": "Dot Esports",       "url": "https://dotesports.com/feed"},
        {"name": "ONE Esports",       "url": "https://www.oneesports.gg/feed/"},
    ],

    # ── YOUTUBE (official trailers) ──────
    "youtube": [
        {"name": "PlayStation YT",      "channel_id": "UCbIXStVbYFMQxkVrSxHw5TQ"},
        {"name": "Xbox YT",             "channel_id": "UCsFZs2MPKoBsEeBzREDRFcg"},
        {"name": "Nintendo America YT", "channel_id": "UCGIY_O-8vW4rfX98KlMkvRg"},
        {"name": "IGN YT",              "channel_id": "UCKy1dAqELo0zrOtPkf0eTMw"},
        {"name": "GameSpot YT",         "channel_id": "UCbu2SsF-Or3Rsn3NxqODImQ"},
    ],
}

YOUTUBE_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={}"

HEADERS = {
    "User-Agent": "LevelFeed-Bot/1.0 (gaming news aggregator; contact via github)"
}

# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def make_id(title: str, link: str) -> str:
    return hashlib.md5(f"{title}{link}".encode()).hexdigest()[:12]

def load_seen(path: Path) -> set:
    if path.exists():
        return set(json.loads(path.read_text()).get("seen_ids", []))
    return set()

def save_seen(path: Path, ids: set):
    path.write_text(json.dumps({"seen_ids": list(ids)}, indent=2))

def parse_date(entry) -> str:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()

def fetch_rss(url: str, source_name: str, category: str) -> list:
    items = []
    try:
        feed = feedparser.parse(url, request_headers=HEADERS)
        for entry in feed.entries[:15]:
            title = getattr(entry, "title", "").strip()
            link  = getattr(entry, "link",  "").strip()
            if not title or not link:
                continue
            summary = getattr(entry, "summary", "")
            # strip html tags from summary
            if summary:
                soup = BeautifulSoup(summary, "html.parser")
                summary = soup.get_text(separator=" ").strip()[:300]
            items.append({
                "id":       make_id(title, link),
                "title":    title,
                "link":     link,
                "summary":  summary,
                "source":   source_name,
                "category": category,
                "fetched":  datetime.now(timezone.utc).isoformat(),
                "date":     parse_date(entry),
            })
    except Exception as e:
        print(f"  [WARN] {source_name}: {e}")
    return items

def scrape_nintendo_newsroom() -> list:
    """Scrape Nintendo Newsroom — no official RSS available."""
    items = []
    try:
        r = requests.get("https://www.nintendo.com/en-us/whatsnew/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("a[href*='/whatsnew/']")[:10]:
            title = a.get_text(strip=True)
            link  = "https://www.nintendo.com" + a["href"] if a["href"].startswith("/") else a["href"]
            if len(title) > 10:
                items.append({
                    "id":       make_id(title, link),
                    "title":    title,
                    "link":     link,
                    "summary":  "",
                    "source":   "Nintendo Newsroom",
                    "category": "nintendo",
                    "fetched":  datetime.now(timezone.utc).isoformat(),
                    "date":     datetime.now(timezone.utc).isoformat(),
                })
    except Exception as e:
        print(f"  [WARN] Nintendo Newsroom scrape: {e}")
    return items

def scrape_liquipedia() -> list:
    """Scrape Liquipedia recent esports news."""
    items = []
    try:
        r = requests.get("https://liquipedia.net/commons/Main_Page", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for li in soup.select(".wiki-mainpage-newsblurb")[:8]:
            a = li.find("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            link  = "https://liquipedia.net" + a["href"] if a["href"].startswith("/") else a["href"]
            if title:
                items.append({
                    "id":       make_id(title, link),
                    "title":    title,
                    "link":     link,
                    "summary":  li.get_text(strip=True)[:300],
                    "source":   "Liquipedia",
                    "category": "esports",
                    "fetched":  datetime.now(timezone.utc).isoformat(),
                    "date":     datetime.now(timezone.utc).isoformat(),
                })
    except Exception as e:
        print(f"  [WARN] Liquipedia scrape: {e}")
    return items

# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
def run():
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    seen_path = output_dir / "seen_bot1.json"
    seen_ids  = load_seen(seen_path)

    all_items = []

    # RSS feeds
    for category, feeds in SOURCES.items():
        if category == "youtube":
            for ch in feeds:
                url = YOUTUBE_RSS.format(ch["channel_id"])
                print(f"  Fetching YouTube: {ch['name']}")
                all_items += fetch_rss(url, ch["name"], "youtube")
        else:
            for feed in feeds:
                print(f"  Fetching: {feed['name']}")
                all_items += fetch_rss(feed["url"], feed["name"], category)

    # Scraping sources
    print("  Scraping: Nintendo Newsroom")
    all_items += scrape_nintendo_newsroom()

    print("  Scraping: Liquipedia")
    all_items += scrape_liquipedia()

    # Deduplicate
    new_items = [item for item in all_items if item["id"] not in seen_ids]
    print(f"\n  Total fetched: {len(all_items)} | New: {len(new_items)}")

    # Update seen ids
    seen_ids.update(item["id"] for item in new_items)
    save_seen(seen_path, seen_ids)

    # Load existing news and prepend new items
    news_path = output_dir / "news_bot1.json"
    existing = []
    if news_path.exists():
        existing = json.loads(news_path.read_text()).get("items", [])

    # Keep max 500 items total
    combined = new_items + existing
    combined = combined[:500]

    news_path.write_text(json.dumps({
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total":        len(combined),
        "new_this_run": len(new_items),
        "items":        combined
    }, indent=2, ensure_ascii=False))

    print(f"  Saved {len(combined)} items to {news_path}")

if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  LevelFeed Bot 1 — Daily Feed")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}\n")
    run()
    print("\n  Done.\n")
